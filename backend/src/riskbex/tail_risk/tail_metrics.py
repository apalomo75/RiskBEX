import numpy as np
import pandas as pd


def historical_var(returns: pd.Series, alpha: float = 0.05) -> float:
    if returns.empty:
        raise ValueError("Cannot compute historical VaR from empty returns.")
    return float(returns.quantile(alpha))


def historical_cvar(returns: pd.Series, alpha: float = 0.05) -> float:
    var_value = historical_var(returns, alpha=alpha)
    tail_returns = returns[returns <= var_value]
    if tail_returns.empty:
        raise ValueError("Cannot compute historical CVaR from empty tail returns.")
    return float(tail_returns.mean())


def compute_tail_cumulative_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        raise ValueError("Cannot compute tail cumulative returns from empty returns.")
    return np.exp(returns.cumsum())


def compute_tail_metrics(
    df_tail: pd.DataFrame,
    return_column: str,
    drawdown_column: str,
    strategy: str,
    sample: str,
    tail_threshold: float,
    tail_share: float,
) -> dict:
    required_columns = [return_column, drawdown_column]
    missing_columns = [column for column in required_columns if column not in df_tail.columns]
    if missing_columns:
        raise ValueError(f"Missing required tail metric columns: {missing_columns}")
    if df_tail.empty:
        raise ValueError(f"No tail events available for {sample} {strategy}.")

    returns = df_tail[return_column].dropna()
    if returns.empty:
        raise ValueError(f"No returns available for {sample} {strategy}.")

    tail_cum = compute_tail_cumulative_returns(returns)
    return {
        "sample": sample,
        "strategy": strategy,
        "n_tail_events": int(len(returns)),
        "tail_threshold": float(tail_threshold),
        "tail_share": float(tail_share),
        "mean_tail_return": float(returns.mean()),
        "median_tail_return": float(returns.median()),
        "min_tail_return": float(returns.min()),
        "tail_volatility": float(returns.std()),
        "tail_total_return": float(tail_cum.iloc[-1] - 1),
        "tail_VaR_95": historical_var(returns, alpha=0.05),
        "tail_CVaR_95": historical_cvar(returns, alpha=0.05),
        "max_backtest_drawdown_on_tail_days": float(df_tail[drawdown_column].min()),
        "hit_ratio_negative": float((returns < 0).mean()),
    }

