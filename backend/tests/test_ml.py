"""ML contracts, future inference boundaries and offline historical equivalence."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from main import app
from scripts.check_ml_equivalence import FIXTURE_ROOT, read_frozen_table, verify_reference
from src.riskbex.backtesting.costs import add_transaction_costs
from src.riskbex.backtesting.ml_backtest import compare_on_common_dates, run_ml_backtest, select_ml_strategy
from src.riskbex.backtesting.strategy_service import get_strategy_backtest
from src.riskbex.backtesting.exposures import build_cvar_exposure_mapping
from src.riskbex.data.loaders import load_ml_predictions
from src.riskbex.ml.config import FEATURE_COLUMNS, XGBOOST_PARAMETERS
from src.riskbex.ml.data import (
    assemble_features, build_next_regime_target, evaluation_rows, prepare_features, training_rows,
)
from src.riskbex.ml.evaluation import classification_metrics
from src.riskbex.ml.inference import (
    TrainedRegimeModel, load_xgboost_model, predict_regimes, validate_predictions,
)


MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text())


def frozen(sample, kind):
    return read_frozen_table(f"{sample}_{kind}", MANIFEST)


def features(dates=None):
    dates = dates or ["2020-12-30", "2020-12-31", "2021-01-04", "2021-01-05"]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "regime": [0, 1, 2, 0][:len(dates)]})
    for index, column in enumerate(FEATURE_COLUMNS):
        df[column] = float(index + 1) / 100
    return df


class FakeClassifier:
    """Test double only, never represented as a recovered or trained XGBoost model."""

    classes_ = np.array([2, 0, 1])
    feature_names_in_ = np.array(FEATURE_COLUMNS)
    n_features_in_ = 11

    def fit(self, *args, **kwargs):
        raise AssertionError("Fitting is forbidden in Sprint 1B")

    def predict_proba(self, frame):
        if tuple(frame.columns) != FEATURE_COLUMNS:
            raise AssertionError("Feature ordering changed")
        return np.tile([.1, .7, .2], (len(frame), 1))

    def predict(self, frame):
        return np.zeros(len(frame), dtype=int)


def bundle(**changes):
    values = dict(classifier=FakeClassifier(), sample="main", trained_through="2020-12-31",
                  artifact_id="test-double-only")
    values.update(changes)
    return TrainedRegimeModel(**values)


class FeatureContractTests(unittest.TestCase):
    def test_historical_master_recovered_from_git_has_eleven_features_and_train_coverage(self):
        master = read_frozen_table("historical_master", MANIFEST)
        actual = prepare_features(master)
        self.assertEqual(actual.shape, (6631, 11))
        dates = pd.to_datetime(master["date"])
        self.assertEqual(int((dates < "2021-01-01").sum()), 5274)
        self.assertEqual(int((dates < "2020-01-01").sum()), 5017)
        self.assertEqual(dates.max(), pd.Timestamp("2026-04-23"))

    def test_exact_eleven_features_in_original_order(self):
        source = features()
        before = source.copy()
        actual = prepare_features(source[list(reversed(source.columns))])
        self.assertEqual(tuple(actual.columns), FEATURE_COLUMNS)
        self.assertEqual(actual.shape, (4, 11))
        pd.testing.assert_frame_equal(source, before)

    def test_every_feature_is_mandatory(self):
        for column in FEATURE_COLUMNS:
            with self.subTest(column=column), self.assertRaises(ValueError):
                prepare_features(features().drop(columns=column))

    def test_no_silent_nan_infinity_string_or_boolean_acceptance(self):
        for value in [np.nan, np.inf, -np.inf, "0.1", True]:
            df = features()
            df["ret_20d"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_features(df)

    def test_duplicate_unsorted_invalid_timezone_or_intraday_dates_fail(self):
        source = features()
        for dates in [
            ["2021-01-04"] * 4,
            ["2021-01-05", "2021-01-04", "2021-01-06", "2021-01-07"],
            ["invalid"] * 4,
            pd.date_range("2021-01-04", periods=4, tz="UTC"),
            pd.date_range("2021-01-04 12:00", periods=4),
        ]:
            df = source.copy()
            df["date"] = dates
            with self.subTest(dates=str(dates)), self.assertRaises(ValueError):
                prepare_features(df)

    def test_assembly_keeps_every_date_and_rejects_missing_coverage(self):
        source = features()
        base = source[["date", "regime", "ret_1d", "ewma_vol", "cvar_95_60d"]]
        assembled = assemble_features(base, source)
        pd.testing.assert_frame_equal(prepare_features(assembled), prepare_features(source))
        with self.assertRaises(ValueError):
            assemble_features(base, source.iloc[1:])
        with self.assertRaises(ValueError):
            assemble_features(base, pd.concat([source, source.iloc[-1:]]))

    def test_duplicate_columns_are_rejected(self):
        df = features()
        with self.assertRaises(ValueError):
            prepare_features(pd.concat([df, df[["ret_1d"]]], axis=1))

    def test_historical_and_causal_training_are_explicit_for_both_samples(self):
        for sample, year in [("main", "2020"), ("robust", "2019")]:
            next_year = str(int(year) + 1)
            df = features([f"{year}-12-30", f"{year}-12-31", f"{next_year}-01-04", f"{next_year}-01-05"])
            labeled = build_next_regime_target(df)
            historical = training_rows(labeled, sample, boundary_policy="historical_tfm")
            causal = training_rows(labeled, sample, boundary_policy="causal")
            self.assertEqual(len(historical), 2)
            self.assertEqual(historical.attrs["targets_crossing_test_boundary"], 1)
            self.assertEqual(len(causal), 1)
            self.assertEqual(causal.attrs["targets_crossing_test_boundary"], 0)
            self.assertEqual(len(evaluation_rows(labeled, sample)), 1)
        with self.assertRaises(TypeError):
            training_rows(labeled, "main")

    def test_next_target_is_next_session_and_final_row_is_preserved(self):
        labeled = build_next_regime_target(features())
        self.assertEqual(labeled.loc[1, "target_date"], pd.Timestamp("2021-01-04"))
        self.assertEqual(labeled["regime_t_plus_1"].iloc[:3].tolist(), [1, 2, 0])
        self.assertTrue(pd.isna(labeled.iloc[-1]["regime_t_plus_1"]))
        self.assertEqual(len(labeled), 4)


class InferenceTests(unittest.TestCase):
    def test_class_columns_follow_model_classes_not_economic_order(self):
        actual = predict_regimes(bundle(), features().iloc[2:], sample="main")
        np.testing.assert_allclose(actual[["proba_0", "proba_1", "proba_2"]], [[.7, .2, .1]] * 2)
        self.assertEqual(actual["regime_pred"].tolist(), [0, 0])

    def test_daily_inference_does_not_need_future_target(self):
        frame = build_next_regime_target(features()).tail(1)
        self.assertTrue(frame["regime_t_plus_1"].isna().all())
        self.assertEqual(len(predict_regimes(bundle(), frame, sample="main")), 1)

    def test_sample_cutoff_feature_metadata_and_artifact_id_are_enforced(self):
        for model, data, sample in [
            (bundle(), features(), "main"),
            (bundle(), features().tail(1), "robust"),
            (bundle(artifact_id=""), features().tail(1), "main"),
            (bundle(feature_columns=tuple(reversed(FEATURE_COLUMNS))), features().tail(1), "main"),
        ]:
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                predict_regimes(model, data, sample=sample)

    def test_wrong_classifier_feature_order_and_class_ids_fail(self):
        for field, value in [("feature_names_in_", list(reversed(FEATURE_COLUMNS))),
                             ("n_features_in_", 3), ("classes_", [0, 0, 2]),
                             ("classes_", [0, 1, 3])]:
            fake = FakeClassifier()
            setattr(fake, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                predict_regimes(bundle(classifier=fake), features().tail(1), sample="main")

    def test_invalid_probability_values_sums_or_class_prediction_fail(self):
        frame = frozen("main", "predictions").head(3)
        for kind in ["negative", "sum", "nan", "mismatch", "fractional_class"]:
            changed = frame.copy()
            if kind == "negative":
                changed.loc[0, "proba_0"] = -.1
            elif kind == "sum":
                changed[["proba_0", "proba_1", "proba_2"]] = .1
            elif kind == "nan":
                changed.loc[0, "proba_1"] = np.nan
            elif kind == "mismatch":
                changed.loc[0, "regime_pred"] = int(np.argmin(changed.loc[0, ["proba_0", "proba_1", "proba_2"]]))
            else:
                changed["regime_pred"] = .5
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_predictions(changed)

    def test_native_model_metadata_hash_is_checked_before_optional_import(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "test.json"
            model.write_text("{}")
            metadata = Path(directory) / "metadata.json"
            metadata.write_text(json.dumps({
                "sample": "main", "trained_through": "2020-12-31",
                "feature_columns": list(FEATURE_COLUMNS), "sha256": "incorrect",
                "classes": [0, 1, 2], "xgboost_version": "unknown",
            }))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_xgboost_model(model, metadata, sample="main")

    def test_recovered_configuration_is_explicit_not_invented_defaults(self):
        self.assertEqual(XGBOOST_PARAMETERS["n_estimators"], 300)
        self.assertEqual(XGBOOST_PARAMETERS["objective"], "multi:softprob")
        self.assertNotIn("tree_method", XGBOOST_PARAMETERS)


class StrategyTests(unittest.TestCase):
    def test_full_historical_replay_costs_turnover_metrics_and_common_dates(self):
        report = verify_reference()
        self.assertFalse(report["model_recovered"])
        for sample, count in [("main", 1375), ("robust", 1632)]:
            row = report["samples"][sample]
            self.assertEqual(row["backtest_rows"], count)
            self.assertEqual(row["excluded_dates"]["regime_only_dates"], ["2026-05-22"])
            self.assertLess(row["max_daily_error"], 1e-12)
            self.assertLess(row["max_cost_metrics_error"], 1e-12)

    def test_original_next_session_labels_match_stored_regime_sequence(self):
        for sample in ["main", "robust"]:
            predictions = frozen(sample, "predictions")
            reference = frozen(sample, "regime_backtest")
            labels = reference.set_index("date")["regime"]
            # Original OOS backtest begins one session after predictions.
            self.assertEqual(predictions["regime_t_plus_1"].tolist(), labels.tolist())

    def test_hard_and_probability_exposure_use_cvar_mapping_from_1a(self):
        reference = json.loads((Path(__file__).parent / "fixtures" / "tfm_cvar_reference.json").read_text())
        for sample in ["main", "robust"]:
            summary = pd.DataFrame(reference["tables"][sample + "_summary"])
            for col in ["regime", "risk_order", "mean_cvar_95_60d"]:
                summary[col] = pd.to_numeric(summary[col])
            mapping = build_cvar_exposure_mapping(summary)
            results, _, _ = run_ml_backtest(frozen(sample, "predictions"), mapping, sample)
            expected = frozen(sample, "ml_backtest")
            for column in ["target_exposure_ml_hard", "target_exposure_ml_proba",
                           "strategy_exposure_ml_hard", "strategy_exposure_ml_proba"]:
                np.testing.assert_allclose(results[column], expected[column], atol=1e-12, rtol=1e-10)

    def test_future_labels_never_determine_positions(self):
        original = frozen("main", "predictions").head(20)
        changed = original.copy()
        changed["regime_t_plus_1"] = (changed["regime_t_plus_1"] + 1) % 3
        changed["regime"] = 0
        a, _, _ = run_ml_backtest(original, frozen("main", "mapping"), "main")
        b, _, _ = run_ml_backtest(changed, frozen("main", "mapping"), "main")
        for column in ["strategy_exposure_ml_hard", "strategy_exposure_ml_proba", "ml_hard_return", "ml_proba_return"]:
            pd.testing.assert_series_equal(a[column], b[column])

    def test_signal_is_shifted_once_and_later_returns_do_not_change_past(self):
        original = frozen("main", "predictions").head(20)
        a, _, _ = run_ml_backtest(original, frozen("main", "mapping"), "main")
        for key in ["hard", "proba"]:
            np.testing.assert_allclose(a[f"strategy_exposure_ml_{key}"].iloc[1:],
                                       a[f"target_exposure_ml_{key}"].iloc[:-1])
        changed = original.copy()
        changed.loc[15:, "ret_1d"] = .5
        b, _, _ = run_ml_backtest(changed, frozen("main", "mapping"), "main")
        pd.testing.assert_frame_equal(a.iloc[:14], b.iloc[:14])

    def test_costs_and_effective_turnover_threshold_do_not_skip_small_trades(self):
        frame = pd.DataFrame({"exposure": [.5, .505, .5], "ret": [0., 0., 0.]})
        actual = add_transaction_costs(frame, exposure_column="exposure", return_column="ret")
        np.testing.assert_allclose(actual["transaction_cost"], [0., .000005, .000005])
        self.assertEqual(actual["transaction_cost"].iloc[0], 0.)
        with self.assertRaises(ValueError):
            add_transaction_costs(frame, exposure_column="exposure", return_column="ret", cost_rate=-.1)

    def test_partition_order_and_missing_mapping_fail(self):
        predictions = frozen("main", "predictions").head(10)
        with self.assertRaises(ValueError):
            run_ml_backtest(predictions.iloc[::-1], frozen("main", "mapping"), "main")
        changed = predictions.copy()
        changed["sample_split_main"] = "train"
        with self.assertRaises(ValueError):
            run_ml_backtest(changed, frozen("main", "mapping"), "main")
        with self.assertRaises(ValueError):
            run_ml_backtest(predictions, frozen("main", "mapping").head(2), "main")

    def test_common_dates_reject_different_market_returns(self):
        ml, _, _ = run_ml_backtest(frozen("main", "predictions"), frozen("main", "mapping"), "main")
        reference = frozen("main", "regime_backtest")
        reference.loc[0, "ret_1d"] += .1
        with self.assertRaises(ValueError):
            compare_on_common_dates(ml, reference, "main")

    def test_loader_reads_frozen_predictions_without_generating_outputs(self):
        path = FIXTURE_ROOT / MANIFEST["sources"]["main_predictions"]["fixture"]
        loaded = load_ml_predictions("main", path=path)
        self.assertEqual(len(loaded), 1376)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FileNotFoundError):
            load_ml_predictions("main", path=Path(directory) / "absent.csv")

    def test_internal_strategy_adapters_do_not_change_public_api(self):
        expected = app.openapi()
        predictions = frozen("main", "predictions").head(20)
        mapping = frozen("main", "mapping")
        with patch("src.riskbex.backtesting.strategy_service.load_ml_predictions", return_value=predictions), \
             patch("src.riskbex.backtesting.strategy_service.load_regime_exposure_mapping", return_value=mapping):
            for strategy in ["buy_hold", "ml_hard", "ml_proba"]:
                results, metrics, turnover = get_strategy_backtest("main", strategy)
                self.assertEqual(set(results["strategy"]), {strategy})
                self.assertFalse(metrics.empty)
                self.assertNotIn("p_regime_0", results)
                self.assertEqual(len(turnover), 0 if strategy == "buy_hold" else 1)
        with patch("src.riskbex.backtesting.strategy_service.run_regime_backtest",
                   return_value=(pd.DataFrame({"existing": [1]}), pd.DataFrame({"existing": [2]}))):
            results, _, _ = get_strategy_backtest("main")
            self.assertEqual(results["existing"].tolist(), [1])
        self.assertEqual(app.openapi(), expected)

    def test_legacy_or_modified_exposure_mapping_is_rejected(self):
        mapping = frozen("main", "mapping")
        predictions = frozen("main", "predictions").head(10)
        with self.assertRaisesRegex(ValueError, "Sprint 1A"):
            run_ml_backtest(predictions, mapping.iloc[:, :4], "main")
        changed = mapping.copy()
        changed.loc[1, "target_exposure"] = .75
        with self.assertRaisesRegex(ValueError, "disagree"):
            run_ml_backtest(predictions, changed, "main")

    def test_frozen_fixture_hash_protects_original_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = MANIFEST["sources"]["main_predictions"]
            raw = gzip.decompress((FIXTURE_ROOT / source["fixture"]).read_bytes())
            (root / source["fixture"]).write_bytes(gzip.compress(raw + b"\n", mtime=0))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                read_frozen_table("main_predictions", MANIFEST, root)


if __name__ == "__main__":
    unittest.main()
