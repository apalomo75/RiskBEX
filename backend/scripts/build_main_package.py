"""Create a new standalone MAIN package by byte-copying approved artifacts. No fitting."""

import argparse
from io import BytesIO
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from src.riskbex.engine.package import canonical_price_hash, file_hash, verify_main_package
from src.riskbex.ml.config import FEATURE_COLUMNS
from src.riskbex.ml.training import git_bytes, sha256
from src.riskbex.regimes.persistence import verify_xgboost_correspondence


def build_main_package(output, repository):
    markov = BACKEND / "experiments/sprint-1d-markov-v2/main/convergence_500"
    xgb = BACKEND / "experiments/sprint-1c-causal-v1/main"
    verify_xgboost_correspondence(markov / "metadata.json", xgb / "metadata.json")
    mm = json.loads((markov / "metadata.json").read_text())
    xm = json.loads((xgb / "metadata.json").read_text())
    validation = json.loads((markov / "validation.json").read_text())
    if not validation["converged"] or validation["train_regime_mismatches"] or validation["full_regime_mismatches"]:
        raise ValueError("Selected MAIN Markov did not pass compatibility.")
    raw = git_bytes(repository, "data/raw/ibex_prices.csv")
    prices = pd.read_csv(BytesIO(raw), float_precision="round_trip")
    first = prices.iloc[0]
    if first["date"] != "2000-01-04":
        raise ValueError("Unexpected original return initialization.")
    previous_close = float(first["ibex_close"] / np.exp(first["ret_1d"]))
    anchor = pd.DataFrame({"date": ["2000-01-03"], "ibex_close": [previous_close]})
    complete = pd.concat([anchor, prices[["date", "ibex_close"]]], ignore_index=True)
    complete["date"] = pd.to_datetime(complete["date"])
    train = complete[complete["date"] <= mm["trained_through"]]
    output = Path(output).resolve()
    if (BACKEND / "model_packages").resolve() not in output.parents:
        raise ValueError("Create the package under backend/model_packages.")
    if output.exists():
        raise FileExistsError("Model packages are immutable; choose a new explicit version.")
    selected = {
        **{f"markov/{name}": markov / name for name in ["metadata.json", "parameters.json", "validation.json", "cvar_mapping.json"]},
        **{f"xgboost/{name}": xgb / name for name in ["metadata.json", "model.ubj", "validation.json"]},
    }
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    for relative, source in selected.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        files[relative] = {"sha256": file_hash(destination), "source_path": str(source.relative_to(BACKEND))}
    versions = {key: mm["versions"][key] for key in ["python", "statsmodels", "numpy", "pandas", "scipy"]}
    versions.update({"scikit-learn": xm["versions"]["scikit_learn"], "xgboost": xm["xgboost_version"]})
    manifest = {
        "schema_version": 1, "package_id": "riskbex-main-v1", "sample": "main",
        "scope": "offline_main_engine_not_daily_activated", "robust_role": "academic_reference_only_not_packaged",
        "product_decision": "Sprint 2: convergent MAIN 500 + MAIN causal-v1 + original train CVaR mapping",
        "components": {"markov_metadata": "markov/metadata.json", "xgboost_metadata": "xgboost/metadata.json",
                       "xgboost_model": "xgboost/model.ubj", "cvar_mapping": "markov/cvar_mapping.json"},
        "files": files, "feature_columns": FEATURE_COLUMNS, "economic_classes": mm["economic_classes"],
        "required_versions": versions, "regime_definition_sha256": mm["academic_regimes_sha256"],
        "training": {"information_cutoff": mm["trained_through"],
                     "markov_first_date": "2000-03-28", "markov_last_date": mm["trained_through"],
                     "markov_rows": 5274, "xgboost_last_feature_date": xm["last_feature_date"],
                     "xgboost_last_target_date": xm["trained_through"], "xgboost_rows": xm["training_input"]["rows"],
                     "xgboost_boundary_policy": xm["boundary_policy"]},
        "feature_policy": {"rolling_windows": [20, 60], "ewma_lambda": .94, "tail_probability": .05,
                           "sample_std_ddof": 1, "filter_history_start": mm["history_start"],
                           "drop_initial_undefined_return_before_indicators": True,
                           "drop_only_initial_warmup": True, "reject_later_missing_features": True},
        "price_initialization": {"previous_session": "2000-01-03", "previous_close": previous_close,
                                 "first_return_session": "2000-01-04", "first_stored_return": float(first["ret_1d"]),
                                 "derivation": "previous_close = first_close / exp(first_stored_log_return)",
                                 "source_git_commit": "8dd66a93c06dc3cbfaac29f086ad2625d32d9756",
                                 "source_raw_prices_sha256": sha256(raw),
                                 "previous_session_date_evidence": "notebook 01 stored output cells 14 and 20"},
        "training_price_prefix": {"rows": len(train), "sha256": canonical_price_hash(train),
                                  "canonicalization": "date ISO + float.hex(close), one record per line, includes initialization"},
        "compatibility": {"train_regime_mismatches": 0, "full_regime_mismatches": 0,
                          "same_train_cvar_mapping": True, "academic_probability_equivalence": False,
                          "markov_max_academic_probability_error": validation["max_probability_error"],
                          "xgboost_version": "causal-v1", "selection_by_oos_returns": False},
        "signal_policy": {"information": "close_t", "markov_state_horizon": "current_session",
                          "xgboost_prediction_horizon": "next_market_session", "exposure_horizon": "next_market_session",
                          "signal_shift_applied": False, "calendar_target_date_inferred": False},
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "manifest.sha256").write_text(file_hash(manifest_path) + "\n")
    verify_main_package(output)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tfm-root", type=Path, default=BACKEND.parent.parent / "TMF-Market-Regimes-Risk-Portfolio")
    args = parser.parse_args()
    print(json.dumps(build_main_package(args.output_dir, args.tfm_root), indent=2))
