"""JSON persistence and full-history filtering of frozen Markov parameters.

No fitting is available through this module. Academic-equivalent and technically
compatible are separate statuses; failed diagnostic candidates cannot be loaded.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels
import statsmodels.api as sm

from src.riskbex.ml.config import normalize_sample
from src.riskbex.ml.data import dated_frame, numeric_values


SPECIFICATION = {"k_regimes": 3, "trend": "c", "switching_variance": True}


@dataclass(frozen=True)
class FrozenMarkovModel:
    sample: str
    parameters: tuple
    parameter_names: tuple
    initial_probabilities: tuple
    history_start: str
    trained_through: str
    economic_classes: tuple
    artifact_id: str
    cvar_mapping: tuple = ()


def parameter_diagnostics(model, parameters):
    parameters = np.asarray(parameters, dtype=float)
    if parameters.shape != (len(model.param_names),) or not np.isfinite(parameters).all():
        raise ValueError("Invalid Markov parameter vector.")
    named = dict(zip(model.param_names, parameters))
    if any(named[f"sigma2[{index}]"] <= 0 for index in range(3)):
        raise ValueError("Markov variances must be strictly positive.")
    transition = np.asarray(model.regime_transition_matrix(parameters)).squeeze()
    if transition.shape != (3, 3) or not np.isfinite(transition).all():
        raise ValueError("Invalid Markov transition matrix.")
    if (transition < 0).any() or (transition > 1).any() or not np.allclose(transition.sum(axis=0), 1., atol=1e-12, rtol=0):
        raise ValueError("Transition columns must be normalized probabilities (to, from).")
    initial = model.initial_probabilities(parameters, transition)
    if not np.isfinite(initial).all() or not np.isclose(initial.sum(), 1., atol=1e-12):
        raise ValueError("Invalid stationary initialization.")
    return {"transition_from_to": transition.T.tolist(), "initial_probabilities": initial.tolist(),
            "variances": [float(named[f"sigma2[{index}]"]) for index in range(3)]}


def filter_frozen_markov(bundle, frame, *, sample):
    if normalize_sample(sample) != normalize_sample(bundle.sample):
        raise ValueError("Markov sample mismatch.")
    output = dated_frame(frame)
    numeric_values(output, ["ret_1d"])
    if output["date"].iloc[0] != pd.Timestamp(bundle.history_start):
        raise ValueError("Full history must start at the original filter initialization date.")
    if output["date"].iloc[-1] < pd.Timestamp(bundle.trained_through):
        raise ValueError("History must include the complete parameter training period.")
    model = sm.tsa.MarkovRegression(output["ret_1d"], **SPECIFICATION)
    model.initialize_steady_state()
    if tuple(model.param_names) != tuple(bundle.parameter_names):
        raise ValueError("Markov parameter names/order differ from the persisted artifact.")
    diagnostics = parameter_diagnostics(model, bundle.parameters)
    np.testing.assert_allclose(diagnostics["initial_probabilities"], bundle.initial_probabilities,
                               atol=1e-14, rtol=1e-12)
    result = model.filter(np.asarray(bundle.parameters), transformed=True, cov_type="none")
    probabilities = np.asarray(result.filtered_marginal_probabilities)
    # Native Hamilton filtering can exceed 1 by a few ulps. Keep its raw values;
    # tolerate roundoff only, never clip or renormalize model probabilities.
    if not np.isfinite(probabilities).all() or (probabilities < -1e-12).any() or (probabilities > 1 + 1e-12).any():
        raise ValueError(f"Invalid filtered probabilities: min={probabilities.min()}, max={probabilities.max()}.")
    if not np.allclose(probabilities.sum(axis=1), 1., atol=1e-10, rtol=0):
        raise ValueError("Filtered probabilities are not normalized.")
    answer = output[["date"]].copy()
    for index in range(3):
        answer[f"p_regime_{index}"] = probabilities[:, index]
    answer["regime"] = probabilities.argmax(axis=1)
    labels = {int(row["regime"]): row["economic_label"] for row in bundle.economic_classes}
    if set(labels) != {0, 1, 2}:
        raise ValueError("Missing persisted economic labels.")
    answer["economic_label"] = answer["regime"].map(labels)
    return answer


def load_frozen_markov(path, *, sample):
    source = Path(path)
    metadata = json.loads(source.read_text())
    if metadata.get("technical_validation") != "passed":
        raise ValueError("Diagnostic Markov candidate has not passed compatibility/convergence gates.")
    if metadata.get("statsmodels_version") != statsmodels.__version__:
        raise ValueError("Use the recorded statsmodels runtime before filtering this model.")
    if normalize_sample(metadata["sample"]) != normalize_sample(sample):
        raise ValueError("Persisted Markov sample mismatch.")
    if metadata["specification"] != SPECIFICATION or metadata["initialization"] != "steady-state":
        raise ValueError("Unexpected Markov specification or initialization.")
    payload = source.parent / metadata["parameters_file"]
    if payload.resolve().parent != source.resolve().parent:
        raise ValueError("Markov parameters must reside alongside metadata.")
    raw = payload.read_bytes()
    if hashlib.sha256(raw).hexdigest() != metadata["parameters_sha256"]:
        raise ValueError("Markov parameter SHA-256 mismatch.")
    associated = {}
    for field, hash_field in [("cvar_mapping_file", "cvar_mapping_sha256")]:
        adjacent = source.parent / metadata[field]
        if adjacent.resolve().parent != source.resolve().parent:
            raise ValueError("Associated Markov files must reside alongside metadata.")
        contents = adjacent.read_bytes()
        if hashlib.sha256(contents).hexdigest() != metadata[hash_field]:
            raise ValueError("Associated CVaR mapping SHA-256 mismatch.")
        associated[field] = json.loads(contents)
    validation = source.parent / "validation.json"
    if hashlib.sha256(validation.read_bytes()).hexdigest() != metadata["validation_sha256"]:
        raise ValueError("Markov validation SHA-256 mismatch.")
    values = json.loads(raw)
    return FrozenMarkovModel(
        metadata["sample"], tuple(values["parameters"]), tuple(values["parameter_names"]),
        tuple(metadata["initial_probabilities"]), metadata["history_start"], metadata["trained_through"],
        tuple(metadata["economic_classes"]), metadata["parameters_sha256"],
        tuple(associated["cvar_mapping_file"]),
    )


def verify_xgboost_correspondence(markov_metadata_path, xgboost_metadata_path):
    """Bind frozen Markov to the exact target provenance and IDs of causal-v1."""
    markov = json.loads(Path(markov_metadata_path).read_text())
    raw = Path(xgboost_metadata_path).read_bytes()
    xgboost = json.loads(raw)
    if markov["technical_validation"] != "passed":
        raise ValueError("Rejected Markov cannot be paired with XGBoost.")
    if hashlib.sha256(raw).hexdigest() != markov["compatible_xgboost_metadata_sha256"]:
        raise ValueError("XGBoost metadata hash mismatch.")
    if markov["sample"] != xgboost["sample"]:
        raise ValueError("Markov and XGBoost samples differ.")
    if markov["academic_regimes_sha256"] != xgboost["source_provenance"]["regimes_sha256"]:
        raise ValueError("Markov reference is not the XGBoost training-label source.")
    order = lambda rows: sorted((int(row["regime"]), row["economic_label"], int(row["risk_order"])) for row in rows)
    if order(markov["economic_classes"]) != order(xgboost["economic_classes"]):
        raise ValueError("Markov and XGBoost economic regime identifiers differ.")
    return True
