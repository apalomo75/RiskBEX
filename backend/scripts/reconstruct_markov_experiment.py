"""Controlled train-only reconstruction; never invoked by the daily pipeline."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.api as sm

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.train_xgboost_experiment import write_frame, write_json
from src.riskbex.backtesting.exposures import build_cvar_exposure_mapping
from src.riskbex.ml.config import SAMPLES
from src.riskbex.ml.data import dated_frame, numeric_values
from src.riskbex.ml.training import prepare_experiment_inputs, read_verified, sha256
from src.riskbex.regimes.markov_switching import fit_markov_regression
from src.riskbex.regimes.persistence import (
    SPECIFICATION, FrozenMarkovModel, filter_frozen_markov, load_frozen_markov, parameter_diagnostics,
)


PROTOCOL = {
    "recipes": [
        {"name": "notebook_100", "maxiter": 100},
        {"name": "convergence_500", "maxiter": 500},
    ],
    "fit": {"method": "bfgs", "em_iter": 5, "search_reps": 0, "disp": False},
    "specification": SPECIFICATION, "initialization": "steady-state",
    "historical_probability_atol": 1e-6,
    "mapping_atol": 1e-12, "mapping_rtol": 1e-10,
    "technical_gates": ["converged", "valid_parameters", "zero_train_regime_mismatches",
                         "zero_full_regime_mismatches", "same_economic_ids", "same_train_cvar_mapping"],
    "selection": "First predeclared recipe passing all technical gates; probability equivalence reported separately.",
    "oos_use": "Validation only; never an optimizer input or return-based selection criterion.",
    "pair_release": "Both MAIN and ROBUST must pass. Partial successes remain offline candidates.",
}


def economic_summary(frame, regimes):
    data = frame.assign(candidate_regime=np.asarray(regimes))
    result = data.groupby("candidate_regime").agg(
        mean_ewma_vol=("ewma_vol", "mean"), mean_cvar_95_60d=("cvar_95_60d", "mean"),
        n_obs=("ret_1d", "size"),
    ).reset_index().rename(columns={"candidate_regime": "regime"})
    result = result.sort_values(["mean_ewma_vol", "mean_cvar_95_60d", "regime"]).reset_index(drop=True)
    if len(result) != 3:
        raise ValueError("All three regimes must occur in the training sample.")
    result["economic_label"] = ["low_risk", "medium_risk", "high_risk"]
    result["risk_order"] = [1, 2, 3]
    return result


def empirical_transitions(regimes):
    series = pd.Series(np.asarray(regimes))
    counts = pd.crosstab(series.shift(1), series).reindex(index=range(3), columns=range(3), fill_value=0)
    return counts.div(counts.sum(axis=1), axis=0).to_numpy()


def compare_reference(frame, predicted, mapping, sample):
    cutoff = pd.Timestamp(SAMPLES[sample]["test_start"])
    train_mask = frame["date"] < cutoff
    probabilities = predicted[[f"p_regime_{k}" for k in range(3)]].to_numpy()
    reference = frame[[f"p_regime_{k}" for k in range(3)]].to_numpy()
    regimes = predicted["regime"].to_numpy()
    truth = frame["regime"].to_numpy()
    train = frame.loc[train_mask]
    summary = economic_summary(train, regimes[train_mask])
    derived_mapping = build_cvar_exposure_mapping(summary)
    expected = mapping.sort_values("risk_order").reset_index(drop=True)
    same_ids = summary["regime"].tolist() == expected["regime"].tolist()
    expected_by_id = expected.set_index("regime")
    actual_by_id = derived_mapping.set_index("regime").reindex(expected["regime"])
    cvar_errors = actual_by_id["mean_cvar_95_60d"].to_numpy() - expected_by_id.loc[expected["regime"], "mean_cvar_95_60d"].to_numpy()
    exposure_errors = actual_by_id["target_exposure"].to_numpy() - expected["target_exposure"].to_numpy()
    same_mapping = bool(np.allclose(actual_by_id["target_exposure"], expected["target_exposure"],
                                    atol=PROTOCOL["mapping_atol"], rtol=PROTOCOL["mapping_rtol"]))
    candidate_transitions = empirical_transitions(regimes[train_mask])
    reference_transitions = empirical_transitions(truth[train_mask])
    report = {
        "full_rows": len(frame), "train_rows": len(train), "oos_rows": int((~train_mask).sum()),
        "max_probability_error": float(np.abs(probabilities - reference).max()),
        "native_probability_min": float(probabilities.min()),
        "native_probability_max": float(probabilities.max()),
        "max_probability_sum_error": float(np.abs(probabilities.sum(axis=1) - 1.).max()),
        "train_max_probability_error": float(np.abs(probabilities[train_mask] - reference[train_mask]).max()),
        "oos_max_probability_error": float(np.abs(probabilities[~train_mask] - reference[~train_mask]).max()),
        "mean_probability_error": float(np.abs(probabilities - reference).mean()),
        "full_regime_mismatches": int((regimes != truth).sum()),
        "train_regime_mismatches": int((regimes[train_mask] != truth[train_mask]).sum()),
        "oos_regime_mismatches": int((regimes[~train_mask] != truth[~train_mask]).sum()),
        "same_economic_ids": same_ids, "same_train_cvar_mapping": same_mapping,
        "train_cvar_errors_by_risk_order": cvar_errors.tolist(),
        "exposure_errors_by_risk_order": exposure_errors.tolist(),
        "academic_mapping": expected.to_dict(orient="records"),
        "candidate_mapping": derived_mapping.to_dict(orient="records"),
        "candidate_summary": summary.to_dict(orient="records"),
        "empirical_transitions_candidate": candidate_transitions.tolist(),
        "empirical_transitions_academic": reference_transitions.tolist(),
        "max_empirical_transition_error": float(np.abs(candidate_transitions - reference_transitions).max()),
        "historical_probability_equivalence": bool(np.abs(probabilities - reference).max() <= PROTOCOL["historical_probability_atol"]),
    }
    differences = frame[["date", "regime", "p_regime_0", "p_regime_1", "p_regime_2"]].merge(
        predicted[["date", "regime", "p_regime_0", "p_regime_1", "p_regime_2"]],
        on="date", suffixes=("_academic", "_candidate"), validate="one_to_one",
    )
    differences["regime_changed"] = differences["regime_academic"] != differences["regime_candidate"]
    return report, differences


def recovery_evidence(repository):
    oid = "a040cd6d3020a861c99bdc3aee0febe5be4b6ce7"
    raw = subprocess.check_output(["git", "-C", str(repository), "cat-file", "blob", oid])
    notebook = json.loads(raw)
    outputs = ["".join(item.get("text", [])) for item in notebook["cells"][15].get("outputs", [])]
    text = next(item for item in outputs if "MODELO 2" in item and "Regime 2 parameters" in item)
    return {
        "status": "partial_rounded_main_only_not_original_full_precision_parameters",
        "source_git_blob": oid, "source_path": "notebooks/03_market_regime_identification.ipynb",
        "source_cell": 15, "source_sha256": sha256(raw), "main_summary_output": text,
        "rounded_main_parameters": [.9806, 1.233e-6, .0167, 1.202e-7, .9661, .0099,
                                     .0009, -.0016, -.0005, 5.453e-5, .0008, .0002],
        "full_precision_vectors_recovered": False, "robust_parameters_recovered": False,
        "original_statsmodels_version": "not_accredited",
        "initialization_evidence": "No initialization override in original code; recorded runtime default is steady-state.",
        "search_scope": "Both local trees and all reachable Git notebook blobs/model filenames; 42 TFM notebook blobs, no serialized models in Git.",
        "original_notebook_metrics": {
            "main": {"aic": -31314.733881085183, "bic": -31235.887348682223,
                     "log_likelihood_from_aic_12_parameters": 15669.366940542591},
            "robust": {"aic": -29974.47603749897, "bic": -29896.22898840516,
                       "log_likelihood_from_aic_12_parameters": 14999.238018749485},
        },
    }


def run(repository, output_dir):
    fixture = BACKEND / "tests/fixtures/tfm_ml"
    inputs, input_provenance = prepare_experiment_inputs(repository, fixture)
    cvar = json.loads((fixture.parent / "tfm_cvar_reference.json").read_text())
    frames, xgb_metadata = {}, {}
    for sample in ["main", "robust"]:
        source = cvar["sources"][sample + "_regimes"]
        frames[sample] = dated_frame(pd.read_csv(repository / source["path"]))
        read_verified(repository / source["path"], source["sha256"])
        numeric_values(frames[sample], ["ret_1d", "ewma_vol", "cvar_95_60d", "p_regime_0", "p_regime_1", "p_regime_2"])
        xgb_path = BACKEND / "experiments/sprint-1c-causal-v1" / sample / "metadata.json"
        xgb_raw = xgb_path.read_bytes()
        xgb = json.loads(xgb_raw)
        if xgb["source_provenance"]["regimes_sha256"] != source["sha256"]:
            raise ValueError("Markov reference differs from the labels used by causal-v1.")
        xgb_metadata[sample] = {"metadata": xgb, "sha256": sha256(xgb_raw)}
    output = output_dir.resolve()
    if (BACKEND / "experiments").resolve() not in output.parents:
        raise ValueError("Use a new directory under backend/experiments.")
    if output.exists():
        raise FileExistsError("Refusing to overwrite or rerun a Markov experiment.")
    evidence = recovery_evidence(repository)
    versions = {"python": platform.python_version(), "statsmodels": statsmodels.__version__,
                "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__}
    output.mkdir(parents=True)
    write_json(output / "protocol.json", PROTOCOL)
    write_json(output / "recovery.json", evidence)
    write_json(output / "versions.json", versions)
    write_json(output / "source_provenance.json", input_provenance)
    write_json(output / "status.json", {"status": "reconstruction_in_progress"})
    # Test the actually recovered rounded MAIN vector before any fit.
    main = frames["main"]
    rounded_model = sm.tsa.MarkovRegression(main["ret_1d"], **SPECIFICATION)
    rounded = np.asarray(rounded_model.filter(evidence["rounded_main_parameters"], cov_type="none").filtered_marginal_probabilities)
    write_json(output / "rounded_recovery_filter.json", {
        "fitted": False, "max_probability_error": float(np.abs(rounded - main[[f"p_regime_{k}" for k in range(3)]].to_numpy()).max()),
        "regime_mismatches": int((rounded.argmax(axis=1) != main["regime"]).sum()),
    })
    summary = {"status": "pending", "versions": versions, "samples": {}, "pair_compatible": False}
    try:
        for sample in ["main", "robust"]:
            sample_dir = output / sample
            sample_dir.mkdir()
            frame = frames[sample]
            train = frame[frame[SAMPLES[sample]["split_column"]] == "train"].reset_index(drop=True)
            expected_rows = 5274 if sample == "main" else 5017
            if len(train) != expected_rows:
                raise ValueError("Unexpected Markov training count; do not apply the XGBoost boundary purge here.")
            mapping = inputs[sample]["mapping"]
            write_frame(sample_dir / "train_input.csv.gz", train[["date", "ret_1d"]])
            write_frame(sample_dir / "filter_input.csv.gz", frame[["date", "ret_1d"]])
            results = []
            for recipe in PROTOCOL["recipes"]:
                folder = sample_dir / recipe["name"]
                folder.mkdir()
                print(f"Fitting {sample}/{recipe['name']} on {len(train)} train rows only", file=sys.stderr, flush=True)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    fitted = fit_markov_regression(train["ret_1d"], 3, maxiter=recipe["maxiter"])
                diagnostics = parameter_diagnostics(fitted.model, fitted.params)
                # Preserve the fitted checkpoint even if a subsequent validation fails.
                write_json(folder / "parameters.json", {"parameter_names": fitted.model.param_names,
                                                          "parameters": list(fitted.params),
                                                          "default_start_parameters": list(fitted.model.start_params)})
                classes = tuple(mapping[["regime", "economic_label", "risk_order"]].to_dict(orient="records"))
                bundle = FrozenMarkovModel(
                    sample, tuple(fitted.params), tuple(fitted.model.param_names),
                    tuple(diagnostics["initial_probabilities"]), frame["date"].min().date().isoformat(),
                    train["date"].max().date().isoformat(), classes, "offline-diagnostic",
                )
                filtered = filter_frozen_markov(bundle, frame[["date", "ret_1d"]], sample=sample)
                comparison, differences = compare_reference(frame, filtered, mapping, sample)
                converged = bool(fitted.mle_retvals.get("converged", False))
                passed = bool(converged and comparison["train_regime_mismatches"] == 0
                              and comparison["full_regime_mismatches"] == 0
                              and comparison["same_economic_ids"] and comparison["same_train_cvar_mapping"])
                comparison.update({
                    "recipe": recipe, "converged": converged, "log_likelihood": float(fitted.llf),
                    "aic": float(fitted.aic), "bic": float(fitted.bic),
                    "optimizer_result": {key: value.tolist() if isinstance(value, np.ndarray) else value
                                         for key, value in fitted.mle_retvals.items()},
                    "warnings": [{"category": type(item.message).__name__, "message": str(item.message)} for item in caught],
                    "parameter_diagnostics": diagnostics, "technical_validation": "passed" if passed else "failed",
                    "transition_comparison_note": "Academic tables are empirical argmax transitions; model parameter transitions are reported separately, not equated.",
                    "academic_log_likelihood": evidence["original_notebook_metrics"][sample]["log_likelihood_from_aic_12_parameters"],
                    "academic_log_likelihood_delta": float(fitted.llf) - evidence["original_notebook_metrics"][sample]["log_likelihood_from_aic_12_parameters"],
                })
                write_json(folder / "parameters.json", {"parameter_names": fitted.model.param_names,
                                                          "parameters": list(fitted.params),
                                                          "default_start_parameters": list(fitted.model.start_params)})
                write_json(folder / "validation.json", comparison)
                write_frame(folder / "probabilities.csv.gz", filtered)
                write_frame(folder / "comparison_by_date.csv.gz", differences)
                write_json(folder / "cvar_mapping.json", mapping.to_dict(orient="records"))
                metadata = {
                    "sample": sample, "technical_validation": "passed" if passed else "failed",
                    "historical_probability_equivalence": comparison["historical_probability_equivalence"],
                    "deployment_activated": False, "specification": SPECIFICATION,
                    "initialization": "steady-state", "initial_probabilities": diagnostics["initial_probabilities"],
                    "statsmodels_version": statsmodels.__version__, "versions": versions,
                    "history_start": bundle.history_start, "trained_through": bundle.trained_through,
                    "economic_classes": list(classes), "parameters_file": "parameters.json",
                    "parameters_sha256": sha256((folder / "parameters.json").read_bytes()),
                    "cvar_mapping_file": "cvar_mapping.json", "cvar_mapping_sha256": sha256((folder / "cvar_mapping.json").read_bytes()),
                    "validation_sha256": sha256((folder / "validation.json").read_bytes()),
                    "academic_regimes_sha256": cvar["sources"][sample + "_regimes"]["sha256"],
                    "compatible_xgboost_metadata_sha256": xgb_metadata[sample]["sha256"],
                    "fit_recipe": {**PROTOCOL["fit"], **recipe},
                }
                write_json(folder / "metadata.json", metadata)
                if passed:
                    loaded = load_frozen_markov(folder / "metadata.json", sample=sample)
                    restored = filter_frozen_markov(loaded, frame[["date", "ret_1d"]], sample=sample)
                    pd.testing.assert_frame_equal(filtered, restored, check_exact=True)
                results.append({key: comparison[key] for key in ["recipe", "converged", "log_likelihood", "max_probability_error",
                    "train_regime_mismatches", "full_regime_mismatches", "same_economic_ids", "same_train_cvar_mapping",
                    "historical_probability_equivalence", "technical_validation"]})
                print(json.dumps(results[-1]), file=sys.stderr, flush=True)
            selected = next((row["recipe"]["name"] for row in results if row["technical_validation"] == "passed"), None)
            summary["samples"][sample] = {"candidates": results, "selected_technical_candidate": selected}
        summary["pair_compatible"] = all(item["selected_technical_candidate"] for item in summary["samples"].values())
        summary["status"] = "technical_pair_validated_not_activated" if summary["pair_compatible"] else "blocked_stop_for_review"
        write_json(output / "summary.json", summary)
        write_json(output / "status.json", {"status": summary["status"], "pair_compatible": bool(summary["pair_compatible"])})
    except Exception as error:
        write_json(output / "status.json", {"status": "failed_stop_for_review", "error": str(error)})
        raise
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tfm-root", type=Path, default=BACKEND.parent.parent / "TMF-Market-Regimes-Risk-Portfolio")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reconstruct", action="store_true", required=True,
                        help="Explicitly authorize this train-only experiment; never used by daily jobs.")
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.tfm_root, arguments.output_dir), indent=2))
