"""Single MAIN inference service: prices through t -> next-session target exposures."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.riskbex.backtesting.exposures import apply_target_exposure
from src.riskbex.engine.package import canonical_price_hash, file_hash, verify_main_package
from src.riskbex.features.market import compute_market_features
from src.riskbex.ml.config import FEATURE_COLUMNS
from src.riskbex.ml.data import dated_frame, numeric_values, prepare_features
from src.riskbex.ml.inference import predict_regimes
from src.riskbex.regimes.persistence import filter_frozen_markov


def implementation_hashes():
    root = Path(__file__).resolve().parents[1]
    names = ["engine/package.py", "engine/service.py", "features/market.py", "features/returns.py",
             "features/volatility.py", "features/downside.py", "features/drawdown.py", "features/tail_risk.py",
             "ml/config.py", "ml/data.py", "ml/inference.py", "regimes/persistence.py", "backtesting/exposures.py"]
    return {name: file_hash(root / name) for name in names}


def prepare_price_history(package, prices, *, as_of=None):
    frame = dated_frame(prices)
    if as_of is not None:
        cutoff = pd.Timestamp(as_of)
        if pd.isna(cutoff) or cutoff.tz is not None or cutoff != cutoff.normalize():
            raise ValueError("as_of must be a valid timezone-naive session cutoff date.")
        # Slice before reading prices or computing any indicator; future values do not participate.
        frame = frame.loc[frame["date"] <= cutoff].copy()
    if frame.empty:
        raise ValueError("No prices at or before the requested information cutoff.")
    numeric_values(frame, ["ibex_close"])
    if not frame["ibex_close"].gt(0).all():
        raise ValueError("Closing prices must be strictly positive.")
    frame = frame[["date", "ibex_close"]].copy()
    initialization = package.manifest["price_initialization"]
    first = frame["date"].iloc[0]
    anchor_date = pd.Timestamp(initialization["previous_session"])
    if first == pd.Timestamp(initialization["first_return_session"]):
        frame = pd.concat([pd.DataFrame({"date": [anchor_date],
                            "ibex_close": [initialization["previous_close"]]}), frame], ignore_index=True)
    elif first != anchor_date:
        raise ValueError("Complete history must start at the recorded price anchor or first return session.")
    train_end = pd.Timestamp(package.manifest["training"]["information_cutoff"])
    if frame["date"].iloc[-1] <= train_end:
        raise ValueError("Operational inference must be strictly after training information cutoff.")
    train = frame.loc[frame["date"] <= train_end]
    expected = package.manifest["training_price_prefix"]
    if len(train) != expected["rows"] or canonical_price_hash(train) != expected["sha256"]:
        raise ValueError("Training price prefix changed or sessions are missing; review instead of silently rebasing.")
    return frame.reset_index(drop=True)


def prepare_engine_features(package, prices, *, as_of=None):
    history = prepare_price_history(package, prices, as_of=as_of)
    features = compute_market_features(history)
    start = pd.Timestamp(package.manifest["feature_policy"]["filter_history_start"])
    features = features.loc[features["date"] >= start].reset_index(drop=True)
    if features.empty or features["date"].iloc[0] != start:
        raise ValueError("Missing original Markov filter initialization session.")
    # Only the documented initial warmup is removed; later NaNs fail explicitly.
    prepare_features(features)
    numeric_values(features, ["var_95_60d"])
    return history, features


def infer_main_signals(package, prices, *, as_of=None):
    manifest = verify_main_package(package.root)
    if file_hash(package.root / "manifest.json") != package.manifest_sha256:
        raise ValueError("Package changed after loading; load a new explicit version.")
    history, features = prepare_engine_features(package, prices, as_of=as_of)
    current = features.tail(1)
    markov = filter_frozen_markov(package.markov, features[["date", "ret_1d"]], sample="main").iloc[-1]
    forecast = predict_regimes(package.xgboost, current[["date", *FEATURE_COLUMNS]], sample="main").iloc[0]
    observed_regime, predicted_regime = int(markov["regime"]), int(forecast["regime_pred"])
    assigned = apply_target_exposure(pd.DataFrame({"regime": [observed_regime, predicted_regime]}), package.mapping)
    probability_exposure = sum(float(forecast[f"proba_{int(row.regime)}"]) * float(row.target_exposure)
                               for row in package.mapping.itertuples())
    if not 0 <= probability_exposure <= 1:
        raise ValueError("Probability-weighted target is outside [0, 1].")
    date = current["date"].iloc[0].date().isoformat()
    classes = {int(row["regime"]): row for row in manifest["economic_classes"]}
    return {
        "schema_version": 1, "engine": "MAIN", "package_id": manifest["package_id"],
        "last_valid_session": date, "signal_information_date": date,
        "requested_as_of": None if as_of is None else pd.Timestamp(as_of).date().isoformat(),
        "information_available_after": "close_of_information_session",
        "execution_horizon": "next_market_session", "target_session_date": None,
        "execution_rule": "Use this target during the next session; do not shift the signal again.",
        "market": {"ibex_close": float(current["ibex_close"].iloc[0]),
                   "ret_1d": float(current["ret_1d"].iloc[0])},
        "features": {name: float(current[name].iloc[0]) for name in FEATURE_COLUMNS},
        "additional_indicators": {"var_95_60d": float(current["var_95_60d"].iloc[0])},
        "markov": {
            "state_date": date, "horizon": "current_session_filtered_state",
            "regime": observed_regime, "economic_label": classes[observed_regime]["economic_label"],
            "risk_order": classes[observed_regime]["risk_order"],
            "probabilities": {str(k): float(markov[f"p_regime_{k}"]) for k in range(3)},
            "parameter_id": package.markov.artifact_id,
        },
        "xgboost": {
            "information_date": date, "horizon": "next_market_session",
            "regime_pred": predicted_regime, "economic_label": classes[predicted_regime]["economic_label"],
            "risk_order": classes[predicted_regime]["risk_order"],
            "probabilities": {str(k): float(forecast[f"proba_{k}"]) for k in range(3)},
            "model_id": package.xgboost.artifact_id,
        },
        "target_exposures": {
            "regime_based": float(assigned["target_exposure"].iloc[0]),
            "ml_hard": float(assigned["target_exposure"].iloc[1]),
            "ml_probability_weighted": float(probability_exposure),
        },
        "provenance": {
            "manifest_sha256": package.manifest_sha256,
            "implementation_sha256": implementation_hashes(),
            "component_sha256": {name: value["sha256"] for name, value in manifest["files"].items()},
            "price_prefix_sha256": canonical_price_hash(history),
            "price_rows_including_initialization": len(history),
            "first_price_session": history["date"].iloc[0].date().isoformat(),
            "last_price_session": date, "required_versions": manifest["required_versions"],
            "regime_reference_sha256": manifest["regime_definition_sha256"],
            "models_retrained": False, "source": "caller_supplied_historical_prices",
            "closed_sessions_required": True, "live_market_freshness_verified": False,
        },
    }
