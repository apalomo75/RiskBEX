import numpy as np
import pandas as pd


def downside_volatility(series: pd.Series) -> float:
    negative_returns = series[series < 0]
    if len(negative_returns) == 0:
        return np.nan
    return negative_returns.std(ddof=1)


def compute_downside_volatility(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window=window).apply(
        downside_volatility,
        raw=False,
    )
