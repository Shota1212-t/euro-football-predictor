from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)

CLASS_LABELS = [0, 1, 2]
CLASS_NAMES = ["HOME_WIN", "DRAW", "AWAY_WIN"]


def _validated_probabilities(proba) -> np.ndarray:
    values = np.asarray(proba, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError(f"proba must have shape (n, 3), got {values.shape}")
    if not np.all(np.isfinite(values)):
        raise ValueError("proba contains NaN or infinity")
    if np.any(values < 0):
        raise ValueError("proba contains a negative value")
    row_sums = values.sum(axis=1, keepdims=True)
    if np.any(row_sums <= 0):
        raise ValueError("proba contains a row whose total is zero")
    return values / row_sums


def multiclass_brier(y, proba, n_classes=3):
    y_array = np.asarray(y, dtype=int)
    proba_array = _validated_probabilities(proba)
    one_hot = np.eye(n_classes)[y_array]
    return float(np.mean(np.sum((proba_array - one_hot) ** 2, axis=1)))


def expected_calibration_error(y, proba, n_bins=10):
    y_array = np.asarray(y, dtype=int)
    proba_array = _validated_probabilities(proba)
    predictions = np.argmax(proba_array, axis=1)
    confidence = np.max(proba_array, axis=1)
    correctness = (predictions == y_array).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for index in range(n_bins):
        lower = edges[index]
        upper = edges[index + 1]
        mask = (
            (confidence >= lower) & (confidence <= upper)
            if index == n_bins - 1
            else (confidence >= lower) & (confidence < upper)
        )
        if not np.any(mask):
            continue
        bin_accuracy = float(np.mean(correctness[mask]))
        bin_confidence = float(np.mean(confidence[mask]))
        ece += float(np.mean(mask)) * abs(bin_accuracy - bin_confidence)
    return float(ece)


def evaluate(y, proba):
    y_array = np.asarray(y, dtype=int)
    proba_array = _validated_probabilities(proba)
    if len(y_array) != len(proba_array):
        raise ValueError("y and proba have different row counts")
    predictions = np.argmax(proba_array, axis=1)
    report = classification_report(
        y_array,
        predictions,
        labels=CLASS_LABELS,
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    return {
        "samples": int(len(y_array)),
        "accuracy": float(accuracy_score(y_array, predictions)),
        "macro_f1": float(f1_score(y_array, predictions, average="macro")),
        "log_loss": float(log_loss(y_array, proba_array, labels=CLASS_LABELS)),
        "brier_score": multiclass_brier(y_array, proba_array),
        "expected_calibration_error": expected_calibration_error(y_array, proba_array),
        "draw_precision": float(report["DRAW"]["precision"]),
        "draw_recall": float(report["DRAW"]["recall"]),
        "draw_f1": float(report["DRAW"]["f1-score"]),
        "confusion_matrix": confusion_matrix(y_array, predictions, labels=CLASS_LABELS).tolist(),
        "classification_report": report,
    }


def constant_probabilities(sample_count: int, probabilities) -> np.ndarray:
    values = np.asarray(probabilities, dtype=float)
    if values.shape != (3,):
        raise ValueError("baseline probabilities must contain exactly three values")
    values = _validated_probabilities(values.reshape(1, 3))[0]
    return np.tile(values, (sample_count, 1))


def baseline_evaluations(y_train, y_test) -> dict:
    """Evaluate simple references without using any test-set information."""
    train = np.asarray(y_train, dtype=int)
    test = np.asarray(y_test, dtype=int)
    counts = np.bincount(train, minlength=3).astype(float)
    priors = counts / counts.sum()
    return {
        "always_home_win": evaluate(
            test,
            constant_probabilities(len(test), [1.0, 0.0, 0.0]),
        ),
        "training_class_prior": evaluate(
            test,
            constant_probabilities(len(test), priors),
        ),
    }


def summarize_metric_runs(runs: list[dict]) -> dict:
    metric_names = (
        "accuracy",
        "macro_f1",
        "log_loss",
        "brier_score",
        "expected_calibration_error",
        "draw_precision",
        "draw_recall",
        "draw_f1",
    )
    if not runs:
        return {"folds": 0, "metrics": {}}
    summary = {}
    for name in metric_names:
        values = np.asarray([run[name] for run in runs], dtype=float)
        summary[name] = {
            "mean": float(values.mean()),
            "std": float(values.std(ddof=0)),
            "min": float(values.min()),
            "max": float(values.max()),
        }
    return {"folds": len(runs), "metrics": summary}
