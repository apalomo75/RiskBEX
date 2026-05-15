import numpy as np
import pandas as pd


def historical_var(series: np.ndarray, alpha: float) -> float:
    return np.quantile(series, alpha)


def historical_cvar(series: np.ndarray, alpha: float) -> float:
    var_threshold = np.quantile(series, alpha)
    tail_losses = series[series <= var_threshold]
    return tail_losses.mean() if len(tail_losses) > 0 else np.nan


def compute_historical_var(
    returns: pd.Series,
    window: int,
    alpha: float,
) -> pd.Series:
    return returns.rolling(window=window, min_periods=window).apply(
        lambda x: historical_var(x, alpha),
        raw=True,
    )


def compute_historical_cvar(
    returns: pd.Series,
    window: int,
    alpha: float,
) -> pd.Series:
    return returns.rolling(window=window, min_periods=window).apply(
        lambda x: historical_cvar(x, alpha),
        raw=True,
    )
