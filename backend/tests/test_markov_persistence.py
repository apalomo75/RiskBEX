"""Frozen filtering tests; no optimizer or fitting is allowed in the tests."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels

from src.riskbex.regimes.markov_switching import extract_transition_matrix
from src.riskbex.regimes.persistence import (
    SPECIFICATION, FrozenMarkovModel, filter_frozen_markov, load_frozen_markov, parameter_diagnostics,
)


def synthetic_bundle():
    parameters = (.95, .01, .02, .001, .95, .02, .001, -.001, 0., .00005, .001, .0002)
    model = sm.tsa.MarkovRegression(np.sin(np.arange(40)) * .01, **SPECIFICATION)
    info = parameter_diagnostics(model, parameters)
    classes = ({"regime": 0, "economic_label": "low_risk", "risk_order": 1},
               {"regime": 2, "economic_label": "medium_risk", "risk_order": 2},
               {"regime": 1, "economic_label": "high_risk", "risk_order": 3})
    bundle = FrozenMarkovModel("main", parameters, tuple(model.param_names),
                                tuple(info["initial_probabilities"]), "2020-01-01", "2020-01-10",
                                classes, "synthetic-not-a-trained-model")
    data = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=40),
                         "ret_1d": np.sin(np.arange(40)) * .01})
    return bundle, data, model


class FrozenMarkovTests(unittest.TestCase):
    def test_filtering_is_normalized_and_never_calls_fit(self):
        bundle, data, _ = synthetic_bundle()
        with patch.object(sm.tsa.MarkovRegression, "fit", side_effect=AssertionError("fit forbidden")):
            result = filter_frozen_markov(bundle, data, sample="main")
        np.testing.assert_allclose(result[[f"p_regime_{k}" for k in range(3)]].sum(axis=1), 1., atol=1e-12)
        self.assertTrue(np.isfinite(result[[f"p_regime_{k}" for k in range(3)]]).all().all())

    def test_future_returns_do_not_change_past_oos_probabilities(self):
        bundle, data, _ = synthetic_bundle()
        original = filter_frozen_markov(bundle, data, sample="main")
        prefix = filter_frozen_markov(bundle, data.iloc[:30], sample="main")
        pd.testing.assert_frame_equal(prefix, original.iloc[:30], check_exact=True)
        changed = data.copy()
        changed.loc[30:, "ret_1d"] = -.10
        alternative = filter_frozen_markov(bundle, changed, sample="main")
        pd.testing.assert_frame_equal(alternative.iloc[:30], original.iloc[:30], check_exact=True)

    def test_wrong_sample_truncated_history_duplicate_dates_and_missing_data_fail(self):
        bundle, data, _ = synthetic_bundle()
        for values, sample in [(data, "robust"), (data.iloc[1:], "main"),
                                (data.iloc[:5], "main"), (pd.concat([data, data.tail(1)]), "main"),
                                (data.assign(ret_1d=np.nan), "main")]:
            with self.subTest(sample=sample, length=len(values)), self.assertRaises(ValueError):
                filter_frozen_markov(bundle, values, sample=sample)

    def test_parameter_validation_and_transition_orientation(self):
        bundle, _, model = synthetic_bundle()
        diagnostics = parameter_diagnostics(model, bundle.parameters)
        extracted = extract_transition_matrix(SimpleNamespace(regime_transition=model.regime_transition_matrix(bundle.parameters)))
        np.testing.assert_allclose(extracted, diagnostics["transition_from_to"])
        np.testing.assert_allclose(extracted.sum(axis=1), 1.)
        for index, value in [(0, 1.5), (9, 0.), (10, np.nan)]:
            parameters = list(bundle.parameters)
            parameters[index] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                parameter_diagnostics(model, parameters)

    def test_rejected_candidate_cannot_be_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text(json.dumps({"technical_validation": "failed"}))
            with self.assertRaisesRegex(ValueError, "not passed"):
                load_frozen_markov(path, sample="main")

    def test_wrong_runtime_is_rejected_before_parameter_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text(json.dumps({"technical_validation": "passed", "statsmodels_version": "not-this-runtime"}))
            with self.assertRaisesRegex(ValueError, "statsmodels"):
                load_frozen_markov(path, sample="main")

    def test_native_probability_roundoff_is_preserved_but_real_bound_errors_fail(self):
        bundle, data, _ = synthetic_bundle()
        probabilities = np.tile([1. + 4e-16, 0., 0.], (len(data), 1))
        with patch.object(sm.tsa.MarkovRegression, "filter",
                          return_value=SimpleNamespace(filtered_marginal_probabilities=probabilities)):
            result = filter_frozen_markov(bundle, data, sample="main")
            self.assertEqual(result["p_regime_0"].iloc[0], probabilities[0, 0])
            self.assertGreater(result["p_regime_0"].iloc[0], 1.)
        probabilities[:, 0] = 1.00001
        with patch.object(sm.tsa.MarkovRegression, "filter",
                          return_value=SimpleNamespace(filtered_marginal_probabilities=probabilities)):
            with self.assertRaisesRegex(ValueError, "Invalid filtered"):
                filter_frozen_markov(bundle, data, sample="main")

    def test_parameter_tampering_is_rejected_before_filtering(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "parameters.json").write_text("{}")
            metadata = {"technical_validation": "passed", "statsmodels_version": statsmodels.__version__,
                        "sample": "main", "specification": SPECIFICATION, "initialization": "steady-state",
                        "parameters_file": "parameters.json", "parameters_sha256": "not-the-hash"}
            (folder / "metadata.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_frozen_markov(folder / "metadata.json", sample="main")


if __name__ == "__main__":
    unittest.main()
