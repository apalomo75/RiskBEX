"""Integrity and compatibility of a standalone MAIN model package."""

from dataclasses import dataclass
import hashlib
from importlib import metadata as library_metadata
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from src.riskbex.backtesting.exposures import build_cvar_exposure_mapping
from src.riskbex.ml.config import FEATURE_COLUMNS
from src.riskbex.ml.data import dated_frame, numeric_values
from src.riskbex.ml.inference import load_xgboost_model
from src.riskbex.regimes.persistence import load_frozen_markov, verify_xgboost_correspondence


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_price_hash(prices):
    data = dated_frame(prices)
    numeric_values(data, ["ibex_close"])
    records = "\n".join(f"{date:%Y-%m-%d}|{float(close).hex()}"
                         for date, close in zip(data["date"], data["ibex_close"])) + "\n"
    return hashlib.sha256(records.encode()).hexdigest()


def package_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if root not in path.parents:
        raise ValueError("Model package paths must remain inside the package.")
    return path


def verify_main_package(root, *, check_runtime=False):
    root = Path(root).resolve()
    path = root / "manifest.json"
    if file_hash(path) != (root / "manifest.sha256").read_text().strip():
        raise ValueError("MAIN manifest SHA-256 mismatch.")
    manifest = json.loads(path.read_text())
    if manifest["sample"] != "main" or manifest["schema_version"] != 1:
        raise ValueError("Only the selected MAIN package is supported.")
    if tuple(manifest["feature_columns"]) != FEATURE_COLUMNS:
        raise ValueError("Package feature order differs from the eleven TFM features.")
    for relative, entry in manifest["files"].items():
        if file_hash(package_file(root, relative)) != entry["sha256"]:
            raise ValueError(f"MAIN component SHA-256 mismatch: {relative}")
    components = manifest["components"]
    for name in ["markov_metadata", "xgboost_metadata", "xgboost_model", "cvar_mapping"]:
        if components[name] not in manifest["files"]:
            raise ValueError(f"Unhashed package component: {name}")
    markov_path = package_file(root, components["markov_metadata"])
    xgb_path = package_file(root, components["xgboost_metadata"])
    verify_xgboost_correspondence(markov_path, xgb_path)
    markov = json.loads(markov_path.read_text())
    xgb = json.loads(xgb_path.read_text())
    dependencies = [
        (markov_path.parent / markov["parameters_file"], markov["parameters_sha256"]),
        (markov_path.parent / markov["cvar_mapping_file"], markov["cvar_mapping_sha256"]),
        (markov_path.parent / "validation.json", markov["validation_sha256"]),
        (xgb_path.parent / "validation.json", xgb["validation_sha256"]),
    ]
    for dependency, checksum in dependencies:
        relative = str(dependency.resolve().relative_to(root))
        if relative not in manifest["files"] or file_hash(package_file(root, relative)) != checksum:
            raise ValueError(f"Unverified nested model dependency: {relative}")
    if (markov_path.parent / markov["cvar_mapping_file"]).resolve() != package_file(root, components["cvar_mapping"]):
        raise ValueError("Mapping component differs from the mapping actually loaded by Markov.")
    if manifest["regime_definition_sha256"] != markov["academic_regimes_sha256"]:
        raise ValueError("Package regime definition differs from model provenance.")
    for field, expected in {"rolling_windows": [20, 60], "ewma_lambda": .94,
                            "tail_probability": .05, "sample_std_ddof": 1}.items():
        if manifest["feature_policy"][field] != expected:
            raise ValueError(f"Package indicator convention changed: {field}")
    if manifest["training"]["information_cutoff"] != markov["trained_through"] or markov["trained_through"] != xgb["trained_through"]:
        raise ValueError("Model information cutoffs are inconsistent.")
    if manifest["feature_policy"]["filter_history_start"] != markov["history_start"]:
        raise ValueError("Markov initialization date changed.")
    if markov["fit_recipe"]["maxiter"] != 500 or markov["technical_validation"] != "passed":
        raise ValueError("The operational MAIN selection requires the validated 500-iteration model.")
    validation = json.loads((markov_path.parent / "validation.json").read_text())
    if (not validation["converged"] or validation["train_regime_mismatches"] != 0
            or validation["full_regime_mismatches"] != 0 or not validation["same_train_cvar_mapping"]):
        raise ValueError("MAIN Markov compatibility evidence failed.")
    if xgb["classes"] != [0, 1, 2] or xgb["boundary_policy"] != "causal":
        raise ValueError("Expected the selected causal-v1 classifier and original class IDs.")
    if tuple(xgb["feature_columns"]) != FEATURE_COLUMNS:
        raise ValueError("XGBoost metadata has another feature order.")
    if file_hash(package_file(root, components["xgboost_model"])) != xgb["sha256"]:
        raise ValueError("XGBoost model does not match its metadata.")
    expected_classes = sorted((int(row["regime"]), row["economic_label"], int(row["risk_order"]))
                              for row in manifest["economic_classes"])
    for rows in [markov["economic_classes"], xgb["economic_classes"]]:
        actual = sorted((int(row["regime"]), row["economic_label"], int(row["risk_order"])) for row in rows)
        if actual != expected_classes:
            raise ValueError("Package, Markov and XGBoost economic classes disagree.")
    mapping = pd.DataFrame(json.loads(package_file(root, components["cvar_mapping"]).read_text()))
    for column in ["regime", "risk_order", "mean_cvar_95_60d", "target_exposure", "defensive_alpha"]:
        mapping[column] = pd.to_numeric(mapping[column], errors="raise")
    mapping_classes = sorted((int(row.regime), row.economic_label, int(row.risk_order)) for row in mapping.itertuples())
    if mapping_classes != expected_classes:
        raise ValueError("CVaR mapping economic classes differ from the models.")
    if mapping["defensive_alpha"].tolist() != [1., 1., 1.]:
        raise ValueError("The MAIN package must preserve the original alpha=1.")
    reconstructed = build_cvar_exposure_mapping(mapping)
    np.testing.assert_allclose(mapping["target_exposure"], reconstructed["target_exposure"], atol=1e-12, rtol=1e-10)
    if check_runtime:
        for name, expected in manifest["required_versions"].items():
            actual = platform.python_version() if name == "python" else library_metadata.version(name)
            if actual != expected:
                raise ValueError(f"MAIN runtime mismatch: {name}={actual}, expected {expected}")
    return manifest


@dataclass(frozen=True)
class MainModelPackage:
    root: Path
    manifest: dict
    manifest_sha256: str
    markov: object
    xgboost: object
    mapping: pd.DataFrame


def load_main_package(root):
    root = Path(root).resolve()
    manifest = verify_main_package(root, check_runtime=True)
    components = manifest["components"]
    markov = load_frozen_markov(package_file(root, components["markov_metadata"]), sample="main")
    xgb = load_xgboost_model(package_file(root, components["xgboost_model"]),
                             package_file(root, components["xgboost_metadata"]), sample="main")
    mapping = pd.DataFrame(markov.cvar_mapping)
    mapping["regime"] = pd.to_numeric(mapping["regime"])
    mapping["target_exposure"] = pd.to_numeric(mapping["target_exposure"])
    return MainModelPackage(root, manifest, file_hash(root / "manifest.json"), markov, xgb, mapping)
