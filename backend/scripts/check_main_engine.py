"""Offline MAIN historical compatibility and real signal examples; prints JSON only."""

import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.check_ml_equivalence import read_frozen_table
from src.riskbex.engine.package import load_main_package
from src.riskbex.engine.service import infer_main_signals, prepare_engine_features
from src.riskbex.ml.config import FEATURE_COLUMNS
from src.riskbex.ml.inference import predict_regimes
from src.riskbex.regimes.persistence import filter_frozen_markov


def read_sprint2_fixture(name):
    root = BACKEND / "tests/fixtures/sprint2"
    entry = json.loads((root / "manifest.json").read_text())[name]
    raw = gzip.decompress((root / entry["file"]).read_bytes())
    if hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]:
        raise ValueError(f"Sprint 2 input changed: {name}")
    return pd.read_csv(BytesIO(raw), float_precision="round_trip")


def verify_engine():
    package = load_main_package(BACKEND / "model_packages/main-v1")
    prices = read_sprint2_fixture("historical_prices")
    _, features = prepare_engine_features(package, prices, as_of="2026-04-23")
    old_manifest = json.loads((BACKEND / "tests/fixtures/tfm_ml/manifest.json").read_text())
    master = read_frozen_table("historical_master", old_manifest)
    master["date"] = pd.to_datetime(master["date"])
    comparison = features.merge(master, on="date", suffixes=("_engine", "_tfm"), validate="one_to_one")
    if len(comparison) != len(master):
        raise AssertionError("Recovered feature coverage differs.")
    feature_errors = {}
    for column in FEATURE_COLUMNS:
        feature_errors[column] = float((comparison[column + "_engine"] - comparison[column + "_tfm"]).abs().max())
        np.testing.assert_allclose(comparison[column + "_engine"], comparison[column + "_tfm"], atol=1e-12, rtol=1e-10)
    filtered = filter_frozen_markov(package.markov, features[["date", "ret_1d"]], sample="main")
    academic = read_frozen_table("main_regime_backtest", old_manifest)
    academic["date"] = pd.to_datetime(academic["date"])
    markov_comparison = filtered.merge(academic, on="date", suffixes=("_engine", "_tfm"), validate="one_to_one")
    regime_changes = int((markov_comparison["regime_engine"] != markov_comparison["regime_tfm"]).sum())
    if regime_changes:
        raise AssertionError("Convergent MAIN regime IDs no longer match the academic reference.")
    markov_error = max(float((markov_comparison[f"p_regime_{k}_engine"] - markov_comparison[f"p_regime_{k}_tfm"]).abs().max()) for k in range(3))
    evaluation = features[features["date"] > pd.Timestamp(package.xgboost.trained_through)]
    predictions = predict_regimes(package.xgboost, evaluation[["date", *FEATURE_COLUMNS]], sample="main")
    expected = read_sprint2_fixture("causal_main_predictions")
    expected["date"] = pd.to_datetime(expected["date"])
    if predictions["date"].tolist() != expected["date"].tolist():
        raise AssertionError("causal-v1 validation dates differ.")
    np.testing.assert_array_equal(predictions["regime_pred"], expected["regime_pred"])
    prediction_error = max(float((predictions[f"proba_{k}"] - expected[f"proba_{k}"]).abs().max()) for k in range(3))
    np.testing.assert_allclose(predictions[[f"proba_{k}" for k in range(3)]], expected[[f"proba_{k}" for k in range(3)]], atol=1e-12, rtol=0)
    original = read_frozen_table("main_predictions", old_manifest)
    original["date"] = pd.to_datetime(original["date"])
    paired = predictions.merge(original, on="date", suffixes=("_engine", "_tfm"), validate="one_to_one")
    class_changes_from_original = int((paired["regime_pred_engine"] != paired["regime_pred_tfm"]).sum())
    extended = read_sprint2_fixture("extended_prices")
    examples = {date: infer_main_signals(package, extended, as_of=date)
                for date in ["2021-01-04", "2026-04-23", "2026-05-15"]}
    return {
        "package_id": package.manifest["package_id"], "manifest_sha256": package.manifest_sha256,
        "feature_rows_compared": len(comparison), "feature_max_errors": feature_errors,
        "markov_oos_rows_compared": len(markov_comparison), "markov_regime_changes_from_tfm": regime_changes,
        "markov_max_probability_difference_from_academic_100_iterations": markov_error,
        "xgboost_rows_compared": len(predictions), "xgboost_class_changes_from_causal_v1": 0,
        "xgboost_max_probability_difference_from_causal_v1": prediction_error,
        "xgboost_class_changes_from_original_tfm": class_changes_from_original,
        "examples": examples,
        "activation": "offline_only_no_download_training_or_operational_writes",
    }


if __name__ == "__main__":
    print(json.dumps(verify_engine(), indent=2, allow_nan=False))
