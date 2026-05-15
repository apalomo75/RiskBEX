import pandas as pd

from src.riskbex.paths import (
    CAP4_INPUT_PATH,
    MASTER_DATASET_PATH,
    RAW_PRICES_PATH,
)


def _load_dataset(path):
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df.reset_index(drop=True)


def load_master_dataset():
    return _load_dataset(MASTER_DATASET_PATH)


def load_cap4_input_dataset():
    return _load_dataset(CAP4_INPUT_PATH)


def load_raw_prices():
    return _load_dataset(RAW_PRICES_PATH)
