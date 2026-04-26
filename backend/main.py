from fastapi import FastAPI
import pandas as pd
from pathlib import Path

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "processed" / "dataset_cap3_master.csv"


def load_data():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


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
def historical_risk():
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

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[cols].tail(250).to_dict(orient="records")
