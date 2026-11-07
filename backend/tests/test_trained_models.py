"""Read-only native XGBoost tests. Run in the recorded training environment."""

import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from src.riskbex.ml.config import FEATURE_COLUMNS, SAMPLES
from src.riskbex.ml.inference import load_xgboost_model, predict_regimes


EXPERIMENT = Path(os.environ.get(
    "RISKBEX_XGB_EXPERIMENT",
    Path(__file__).resolve().parents[1] / "experiments/sprint-1c-causal-v1",
))
NATIVE_AVAILABLE = importlib.util.find_spec("xgboost") is not None and (EXPERIMENT / "summary.json").is_file()


@unittest.skipUnless(NATIVE_AVAILABLE, "Requires XGBoost runtime and persisted Sprint 1C models; never trains in tests.")
class PersistedXgboostTests(unittest.TestCase):
    def test_actual_models_reload_and_predict_without_future_labels(self):
        for sample in ["main", "robust"]:
            with self.subTest(sample=sample):
                folder = EXPERIMENT / sample
                loaded = load_xgboost_model(folder / "model.ubj", folder / "metadata.json", sample=sample)
                observations = pd.read_csv(folder / "inference_smoke_input.csv.gz", float_precision="round_trip")
                self.assertEqual(observations.columns.tolist(), ["date", *FEATURE_COLUMNS])
                actual = predict_regimes(loaded, observations, sample=sample)
                expected = pd.read_csv(folder / "inference_smoke_expected.csv.gz", float_precision="round_trip")
                self.assertEqual(actual["date"].dt.strftime("%Y-%m-%d").tolist(), expected["date"].tolist())
                np.testing.assert_array_equal(actual["regime_pred"], expected["regime_pred"])
                np.testing.assert_array_equal(actual[["proba_0", "proba_1", "proba_2"]].to_numpy(dtype=float),
                                              expected[["proba_0", "proba_1", "proba_2"]].to_numpy())

    def test_persisted_inputs_hashes_and_purge(self):
        for sample, count in [("main", 5273), ("robust", 5016)]:
            folder = EXPERIMENT / sample
            metadata = json.loads((folder / "metadata.json").read_text())
            self.assertEqual(tuple(metadata["feature_columns"]), FEATURE_COLUMNS)
            self.assertEqual(metadata["classes"], [0, 1, 2])
            self.assertEqual(metadata["boundary_policy"], "causal")
            self.assertEqual(hashlib.sha256((folder / "validation.json").read_bytes()).hexdigest(), metadata["validation_sha256"])
            for prefix in ["training", "validation"]:
                compressed = (folder / f"{prefix}_input.csv.gz").read_bytes()
                raw = gzip.decompress(compressed)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata[f"{prefix}_input"]["sha256_csv"])
                self.assertEqual(hashlib.sha256(compressed).hexdigest(), metadata[f"{prefix}_input"]["sha256_gzip"])
            training = pd.read_csv(folder / "training_input.csv.gz")
            self.assertEqual(len(training), count)
            cutoff = pd.Timestamp(SAMPLES[sample]["test_start"])
            dates, target_dates = pd.to_datetime(training["date"]), pd.to_datetime(training["target_date"])
            self.assertTrue((target_dates > dates).all())
            self.assertTrue((target_dates < cutoff).all())
            self.assertEqual(target_dates.max(), pd.Timestamp(metadata["trained_through"]))

    def test_corrupted_model_is_rejected_before_loading(self):
        for sample in ["main", "robust"]:
            folder = EXPERIMENT / sample
            with tempfile.TemporaryDirectory() as directory:
                corrupted = Path(directory) / "model.ubj"
                corrupted.write_bytes((folder / "model.ubj").read_bytes() + b"tampered")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    load_xgboost_model(corrupted, folder / "metadata.json", sample=sample)


if __name__ == "__main__":
    unittest.main()
