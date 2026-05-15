import pandas as pd

from src.riskbex.regimes.heuristic import classify_regime, compute_risk_score


def get_risk_score_with_fallback(row):
    dataset_score = row.get("risk_score")
    if pd.notna(dataset_score):
        return int(round(float(dataset_score)))
    return compute_risk_score(row)


def get_risk_level_with_fallback(row):
    dataset_level = row.get("risk_level")
    if pd.notna(dataset_level):
        return str(dataset_level)

    fallback_score = get_risk_score_with_fallback(row)
    if pd.isna(fallback_score):
        return None
    if fallback_score <= 33:
        return "bajo"
    if fallback_score <= 66:
        return "medio"
    return "alto"
