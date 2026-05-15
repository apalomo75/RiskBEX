from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.config import (
    EWMA_LAMBDA,
    MAIN_TEST_START,
    ROBUST_TEST_START,
    ROLLING_LONG_WINDOW,
    ROLLING_SHORT_WINDOW,
    START_DATE,
    TICKER,
)
from src.riskbex.features.downside import compute_downside_volatility
from src.riskbex.features.drawdown import compute_drawdown
from src.riskbex.features.returns import (
    compute_log_returns,
    compute_risk_adjusted_return,
    compute_rolling_return,
)
from src.riskbex.features.scoring import compute_risk_score
from src.riskbex.features.tail_risk import (
    compute_historical_cvar,
    compute_historical_var,
)
from src.riskbex.features.volatility import compute_ewma_volatility
from src.riskbex.paths import (
    CAP4_INPUT_PATH,
    CHAPTER2_FIGURES_DIR,
    MASTER_DATASET_PATH,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    RAW_PRICES_PATH,
)
from src.riskbex.reporting.figures import generate_chapter2_figures

# =========================
# PATHS
# =========================
FIGURES_DIR = CHAPTER2_FIGURES_DIR

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

RAW_OUTPUT = RAW_PRICES_PATH
PROCESSED_OUTPUT = MASTER_DATASET_PATH
CAP4_OUTPUT = CAP4_INPUT_PATH

# =========================
# PARAMETERS
# =========================
SHORT_WINDOW = ROLLING_SHORT_WINDOW
MEDIUM_WINDOW = ROLLING_LONG_WINDOW
VAR_TAIL_PROB = 0.05

# =========================
# STEP 1: DOWNLOAD IBEX
# =========================
print("Downloading IBEX data...")

ibex = yf.download(
    TICKER,
    start=START_DATE,
    progress=False,
    auto_adjust=True
)

if ibex.empty:
    raise ValueError("Downloaded dataset is empty.")

ibex = ibex.reset_index()

if "Date" not in ibex.columns:
    raise ValueError("Column 'Date' not found in downloaded dataset.")

if "Close" not in ibex.columns:
    raise ValueError("Column 'Close' not found in downloaded dataset.")

ibex = ibex[["Date", "Close"]].copy()
ibex.columns = ["date", "ibex_close"]

ibex["date"] = pd.to_datetime(ibex["date"])
ibex = ibex.sort_values("date").reset_index(drop=True)

# daily log returns
ibex["ret_1d"] = compute_log_returns(ibex["ibex_close"])
ibex = ibex.dropna(subset=["ret_1d"]).reset_index(drop=True)

ibex.to_csv(RAW_OUTPUT, index=False)

print(f"Raw data exported to: {RAW_OUTPUT}")
print(f"Raw shape: {ibex.shape}")

# =========================
# STEP 2: FEATURE ENGINEERING
# =========================
print("Computing risk features...")

df = ibex.set_index("date").copy()

# performance features
df["ret_20d"] = compute_rolling_return(df["ret_1d"], SHORT_WINDOW)
df["ret_60d"] = compute_rolling_return(df["ret_1d"], MEDIUM_WINDOW)

# volatility features
df["vol_20d"] = df["ret_1d"].rolling(
    window=SHORT_WINDOW,
    min_periods=SHORT_WINDOW
).std(ddof=1)

df["vol_60d"] = df["ret_1d"].rolling(
    window=MEDIUM_WINDOW,
    min_periods=MEDIUM_WINDOW
).std(ddof=1)

# downside risk
df["downside_vol_20d"] = compute_downside_volatility(df["ret_1d"], SHORT_WINDOW)
df["downside_vol_60d"] = compute_downside_volatility(df["ret_1d"], MEDIUM_WINDOW)

# tail risk
df["var_95_60d"] = compute_historical_var(df["ret_1d"], MEDIUM_WINDOW, VAR_TAIL_PROB)
df["cvar_95_60d"] = compute_historical_cvar(df["ret_1d"], MEDIUM_WINDOW, VAR_TAIL_PROB)

# EWMA volatility (daily scale)
df["ewma_vol"] = compute_ewma_volatility(df["ret_1d"], EWMA_LAMBDA)

# drawdown
df["drawdown"] = compute_drawdown(df["ibex_close"])

# skewness
df["skew_60d"] = df["ret_1d"].rolling(
    window=MEDIUM_WINDOW,
    min_periods=MEDIUM_WINDOW
).skew()

feature_columns = [
    "ibex_close",
    "ret_1d",
    "ret_20d",
    "ret_60d",
    "vol_20d",
    "vol_60d",
    "ewma_vol",
    "downside_vol_20d",
    "downside_vol_60d",
    "var_95_60d",
    "cvar_95_60d",
    "drawdown",
    "skew_60d",
]

master_base_df = df[feature_columns].copy()
master_base_df = master_base_df.dropna(subset=feature_columns)
master_base_df = master_base_df.reset_index()
master_base_df = master_base_df.sort_values("date").reset_index(drop=True)

master_base_df["sample_split_main"] = pd.Categorical(
    np.where(master_base_df["date"] < pd.Timestamp(MAIN_TEST_START), "train", "test")
)

master_base_df["sample_split_robust"] = pd.Categorical(
    np.where(master_base_df["date"] < pd.Timestamp(ROBUST_TEST_START), "train", "test")
)

master_base_df["ret_risk_20d"] = compute_risk_adjusted_return(
    master_base_df["ret_20d"],
    master_base_df["vol_20d"],
)
master_base_df["ret_risk_60d"] = compute_risk_adjusted_return(
    master_base_df["ret_60d"],
    master_base_df["vol_60d"],
)

master_base_df.to_csv(CAP4_OUTPUT, index=False)
print(f"Cap4 input exported to: {CAP4_OUTPUT}")

master_df = compute_risk_score(master_base_df)
master_df.to_csv(PROCESSED_OUTPUT, index=False)

print(f"Processed data exported to: {PROCESSED_OUTPUT}")
print(f"Processed shape: {master_df.shape}")
print(f"Date coverage: {master_df['date'].min()} to {master_df['date'].max()}")

# =========================
# STEP 3: GENERATE FIGURES
# =========================
print("Generating figures...")
generate_chapter2_figures(master_df, FIGURES_DIR)

print("Figures generated successfully.")
print("Daily update completed successfully.")
