"""Validate persisted reconstruction candidates without performing any fitting."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import statsmodels
import statsmodels.api as sm

from src.riskbex.regimes.persistence import (
    FrozenMarkovModel, filter_frozen_markov, load_frozen_markov, verify_xgboost_correspondence,
)


BACKEND = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("RISKBEX_MARKOV_EXPERIMENT", BACKEND / "experiments/sprint-1d-markov-v2"))
AVAILABLE = statsmodels.__version__ == "0.14.5" and (ROOT / "summary.json").is_file()


def reference_frame(sample):
    manifest = json.loads((BACKEND / "tests/fixtures/tfm_cvar_reference.json").read_text())
    path = BACKEND.parent.parent / "TMF-Market-Regimes-Risk-Portfolio" / manifest["sources"][sample + "_regimes"]["path"]
    return pd.read_csv(path)


def diagnostic_bundle(sample, folder):
    metadata = json.loads((folder / "metadata.json").read_text())
    parameters = json.loads((folder / "parameters.json").read_text())
    return FrozenMarkovModel(sample, tuple(parameters["parameters"]), tuple(parameters["parameter_names"]),
                              tuple(metadata["initial_probabilities"]), metadata["history_start"],
                              metadata["trained_through"], tuple(metadata["economic_classes"]), "diagnostic-only")


@unittest.skipUnless(AVAILABLE, "Requires completed Markov experiment and recorded statsmodels 0.14.5; never fits.")
class MarkovArtifactTests(unittest.TestCase):
    def test_historical_probabilities_and_labels_are_reproducible_from_saved_parameters(self):
        for sample in ["main", "robust"]:
            reference = reference_frame(sample)
            for recipe in ["notebook_100", "convergence_500"]:
                folder = ROOT / sample / recipe
                bundle = diagnostic_bundle(sample, folder)
                with patch.object(sm.tsa.MarkovRegression, "fit", side_effect=AssertionError("fit forbidden")):
                    result = filter_frozen_markov(bundle, reference[["date", "ret_1d"]], sample=sample)
                expected = pd.read_csv(folder / "probabilities.csv.gz", float_precision="round_trip")
                np.testing.assert_array_equal(result["regime"], expected["regime"])
                np.testing.assert_array_equal(result[[f"p_regime_{k}" for k in range(3)]], expected[[f"p_regime_{k}" for k in range(3)]])
                validation = json.loads((folder / "validation.json").read_text())
                error = np.abs(result[[f"p_regime_{k}" for k in range(3)]].to_numpy() - reference[[f"p_regime_{k}" for k in range(3)]].to_numpy()).max()
                self.assertAlmostEqual(error, validation["max_probability_error"], places=14)

    def test_technical_gate_matches_convergence_and_training_target_compatibility(self):
        for sample in ["main", "robust"]:
            for recipe in ["notebook_100", "convergence_500"]:
                folder = ROOT / sample / recipe
                metadata = json.loads((folder / "metadata.json").read_text())
                report = json.loads((folder / "validation.json").read_text())
                if metadata["technical_validation"] == "passed":
                    self.assertTrue(report["converged"])
                    self.assertEqual(report["train_regime_mismatches"], 0)
                    self.assertEqual(report["full_regime_mismatches"], 0)
                    self.assertTrue(report["same_train_cvar_mapping"])
                    self.assertTrue(verify_xgboost_correspondence(folder / "metadata.json",
                        BACKEND / "experiments/sprint-1c-causal-v1" / sample / "metadata.json"))
                    load_frozen_markov(folder / "metadata.json", sample=sample)
                else:
                    with self.assertRaisesRegex(ValueError, "not passed"):
                        load_frozen_markov(folder / "metadata.json", sample=sample)

    def test_new_observations_and_future_returns_do_not_alter_past_probabilities(self):
        for sample in ["main", "robust"]:
            frame = reference_frame(sample)[["date", "ret_1d"]]
            # Original train-only parameters did not observe these last OOS rows.
            bundle = diagnostic_bundle(sample, ROOT / sample / "notebook_100")
            prefix = frame.iloc[:-10]
            previous = filter_frozen_markov(bundle, prefix, sample=sample)
            extended = filter_frozen_markov(bundle, frame, sample=sample)
            pd.testing.assert_frame_equal(previous, extended.iloc[:-10], check_exact=True)
            changed = frame.copy()
            changed.iloc[-10:, changed.columns.get_loc("ret_1d")] = -.15
            stress = filter_frozen_markov(bundle, changed, sample=sample)
            pd.testing.assert_frame_equal(previous, stress.iloc[:-10], check_exact=True)
            self.assertFalse(stress[[f"p_regime_{k}" for k in range(3)]].isna().any().any())

    def test_same_mapping_and_empirical_transitions_require_same_training_labels(self):
        for sample in ["main", "robust"]:
            for recipe in ["notebook_100", "convergence_500"]:
                report = json.loads((ROOT / sample / recipe / "validation.json").read_text())
                if report["train_regime_mismatches"] == 0:
                    self.assertTrue(report["same_train_cvar_mapping"])
                    self.assertLess(report["max_empirical_transition_error"], 1e-12)
                self.assertLess(report["max_probability_sum_error"], 1e-10)


if __name__ == "__main__":
    unittest.main()
