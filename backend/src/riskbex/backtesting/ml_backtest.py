"""Replay the notebook 06 ML strategies using frozen or newly inferred signals."""

import numpy as np
import pandas as pd

from src.riskbex.backtesting.costs import add_transaction_costs, summarize_returns, summarize_turnover
from src.riskbex.backtesting.exposures import (
    apply_shifted_exposure, apply_target_exposure, build_cvar_exposure_mapping,
)
from src.riskbex.backtesting.metrics import compute_drawdown
from src.riskbex.ml.config import SAMPLES, normalize_sample
from src.riskbex.ml.data import numeric_values
from src.riskbex.ml.inference import validate_predictions


def run_ml_backtest(predictions, mapping, sample, *, cost_rate=0.001):
    """Return wide daily results, gross/net metrics and turnover; never write CSV.

    Targets are built at t from predictions for t+1. Exposure is shifted once
    inside OOS and the first OOS row is dropped, matching the TFM convention.
    regime_t_plus_1 is evaluation-only and never read to form a position.
    """
    name = normalize_sample(sample)
    output = validate_predictions(predictions)
    numeric_values(output, ["ret_1d"])
    split_column = SAMPLES[name]["split_column"]
    if split_column not in output:
        raise ValueError(f"Missing explicit sample partition: {split_column}")
    expected = np.where(output["date"] < pd.Timestamp(SAMPLES[name]["test_start"]), "train", "test")
    if not output[split_column].eq(expected).all():
        raise ValueError("Stored partition disagrees with sample dates.")
    output = output.loc[output[split_column] == "test"].copy().reset_index(drop=True)
    if len(output) < 2:
        raise ValueError("At least two OOS predictions are needed for the operational shift.")
    if len(mapping) != 3 or set(mapping["regime"]) != {0, 1, 2}:
        raise ValueError("Exposure mapping must cover exactly the three regime IDs.")
    provenance = ["methodology", "defensive_alpha", "mean_cvar_95_60d"]
    if not set(provenance) <= set(mapping.columns):
        raise ValueError("ML requires the CVaR train mapping from Sprint 1A, not legacy fixed exposures.")
    if not mapping["methodology"].eq("CVaR_train_abs_ratio").all():
        raise ValueError("Unknown exposure methodology.")
    numeric_values(mapping, ["defensive_alpha"])
    if mapping["defensive_alpha"].nunique() != 1:
        raise ValueError("All regimes must share the same defensive alpha.")
    numeric_values(mapping, ["target_exposure"])
    reconstructed = build_cvar_exposure_mapping(mapping, mapping["defensive_alpha"].iloc[0])
    stored = mapping.set_index("regime")["target_exposure"].reindex(reconstructed["regime"])
    if not np.allclose(stored, reconstructed["target_exposure"], atol=1e-12, rtol=1e-10):
        raise ValueError("Stored target exposures disagree with the CVaR training ratio.")
    numeric_values(mapping, ["target_exposure"])
    if not mapping["target_exposure"].between(0, 1).all():
        raise ValueError("Target exposures must lie in [0, 1].")
    hard = apply_target_exposure(pd.DataFrame({"regime": output["regime_pred"]}), mapping)
    output["target_exposure_ml_hard"] = hard["target_exposure"].to_numpy()
    output["target_exposure_ml_proba"] = 0.
    # Preserve notebook summation order (economic mapping order, not numeric IDs).
    for row in mapping.itertuples():
        output["target_exposure_ml_proba"] += output[f"proba_{int(row.regime)}"] * row.target_exposure
    if not output["target_exposure_ml_proba"].between(0, 1).all():
        raise ValueError("Probability-weighted exposure is outside [0, 1].")
    shifted = {}
    for key in ["hard", "proba"]:
        shifted[key] = apply_shifted_exposure(pd.DataFrame({
            "target_exposure": output[f"target_exposure_ml_{key}"]
        }))["strategy_exposure"].to_numpy()
    output = output.iloc[1:].reset_index(drop=True)
    output["benchmark_return"] = output["ret_1d"]
    output["benchmark_cum"] = np.exp(output["benchmark_return"].cumsum())
    output["benchmark_drawdown"] = compute_drawdown(output["benchmark_cum"])
    metrics = [summarize_returns(output["benchmark_return"], output["date"],
                                  sample=name, strategy="Buy & Hold")]
    turnover = []
    for key, label in [("hard", "ML Hard"), ("proba", "ML Probability-Weighted")]:
        exposure_column = f"strategy_exposure_ml_{key}"
        return_column = f"ml_{key}_return"
        output[exposure_column] = shifted[key]
        output[return_column] = output[exposure_column] * output["ret_1d"]
        output[f"ml_{key}_cum"] = np.exp(output[return_column].cumsum())
        output[f"ml_{key}_drawdown"] = compute_drawdown(output[f"ml_{key}_cum"])
        costs = add_transaction_costs(output, exposure_column=exposure_column,
                                     return_column=return_column, cost_rate=cost_rate)
        for source, destination in [
            ("exposure_change", f"exposure_change_ml_{key}"),
            ("transaction_cost", f"transaction_cost_ml_{key}"),
            ("strategy_return_net", f"ml_{key}_return_net"),
        ]:
            output[destination] = costs[source]
        metrics.extend([
            summarize_returns(output[return_column], output["date"], sample=name,
                              strategy=label + " gross"),
            summarize_returns(output[f"ml_{key}_return_net"], output["date"], sample=name,
                              strategy=label + " net of costs", cost_rate=cost_rate,
                              total_cost=costs["transaction_cost"].sum()),
        ])
        turnover.append(summarize_turnover(
            costs["exposure_change"], sample=name,
            strategy="ML Hard Classification" if key == "hard" else label, cost_rate=cost_rate,
        ))
    return output, pd.DataFrame(metrics), pd.DataFrame(turnover)


