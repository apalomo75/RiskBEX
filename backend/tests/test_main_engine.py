"""Package integrity and offline MAIN acceptance tests. No training or downloads."""

import importlib.util
import json
from pathlib import Path
import platform
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import statsmodels
import statsmodels.api as sm

from scripts.check_main_engine import read_sprint2_fixture, verify_engine
from src.riskbex.engine.package import file_hash, load_main_package, verify_main_package
from src.riskbex.engine.service import infer_main_signals, prepare_engine_features


BACKEND = Path(__file__).resolve().parents[1]
PACKAGE = BACKEND / "model_packages/main-v1"
NATIVE = (importlib.util.find_spec("xgboost") is not None and statsmodels.__version__ == "0.14.5"
          and platform.python_version() == "3.11.14" and PACKAGE.is_dir())


def update_manifest(root, change):
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))
    (root / "manifest.sha256").write_text(file_hash(path) + "\n")


class MainPackageIntegrityTests(unittest.TestCase):
    def test_main_only_package_matches_selected_sources(self):
        manifest = verify_main_package(PACKAGE)
        self.assertEqual(manifest["sample"], "main")
        self.assertEqual(manifest["training"]["markov_rows"], 5274)
        self.assertEqual(manifest["training"]["xgboost_rows"], 5273)
        self.assertEqual(len(manifest["feature_columns"]), 11)
        self.assertFalse(any("robust" in name.lower() for name in manifest["files"]))
        for relative, entry in manifest["files"].items():
            source = BACKEND / entry["source_path"]
            self.assertEqual(file_hash(PACKAGE / relative), file_hash(source))

    def test_component_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            shutil.copytree(PACKAGE, root)
            (root / "xgboost/model.ubj").write_bytes(b"not-the-model")
            with self.assertRaisesRegex(ValueError, "component SHA-256"):
                verify_main_package(root)

    def test_manifest_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            shutil.copytree(PACKAGE, root)
            with (root / "manifest.json").open("a") as stream:
                stream.write(" ")
            with self.assertRaisesRegex(ValueError, "manifest SHA-256"):
                verify_main_package(root)

    def test_feature_order_and_economic_ids_cannot_change_even_with_new_checksum(self):
        changes = [lambda value: value["feature_columns"].reverse(),
                   lambda value: value["economic_classes"][0].update(economic_label="high_risk")]
        for change in changes:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "package"
                shutil.copytree(PACKAGE, root)
                update_manifest(root, change)
                with self.assertRaises(ValueError):
                    verify_main_package(root)

    def test_indicator_configuration_cannot_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            shutil.copytree(PACKAGE, root)
            update_manifest(root, lambda value: value["feature_policy"].update(ewma_lambda=.97))
            with self.assertRaisesRegex(ValueError, "indicator convention"):
                verify_main_package(root)

    def test_external_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "package"
            shutil.copytree(PACKAGE, root)
            update_manifest(root, lambda value: value["files"].update({"../escape": {"sha256": "bad"}}))
            with self.assertRaisesRegex(ValueError, "inside the package"):
                verify_main_package(root)

    def test_wrong_runtime_is_explicit(self):
        with patch("src.riskbex.engine.package.platform.python_version", return_value="wrong-version"):
            with self.assertRaisesRegex(ValueError, "runtime mismatch"):
                verify_main_package(PACKAGE, check_runtime=True)


