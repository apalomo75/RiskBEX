"""TFM financial indicators from prices, reusing the existing feature functions."""

from src.riskbex.features.downside import compute_downside_volatility
from src.riskbex.features.drawdown import compute_drawdown
from src.riskbex.features.returns import compute_log_returns, compute_rolling_return
from src.riskbex.features.tail_risk import compute_historical_cvar, compute_historical_var
from src.riskbex.features.volatility import compute_ewma_volatility
from src.riskbex.ml.data import dated_frame, numeric_values


def compute_market_features(prices):
    """The first price is return context only, excluded before EWMA/drawdown.

    This matches notebook 01 dropping its initial undefined return before the
    notebook 02 indicators. Warmup NaNs are retained for the engine to validate.
    """
    frame = dated_frame(prices)
    numeric_values(frame, ["ibex_close"])
    if not frame["ibex_close"].gt(0).all() or len(frame) < 2:
        raise ValueError("At least two strictly positive closing prices are required.")
    frame = frame[["date", "ibex_close"]].copy()
    frame["ret_1d"] = compute_log_returns(frame["ibex_close"])
    frame = frame.iloc[1:].reset_index(drop=True)
    returns = frame["ret_1d"]
    for window in [20, 60]:
        frame[f"ret_{window}d"] = compute_rolling_return(returns, window)
        frame[f"vol_{window}d"] = returns.rolling(window, min_periods=window).std(ddof=1)
        frame[f"downside_vol_{window}d"] = compute_downside_volatility(returns, window)
    frame["ewma_vol"] = compute_ewma_volatility(returns, .94)
    frame["var_95_60d"] = compute_historical_var(returns, 60, .05)
    frame["cvar_95_60d"] = compute_historical_cvar(returns, 60, .05)
    frame["drawdown"] = compute_drawdown(frame["ibex_close"])
    frame["skew_60d"] = returns.rolling(60, min_periods=60).skew()
    return frame
