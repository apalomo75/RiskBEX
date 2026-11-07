"""TFM notebook 06 cost/turnover conventions, independent of output files."""

import numpy as np
import pandas as pd

from src.riskbex.backtesting.metrics import compute_drawdown, compute_strategy_metrics
from src.riskbex.ml.data import numeric_values


def add_transaction_costs(frame, *, exposure_column, return_column, cost_rate=0.001):
    if not np.isfinite(cost_rate) or cost_rate < 0:
        raise ValueError("cost_rate must be finite and nonnegative.")
    numeric_values(frame, [exposure_column, return_column])
    if not frame[exposure_column].between(0, 1).all():
        raise ValueError("Executed exposure must lie in [0, 1].")
    output = frame.copy()
    output["exposure_change"] = output[exposure_column].diff().abs().fillna(0.)
    output["transaction_cost"] = cost_rate * output["exposure_change"]
    output["strategy_return_net"] = output[return_column] - output["transaction_cost"]
    return output


def summarize_turnover(changes, *, sample, strategy, cost_rate=0.001, threshold=0.01):
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Effective turnover threshold must be finite and nonnegative.")
    changes = changes.fillna(0.)
    return {
        "sample": sample.upper(), "strategy": strategy, "cost_rate": cost_rate,
        "turnover_threshold": threshold, "total_turnover": float(changes.sum()),
        "average_daily_turnover": float(changes.mean()),
        "annualized_turnover": float(changes.mean() * 252),
        "mean_abs_change": float(changes.mean()), "median_abs_change": float(changes.median()),
        "raw_changes": int((changes > 0).sum()),
        "effective_changes": int((changes > threshold).sum()), "n_observations": len(changes),
    }


def summarize_returns(returns, dates, *, sample, strategy, cost_rate=0., total_cost=0.):
    if returns.empty or not np.isfinite(returns.to_numpy(dtype=float)).all():
        raise ValueError("Metrics require nonempty finite returns.")
    cumulative = np.exp(returns.cumsum())
    row = compute_strategy_metrics(returns, cumulative, compute_drawdown(cumulative),
                                   strategy, sample.upper(), dates)
    vol = row["daily_volatility"]
    cvar = row["CVaR_95"]
    row.update({
        "sharpe_ratio": np.nan if np.isclose(vol, 0.) else row["mean_daily_return"] / vol * np.sqrt(252),
        "return_cvar_ratio": np.nan if np.isclose(cvar, 0.) else row["total_return"] / abs(cvar),
        "cost_rate": cost_rate, "total_transaction_cost": float(total_cost),
    })
    return row
