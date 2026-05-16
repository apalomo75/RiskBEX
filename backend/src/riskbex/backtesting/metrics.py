import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def compute_drawdown(cumulative_returns: pd.Series) -> pd.Series:
    rolling_max = cumulative_returns.cummax()
    return cumulative_returns / rolling_max - 1


def historical_var(returns: pd.Series, alpha: float = 0.05) -> float:
    return float(returns.quantile(alpha))


def historical_cvar(returns: pd.Series, alpha: float = 0.05) -> float:
    var_95 = historical_var(returns, alpha=alpha)
    tail_returns = returns[returns <= var_95]
    return float(tail_returns.mean())


def compute_strategy_metrics(
    returns: pd.Series,
    cumulative_returns: pd.Series,
    drawdown: pd.Series,
    strategy: str,
    sample: str,
    dates: pd.Series,
) -> dict:
    if returns.empty:
        raise ValueError(f"No returns available to compute metrics for {sample} {strategy}.")

    parsed_dates = pd.to_datetime(dates)
    return {
        "sample": sample,
        "strategy": strategy,
        "total_return": float(cumulative_returns.iloc[-1] - 1),
        "mean_daily_return": float(returns.mean()),
        "daily_volatility": float(returns.std()),
        "annualized_volatility": float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)),
        "VaR_95": historical_var(returns, alpha=0.05),
        "CVaR_95": historical_cvar(returns, alpha=0.05),
        "max_drawdown": float(drawdown.min()),
        "n_observations": int(len(returns)),
        "start_date": parsed_dates.min().date().isoformat(),
        "end_date": parsed_dates.max().date().isoformat(),
    }

