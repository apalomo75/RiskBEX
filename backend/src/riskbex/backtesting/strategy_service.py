"""Internal entry point for future strategy selectors; existing HTTP contracts stay unchanged."""

import pandas as pd

from src.riskbex.backtesting.ml_backtest import run_ml_backtest, select_ml_strategy
from src.riskbex.backtesting.regime_backtest import run_regime_backtest
from src.riskbex.data.loaders import load_ml_predictions, load_regime_exposure_mapping
from src.riskbex.ml.config import normalize_sample


def get_strategy_backtest(sample, strategy="regime_based"):
    name = normalize_sample(sample)
    if strategy == "regime_based":
        results, metrics = run_regime_backtest(name)
        return results, metrics, pd.DataFrame()
    if strategy not in {"buy_hold", "ml_hard", "ml_proba"}:
        raise ValueError("Unknown strategy selector.")
    predictions = load_ml_predictions(name)
    mapping = load_regime_exposure_mapping(name)
    results, metrics, turnover = run_ml_backtest(predictions, mapping, name)
    labels = {
        "buy_hold": ["Buy & Hold"],
        "ml_hard": ["ML Hard gross", "ML Hard net of costs"],
        "ml_proba": ["ML Probability-Weighted gross", "ML Probability-Weighted net of costs"],
    }
    turnover_label = {
        "buy_hold": None, "ml_hard": "ML Hard Classification", "ml_proba": "ML Probability-Weighted",
    }[strategy]
    selected_turnover = turnover.loc[turnover["strategy"] == turnover_label].copy()
    return (select_ml_strategy(results, strategy),
            metrics[metrics["strategy"].isin(labels[strategy])].copy(), selected_turnover)
