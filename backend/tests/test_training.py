"""Preflight and persistence guard tests; these tests never fit models."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.train_xgboost_experiment import run_experiment
from src.riskbex.ml.training import read_verified


class TrainingPreparationTests(unittest.TestCase):
    def test_preflight_only_does_not_require_xgboost_or_create_output(self):
        with patch("scripts.train_xgboost_experiment.prepare_experiment_inputs", return_value=({}, {"checked": True})), \
             patch.dict("sys.modules", {"xgboost": None}):
            result = run_experiment(Path("unused"), Path("unused"), None, train=False)
            self.assertEqual(result["status"], "preflight_passed_no_training")

    def test_source_hash_mismatch_stops_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            source.write_text("changed")
            with self.assertRaisesRegex(ValueError, "Reference changed"):
                read_verified(source, "not-the-hash")

    def test_output_cannot_be_operational_or_overwrite_existing_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "experiments" / "existing"
            existing.mkdir(parents=True)
            with patch("scripts.train_xgboost_experiment.PROJECT_ROOT", root), \
                 patch("scripts.train_xgboost_experiment.prepare_experiment_inputs", return_value=({}, {})), \
                 patch.dict("sys.modules", {"xgboost": None}):
                with self.assertRaisesRegex(ValueError, "backend/experiments"):
                    run_experiment(root, root, root / "data", train=True)
                with self.assertRaises(FileExistsError):
                    run_experiment(root, root, existing, train=True)

    def test_real_local_preflight_matches_both_training_references_without_fit(self):
        from src.riskbex.ml.training import prepare_experiment_inputs

        backend = Path(__file__).resolve().parents[1]
        academic = backend.parent.parent / "TMF-Market-Regimes-Risk-Portfolio"
        if not academic.exists():
            self.skipTest("Original local TFM required for source/label verification.")
        inputs, provenance = prepare_experiment_inputs(academic, backend / "tests/fixtures/tfm_ml")
        for sample, rows, cutoff in [("main", 5273, "2021-01-01"), ("robust", 5016, "2020-01-01")]:
            train = inputs[sample]["train"]
            self.assertEqual(len(train), rows)
            self.assertTrue((train["target_date"] < pd.Timestamp(cutoff)).all())
            self.assertEqual(provenance["samples"][sample]["historical_train_rows"] - len(train), 1)


if __name__ == "__main__":
    unittest.main()
