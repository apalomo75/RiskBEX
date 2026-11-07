"""Batch inference and TFM backtest conventions; no future labels are required."""
import numpy as np
import pandas as pd
from src.riskbex.engine.service import prepare_engine_features
from src.riskbex.ml.config import FEATURE_COLUMNS
from src.riskbex.ml.inference import predict_regimes
from src.riskbex.regimes.persistence import filter_frozen_markov
from src.riskbex.backtesting.ml_backtest import run_ml_backtest
from src.riskbex.backtesting.costs import add_transaction_costs, summarize_returns, summarize_turnover


def build_history(package, prices):
    _, features = prepare_engine_features(package, prices)
    states = filter_frozen_markov(package.markov, features[['date', 'ret_1d']], sample='main')
    oos = features.loc[features.date > pd.Timestamp(package.xgboost.trained_through)].copy()
    predictions = predict_regimes(package.xgboost, oos[['date', *FEATURE_COLUMNS]], sample='main')
    # XGBoost emits float32; persisted academic/causal probabilities are float64.
    # Promote before exposure arithmetic so batch and single-signal calculations agree.
    for column in ['proba_0', 'proba_1', 'proba_2']:
        predictions[column] = predictions[column].astype('float64')
    predictions = predictions.merge(oos[['date', 'ret_1d']], on='date', validate='one_to_one')
    predictions['sample_split_main'] = 'test'
    signals = predictions.merge(states, on='date', validate='one_to_one')
    mapping = package.mapping.set_index('regime').target_exposure
    signals['target_exposure_regime_based'] = signals.regime.map(mapping)
    signals['target_exposure_ml_hard'] = signals.regime_pred.map(mapping)
    signals['target_exposure_ml_proba'] = sum(signals[f'proba_{int(row.regime)}'] * row.target_exposure
                                            for row in package.mapping.itertuples())
    backtest, metrics, turnover = run_ml_backtest(predictions, package.mapping, 'main')
    # Targets already mean next-session exposure. Exactly one alignment to realised dates.
    backtest['strategy_exposure_regime_based'] = signals.target_exposure_regime_based.shift(1).iloc[1:].to_numpy()
    backtest['regime_based_return'] = backtest.strategy_exposure_regime_based * backtest.ret_1d
    backtest['regime_based_cum'] = np.exp(backtest.regime_based_return.cumsum())
    backtest['regime_based_drawdown'] = backtest.regime_based_cum / backtest.regime_based_cum.cummax() - 1
    costs = add_transaction_costs(backtest, exposure_column='strategy_exposure_regime_based',
                                 return_column='regime_based_return')
    for source, destination in [('exposure_change', 'exposure_change_regime_based'),
                                ('transaction_cost', 'transaction_cost_regime_based'),
                                ('strategy_return_net', 'regime_based_return_net')]:
        backtest[destination] = costs[source]
    extra = [summarize_returns(backtest.regime_based_return, backtest.date, sample='main', strategy='Regime-based gross'),
             summarize_returns(backtest.regime_based_return_net, backtest.date, sample='main',
                               strategy='Regime-based net of costs', cost_rate=.001,
                               total_cost=backtest.transaction_cost_regime_based.sum())]
    turnover = pd.concat([turnover, pd.DataFrame([summarize_turnover(costs.exposure_change,
                                 sample='main', strategy='Regime-based')])], ignore_index=True)
    metrics = pd.concat([metrics, pd.DataFrame(extra)], ignore_index=True)
    for key in ['regime_based', 'ml_hard', 'ml_proba']:
        backtest[f'{key}_cum_net'] = np.exp(backtest[f'{key}_return_net'].cumsum())
    # Model identities are recorded once in the containing immutable run manifest.
    return {'features': features, 'signals': signals, 'backtest': backtest,
            'metrics': metrics, 'turnover': turnover}
