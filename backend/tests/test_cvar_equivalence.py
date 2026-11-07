"""Offline equivalence tests; no downloads, fitting, or operational CSV writes."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from main import app
from scripts import prepare_regime_datasets as prepare
from src.riskbex.api.routes import backtesting, regimes
from src.riskbex.api.schemas import (
    AdaptiveBacktestMetricsRow,
    AdaptiveBacktestResultRow,
    RegimeSummaryRow,
)
from src.riskbex.backtesting.exposures import build_cvar_exposure_mapping
from src.riskbex.backtesting.regime_backtest import run_regime_backtest
from src.riskbex.data import loaders
from src.riskbex.regimes.interpretation import (
    build_regime_label_mapping,
    build_regime_summary,
)


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "tfm_cvar_reference.json").read_text()
)


def reference_table(name):
    df = pd.DataFrame(FIXTURE["tables"][name])
    for column in df.columns:
        if column not in {"economic_label", "methodology"}:
            df[column] = pd.to_numeric(df[column])
    return df


def sample_data():
    # Adversarial OOS values would reverse the economic order if included.
    rows = []
    for regime, vol, cvar in [(0, .01, -.02), (1, .03, -.08), (2, .02, -.04)]:
        rows.append({
            "date": f"2019-01-0{regime + 1}", "ret_1d": -.01,
            "ewma_vol": vol, "cvar_95_60d": cvar,
            "main_regime": regime, "robust_regime": regime,
            "sample_split_main": "train", "sample_split_robust": "train",
        })
    rows.append({**rows[0], "date": "2021-01-04", "ewma_vol": 10.,
                 "cvar_95_60d": -100., "sample_split_main": "test",
                 "sample_split_robust": "test"})
    df = pd.DataFrame(rows)
    for prefix in ["main", "robust"]:
        for regime in range(3):
            df[f"{prefix}_p_regime_{regime}"] = (df[f"{prefix}_regime"] == regime).astype(float)
    return df


class CvarEquivalenceTests(unittest.TestCase):
    def test_both_tfm_exposure_mappings(self):
        for sample in ["main", "robust"]:
            with self.subTest(sample=sample):
                summary = reference_table(sample + "_summary")
                summary["split"] = sample.upper()
                actual = prepare.build_exposure_mapping(summary, sample.upper())
                expected = reference_table(sample + "_mapping")
                pd.testing.assert_frame_equal(actual, expected, check_dtype=False,
                                              atol=1e-12, rtol=1e-10)

    def test_tfm_order_uses_signed_cvar_as_tiebreaker(self):
        summary = pd.DataFrame({"regime": [0, 1, 2], "mean_ewma_vol": [.01, .01, .02],
                                "mean_cvar_95_60d": [-.02, -.04, -.03]})
        self.assertEqual(build_regime_label_mapping(summary)["regime"].tolist(), [1, 0, 2])

    def test_oos_values_do_not_change_train_summary_or_exposure(self):
        df = sample_data()
        original = build_regime_summary(df)
        mutated = df.copy()
        mutated.loc[3, ["ewma_vol", "cvar_95_60d", "ret_1d"]] = [999., -999., 99.]
        mutated.loc[3, ["main_regime", "robust_regime"]] = [2, 1]
        pd.testing.assert_frame_equal(original, build_regime_summary(mutated))
        self.assertEqual(original.groupby("split")["n_obs"].sum().tolist(), [3, 3])
        # Existing API uses fractions despite the historical field name.
        np.testing.assert_allclose(original.groupby("split")["frequency_pct"].sum(), 1.)

    def test_each_sample_uses_its_own_train_partition(self):
        df = sample_data()
        df.loc[3, "sample_split_main"] = "train"
        summary = build_regime_summary(df)
        self.assertEqual(summary.groupby("split")["n_obs"].sum().to_dict(), {"MAIN": 4, "ROBUST": 3})

    def test_relabelled_regime_ids_are_not_hardcoded(self):
        source = reference_table("main_summary")
        source["regime"] = source["regime"].map({0: 2, 2: 1, 1: 0})
        actual = build_cvar_exposure_mapping(source)
        self.assertEqual(actual["regime"].tolist(), [2, 1, 0])
        np.testing.assert_allclose(actual["target_exposure"],
                                   reference_table("main_mapping")["target_exposure"])

    def test_invalid_cvar_fails_closed(self):
        for value in [0., np.nan, np.inf]:
            with self.subTest(value=value):
                df = reference_table("main_summary")
                df.loc[1, "mean_cvar_95_60d"] = value
                with self.assertRaises(ValueError):
                    build_cvar_exposure_mapping(df)

    def test_invalid_alpha_is_rejected(self):
        for value in [0., -1., np.nan, np.inf]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_cvar_exposure_mapping(reference_table("main_summary"), value)

    def test_duplicate_labels_regimes_and_wrong_risk_order_are_rejected(self):
        for column, value in [("regime", 0), ("economic_label", "low_risk"), ("risk_order", 1)]:
            df = reference_table("main_summary")
            df.loc[1, column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                build_cvar_exposure_mapping(df)

    def test_nonmonotonic_cvar_exposures_are_rejected(self):
        df = reference_table("main_summary")
        df.loc[1, "mean_cvar_95_60d"] = -.001
        with self.assertRaises(ValueError):
            build_cvar_exposure_mapping(df)

    def test_missing_train_and_nonfinite_train_data_are_rejected(self):
        df = sample_data()
        for kind in ["no_train", "nonfinite", "missing_regime"]:
            changed = df.copy()
            if kind == "no_train":
                changed["sample_split_main"] = "test"
            elif kind == "nonfinite":
                changed.loc[0, "ewma_vol"] = np.inf
            else:
                changed = changed[changed["main_regime"] != 1]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build_regime_summary(changed)

    def test_existing_summary_response_schema(self):
        for row in build_regime_summary(sample_data()).to_dict(orient="records"):
            RegimeSummaryRow.model_validate(row)

    def test_preparation_uses_train_and_existing_loader_accepts_new_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            input_path = folder / "regime_dataset.csv"
            data = sample_data()
            extra = pd.concat([data.tail(1), data.tail(1)], ignore_index=True)
            extra["date"] = ["2021-01-05", "2021-01-06"]
            pd.concat([data, extra], ignore_index=True).to_csv(input_path, index=False)
            changes = {
                "REGIME_DATASET_PATH": input_path,
                "REGIME_SUMMARY_PATH": folder / "regime_summary.csv",
                "MAIN_OUTPUT_PATH": folder / "regime_dataset_main.csv",
                "ROBUST_OUTPUT_PATH": folder / "regime_dataset_robust.csv",
                "MAIN_MAPPING_PATH": folder / "regime_exposure_mapping.csv",
                "ROBUST_MAPPING_PATH": folder / "regime_exposure_mapping_robust.csv",
            }
            with patch.multiple(prepare, **changes), patch("builtins.print"):
                prepare.main()
            with patch.object(loaders, "PROCESSED_DATA_DIR", folder):
                for sample in ["main", "robust"]:
                    mapping = loaders.load_regime_exposure_mapping(sample)
                    np.testing.assert_allclose(mapping["target_exposure"], [1., .5, .25])
                    self.assertEqual(len(loaders.load_clean_regime_dataset(sample)), 6)
                    backtest, metrics = run_regime_backtest(sample)
                    self.assertEqual(len(backtest), 2)
                    with patch.object(backtesting, "load_adaptive_backtest_results", return_value=backtest):
                        for row in backtesting.backtesting_results(sample):
                            AdaptiveBacktestResultRow.model_validate(row)
                    with patch.object(backtesting, "load_adaptive_backtest_metrics", return_value=metrics):
                        for row in backtesting.backtesting_metrics():
                            AdaptiveBacktestMetricsRow.model_validate(row)
            with patch("src.riskbex.api.routes.regimes.load_regime_summary",
                       return_value=pd.read_csv(changes["REGIME_SUMMARY_PATH"])):
                response = regimes.regimes_summary(split="MAIN")
                self.assertEqual(sum(row["n_obs"] for row in response), 3)
                for row in response:
                    RegimeSummaryRow.model_validate(row)

    def test_existing_api_routes_are_preserved(self):
        expected = {
            ("GET", "/health"), ("GET", "/latest-risk"), ("GET", "/historical-risk"),
            ("POST", "/run-update"),
            *(("GET", "/regimes/" + name) for name in
              ["latest", "history", "summary", "model-selection", "transitions", "durations"]),
            *(("GET", "/backtesting/" + name) for name in ["results", "metrics", "latest"]),
            *(("GET", "/tail-risk/" + name) for name in ["events", "metrics", "thresholds", "latest"]),
        }
        actual = {(method, route.path) for route in app.routes for method in getattr(route, "methods", [])}
        self.assertTrue(expected <= actual)


class LocalTfmIntegrationTests(unittest.TestCase):
    def test_frozen_local_regimes_reproduce_training_statistics_and_mapping(self):
        root = Path(os.environ.get("TFM_REFERENCE_DIR", Path(__file__).resolve().parents[3] /
                                   "TMF-Market-Regimes-Risk-Portfolio"))
        if not root.is_dir():
            self.skipTest("Local TFM unavailable; compact fixture tests still run.")
        samples = []
        for sample in ["main", "robust"]:
            source = FIXTURE["sources"][sample + "_regimes"]
            path = root / source["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"],
                             "TFM candidate changed; review reference instead of updating expectations blindly.")
            df = pd.read_csv(path)
            # Merge actual MAIN/ROBUST model outputs; never train or regenerate them.
            samples.append(df.rename(columns={"regime": sample + "_regime"}))
        combined = samples[0].merge(samples[1][["date", "robust_regime"]],
                                    on="date", validate="one_to_one")
        summary = build_regime_summary(combined)
        for sample in ["main", "robust"]:
            actual = summary[summary["split"] == sample.upper()].sort_values("risk_order")
            expected = reference_table(sample + "_summary")
            for column in ["regime", "n_obs", "mean_ret_1d", "mean_ewma_vol", "mean_cvar_95_60d"]:
                np.testing.assert_allclose(actual[column], expected[column], atol=1e-12, rtol=1e-10)
            mapping = prepare.build_exposure_mapping(summary, sample.upper())
            np.testing.assert_allclose(mapping["target_exposure"],
                                       reference_table(sample + "_mapping")["target_exposure"],
                                       atol=1e-12, rtol=1e-10)


if __name__ == "__main__":
    unittest.main()
