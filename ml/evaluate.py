import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)


def multiclass_brier(y, proba, n_classes=3):
    y_array = np.asarray(y, dtype=int)
    proba_array = np.asarray(proba, dtype=float)
    one_hot = np.eye(n_classes)[y_array]
    return float(np.mean(np.sum((proba_array - one_hot) ** 2, axis=1)))


def expected_calibration_error(y, proba, n_bins=10):
    y_array = np.asarray(y, dtype=int)
    proba_array = np.asarray(proba, dtype=float)
    predictions = np.argmax(proba_array, axis=1)
    confidence = np.max(proba_array, axis=1)
    correctness = (predictions == y_array).astype(float)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for index in range(n_bins):
        lower = edges[index]
        upper = edges[index + 1]
        if index == n_bins - 1:
            mask = (confidence >= lower) & (confidence <= upper)
        else:
            mask = (confidence >= lower) & (confidence < upper)

        if not np.any(mask):
            continue

        bin_accuracy = float(np.mean(correctness[mask]))
        bin_confidence = float(np.mean(confidence[mask]))
        bin_weight = float(np.mean(mask))
        ece += bin_weight * abs(bin_accuracy - bin_confidence)

    return float(ece)


def evaluate(y, proba):
    y_array = np.asarray(y, dtype=int)
    proba_array = np.asarray(proba, dtype=float)
    predictions = np.argmax(proba_array, axis=1)

    report = classification_report(
        y_array,
        predictions,
        labels=[0, 1, 2],
        target_names=["HOME_WIN", "DRAW", "AWAY_WIN"],
        output_dict=True,
        zero_division=0,
    )

    return {
        "accuracy": float(accuracy_score(y_array, predictions)),
        "macro_f1": float(f1_score(y_array, predictions, average="macro")),
        "log_loss": float(log_loss(y_array, proba_array, labels=[0, 1, 2])),
        "brier_score": multiclass_brier(y_array, proba_array),
        "expected_calibration_error": expected_calibration_error(
            y_array,
            proba_array,
        ),
        "draw_precision": float(report["DRAW"]["precision"]),
        "draw_recall": float(report["DRAW"]["recall"]),
        "draw_f1": float(report["DRAW"]["f1-score"]),
        "confusion_matrix": confusion_matrix(
            y_array,
            predictions,
            labels=[0, 1, 2],
        ).tolist(),
        "classification_report": report,
    }
