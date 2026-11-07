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
    frame = data['features'].merge(regime_points(data)[['date', 'regime_label']], on='date', validate='one_to_one')
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
