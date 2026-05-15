from typing import Optional

from fastapi import APIRouter

from src.riskbex.api.schemas import HistoricalRiskPoint, LatestRiskResponse
from src.riskbex.data.loaders import load_master_dataset
from src.riskbex.regimes.heuristic import classify_regime, compute_risk_score
from src.risk_model import (
    get_risk_level_with_fallback,
    get_risk_score_with_fallback,
)


router = APIRouter()


def load_data():
    return load_master_dataset()


@router.get("/latest-risk", response_model=LatestRiskResponse)
def latest_risk():
    df = load_data()
    latest = df.iloc[-1]
    risk_score = get_risk_score_with_fallback(latest)
    risk_level = get_risk_level_with_fallback(latest)

    return {
        "date": latest["date"].strftime("%Y-%m-%d"),
        "vol_20d": float(latest["vol_20d"]),
        "vol_60d": float(latest["vol_60d"]),
        "var_95_60d": float(latest["var_95_60d"]),
        "cvar_95_60d": float(latest["cvar_95_60d"]),
        "drawdown": float(latest["drawdown"]),
        "skew_60d": float(latest["skew_60d"]),
        "regime_label": classify_regime(latest),
        "risk_score": risk_score,
        "risk_level": risk_level,
    }


@router.get("/historical-risk", response_model=list[HistoricalRiskPoint])
def historical_risk(limit: Optional[str] = None):
    df = load_data().copy()
    df["regime_label"] = df.apply(classify_regime, axis=1)
    if "risk_score" in df.columns:
        df["risk_score"] = df.apply(get_risk_score_with_fallback, axis=1)
    else:
        df["risk_score"] = df.apply(compute_risk_score, axis=1)

    df["risk_level"] = df.apply(get_risk_level_with_fallback, axis=1)

    cols = [
        "date",
        "vol_20d",
        "vol_60d",
        "var_95_60d",
        "cvar_95_60d",
        "drawdown",
        "skew_60d",
        "regime_label",
        "risk_score",
        "risk_level",
    ]

    default_limit = 250
    records_limit = default_limit

    if limit is not None:
        if limit.lower() == "all":
            records_limit = None
        else:
            try:
                parsed_limit = int(limit)
                if parsed_limit > 0:
                    records_limit = parsed_limit
            except (TypeError, ValueError):
                records_limit = default_limit

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    if records_limit is None:
        return df[cols].to_dict(orient="records")

    return df[cols].tail(records_limit).to_dict(orient="records")
