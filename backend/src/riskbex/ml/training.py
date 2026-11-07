"""Explicit offline experiment preparation. Importing does not train or load XGBoost."""

import ast
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from src.riskbex.ml.config import FEATURE_COLUMNS, SAMPLES, XGBOOST_PARAMETERS
from src.riskbex.ml.data import (
    assemble_features, build_next_regime_target, dated_frame, evaluation_rows,
    numeric_values, prepare_features, training_rows,
)


REFERENCE_COMMIT = "8dd66a93c06dc3cbfaac29f086ad2625d32d9756"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def read_verified(path, checksum):
    raw = Path(path).read_bytes()
    if sha256(raw) != checksum:
        raise ValueError(f"Reference changed: {path}")
    return raw


def git_bytes(repository, relative_path):
    return subprocess.check_output([
        "git", "-C", str(repository), "show", f"{REFERENCE_COMMIT}:{relative_path}",
    ])


def verify_notebook_parameters(repository):
    path = Path(repository) / "notebooks/05_xgboost_regime_classifier.ipynb"
    raw = path.read_bytes()
    notebook = json.loads(raw)
    tree = ast.parse("".join(notebook["cells"][10]["source"]))
    configurations = [
        {keyword.arg: ast.literal_eval(keyword.value) for keyword in node.keywords}
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "XGBClassifier"
    ]
    if len(configurations) != 2 or any(config != XGBOOST_PARAMETERS for config in configurations):
        raise ValueError("XGBoost parameters differ from notebook 05; stop before training.")
    # The feature construction source must still match the historical commit.
    sources = {str(path.relative_to(repository)): sha256(raw)}
    for name in ["01_data_download_and_preprocessing.ipynb", "02_feature_engineering_risk_variables.ipynb"]:
        relative = f"notebooks/{name}"
        current_raw = (Path(repository) / relative).read_bytes()
        current = json.loads(current_raw)
        historical = json.loads(git_bytes(repository, relative))
        code = lambda document: ["".join(cell["source"]) for cell in document["cells"] if cell["cell_type"] == "code"]
        if code(current) != code(historical):
            raise ValueError(f"Feature construction changed in {relative}.")
        sources[relative] = sha256(current_raw)
    return sources


def reconstruct_features(prices):
    """Notebook 02 formulas; used to verify the recovered input, not replace it."""
    output = prices[["date", "ret_1d"]].copy()
    returns = prices["ret_1d"]
    for window in [20, 60]:
        output[f"ret_{window}d"] = returns.rolling(window).sum()
        output[f"vol_{window}d"] = returns.rolling(window).std(ddof=1)
        output[f"downside_vol_{window}d"] = returns.rolling(window).apply(
            lambda values: values[values < 0].std(ddof=1), raw=False,
        )
    output["ewma_vol"] = np.sqrt(returns.pow(2).ewm(alpha=1 - .94, adjust=False).mean())
    output["cvar_95_60d"] = returns.rolling(60).apply(
        lambda values: values[values <= np.quantile(values, 1 - .95)].mean(), raw=True,
    )
    output["drawdown"] = prices["ibex_close"] / prices["ibex_close"].cummax() - 1
    output["skew_60d"] = returns.rolling(60).skew()
    return output


