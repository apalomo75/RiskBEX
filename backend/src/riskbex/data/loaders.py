import pandas as pd

from src.riskbex.config import REGIME_FEATURES, REGIME_SPLIT_COLUMN, REGIME_TRAIN_LABEL
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


def load_regime_input_dataset():
    df = load_cap4_input_dataset()
    required_columns = [*REGIME_FEATURES, REGIME_SPLIT_COLUMN]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required regime input columns: {missing_columns}")
    return df


def load_regime_train_dataset():
    df = load_regime_input_dataset()
    return df[df[REGIME_SPLIT_COLUMN] == REGIME_TRAIN_LABEL].reset_index(drop=True)
