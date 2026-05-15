import numpy as np
import pandas as pd


BURN_IN_OBS = 252

RISK_WEIGHTS = {
    "vol_score": 0.30,
    "cvar_score": 0.30,
    "drawdown_score": 0.25,
    "downside_score": 0.15,
}


def historical_percentile_midrank(
    value: float,
    history: pd.Series,
) -> float:
    valid_history = history.dropna()
    if pd.isna(value) or valid_history.empty:
        return np.nan

    lower_count = (valid_history < value).sum()
    equal_count = (valid_history == value).sum()
    return (lower_count + 0.5 * equal_count) / len(valid_history)


def assign_risk_level(score: float):
    if pd.isna(score):
        return np.nan
    if score <= 33:
        return "bajo"
    if score <= 66:
        return "medio"
    return "alto"


def compute_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = ["ewma_vol", "cvar_95_60d", "drawdown", "downside_vol_60d"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column for risk score computation: {col}")

    df = df.copy()
    component_scores = {
        "vol_score": [],
        "cvar_score": [],
        "drawdown_score": [],
        "downside_score": [],
    }
    aggregate_scores = []

    for idx in range(len(df)):
        vol_value = df.at[idx, "ewma_vol"]
        cvar_value = df.at[idx, "cvar_95_60d"]
        drawdown_value = df.at[idx, "drawdown"]
        downside_value = df.at[idx, "downside_vol_60d"]

        if pd.isna(vol_value) or pd.isna(cvar_value) or pd.isna(drawdown_value) or pd.isna(downside_value):
            for key in component_scores:
                component_scores[key].append(np.nan)
            aggregate_scores.append(np.nan)
            continue

        history = df.iloc[:idx]
        vol_hist = history["ewma_vol"]
        cvar_hist = -history["cvar_95_60d"]
        drawdown_hist = -history["drawdown"]
        downside_hist = history["downside_vol_60d"]

        min_history_size = min(
            vol_hist.dropna().shape[0],
            cvar_hist.dropna().shape[0],
            drawdown_hist.dropna().shape[0],
            downside_hist.dropna().shape[0],
        )
        if min_history_size < BURN_IN_OBS:
            for key in component_scores:
                component_scores[key].append(np.nan)
            aggregate_scores.append(np.nan)
            continue

        vol_score = 100 * historical_percentile_midrank(vol_value, vol_hist)
        cvar_score = 100 * historical_percentile_midrank(-cvar_value, cvar_hist)
        drawdown_score = 100 * historical_percentile_midrank(-drawdown_value, drawdown_hist)
        downside_score = 100 * historical_percentile_midrank(downside_value, downside_hist)

        component_scores["vol_score"].append(vol_score)
        component_scores["cvar_score"].append(cvar_score)
        component_scores["drawdown_score"].append(drawdown_score)
        component_scores["downside_score"].append(downside_score)

        score_raw = (
            RISK_WEIGHTS["vol_score"] * vol_score
            + RISK_WEIGHTS["cvar_score"] * cvar_score
            + RISK_WEIGHTS["drawdown_score"] * drawdown_score
            + RISK_WEIGHTS["downside_score"] * downside_score
        )
        aggregate_scores.append(int(round(np.clip(score_raw, 0, 100))))

    for col, values in component_scores.items():
        df[col] = values

    df["risk_score"] = aggregate_scores
    df["risk_level"] = df["risk_score"].apply(assign_risk_level)
    return df