def prepare_experiment_inputs(repository, fixture_root):
    """Preflight gate. Raises on unexplained feature/label/source differences."""
    repository, fixture_root = Path(repository), Path(fixture_root)
    manifest_raw = (fixture_root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    cvar_raw = (fixture_root.parent / "tfm_cvar_reference.json").read_bytes()
    cvar_reference = json.loads(cvar_raw)
    source_hashes = verify_notebook_parameters(repository)
    master_source = manifest["sources"]["historical_master"]
    master_raw = gzip.decompress((fixture_root / master_source["fixture"]).read_bytes())
    if sha256(master_raw) != master_source["sha256"]:
        raise ValueError("Frozen historical master hash mismatch.")
    if master_raw != git_bytes(repository, master_source["source_path"]):
        raise ValueError("Frozen master differs from the recorded academic Git commit.")
    master = dated_frame(pd.read_csv(BytesIO(master_raw)))
    prepare_features(master)
    prices_raw = git_bytes(repository, "data/raw/ibex_prices.csv")
    prices = dated_frame(pd.read_csv(BytesIO(prices_raw)))
    numeric_values(prices, ["ibex_close", "ret_1d"])
    if not (prices["ibex_close"] > 0).all():
        raise ValueError("Raw prices must be strictly positive.")
    np.testing.assert_allclose(prices["ret_1d"].iloc[1:],
                               np.log(prices["ibex_close"] / prices["ibex_close"].shift(1)).iloc[1:],
                               atol=1e-12, rtol=1e-10)
    rebuilt = reconstruct_features(prices)
    comparison = master[["date", *FEATURE_COLUMNS]].merge(
        rebuilt, on="date", suffixes=("_saved", "_rebuilt"), validate="one_to_one",
    )
    if len(comparison) != len(master):
        raise ValueError("Raw prices do not cover every recovered feature row.")
    feature_errors = {}
    for column in FEATURE_COLUMNS:
        saved, rebuilt_values = comparison[column + "_saved"], comparison[column + "_rebuilt"]
        np.testing.assert_allclose(saved, rebuilt_values, atol=1e-12, rtol=1e-10,
                                   err_msg=f"Recovered feature differs: {column}")
        feature_errors[column] = float(np.max(np.abs(saved - rebuilt_values)))
    experiments = {}
    provenance = {
        "reference_commit": REFERENCE_COMMIT, "notebook_hashes": source_hashes,
        "frozen_master_sha256": sha256(master_raw), "git_raw_prices_sha256": sha256(prices_raw),
        "ml_fixture_manifest_sha256": sha256(manifest_raw),
        "cvar_fixture_manifest_sha256": sha256(cvar_raw),
        "feature_reconstruction_max_errors": feature_errors, "samples": {},
    }
    final_feature_date = pd.to_datetime(master["date"]).max()
    for sample, suffix, expected_count in [("main", "", 5274), ("robust", "_robust", 5017)]:
        source = cvar_reference["sources"][sample + "_regimes"]
        regime_raw = read_verified(repository / source["path"], source["sha256"])
        regimes = pd.read_csv(BytesIO(regime_raw))
        labeled_full = build_next_regime_target(regimes)
        cutoff = pd.Timestamp(SAMPLES[sample]["test_start"])
        train_labels = labeled_full.loc[labeled_full["date"] < cutoff]
        relative = f"data/processed/dataset_cap4_regimes_train{suffix}.csv"
        train_raw = (repository / relative).read_bytes()
        saved_train = pd.read_csv(BytesIO(train_raw))
        if len(train_labels) != expected_count or train_labels["date"].tolist() != pd.to_datetime(saved_train["date"]).tolist():
            raise ValueError(f"{sample}: train session coverage differs from the TFM.")
        if train_labels["regime"].tolist() != saved_train["regime"].tolist():
            raise ValueError(f"{sample}: train regime labels differ from saved TFM labels.")
        train_master = master.assign(date=pd.to_datetime(master["date"]))
        joined = train_labels.merge(train_master, on="date", suffixes=("_regime", "_master"), validate="one_to_one")
        if len(joined) != expected_count:
            raise ValueError(f"{sample}: recovered master does not cover all train sessions.")
        for column in ["ret_1d", "ewma_vol", "cvar_95_60d"]:
            np.testing.assert_allclose(joined[column + "_regime"], joined[column + "_master"],
                                       atol=1e-12, rtol=1e-10, err_msg=f"{sample}: train {column}")
        available = labeled_full.loc[labeled_full["date"] <= final_feature_date]
        assembled = assemble_features(available, master)
        train = training_rows(assembled, sample, boundary_policy="causal")
        evaluation = evaluation_rows(assembled, sample)
        if len(train) != expected_count - 1 or not (train["target_date"] < cutoff).all():
            raise ValueError(f"{sample}: temporal purge is not the expected single boundary row.")
        if set(train["regime_t_plus_1"].astype(int)) != {0, 1, 2}:
            raise ValueError(f"{sample}: training does not contain all three classes.")
        prediction_source = manifest["sources"][sample + "_predictions"]
        prediction_raw = gzip.decompress((fixture_root / prediction_source["fixture"]).read_bytes())
        if sha256(prediction_raw) != prediction_source["sha256"]:
            raise ValueError(f"{sample}: frozen predictions changed.")
        historical = pd.read_csv(BytesIO(prediction_raw))
        historical["date"] = pd.to_datetime(historical["date"])
        expected_eval = historical.loc[historical["date"].isin(evaluation["date"])].reset_index(drop=True)
        if evaluation["date"].tolist() != expected_eval["date"].tolist():
            raise ValueError(f"{sample}: validation dates do not match historical predictions.")
        np.testing.assert_array_equal(evaluation["regime_t_plus_1"].astype(int), expected_eval["regime_t_plus_1"])
        for column in ["regime", "ret_1d"]:
            np.testing.assert_allclose(evaluation[column], expected_eval[column], atol=1e-12, rtol=1e-10)
        mapping = pd.DataFrame(manifest["tables"][sample + "_mapping"])
        for column in ["regime", "risk_order", "target_exposure", "mean_cvar_95_60d", "defensive_alpha"]:
            mapping[column] = pd.to_numeric(mapping[column])
        experiments[sample] = {"train": train, "evaluation": evaluation,
                               "historical_predictions": expected_eval, "mapping": mapping}
        provenance["samples"][sample] = {
            "regimes_sha256": sha256(regime_raw), "saved_train_sha256": sha256(train_raw),
            "saved_train_source": relative, "predictions_sha256": sha256(prediction_raw),
            "historical_train_rows": expected_count, "purged_train_rows": len(train),
            "first_feature_date": train["date"].min().date().isoformat(),
            "last_feature_date": train["date"].max().date().isoformat(),
            "last_label_date": train["target_date"].max().date().isoformat(),
            "removed_boundary_feature_date": train_labels["date"].max().date().isoformat(),
            "oos_rows": len(evaluation), "oos_first_date": evaluation["date"].min().date().isoformat(),
            "oos_last_date": evaluation["date"].max().date().isoformat(),
            "original_oos_rows": len(historical),
            "excluded_original_dates": historical.loc[~historical["date"].isin(evaluation["date"]), "date"].dt.strftime("%Y-%m-%d").tolist(),
            "class_counts": {str(k): int(v) for k, v in train["regime_t_plus_1"].value_counts().items()},
        }
    return experiments, provenance
