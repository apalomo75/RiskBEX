from fastapi import FastAPI
from typing import Optional
import pandas as pd
from pathlib import Path

from src.risk_model import classify_regime, compute_risk_score

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "processed" / "dataset_cap3_master.csv"


def load_data():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df



@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/latest-risk")
def latest_risk():
    df = load_data()
    latest = df.iloc[-1]

    return {
        "date": latest["date"].strftime("%Y-%m-%d"),
        "vol_20d": float(latest["vol_20d"]),
        "vol_60d": float(latest["vol_60d"]),
        "var_95_60d": float(latest["var_95_60d"]),
        "cvar_95_60d": float(latest["cvar_95_60d"]),
        "drawdown": float(latest["drawdown"]),
        "skew_60d": float(latest["skew_60d"]),
        "regime_label": classify_regime(latest),
        "risk_score": compute_risk_score(latest),
    }


@app.get("/historical-risk")
def historical_risk(limit: Optional[str] = None):
    df = load_data().copy()
    df["regime_label"] = df.apply(classify_regime, axis=1)
    df["risk_score"] = df.apply(compute_risk_score, axis=1)

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
