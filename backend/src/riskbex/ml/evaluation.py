"""Evaluation of labeled historical predictions; not a training or inference path."""

import numpy as np

from src.riskbex.ml.data import regime_values
from src.riskbex.ml.inference import validate_predictions


def classification_metrics(frame, *, stress_regime):
    predictions = validate_predictions(frame)
    if "regime_t_plus_1" not in predictions:
        raise ValueError("Historical evaluation requires known next-session labels.")
    true = regime_values(predictions["regime_t_plus_1"], "regime_t_plus_1")
    predicted = predictions["regime_pred"].to_numpy()
    stress = regime_values([stress_regime], "stress_regime")[0]
    recalls = [float((predicted[true == label] == label).mean()) for label in np.unique(true)]
    confusion = np.zeros((3, 3), dtype=int)
    np.add.at(confusion, (true, predicted), 1)
    return {
        "accuracy": float((true == predicted).mean()),
        "balanced_accuracy": float(np.mean(recalls)),
        "stress_recall": float((predicted[true == stress] == stress).mean()) if (true == stress).any() else None,
        "n_observations": len(predictions), "confusion_matrix": confusion.tolist(),
    }