def select_ml_strategy(results, strategy):
    """Internal adapter for future routes, without repurposing Markov probability fields."""
    if strategy not in {"buy_hold", "ml_hard", "ml_proba"}:
        raise ValueError("strategy must be buy_hold, ml_hard or ml_proba")
    output = results.copy()
    output["strategy"] = strategy
    if strategy == "buy_hold":
        output["target_exposure"] = 1.
        output["strategy_exposure"] = 1.
        source = "benchmark"
    else:
        key = strategy.removeprefix("ml_")
        output["target_exposure"] = output[f"target_exposure_ml_{key}"]
        output["strategy_exposure"] = output[f"strategy_exposure_ml_{key}"]
        source = strategy
    for destination, suffix in [("strategy_return", "return"), ("strategy_cum", "cum"),
                                ("strategy_drawdown", "drawdown")]:
        output[destination] = output[f"{source}_{suffix}"]
    return output


def compare_on_common_dates(ml_results, regime_results, sample):
    """Recompute all four strategies on exactly the same dates, with explicit exclusions."""
    from src.riskbex.ml.data import dated_frame

    ml = dated_frame(ml_results)
    regime = dated_frame(regime_results)
    reference = regime[["date", "ret_1d", "strategy_return"]].rename(columns={
        "ret_1d": "regime_market_return", "strategy_return": "regime_strategy_return",
    })
    common = ml.merge(reference, on="date", how="inner", validate="one_to_one")
    if common.empty or not np.allclose(common["ret_1d"], common["regime_market_return"],
                                       atol=1e-12, rtol=1e-10):
        raise ValueError("No common dates or market returns disagree on common dates.")
    rows = []
    for label, column in [("Buy & Hold", "benchmark_return"), ("Regime-based", "regime_strategy_return"),
                          ("ML Hard", "ml_hard_return"), ("ML Probability-weighted", "ml_proba_return")]:
        rows.append(summarize_returns(common[column], common["date"], sample=sample, strategy=label))
    exclusions = {
        "ml_only_dates": ml.loc[~ml["date"].isin(common["date"]), "date"].dt.strftime("%Y-%m-%d").tolist(),
        "regime_only_dates": regime.loc[~regime["date"].isin(common["date"]), "date"].dt.strftime("%Y-%m-%d").tolist(),
    }
    return pd.DataFrame(rows), exclusions
