import numpy as np
import pandas as pd

from src.riskbex.data.loaders import load_adaptive_backtest_results
from src.riskbex.paths import PROCESSED_DATA_DIR
from src.riskbex.tail_risk.tail_events import (
    add_tail_event_flag,
    compute_tail_threshold,
    validate_tail_events,
)
from src.riskbex.tail_risk.tail_metrics import (
    compute_tail_cumulative_returns,
    compute_tail_metrics,
)


TAIL_ANALYSIS_MAIN_PATH = PROCESSED_DATA_DIR / "tail_analysis_main.csv"
TAIL_ANALYSIS_ROBUST_PATH = PROCESSED_DATA_DIR / "tail_analysis_robust.csv"
TAIL_METRICS_PATH = PROCESSED_DATA_DIR / "tail_metrics.csv"
TAIL_THRESHOLDS_PATH = PROCESSED_DATA_DIR / "tail_thresholds.csv"

TAIL_QUANTILE = 0.05

SAMPLE_CONFIG = {
    "main": {
        "sample_label": "MAIN",
        "output_path": TAIL_ANALYSIS_MAIN_PATH,
    },
    "robust": {
        "sample_label": "ROBUST",
        "output_path": TAIL_ANALYSIS_ROBUST_PATH,
    },
}

TAIL_ANALYSIS_COLUMNS = [
    "date",
    "sample",
    "ret_1d",
    "stress_tail_event",
    "tail_threshold",
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
    "benchmark_tail_cum",
    "strategy_tail_cum",
]


def _normalize_sample(sample: str) -> str:
    normalized_sample = str(sample).lower()
    if normalized_sample not in SAMPLE_CONFIG:
        raise ValueError("sample must be 'main' or 'robust'")
    return normalized_sample


def _validate_backtest_results(df: pd.DataFrame, sample: str) -> None:
    required_columns = [
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
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required {sample} adaptive backtest columns: {missing_columns}"
        )
    if df.empty:
        raise ValueError(f"{sample} adaptive backtest results are empty.")
    if df["date"].isna().any():
        raise ValueError(f"{sample} adaptive backtest results have invalid dates.")
    if df["date"].duplicated().any():
        raise ValueError(f"{sample} adaptive backtest results have duplicated dates.")
    if not df["date"].is_monotonic_increasing:
        raise ValueError(f"{sample} adaptive backtest dates are not sorted.")
    for column in ["ret_1d", "benchmark_return", "strategy_return"]:
        if df[column].isna().any():
            raise ValueError(f"{sample} adaptive backtest results have null {column}.")


def _add_tail_cumulative_columns(df: pd.DataFrame) -> pd.DataFrame:
    output_df = df.copy()
    output_df["benchmark_tail_cum"] = np.nan
    output_df["strategy_tail_cum"] = np.nan
    tail_mask = output_df["stress_tail_event"]
    df_tail = output_df.loc[tail_mask]
    if df_tail.empty:
        raise ValueError("Cannot compute tail cumulative returns without tail events.")

    # Tail cumulative returns are only defined on stress days in v1. Non-tail rows
    # remain NaN to avoid confusing this series with the full backtest trajectory.
    output_df.loc[tail_mask, "benchmark_tail_cum"] = compute_tail_cumulative_returns(
        df_tail["benchmark_return"]
    ).to_numpy()
    output_df.loc[tail_mask, "strategy_tail_cum"] = compute_tail_cumulative_returns(
        df_tail["strategy_return"]
    ).to_numpy()
    return output_df


def _build_threshold_row(
    analysis_df: pd.DataFrame,
    sample_label: str,
    threshold: float,
    tail_share: float,
) -> dict:
    dates = pd.to_datetime(analysis_df["date"])
    return {
        "sample": sample_label,
        "threshold_quantile": TAIL_QUANTILE,
        "tail_threshold": float(threshold),
        "n_observations": int(len(analysis_df)),
        "n_tail_events": int(analysis_df["stress_tail_event"].sum()),
        "tail_share": float(tail_share),
        "start_date": dates.min().date().isoformat(),
        "end_date": dates.max().date().isoformat(),
        "worst_market_return": float(analysis_df["ret_1d"].min()),
    }


def run_tail_analysis(sample: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    normalized_sample = _normalize_sample(sample)
    sample_label = SAMPLE_CONFIG[normalized_sample]["sample_label"]

    backtest_df = load_adaptive_backtest_results(normalized_sample)
    _validate_backtest_results(backtest_df, normalized_sample)

    threshold = compute_tail_threshold(backtest_df, quantile=TAIL_QUANTILE)
    analysis_df = add_tail_event_flag(backtest_df, threshold)
    validate_tail_events(analysis_df)
    analysis_df["sample"] = sample_label
    analysis_df["tail_threshold"] = threshold
    analysis_df = _add_tail_cumulative_columns(analysis_df)
    analysis_df = analysis_df[TAIL_ANALYSIS_COLUMNS]

    df_tail = analysis_df[analysis_df["stress_tail_event"]].copy()
    if df_tail.empty:
        raise ValueError(f"No tail events found for {sample_label}.")
    tail_share = len(df_tail) / len(analysis_df)

    threshold_df = pd.DataFrame(
        [_build_threshold_row(analysis_df, sample_label, threshold, tail_share)]
    )
    metrics_df = pd.DataFrame(
        [
            compute_tail_metrics(
                df_tail=df_tail,
                return_column="benchmark_return",
                drawdown_column="benchmark_drawdown",
                strategy="Buy & Hold",
                sample=sample_label,
                tail_threshold=threshold,
                tail_share=tail_share,
            ),
            compute_tail_metrics(
                df_tail=df_tail,
                return_column="strategy_return",
                drawdown_column="strategy_drawdown",
                strategy="Regime Strategy",
                sample=sample_label,
                tail_threshold=threshold,
                tail_share=tail_share,
            ),
        ]
    )
    return analysis_df, metrics_df, threshold_df


def run_all_tail_analyses() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    main_analysis_df, main_metrics_df, main_threshold_df = run_tail_analysis("main")
    robust_analysis_df, robust_metrics_df, robust_threshold_df = run_tail_analysis("robust")
    metrics_df = pd.concat([main_metrics_df, robust_metrics_df], ignore_index=True)
    thresholds_df = pd.concat([main_threshold_df, robust_threshold_df], ignore_index=True)
    return main_analysis_df, robust_analysis_df, metrics_df, thresholds_df


def save_tail_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    main_analysis_df, robust_analysis_df, metrics_df, thresholds_df = run_all_tail_analyses()
    main_analysis_df.to_csv(TAIL_ANALYSIS_MAIN_PATH, index=False)
    robust_analysis_df.to_csv(TAIL_ANALYSIS_ROBUST_PATH, index=False)
    metrics_df.to_csv(TAIL_METRICS_PATH, index=False)
    thresholds_df.to_csv(TAIL_THRESHOLDS_PATH, index=False)
    return main_analysis_df, robust_analysis_df, metrics_df, thresholds_df

