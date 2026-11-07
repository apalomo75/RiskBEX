"""Explicit, offline MAIN/ROBUST experiment. Never called by the daily pipeline."""

import argparse
import gzip
import json
from pathlib import Path
import platform
import sys
import warnings

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.backtesting.ml_backtest import compare_on_common_dates, run_ml_backtest
from src.riskbex.ml.config import FEATURE_COLUMNS, SAMPLES, XGBOOST_PARAMETERS
from src.riskbex.ml.data import prepare_features
from src.riskbex.ml.evaluation import classification_metrics
from src.riskbex.ml.inference import TrainedRegimeModel, load_xgboost_model, predict_regimes
from src.riskbex.ml.training import prepare_experiment_inputs, sha256


def json_value(value):
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def write_json(path, value):
    path.write_text(json.dumps(json_value(value), indent=2, allow_nan=False) + "\n")


def write_frame(path, frame):
    raw = frame.to_csv(index=False, float_format="%.17g", date_format="%Y-%m-%d").encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    return {"sha256_csv": sha256(raw), "sha256_gzip": sha256(path.read_bytes()), "rows": len(frame)}


def compare_predictions(sample, data, predictions, fixture_root):
    from scripts.check_ml_equivalence import read_frozen_table

    original = data["historical_predictions"]
    mapping = data["mapping"]
    stress = int(mapping.loc[mapping["economic_label"] == "high_risk", "regime"].iloc[0])
    previous, old_metrics, old_turnover = run_ml_backtest(original, mapping, sample)
    current, new_metrics, new_turnover = run_ml_backtest(predictions, mapping, sample)
    if not current["date"].equals(previous["date"]):
        raise ValueError("New and academic strategy dates differ.")
    daily = original[["date", "regime_t_plus_1", "regime_pred", "proba_0", "proba_1", "proba_2"]].merge(
        predictions[["date", "regime_pred", "proba_0", "proba_1", "proba_2"]],
        on="date", validate="one_to_one", suffixes=("_tfm", "_new"),
    )
    daily["classification_changed"] = daily["regime_pred_tfm"] != daily["regime_pred_new"]
    probability_errors = {}
    for regime in range(3):
        delta = daily[f"proba_{regime}_new"] - daily[f"proba_{regime}_tfm"]
        daily[f"proba_{regime}_delta"] = delta
        probability_errors[str(regime)] = {
            "max_abs": float(delta.abs().max()), "mean_abs": float(delta.abs().mean()),
            "rmse": float(np.sqrt((delta ** 2).mean())),
        }
    exposures = previous[["date", "strategy_exposure_ml_hard", "strategy_exposure_ml_proba"]].merge(
        current[["date", "strategy_exposure_ml_hard", "strategy_exposure_ml_proba"]],
        on="date", validate="one_to_one", suffixes=("_tfm", "_new"),
    )
    exposure_errors = {}
    for strategy in ["hard", "proba"]:
        column = f"strategy_exposure_ml_{strategy}"
        delta = exposures[column + "_new"] - exposures[column + "_tfm"]
        exposures[column + "_delta"] = delta
        exposure_errors[strategy] = {"max_abs": float(delta.abs().max()), "mean_abs": float(delta.abs().mean()),
                                     "changed_sessions": int((delta.abs() > 1e-12).sum())}
    daily = daily.merge(exposures, on="date", how="left", validate="one_to_one")
    metric_differences = []
    for _, row in old_metrics.iterrows():
        new = new_metrics.loc[new_metrics["strategy"] == row["strategy"]].iloc[0]
        for column in ["total_return", "daily_volatility", "VaR_95", "CVaR_95", "max_drawdown", "sharpe_ratio", "total_transaction_cost"]:
            metric_differences.append({"strategy": row["strategy"], "metric": column,
                                       "tfm": row[column], "new": new[column], "delta": new[column] - row[column]})
    manifest = json.loads((fixture_root / "manifest.json").read_text())
    regime_reference = read_frozen_table(sample + "_regime_backtest", manifest, fixture_root)
    old_common, exclusions = compare_on_common_dates(previous, regime_reference, sample)
    new_common, _ = compare_on_common_dates(current, regime_reference, sample)
    report = {
        "classification_tfm": classification_metrics(original, stress_regime=stress),
        "classification_new": classification_metrics(predictions, stress_regime=stress),
        "classification_changes": int(daily["classification_changed"].sum()),
        "classification_change_share": float(daily["classification_changed"].mean()),
        "probability_differences": probability_errors, "exposure_differences": exposure_errors,
        "metric_differences": metric_differences,
        "common_gross_metrics_tfm": old_common.to_dict(orient="records"),
        "common_gross_metrics_new": new_common.to_dict(orient="records"),
        "common_date_exclusions": exclusions,
        "turnover_tfm": old_turnover.to_dict(orient="records"),
        "turnover_new": new_turnover.to_dict(orient="records"),
        "attribution_limit": "Joint effect of approved purge, runtime/defaults and recovered inputs; no unpurged control was trained.",
    }
    return report, daily, current, new_metrics