@unittest.skipUnless(NATIVE, "Requires the recorded MAIN runtime; never installs or fits models.")
class MainEngineNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = load_main_package(PACKAGE)
        cls.prices = read_sprint2_fixture("extended_prices")

    def test_real_offline_execution_has_all_signals_and_normalized_probabilities(self):
        signal = infer_main_signals(self.package, self.prices, as_of="2026-05-15")
        self.assertEqual(signal["last_valid_session"], "2026-05-15")
        self.assertEqual(signal["engine"], "MAIN")
        self.assertEqual(len(signal["features"]), 11)
        for name in ["markov", "xgboost"]:
            self.assertAlmostEqual(sum(signal[name]["probabilities"].values()), 1., places=6)
        self.assertEqual(set(signal["target_exposures"]), {"regime_based", "ml_hard", "ml_probability_weighted"})
        self.assertTrue(all(0 <= value <= 1 for value in signal["target_exposures"].values()))

    def test_inference_never_calls_fit(self):
        from xgboost import XGBClassifier
        with patch.object(sm.tsa.MarkovRegression, "fit", side_effect=AssertionError("Markov fit forbidden")), \
             patch.object(XGBClassifier, "fit", side_effect=AssertionError("XGBoost fit forbidden")):
            result = infer_main_signals(self.package, self.prices, as_of="2026-05-15")
            self.assertFalse(result["provenance"]["models_retrained"])

    def test_repeated_execution_is_identical_and_input_unchanged(self):
        before = self.prices.copy(deep=True)
        a = infer_main_signals(self.package, self.prices, as_of="2026-05-15")
        b = infer_main_signals(self.package, self.prices, as_of="2026-05-15")
        self.assertEqual(a, b)
        pd.testing.assert_frame_equal(before, self.prices)

    def test_future_prices_do_not_change_any_signal_or_provenance(self):
        a = infer_main_signals(self.package, self.prices, as_of="2026-04-23")
        changed = self.prices.copy()
        changed.loc[changed["date"] > "2026-04-23", "ibex_close"] = np.nan
        b = infer_main_signals(self.package, changed, as_of="2026-04-23")
        self.assertEqual(a, b)
        truncated = self.prices[self.prices["date"] <= "2026-04-23"]
        self.assertEqual(a, infer_main_signals(self.package, truncated, as_of="2026-04-23"))

    def test_new_sessions_outside_training_and_validation_need_no_future_labels(self):
        observations = self.prices[["date", "ibex_close"]]
        a = infer_main_signals(self.package, observations, as_of="2026-05-15")
        self.assertGreater(a["signal_information_date"], "2026-04-23")
        polluted = observations.assign(regime_t_plus_1=99, regime=99, ret_1d=999.)
        self.assertEqual(a, infer_main_signals(self.package, polluted, as_of="2026-05-15"))

    def test_next_session_targets_are_not_shifted_again(self):
        signal = infer_main_signals(self.package, self.prices, as_of="2021-01-04")
        self.assertEqual(signal["signal_information_date"], "2021-01-04")
        self.assertEqual(signal["execution_horizon"], "next_market_session")
        self.assertEqual(signal["markov"]["horizon"], "current_session_filtered_state")
        self.assertEqual(signal["xgboost"]["horizon"], "next_market_session")
        self.assertIsNone(signal["target_session_date"])
        self.assertTrue(all(value is not None for value in signal["target_exposures"].values()))

    def test_three_strategies_apply_the_same_train_mapping(self):
        signal = infer_main_signals(self.package, self.prices, as_of="2026-05-15")
        mapping = self.package.mapping.set_index("regime")["target_exposure"].to_dict()
        self.assertEqual(signal["target_exposures"]["regime_based"], mapping[signal["markov"]["regime"]])
        self.assertEqual(signal["target_exposures"]["ml_hard"], mapping[signal["xgboost"]["regime_pred"]])
        expected = sum(signal["xgboost"]["probabilities"][str(k)] * mapping[k] for k in mapping)
        self.assertAlmostEqual(signal["target_exposures"]["ml_probability_weighted"], expected, places=15)

    def test_training_history_revisions_and_missing_sessions_fail_closed(self):
        changed = self.prices.copy()
        changed.loc[0, "ibex_close"] += .01
        with self.assertRaisesRegex(ValueError, "Training price prefix"):
            infer_main_signals(self.package, changed, as_of="2026-05-15")
        with self.assertRaisesRegex(ValueError, "Training price prefix"):
            infer_main_signals(self.package, self.prices.drop(index=10), as_of="2026-05-15")

    def test_invalid_prices_dates_and_pretraining_cutoff_are_rejected(self):
        for changed in [self.prices.iloc[::-1], pd.concat([self.prices, self.prices.tail(1)]),
                        self.prices.assign(ibex_close=-1.), self.prices.assign(ibex_close="1")]:
            with self.assertRaises(ValueError):
                infer_main_signals(self.package, changed, as_of="2026-05-15")
        with self.assertRaisesRegex(ValueError, "after training"):
            infer_main_signals(self.package, self.prices, as_of="2020-12-31")

    def test_self_contained_package_works_after_copying_without_original_model_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "main"
            shutil.copytree(PACKAGE, root)
            package = load_main_package(root)
            self.assertEqual(infer_main_signals(package, self.prices, as_of="2026-05-15"),
                             infer_main_signals(self.package, self.prices, as_of="2026-05-15"))

    def test_historical_feature_and_model_compatibility(self):
        report = verify_engine()
        self.assertEqual(report["feature_rows_compared"], 6631)
        self.assertEqual(report["markov_regime_changes_from_tfm"], 0)
        self.assertEqual(report["xgboost_class_changes_from_causal_v1"], 0)
        self.assertEqual(report["xgboost_class_changes_from_original_tfm"], 11)


if __name__ == "__main__":
    unittest.main()
