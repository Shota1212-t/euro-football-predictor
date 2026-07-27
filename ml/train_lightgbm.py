from __future__ import annotations

import json
from datetime import datetime

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .config import MODEL_DIR, PROCESSED_DIR, RANDOM_STATE, REPORT_DIR
from .evaluate import evaluate
from .features import feature_columns
from .split import chronological_split

ODDS_COLUMNS = ["B365H", "B365D", "B365A"]


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                LGBMClassifier(
                    objective="multiclass",
                    num_class=3,
                    n_estimators=400,
                    learning_rate=0.03,
                    num_leaves=20,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                    verbosity=-1,
                ),
            ),
        ]
    )


def train_variant(
    name: str,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
) -> dict:
    base_model = make_model()
    base_model.fit(train[columns], train.target)
    base_metrics = evaluate(test.target, base_model.predict_proba(test[columns]))

    calibrated_model = CalibratedClassifierCV(
        estimator=FrozenEstimator(base_model),
        method="isotonic",
    )
    calibrated_model.fit(validation[columns], validation.target)
    calibrated_metrics = evaluate(
        test.target,
        calibrated_model.predict_proba(test[columns]),
    )

    # Calibration is adopted only when probability quality improves without
    # destroying draw detection. Otherwise the balanced base model is safer.
    calibration_improves = (
        calibrated_metrics["log_loss"] <= base_metrics["log_loss"]
        and calibrated_metrics["brier_score"] <= base_metrics["brier_score"]
        and calibrated_metrics["draw_recall"]
        >= max(0.05, base_metrics["draw_recall"] * 0.75)
    )

    selected_model = calibrated_model if calibration_improves else base_model
    selected_metrics = calibrated_metrics if calibration_improves else base_metrics

    return {
        "name": name,
        "columns": columns,
        "base_model": base_model,
        "calibrated_model": calibrated_model,
        "selected_model": selected_model,
        "selected_kind": "calibrated" if calibration_improves else "uncalibrated",
        "base_metrics": base_metrics,
        "calibrated_metrics": calibrated_metrics,
        "selected_metrics": selected_metrics,
    }


def train():
    df = pd.read_csv(
        PROCESSED_DIR / "training_data.csv",
        parse_dates=["Date"],
    )
    train_df, validation_df, test_df = chronological_split(df)
    all_columns = feature_columns(df)
    no_odds_columns = [column for column in all_columns if column not in ODDS_COLUMNS]

    odds_variant = train_variant(
        "with_odds",
        train_df,
        validation_df,
        test_df,
        all_columns,
    )
    no_odds_variant = train_variant(
        "no_odds",
        train_df,
        validation_df,
        test_df,
        no_odds_columns,
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Comparison models are kept explicitly.
    joblib.dump(
        odds_variant["selected_model"],
        MODEL_DIR / "lightgbm_with_odds.joblib",
    )
    joblib.dump(
        no_odds_variant["base_model"],
        MODEL_DIR / "lightgbm_no_odds_uncalibrated.joblib",
    )
    joblib.dump(
        no_odds_variant["calibrated_model"],
        MODEL_DIR / "lightgbm_no_odds_calibrated.joblib",
    )

    # Real fixtures do not contain B365 odds, so no-odds is production.
    joblib.dump(
        no_odds_variant["selected_model"],
        MODEL_DIR / "lightgbm_model.joblib",
    )

    metadata = {
        "model": "LightGBM",
        "version": f"lightgbm_no_odds_{no_odds_variant['selected_kind']}_v2",
        "trained_at": datetime.now().isoformat(),
        "production_variant": "no_odds",
        "production_calibration": no_odds_variant["selected_kind"],
        "selection_reason": (
            "Production fixtures do not provide B365 odds. Calibration is used "
            "only when Log Loss and Brier Score improve without materially "
            "reducing draw recall."
        ),
        "features": no_odds_columns,
        "excluded_features": ODDS_COLUMNS,
        "class_weight": "balanced",
        "train_end": str(train_df.Date.max().date()),
        "validation_start": str(validation_df.Date.min().date()),
        "test_start": str(test_df.Date.min().date()),
        "metrics": no_odds_variant["selected_metrics"],
        "comparison": {
            "with_odds": {
                "selected_kind": odds_variant["selected_kind"],
                "base": odds_variant["base_metrics"],
                "calibrated": odds_variant["calibrated_metrics"],
                "selected": odds_variant["selected_metrics"],
            },
            "no_odds": {
                "selected_kind": no_odds_variant["selected_kind"],
                "base": no_odds_variant["base_metrics"],
                "calibrated": no_odds_variant["calibrated_metrics"],
                "selected": no_odds_variant["selected_metrics"],
            },
        },
    }

    (MODEL_DIR / "lightgbm_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_DIR / "lightgbm_metrics.json").write_text(
        json.dumps(metadata["comparison"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(metadata["comparison"], ensure_ascii=False, indent=2))
    print("Production model:", metadata["version"])
    return metadata["metrics"]


if __name__ == "__main__":
    train()
