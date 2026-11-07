"""Read-only request snapshots of validated MAIN publications; never infer or train."""
import os
from pathlib import Path
import pandas as pd
from fastapi import HTTPException
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.loaders import load_operational_results

BACKEND = Path(__file__).resolve().parents[3]


def utc_now():
    return pd.Timestamp.now(tz='UTC')


def snapshot():
    root = Path(os.environ.get('RISKBEX_OPERATIONAL_DIR', BACKEND / 'runtime/main'))
    try:
        calendar = SessionCalendar.load(os.environ.get('RISKBEX_CALENDAR', BACKEND / 'config/bme-2026.json'))
        data = load_operational_results(root, calendar=calendar, now=utc_now())
        # Resolve by the already selected manifest, never read current.json a second time.
        directory = root / 'versions' / data['manifest']['version']
        data['features'] = pd.read_csv(directory / 'features.csv', float_precision='round_trip')
        latest = data['latest']
        mode = latest['provenance'].get('source_mode', 'unknown')
        freshness = latest['freshness']['status']
        if mode != 'live' or not latest['provenance'].get('live_market_freshness_verified', False):
            freshness = 'simulated' if mode == 'offline_simulation' else 'historical'
        data['publication'] = {
            'version': data['manifest']['version'], 'model_version': latest['package_id'],
            'model_manifest_sha256': data['manifest']['model_manifest_sha256'],
            'data_date': latest['last_valid_session'], 'generated_at': latest['generated_at'],
            'last_successful_update': latest['generated_at'],
            'target_session_date': latest['target_session_date'], 'source_mode': mode,
            'freshness': freshness, 'is_current': freshness == 'current',
            'expected_data_date': latest['freshness']['expected_data_date'],
            'update_status': data['update_status'],
        }
        return data
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(status_code=503, detail='No usable validated MAIN publication is available.') from exc


def regime_points(data):
    frame = data['history'].copy()
    frame['split'] = 'MAIN'
    frame['regime_label'] = frame['economic_label']
    frame['risk_order'] = frame.economic_label.map({'low_risk': 1, 'medium_risk': 2, 'high_risk': 3})
    frame['publication'] = [data['publication']] * len(frame)
    return frame


def risk_points(data):
    signals = regime_points(data).copy()
    optional = {'xgboost_regime':'regime_pred','xgboost_probability_0':'proba_0',
      'xgboost_probability_1':'proba_1','xgboost_probability_2':'proba_2',
      'target_exposure_regime_based':'target_exposure_regime_based',
      'target_exposure_ml_hard':'target_exposure_ml_hard',
      'target_exposure_ml_probability_weighted':'target_exposure_ml_proba'}
    cols = ['date','regime','regime_label','economic_label','p_regime_0','p_regime_1','p_regime_2']
    cols += [c for c in optional.values() if c in signals]
    signals = signals[cols].rename(columns={v:k for k,v in optional.items() if v in signals})
    frame = data['features'].merge(signals, on='date', validate='one_to_one')
    frame['information_date'] = frame['date'].astype(str)
    frame['model_version'] = data['publication']['model_version']
    frame['next_session_date'] = None
    # The frozen engine does not publish the legacy heuristic score. Do not invent one.
    frame['risk_score'] = None
    frame['risk_level'] = frame.regime_label
    frame['publication'] = [data['publication']] * len(frame)
    return frame


def backtest_points(data, strategy='regime_based'):
    if strategy not in {'regime_based', 'ml_hard', 'ml_proba'}:
        raise HTTPException(status_code=400, detail='Unknown MAIN strategy.')
    frame = data['backtest'].merge(regime_points(data)[['date', 'regime', 'regime_label', 'risk_order',
                        'p_regime_0', 'p_regime_1', 'p_regime_2', 'target_exposure_regime_based']],
                        on='date', validate='one_to_one')
    # ML targets already exist in backtest; regime target comes from the signal on that date.
    frame['target_exposure'] = frame['target_exposure_'+strategy]
    frame['strategy_exposure'] = frame['strategy_exposure_'+strategy]
    prefix = 'regime_based' if strategy == 'regime_based' else strategy
    for suffix in ['return', 'cum', 'drawdown']:
        frame['strategy_'+suffix] = frame[prefix+'_'+suffix]
    frame['publication'] = [dict(data['publication'], strategy=strategy)] * len(frame)
    return frame


def performance_snapshot(data):
    """Expose stored performance from one verified version, without model inference."""
    import json
    import numpy as np

    try:
        frame, signals, metrics, turnover = (data[k] for k in ['backtest', 'history', 'metrics', 'turnover'])
        if frame.empty or frame.date.tolist() != signals.date.iloc[1:].tolist():
            raise ValueError('Performance and signal dates differ.')
        labels = {'regime_based': 'Regime-based', 'ml_hard': 'ML Hard',
                  'ml_proba': 'ML Probability-Weighted'}
        required_metrics = {'Buy & Hold'} | {label + suffix for label in labels.values()
                                                            for suffix in [' gross', ' net of costs']}
        if set(metrics.strategy) != required_metrics or len(metrics) != 7:
            raise ValueError('Incomplete strategy metrics.')
        if (not metrics.start_date.eq(frame.date.iloc[0]).all()
                or not metrics.end_date.eq(frame.date.iloc[-1]).all()
                or not metrics.n_observations.eq(len(frame)).all()
                or not metrics['sample'].eq('MAIN').all()):
            raise ValueError('Evaluation windows differ.')
        metric_columns = ['total_return', 'annualized_volatility', 'CVaR_95',
                          'max_drawdown', 'total_transaction_cost', 'cost_rate']
        if not np.isfinite(metrics[metric_columns].to_numpy(dtype=float)).all():
            raise ValueError('Incomplete performance metrics.')
        required = ['benchmark_return', 'benchmark_cum', 'benchmark_drawdown']
        for key in labels:
            required += [f'strategy_exposure_{key}', f'{key}_return', f'{key}_cum',
                         f'{key}_drawdown', f'{key}_return_net', f'{key}_cum_net',
                         f'transaction_cost_{key}', f'exposure_change_{key}']
            if not np.allclose(frame[f'strategy_exposure_{key}'],
                               signals[f'target_exposure_{key}'].iloc[:-1], atol=1e-12, rtol=1e-10):
                raise ValueError('Prior-close target alignment differs.')
        if not np.isfinite(frame[required].to_numpy(dtype=float)).all():
            raise ValueError('Incomplete performance series.')
        if len(turnover) != 3 or set(turnover.strategy) != {'Regime-based', 'ML Hard Classification', 'ML Probability-Weighted'}:
            raise ValueError('Incomplete turnover summary.')
        if (not turnover.n_observations.eq(len(frame)).all()
                or not np.isfinite(turnover[['total_turnover', 'annualized_turnover',
                                             'raw_changes', 'effective_changes']].to_numpy(dtype=float)).all()):
            raise ValueError('Incomplete turnover metrics.')
        def records(table):
            return json.loads(table.to_json(orient='records', double_precision=15))
        return {'publication': data['publication'],
                'conventions': {'cost_rate': data['manifest']['cost_rate'],
                                'returns': data['manifest']['return_convention'],
                                'provenance': data['manifest']['provenance']},
                'results': records(frame[['date', *required]]),
                'metrics': records(metrics), 'turnover': records(turnover)}
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        raise HTTPException(status_code=503, detail='The validated publication lacks a complete strategy comparison.') from exc
