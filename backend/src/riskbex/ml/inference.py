"""Apply a caller-supplied trained classifier. No dependency on fitting APIs."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.riskbex.ml.config import FEATURE_COLUMNS, normalize_sample
from src.riskbex.ml.data import dated_frame, numeric_values, prepare_features, regime_values


def validate_predictions(frame):
    output = dated_frame(frame)
    probabilities = numeric_values(output, [f"proba_{k}" for k in range(3)])
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Regime probabilities must lie in [0, 1].")
    if not np.allclose(probabilities.sum(axis=1), 1., atol=1e-6, rtol=0):
        raise ValueError("Regime probabilities must sum to one; no renormalization.")
    if "regime_pred" not in output:
        raise ValueError("regime_pred is required.")
    predictions = regime_values(output["regime_pred"], "regime_pred")
    maximum = probabilities.max(axis=1)
    if not np.isclose(probabilities[np.arange(len(output)), predictions], maximum,
                      atol=1e-12, rtol=0).all():
        raise ValueError("Predicted class must have maximal probability.")
    output["regime_pred"] = predictions
    return output


@dataclass(frozen=True)
class TrainedRegimeModel:
    classifier: Any
    sample: str
    trained_through: str
    feature_columns: tuple = FEATURE_COLUMNS
    artifact_id: str = ""


def load_xgboost_model(path, metadata_path, *, sample):
    """Load only a native XGBoost JSON/UBJ model with explicit provenance metadata.

    No pickle execution, training, dependency installation or model fallback.
    No original artifact was recovered in Sprint 1B; this is a future load path.
    """
    source = Path(path)
    if source.suffix.lower() not in {".json", ".ubj"}:
        raise ValueError("Use native XGBoost JSON or UBJ artifacts.")
    metadata = json.loads(Path(metadata_path).read_text())
    required = {"sample", "trained_through", "feature_columns", "sha256", "classes", "xgboost_version"}
    if not required <= metadata.keys():
        raise ValueError(f"Model metadata missing fields: {sorted(required - metadata.keys())}")
    if normalize_sample(metadata["sample"]) != normalize_sample(sample):
        raise ValueError("Model metadata belongs to another sample.")
    if tuple(metadata["feature_columns"]) != FEATURE_COLUMNS:
        raise ValueError("Model metadata does not match the eleven-feature contract.")
    if hashlib.sha256(source.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("Model SHA-256 does not match metadata.")
    import xgboost  # Optional runtime dependency; absent in the current backend environment.

    if xgboost.__version__ != metadata["xgboost_version"]:
        raise ValueError("XGBoost runtime differs from model metadata; validate explicitly before use.")
    classifier = xgboost.XGBClassifier()
    classifier.load_model(str(source))
    if list(classifier.classes_) != metadata["classes"]:
        raise ValueError("Loaded class order differs from model metadata.")
    return TrainedRegimeModel(classifier, metadata["sample"], metadata["trained_through"],
                              tuple(metadata["feature_columns"]), metadata["sha256"])


def predict_regimes(bundle, frame, *, sample):
    name = normalize_sample(sample)
    if normalize_sample(bundle.sample) != name:
        raise ValueError("Model sample does not match requested MAIN/ROBUST sample.")
    if tuple(bundle.feature_columns) != FEATURE_COLUMNS or not bundle.artifact_id:
        raise ValueError("Model requires exact feature order and a nonempty artifact_id.")
    output = dated_frame(frame)
    trained_through = pd.Timestamp(bundle.trained_through)
    if pd.isna(trained_through) or trained_through.tz is not None:
        raise ValueError("Invalid model training cutoff.")
    if not (output["date"] > trained_through).all():
        raise ValueError("Inference dates must be strictly after model training cutoff.")
    model = bundle.classifier
    classes = regime_values(getattr(model, "classes_", []), "classes_")
    if len(classes) != 3 or set(classes) != {0, 1, 2}:
        raise ValueError("Trained classifier must expose three distinct regime classes.")
    if hasattr(model, "feature_names_in_") and tuple(model.feature_names_in_) != FEATURE_COLUMNS:
        raise ValueError("Classifier feature names disagree with original TFM order.")
    if hasattr(model, "n_features_in_") and model.n_features_in_ != len(FEATURE_COLUMNS):
        raise ValueError("Classifier was not fitted with eleven features.")
    features = prepare_features(output)
    probabilities = np.asarray(model.predict_proba(features))
    if probabilities.shape != (len(features), 3):
        raise ValueError("Unexpected predict_proba shape.")
    predictions = np.asarray(model.predict(features))
    if predictions.shape != (len(features),):
        raise ValueError("Unexpected predict shape.")
    result = output[["date"]].copy()
    result["regime_pred"] = predictions
    for index, regime in enumerate(classes):
        result[f"proba_{regime}"] = probabilities[:, index]
    return validate_predictions(result)
