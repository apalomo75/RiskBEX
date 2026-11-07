"""Strict feature contracts and separate historical/training preparation."""

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from src.riskbex.ml.config import FEATURE_COLUMNS, SAMPLES, normalize_sample


def dated_frame(frame):
    if frame.empty or frame.columns.duplicated().any() or "date" not in frame:
        raise ValueError("Expected nonempty data, unique columns and a date column.")
    output = frame.copy().reset_index(drop=True)
    output["date"] = pd.to_datetime(output["date"], errors="raise")
    dates = output["date"]
    if dates.dt.tz is not None or dates.isna().any():
        raise ValueError("Dates must be valid timezone-naive daily sessions.")
    if not dates.eq(dates.dt.normalize()).all():
        raise ValueError("Intraday timestamps are not daily session dates.")
    if dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError("Dates must be unique and sorted; refusing silent reordering.")
    return output


def numeric_values(frame, columns):
    missing = [column for column in columns if column not in frame]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    for column in columns:
        if not is_numeric_dtype(frame[column]) or is_bool_dtype(frame[column]):
            raise ValueError(f"{column} must be numeric, not strings or booleans.")
    values = frame[list(columns)].to_numpy(dtype=float, na_value=np.nan)
    if not np.isfinite(values).all():
        raise ValueError(f"Missing or nonfinite values in {list(columns)}; no rows dropped.")
    return values


def regime_values(values, name="regime"):
    series = pd.Series(values)
    array = numeric_values(pd.DataFrame({name: series}), [name]).ravel()
    if not np.isin(array, [0, 1, 2]).all():
        raise ValueError(f"{name} must contain integer regimes 0, 1 or 2.")
    return array.astype(int)


def prepare_features(frame):
    """Return exactly the eleven ordered features; never discard rows or features."""
    output = dated_frame(frame)
    numeric_values(output, FEATURE_COLUMNS)
    return output[list(FEATURE_COLUMNS)].astype(float)


def assemble_features(regimes, master):
    """Notebook 05 one-to-one join, with mandatory coverage instead of silent drops."""
    base = dated_frame(regimes)
    extra = dated_frame(master)
    base_features = ["ret_1d", "ewma_vol", "cvar_95_60d"]
    extras = [column for column in FEATURE_COLUMNS if column not in base_features]
    numeric_values(base, base_features)
    numeric_values(extra, extras)
    if set(extras) & set(base.columns):
        raise ValueError("Additional features already present; choose one explicit source.")
    joined = base.merge(extra[["date", *extras]], on="date", how="left", validate="one_to_one")
    prepare_features(joined)
    return joined


def build_next_regime_target(frame):
    """Historical labels: preserve the final unknown target for daily inference."""
    output = dated_frame(frame)
    if "regime" not in output:
        raise ValueError("regime is required to construct next-session labels.")
    output["regime"] = regime_values(output["regime"])
    output["target_date"] = output["date"].shift(-1)
    output["regime_t_plus_1"] = output["regime"].shift(-1).astype("Int64")
    return output


def evaluation_rows(frame, sample):
    """OOS labeled rows only; no fitting, scaling or feature selection."""
    name = normalize_sample(sample)
    output = dated_frame(frame)
    if "target_date" not in output or "regime_t_plus_1" not in output:
        raise ValueError("Build explicit next-session labels before evaluation.")
    output["target_date"] = pd.to_datetime(output["target_date"])
    valid = output["target_date"].notna() & output["regime_t_plus_1"].notna()
    selected = output.loc[valid & (output["date"] >= pd.Timestamp(SAMPLES[name]["test_start"]))].copy()
    if selected.empty or not (selected["target_date"] > selected["date"]).all():
        raise ValueError("Evaluation requires nonempty, strictly future targets.")
    prepare_features(selected)
    regime_values(selected["regime_t_plus_1"], "regime_t_plus_1")
    return selected.reset_index(drop=True)


def training_rows(frame, sample, *, boundary_policy):
    """Prepare only; never fit. Caller must explicitly choose historical or causal.

    historical_tfm reproduces the original boundary crossing. causal excludes
    labels whose target date reaches test. Neither policy is chosen implicitly.
    """
    name = normalize_sample(sample)
    if boundary_policy not in {"historical_tfm", "causal"}:
        raise ValueError("Explicit boundary_policy must be historical_tfm or causal.")
    output = dated_frame(frame)
    if "target_date" not in output or "regime_t_plus_1" not in output:
        raise ValueError("Explicit next-session labels are required.")
    output["target_date"] = pd.to_datetime(output["target_date"])
    cutoff = pd.Timestamp(SAMPLES[name]["test_start"])
    valid = output["target_date"].notna() & output["regime_t_plus_1"].notna()
    selected = output.loc[valid & (output["date"] < cutoff)].copy()
    if boundary_policy == "causal":
        selected = selected.loc[selected["target_date"] < cutoff].copy()
    if selected.empty or not (selected["target_date"] > selected["date"]).all():
        raise ValueError("Training requires nonempty, strictly future targets.")
    prepare_features(selected)
    regime_values(selected["regime_t_plus_1"], "regime_t_plus_1")
    selected.attrs["boundary_policy"] = boundary_policy
    selected.attrs["targets_crossing_test_boundary"] = int((selected["target_date"] >= cutoff).sum())
    return selected.reset_index(drop=True)
