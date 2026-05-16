import numpy as np
import pandas as pd

from src.riskbex.backtesting.exposures import (
    apply_shifted_exposure,
    apply_target_exposure,
)
from src.riskbex.backtesting.metrics import (
    compute_drawdown,
    compute_strategy_metrics,
)
from src.riskbex.data.loaders import (
    load_clean_regime_dataset,
    load_regime_exposure_mapping,
)
from src.riskbex.paths import PROCESSED_DATA_DIR


BACKTEST_MAIN_PATH = PROCESSED_DATA_DIR / "adaptive_backtest_main.csv"
BACKTEST_ROBUST_PATH = PROCESSED_DATA_DIR / "adaptive_backtest_robust.csv"
BACKTEST_METRICS_PATH = PROCESSED_DATA_DIR / "adaptive_backtest_metrics.csv"

SAMPLE_CONFIG = {
    "main": {
        "split_column": "sample_split_main",
        "output_path": BACKTEST_MAIN_PATH,
        "sample_label": "MAIN",
    },
    "robust": {
        "split_column": "sample_split_robust",
        "output_path": BACKTEST_ROBUST_PATH,
        "sample_label": "ROBUST",
    },
}

BACKTEST_BASE_COLUMNS = [
    "date",
    "ret_1d",
    "regime",
    "regime_label",
    "risk_order",
    "p_regime_0",
    "p_regime_1",
    "p_regime_2",
    "target_exposure",
    "strategy_exposure",
    "benchmark_return",
    "strategy_return",
    "benchmark_cum",
    "strategy_cum",
    "benchmark_drawdown",
    "strategy_drawdown",
]


def _normalize_sample(sample: str) -> str:
    normalized_sample = str(sample).lower()
    if normalized_sample not in SAMPLE_CONFIG:
        raise ValueError("sample must be 'main' or 'robust'")
    return normalized_sample


def _validate_backtest_input(df: pd.DataFrame, split_column: str, sample: str) -> None:
    required_columns = [
        "date",
        "ret_1d",
        split_column,
        "regime",
        "regime_label",
        "risk_order",
        "p_regime_0",
        "p_regime_1",
        "p_regime_2",
    ]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required {sample} backtest input columns: {missing_columns}"
        )


def _filter_oos(df: pd.DataFrame, split_column: str, sample: str) -> pd.DataFrame:
    test_df = df[df[split_column] == "test"].copy()
    if test_df.empty:
        raise ValueError(f"No out-of-sample test rows found for {sample}.")
    return test_df.sort_values("date").reset_index(drop=True)


def run_regime_backtest(sample: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalized_sample = _normalize_sample(sample)
    config = SAMPLE_CONFIG[normalized_sample]
    split_column = config["split_column"]
    sample_label = config["sample_label"]

    regime_df = load_clean_regime_dataset(normalized_sample)
    mapping_df = load_regime_exposure_mapping(normalized_sample)
    _validate_backtest_input(regime_df, split_column, normalized_sample)

    backtest_df = _filter_oos(regime_df, split_column, normalized_sample)
    backtest_df = apply_target_exposure(backtest_df, mapping_df)
    backtest_df = apply_shifted_exposure(backtest_df)

    backtest_df["benchmark_return"] = backtest_df["ret_1d"]
    backtest_df["strategy_return"] = (
        backtest_df["strategy_exposure"] * backtest_df["ret_1d"]
    )
    backtest_df["benchmark_cum"] = np.exp(backtest_df["benchmark_return"].cumsum())
    backtest_df["strategy_cum"] = np.exp(backtest_df["strategy_return"].cumsum())
    backtest_df["benchmark_drawdown"] = compute_drawdown(backtest_df["benchmark_cum"])
    backtest_df["strategy_drawdown"] = compute_drawdown(backtest_df["strategy_cum"])

    output_columns = [
        "date",
        "ret_1d",
        split_column,
        *BACKTEST_BASE_COLUMNS[2:],
    ]
    backtest_df = backtest_df[output_columns]

    metrics_df = pd.DataFrame(
        [
            compute_strategy_metrics(
                returns=backtest_df["benchmark_return"],
                cumulative_returns=backtest_df["benchmark_cum"],
                drawdown=backtest_df["benchmark_drawdown"],
                strategy="Buy & Hold",
                sample=sample_label,
                dates=backtest_df["date"],
            ),
            compute_strategy_metrics(
                returns=backtest_df["strategy_return"],
                cumulative_returns=backtest_df["strategy_cum"],
                drawdown=backtest_df["strategy_drawdown"],
                strategy="Regime Strategy",
                sample=sample_label,
                dates=backtest_df["date"],
            ),
        ]
    )
    return backtest_df, metrics_df


def run_all_regime_backtests() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    main_df, main_metrics_df = run_regime_backtest("main")
    robust_df, robust_metrics_df = run_regime_backtest("robust")
    metrics_df = pd.concat([main_metrics_df, robust_metrics_df], ignore_index=True)
    return main_df, robust_df, metrics_df


def save_backtest_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    main_df, robust_df, metrics_df = run_all_regime_backtests()
    main_df.to_csv(BACKTEST_MAIN_PATH, index=False)
    robust_df.to_csv(BACKTEST_ROBUST_PATH, index=False)
    metrics_df.to_csv(BACKTEST_METRICS_PATH, index=False)
    return main_df, robust_df, metrics_df

