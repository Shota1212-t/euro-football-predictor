from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from .config import MODEL_DIR, PROCESSED_DIR, RANDOM_STATE, REPORT_DIR
from .evaluate import baseline_evaluations, evaluate, summarize_metric_runs
from .features import feature_columns
from .split import (
    calibration_selection_split,
    chronological_split,
    expanding_window_splits,
)

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


def calibration_is_acceptable(candidate: dict, reference: dict) -> bool:
    return (
        candidate["log_loss"] <= reference["log_loss"]
        and candidate["brier_score"] <= reference["brier_score"]
        and candidate["draw_recall"] >= max(0.05, reference["draw_recall"] * 0.75)
    )


def train_variant(
    name: str,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
) -> dict:
    calibration_df, selection_df = calibration_selection_split(validation)

    base_model = make_model()
    base_model.fit(train[columns], train.target)

    calibrated_model = CalibratedClassifierCV(
        estimator=FrozenEstimator(base_model),
        method="isotonic",
    )
    calibrated_model.fit(calibration_df[columns], calibration_df.target)

    # Select calibration without looking at the final test set.
    base_selection_metrics = evaluate(
        selection_df.target,
        base_model.predict_proba(selection_df[columns]),
    )
    calibrated_selection_metrics = evaluate(
        selection_df.target,
        calibrated_model.predict_proba(selection_df[columns]),
    )
    use_calibration = calibration_is_acceptable(
        calibrated_selection_metrics,
        base_selection_metrics,
    )

    selected_model = calibrated_model if use_calibration else base_model
    base_test_metrics = evaluate(test.target, base_model.predict_proba(test[columns]))
    calibrated_test_metrics = evaluate(
        test.target,
        calibrated_model.predict_proba(test[columns]),
    )
    selected_test_metrics = (
        calibrated_test_metrics if use_calibration else base_test_metrics
    )

    return {
        "name": name,
        "columns": columns,
        "base_model": base_model,
        "calibrated_model": calibrated_model,
        "selected_model": selected_model,
        "selected_kind": "calibrated" if use_calibration else "uncalibrated",
        "selection": {
            "base": base_selection_metrics,
            "calibrated": calibrated_selection_metrics,
        },
        "test": {
            "base": base_test_metrics,
            "calibrated": calibrated_test_metrics,
            "selected": selected_test_metrics,
        },
    }


def rolling_evaluation(df: pd.DataFrame, columns: list[str]) -> dict:
    runs = []
    for fold, (train_df, evaluation_df) in enumerate(
        expanding_window_splits(df),
        start=1,
    ):
        model = make_model()
        model.fit(train_df[columns], train_df.target)
        metrics = evaluate(
            evaluation_df.target,
            model.predict_proba(evaluation_df[columns]),
        )
        runs.append(
            {
                "fold": fold,
                "train_start": str(train_df.Date.min().date()),
                "train_end": str(train_df.Date.max().date()),
                "evaluation_start": str(evaluation_df.Date.min().date()),
                "evaluation_end": str(evaluation_df.Date.max().date()),
                **metrics,
            }
        )
    return {"runs": runs, "summary": summarize_metric_runs(runs)}


def train():
    df = pd.read_csv(PROCESSED_DIR / "training_data.csv", parse_dates=["Date"])
    train_df, validation_df, test_df = chronological_split(df)
    all_columns = feature_columns(df)
    no_odds_columns = [column for column in all_columns if column not in ODDS_COLUMNS]

    odds_variant = train_variant(
        "with_odds", train_df, validation_df, test_df, all_columns
    )
    no_odds_variant = train_variant(
        "no_odds", train_df, validation_df, test_df, no_odds_columns
    )

    # Rolling evaluation excludes the untouched final test period.
    pretest_df = pd.concat([train_df, validation_df], ignore_index=True)
    rolling = rolling_evaluation(pretest_df, no_odds_columns)
    baselines = baseline_evaluations(train_df.target, test_df.target)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(odds_variant["selected_model"], MODEL_DIR / "lightgbm_with_odds.joblib")
    joblib.dump(
        no_odds_variant["base_model"],
        MODEL_DIR / "lightgbm_no_odds_uncalibrated.joblib",
    )
    joblib.dump(
        no_odds_variant["calibrated_model"],
        MODEL_DIR / "lightgbm_no_odds_calibrated.joblib",
    )
    joblib.dump(no_odds_variant["selected_model"], MODEL_DIR / "lightgbm_model.joblib")

    metadata = {
        "model": "LightGBM",
        "version": f"lightgbm_no_odds_{no_odds_variant['selected_kind']}_v3",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "production_variant": "no_odds",
        "production_calibration": no_odds_variant["selected_kind"],
        "selection_reason": (
            "Production fixtures do not provide B365 odds. Calibration is selected "
            "on a chronological selection subset and the final test set remains untouched."
        ),
        "features": no_odds_columns,
        "excluded_features": ODDS_COLUMNS,
        "class_weight": "balanced",
        "split": {
            "method": "chronological_holdout",
            "train_end": str(train_df.Date.max().date()),
            "validation_start": str(validation_df.Date.min().date()),
            "test_start": str(test_df.Date.min().date()),
            "test_samples": int(len(test_df)),
        },
        "metrics": no_odds_variant["test"]["selected"],
        "baselines": baselines,
        "rolling_evaluation": rolling,
        "comparison": {
            "with_odds": {
                "selected_kind": odds_variant["selected_kind"],
                "selection": odds_variant["selection"],
                "test": odds_variant["test"],
            },
            "no_odds": {
                "selected_kind": no_odds_variant["selected_kind"],
                "selection": no_odds_variant["selection"],
                "test": no_odds_variant["test"],
            },
        },
    }

    (MODEL_DIR / "lightgbm_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (REPORT_DIR / "lightgbm_metrics.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps({
        "baselines": baselines,
        "rolling_summary": rolling["summary"],
        "production_test": metadata["metrics"],
    }, ensure_ascii=False, indent=2))
    print("Production model:", metadata["version"])
    return metadata["metrics"]


if __name__ == "__main__":
    train()
