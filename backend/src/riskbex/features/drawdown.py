import pandas as pd


def compute_drawdown(price_series: pd.Series) -> pd.Series:
    return price_series / price_series.cummax() - 1.0
