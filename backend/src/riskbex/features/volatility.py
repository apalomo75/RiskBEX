import numpy as np
import pandas as pd

from src.riskbex.config import EWMA_LAMBDA


def compute_ewma_volatility(
    returns: pd.Series,
    ewma_lambda: float = EWMA_LAMBDA,
) -> pd.Series:
    return np.sqrt(
        returns.pow(2).ewm(alpha=1 - ewma_lambda, adjust=False).mean()
    )
