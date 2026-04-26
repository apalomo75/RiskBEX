def classify_regime(row):
    if row["vol_20d"] > 0.02 or row["drawdown"] < -0.20:
        return "stress"
    elif row["vol_20d"] > 0.012 or row["drawdown"] < -0.10:
        return "turbulence"
    else:
        return "calm"


def compute_risk_score(row):
    vol_score = min(max(row["vol_20d"] / 0.03, 0), 1) * 40
    cvar_score = min(max(abs(row["cvar_95_60d"]) / 0.08, 0), 1) * 35
    drawdown_score = min(max(abs(row["drawdown"]) / 0.50, 0), 1) * 25
    return round(vol_score + cvar_score + drawdown_score)
