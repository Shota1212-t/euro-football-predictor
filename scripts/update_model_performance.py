from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "ml" / "models" / "lightgbm_metadata.json"
OUTPUT_PATH = ROOT / "data" / "predictions" / "model_performance.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"必要なファイルがありません: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def build_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    metrics = metadata.get("metrics") or {}
    report = metrics.get("classification_report") or {}
    class_metrics = {
        "home_win": report.get("HOME_WIN") or {},
        "draw": report.get("DRAW") or {},
        "away_win": report.get("AWAY_WIN") or {},
    }
    supports = [
        int(item.get("support", 0))
        for item in class_metrics.values()
    ]
    total_predictions = sum(supports)
    accuracy = float(metrics.get("accuracy", 0.0))

    return {
        "model_name": metadata.get("model", "LightGBM"),
        "model_version": metadata.get("version"),
        "trained_at": metadata.get("trained_at"),
        "production_variant": metadata.get("production_variant"),
        "production_calibration": metadata.get("production_calibration"),
        "selection_reason": metadata.get("selection_reason"),
        "class_weight": metadata.get("class_weight"),
        "features": metadata.get("features") or [],
        "feature_count": len(metadata.get("features") or []),
        "excluded_features": metadata.get("excluded_features") or [],
        "train_end": metadata.get("train_end"),
        "validation_start": metadata.get("validation_start"),
        "test_start": metadata.get("test_start"),
        "evaluation_type": "chronological_holdout",
        "overall_accuracy": accuracy,
        "macro_f1": metrics.get("macro_f1"),
        "log_loss": metrics.get("log_loss"),
        "brier_score": metrics.get("brier_score"),
        "expected_calibration_error": metrics.get("expected_calibration_error"),
        "draw_precision": metrics.get("draw_precision"),
        "draw_recall": metrics.get("draw_recall"),
        "draw_f1": metrics.get("draw_f1"),
        "confusion_matrix": metrics.get("confusion_matrix") or [],
        "class_metrics": class_metrics,
        "total_predictions": total_predictions,
        "correct_predictions": int(round(accuracy * total_predictions)),
        "by_league": [],
        "operational_results_available": False,
        "operational_note": (
            "表示値は時系列ホールドアウトテスト731試合の評価結果です。"
            "運用開始後の実試合的中率ではありません。"
        ),
        "probability_note": (
            "本番モデルは未校正です。確率値はモデル出力の参考値であり、"
            "現実の発生確率として断定できません。"
        ),
    }


def main() -> None:
    metadata = read_json(METADATA_PATH)
    payload = build_payload(metadata)
    atomic_write(OUTPUT_PATH, payload)
    print(f"モデル精度データ更新完了: {OUTPUT_PATH}")
    print(f"モデル: {payload['model_version']}")
    print(f"評価試合数: {payload['total_predictions']}")
    print(f"Accuracy: {payload['overall_accuracy']:.4f}")
    print(f"Macro F1: {payload['macro_f1']:.4f}")


if __name__ == "__main__":
    main()