def run_experiment(repository, fixture_root, output_dir, *, train=False):
    # Every sample must pass before the first fit. OOS is never passed to fit.
    data, provenance = prepare_experiment_inputs(repository, fixture_root)
    if not train:
        return {"status": "preflight_passed_no_training", "provenance": provenance}
    if output_dir is None:
        raise ValueError("An explicit, new experiment directory is required.")
    output = Path(output_dir).resolve()
    allowed = (PROJECT_ROOT / "experiments").resolve()
    if allowed not in output.parents:
        raise ValueError("Outputs must be a new subdirectory under backend/experiments.")
    if output.exists():
        raise FileExistsError("Experiment already exists; refusing overwrite or automatic retraining.")
    import sklearn
    import xgboost

    versions = {"python": platform.python_version(), "python_executable": sys.executable,
                "pandas": pd.__version__, "numpy": np.__version__,
                "scikit_learn": sklearn.__version__, "xgboost": xgboost.__version__}
    provenance["implementation_sha256"] = {
        str(path.relative_to(PROJECT_ROOT)): sha256(path.read_bytes())
        for path in [Path(__file__).resolve(), PROJECT_ROOT / "src/riskbex/ml/training.py",
                     PROJECT_ROOT / "src/riskbex/ml/config.py", PROJECT_ROOT / "src/riskbex/ml/data.py",
                     PROJECT_ROOT / "src/riskbex/ml/inference.py", PROJECT_ROOT / "src/riskbex/ml/evaluation.py",
                     PROJECT_ROOT / "src/riskbex/backtesting/ml_backtest.py",
                     PROJECT_ROOT / "src/riskbex/backtesting/costs.py",
                     PROJECT_ROOT / "src/riskbex/backtesting/metrics.py"]
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "preflight.json", provenance)
    write_json(output / "versions.json", versions)
    write_json(output / "runtime.json", {"platform": platform.platform(), "xgboost_build": xgboost.build_info()})
    write_json(output / "status.json", {"status": "training", "boundary_policy": "causal"})
    summary = {"status": "complete", "boundary_policy": "causal", "versions": versions, "samples": {}}
    try:
        for sample in ["main", "robust"]:
            folder = output / sample
            folder.mkdir()
            experiment = data[sample]
            train_frame, evaluation = experiment["train"], experiment["evaluation"]
            train_hashes = write_frame(folder / "training_input.csv.gz", train_frame[["date", "target_date", *FEATURE_COLUMNS, "regime_t_plus_1"]])
            evaluation_hashes = write_frame(folder / "validation_input.csv.gz", evaluation[["date", "target_date", *FEATURE_COLUMNS, "regime_t_plus_1"]])
            classifier = xgboost.XGBClassifier(**XGBOOST_PARAMETERS)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                classifier.fit(prepare_features(train_frame), train_frame["regime_t_plus_1"].astype(int))
            if caught:
                messages = [str(item.message) for item in caught]
                write_json(folder / "fit_warnings.json", messages)
                raise RuntimeError("Training emitted warnings; stop for review without changing the experiment.")
            model_path = folder / "model.ubj"
            classifier.save_model(model_path)
            write_json(folder / "parameters.json", {"explicit_tfm": XGBOOST_PARAMETERS,
                                                      "effective_wrapper": classifier.get_params()})
            write_json(folder / "booster_config.json", json.loads(classifier.get_booster().save_config()))
            cutoff = train_frame["target_date"].max().date().isoformat()
            metadata = {
                "sample": sample, "trained_through": cutoff,
                "last_feature_date": train_frame["date"].max().date().isoformat(),
                "feature_columns": FEATURE_COLUMNS, "classes": classifier.classes_.tolist(),
                "economic_classes": experiment["mapping"][["regime", "economic_label", "risk_order"]].to_dict(orient="records"),
                "sha256": sha256(model_path.read_bytes()), "xgboost_version": versions["xgboost"],
                "versions": versions, "boundary_policy": "causal", "training_input": train_hashes,
                "validation_input": evaluation_hashes, "source_provenance": provenance["samples"][sample],
                "preflight_sha256": sha256((output / "preflight.json").read_bytes()),
                "explicit_parameters": XGBOOST_PARAMETERS,
            }
            metadata_path = folder / "metadata.json"
            write_json(metadata_path, metadata)
            bundle = TrainedRegimeModel(classifier, sample, cutoff, FEATURE_COLUMNS, metadata["sha256"])
            inferred = predict_regimes(bundle, evaluation[["date", *FEATURE_COLUMNS]], sample=sample)
            predictions = evaluation[["date", SAMPLES[sample]["split_column"], "ret_1d", "regime", "regime_t_plus_1"]].merge(
                inferred, on="date", validate="one_to_one",
            )
            report, daily, backtest, metrics = compare_predictions(sample, experiment, predictions, fixture_root)
            restored = load_xgboost_model(model_path, metadata_path, sample=sample)
            restored_predictions = predict_regimes(restored, evaluation[["date", *FEATURE_COLUMNS]], sample=sample)
            pd.testing.assert_frame_equal(inferred, restored_predictions, check_exact=True)
            smoke_input = evaluation[["date", *FEATURE_COLUMNS]].tail(1)
            smoke_predictions = predict_regimes(restored, smoke_input, sample=sample)
            if len(smoke_predictions) != 1:
                raise AssertionError("Daily inference without future labels failed.")
            write_frame(folder / "inference_smoke_input.csv.gz", smoke_input)
            write_frame(folder / "inference_smoke_expected.csv.gz", smoke_predictions)
            write_frame(folder / "validation_predictions.csv.gz", predictions)
            write_frame(folder / "daily_comparison.csv.gz", daily)
            write_frame(folder / "validation_backtest.csv.gz", backtest)
            write_frame(folder / "validation_metrics.csv.gz", metrics)
            report["serialization_roundtrip_exact"] = True
            report["daily_inference_without_labels"] = True
            write_json(folder / "validation.json", report)
            metadata["validation_sha256"] = sha256((folder / "validation.json").read_bytes())
            metadata["inference_smoke_input_sha256"] = sha256((folder / "inference_smoke_input.csv.gz").read_bytes())
            metadata["inference_smoke_expected_sha256"] = sha256((folder / "inference_smoke_expected.csv.gz").read_bytes())
            write_json(metadata_path, metadata)
            summary["samples"][sample] = {
                "model_sha256": metadata["sha256"], "train_rows": len(train_frame),
                "last_feature_date": metadata["last_feature_date"], "trained_through": cutoff,
                "oos_rows": len(evaluation), "oos_end": evaluation["date"].max().date().isoformat(),
                "classification_tfm": report["classification_tfm"], "classification_new": report["classification_new"],
                "classification_changes": report["classification_changes"],
                "serialization_roundtrip_exact": True, "daily_inference_without_labels": True,
            }
            print(f"Completed {sample}: {len(train_frame)} train / {len(evaluation)} OOS", file=sys.stderr, flush=True)
        write_json(output / "summary.json", summary)
        write_json(output / "status.json", {"status": "complete", "boundary_policy": "causal"})
    except Exception as error:
        write_json(output / "status.json", {"status": "failed_stop_for_review", "error": str(error)})
        raise
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preflight-only", action="store_true")
    action.add_argument("--train", action="store_true")
    parser.add_argument("--tfm-root", type=Path, default=PROJECT_ROOT.parent.parent / "TMF-Market-Regimes-Risk-Portfolio")
    parser.add_argument("--fixture-root", type=Path, default=PROJECT_ROOT / "tests/fixtures/tfm_ml")
    parser.add_argument("--output-dir", type=Path)
    arguments = parser.parse_args()
    result = run_experiment(arguments.tfm_root, arguments.fixture_root, arguments.output_dir, train=arguments.train)
    print(json.dumps(json_value(result), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
