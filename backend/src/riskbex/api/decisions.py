"""Read-only historical decision explanations tied to a verified MAIN snapshot."""
import json

import numpy as np
import pandas as pd
from fastapi import HTTPException

from src.riskbex.api.operational import BACKEND
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.store import digest

TARGETS = ['regime_based', 'ml_hard', 'ml_proba']


def decision_snapshot(data):
    try:
        manifest = data['manifest']
        package_root = BACKEND / 'model_packages/main-v1'
        package_path = package_root / 'manifest.json'
        if digest(package_path) != manifest['model_manifest_sha256']:
            raise ValueError('The available model package differs from the publication.')
        package = json.loads(package_path.read_text())
        if package['sample'] != 'main' or package['package_id'] != data['latest']['package_id']:
            raise ValueError('Not the published MAIN package.')
        relative = package['components']['cvar_mapping']
        mapping_path = (package_root / relative).resolve()
        if package_root.resolve() not in mapping_path.parents:
            raise ValueError('Invalid mapping path.')
        expected = package['files'][relative]['sha256']
        if expected != manifest['model_hashes'][relative] or digest(mapping_path) != expected:
            raise ValueError('Mapping integrity differs from the publication.')
        mapping = pd.DataFrame(json.loads(mapping_path.read_text()))
        ordered = mapping.sort_values('risk_order')
        if (len(mapping) != 3 or set(mapping.regime) != {0, 1, 2}
                or ordered.economic_label.tolist() != ['low_risk', 'medium_risk', 'high_risk']
                or ordered.risk_order.tolist() != [1, 2, 3]
                or not mapping.methodology.eq('CVaR_train_abs_ratio').all()
                or not mapping.target_exposure.between(0, 1).all()):
            raise ValueError('Incomplete CVaR mapping.')
        exposure = mapping.set_index('regime').target_exposure
        labels = mapping.set_index('regime').economic_label
        columns = ['date', 'regime', 'regime_pred', 'economic_label',
                   *[f'p_regime_{i}' for i in range(3)], *[f'proba_{i}' for i in range(3)],
                   *[f'target_exposure_{key}' for key in TARGETS]]
        frame = data['history'][columns].copy()
        if frame.empty or not frame.economic_label.eq(frame.regime.map(labels)).all():
            raise ValueError('Missing signals or inconsistent regime labels.')
        for prefix in ['p_regime_', 'proba_']:
            probabilities = frame[[f'{prefix}{i}' for i in range(3)]]
            if (not np.isfinite(probabilities.to_numpy()).all()
                    or not probabilities.ge(0).all().all() or not probabilities.le(1).all().all()
                    or not np.allclose(probabilities.sum(axis=1), 1, atol=1e-6)):
                raise ValueError('Invalid probabilities.')
        reconstructed = [frame.regime.map(exposure), frame.regime_pred.map(exposure),
                         sum(frame[f'proba_{int(k)}'] * v for k, v in exposure.items())]
        for key, expected_target in zip(TARGETS, reconstructed):
            if not np.allclose(frame[f'target_exposure_{key}'], expected_target, atol=1e-12, rtol=1e-10):
                raise ValueError('Historical targets disagree with the published mapping.')
        features = data['features']
        next_dates = pd.Series(features.date.shift(-1).to_numpy(), index=features.date)
        frame['next_session_date'] = frame.date.map(next_dates)
        calendar = SessionCalendar(manifest['calendar'])
        if calendar.digest != manifest['calendar_sha256']:
            raise ValueError('Published calendar integrity differs.')
        final_target = calendar.next_session(frame.date.iloc[-1]).date().isoformat()
        if final_target != data['latest']['target_session_date']:
            raise ValueError('Published final target session differs.')
        frame.loc[frame.index[-1], 'next_session_date'] = final_target
        if frame.next_session_date.isna().any() or not (frame.next_session_date > frame.date).all():
            raise ValueError('Missing subsequent session dates.')
        if 'ibex_close' in features:
            frame = frame.merge(features[['date', 'ibex_close']], on='date', how='left', validate='one_to_one')
        else:
            frame['ibex_close'] = None
        frame['xgboost_economic_label'] = frame.regime_pred.map(labels)
        frame['previous_session_date'] = frame.date.shift(1)
        for key in TARGETS:
            target = frame[f'target_exposure_{key}']
            frame[f'previous_target_{key}'] = target.shift(1)
            change = (target - target.shift(1)) * 100
            change = change.mask(change.abs() < 1e-10, 0.)
            frame[f'change_pp_{key}'] = change
            frame[f'direction_{key}'] = change.map(
                lambda value: 'N/A' if pd.isna(value) else 'Increase' if value > 0 else 'Decrease' if value < 0 else 'Unchanged')
        return {'publication': data['publication'], 'mapping_sha256': expected,
                'mapping': ordered[['regime', 'economic_label', 'risk_order', 'target_exposure']].to_dict(orient='records'),
                'sessions': json.loads(frame.to_json(orient='records', double_precision=15))}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        raise HTTPException(status_code=503, detail='A complete verified MAIN decision history is unavailable.') from exc
