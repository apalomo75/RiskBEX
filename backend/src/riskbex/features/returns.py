import numpy as np
import pandas as pd


def compute_log_returns(price_series: pd.Series) -> pd.Series:
    return np.log(price_series / price_series.shift(1))


def compute_rolling_return(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window=window, min_periods=window).sum()


def compute_risk_adjusted_return(
    rolling_return: pd.Series,
    rolling_vol: pd.Series,
) -> pd.Series:
    risk_adjusted_return = rolling_return / rolling_vol
    return risk_adjusted_return.replace([np.inf, -np.inf], np.nan)
