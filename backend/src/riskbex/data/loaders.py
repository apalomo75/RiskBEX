import pandas as pd

from src.riskbex.config import REGIME_FEATURES, REGIME_SPLIT_COLUMN, REGIME_TRAIN_LABEL
from src.riskbex.paths import (
    CAP4_INPUT_PATH,
    MASTER_DATASET_PATH,
    PROCESSED_DATA_DIR,
    RAW_PRICES_PATH,
    REGIME_DATASET_PATH,
    REGIME_DURATION_SUMMARY_PATH,
    REGIME_MODEL_SELECTION_PATH,
    REGIME_SUMMARY_PATH,
    REGIME_TRANSITION_MATRIX_PATH,
)


def _load_dataset(path):
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df.reset_index(drop=True)


def _validate_columns(df, required_columns, dataset_name):
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required {dataset_name} columns: {missing_columns}"
        )


def _normalize_sample(sample):
    normalized_sample = str(sample).lower()
    if normalized_sample not in {"main", "robust"}:
        raise ValueError("sample must be 'main' or 'robust'")
    return normalized_sample


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


def load_model_selection():
    df = _load_dataset(REGIME_MODEL_SELECTION_PATH)
    _validate_columns(
        df,
        ["split", "k_regimes", "aic", "bic", "converged", "selected"],
        "model selection",
    )
    return df


def load_regime_dataset():
    df = _load_dataset(REGIME_DATASET_PATH)
    _validate_columns(
        df,
        [
            "date",
            "main_regime",
            "robust_regime",
            "main_p_regime_0",
            "main_p_regime_1",
            "main_p_regime_2",
            "robust_p_regime_0",
            "robust_p_regime_1",
            "robust_p_regime_2",
        ],
        "regime dataset",
    )
    return df


def load_regime_summary():
    df = _load_dataset(REGIME_SUMMARY_PATH)
    _validate_columns(
        df,
        ["split", "regime", "economic_label", "risk_order"],
        "regime summary",
    )
    return df


def load_transition_matrix():
    df = _load_dataset(REGIME_TRANSITION_MATRIX_PATH)
    _validate_columns(
        df,
        [
            "split",
            "from_regime",
            "to_regime",
            "transition_probability",
            "from_label",
            "to_label",
        ],
        "transition matrix",
    )
    return df


def load_duration_summary():
    df = _load_dataset(REGIME_DURATION_SUMMARY_PATH)
    _validate_columns(
        df,
        [
            "split",
            "scope",
            "regime",
            "economic_label",
            "risk_order",
            "mean_duration_trading_days",
            "median_duration_trading_days",
            "max_duration_trading_days",
        ],
        "duration summary",
    )
    return df


def load_clean_regime_dataset(sample: str = "main"):
    normalized_sample = _normalize_sample(sample)
    filename = (
        "regime_dataset_main.csv"
        if normalized_sample == "main"
        else "regime_dataset_robust.csv"
    )
    df = _load_dataset(PROCESSED_DATA_DIR / filename)
    split_column = (
        "sample_split_main"
        if normalized_sample == "main"
        else "sample_split_robust"
    )
    _validate_columns(
        df,
        [
            "date",
            "ret_1d",
            "ewma_vol",
            "cvar_95_60d",
            split_column,
            "regime",
            "regime_label",
            "risk_order",
            "p_regime_0",
            "p_regime_1",
            "p_regime_2",
        ],
        f"clean {normalized_sample} regime dataset",
    )
    return df


def load_regime_exposure_mapping(sample: str = "main"):
    normalized_sample = _normalize_sample(sample)
    filename = (
        "regime_exposure_mapping.csv"
        if normalized_sample == "main"
        else "regime_exposure_mapping_robust.csv"
    )
    df = _load_dataset(PROCESSED_DATA_DIR / filename)
    _validate_columns(
        df,
        ["regime", "economic_label", "risk_order", "target_exposure"],
        f"{normalized_sample} regime exposure mapping",
    )
    return df
