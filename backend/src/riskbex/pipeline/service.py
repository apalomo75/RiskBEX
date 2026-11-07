"""Daily MAIN orchestration. No fit, scheduling, UI writes or legacy CSV replacement."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from src.riskbex.engine.package import canonical_price_hash, verify_main_package
from src.riskbex.engine.service import infer_main_signals, implementation_hashes, prepare_price_history
from src.riskbex.pipeline.history import build_history
from src.riskbex.pipeline.provider import merge_new_sessions, validate_prices
from src.riskbex.pipeline.store import digest


def pipeline_hashes():
    result = implementation_hashes()
    root = Path(__file__).parent
    result.update({f'pipeline/{p.name}': digest(p) for p in sorted(root.glob('*.py'))})
    for name in ['costs.py', 'metrics.py', 'ml_backtest.py']:
        result[f'backtesting/{name}'] = digest(root.parent / 'backtesting' / name)
    return result


def verify_gate(path, package):
    gate = json.loads(Path(path).read_text())
    if gate.get('status') != 'passed' or gate.get('model_manifest_sha256') != package.manifest_sha256:
        raise ValueError('Missing successful quantitative regression for this model package.')
    if gate.get('implementation_sha256') != pipeline_hashes():
        raise ValueError('Regression receipt is stale: implementation changed.')
    return gate


def update_main(package, seed, provider, calendar, store, *, now, regression_receipt):
    now = pd.Timestamp(now)
    if now.tz is None:
        raise ValueError('now must be timezone-aware.')
    # A concurrency rejection must not overwrite the active process status.
    with store.lock():
        attempt = {'generated_at': now.isoformat(), 'source': provider.source, 'status': 'running',
                   'package_id': package.manifest['package_id'],
                   'model_manifest_sha256': package.manifest_sha256,
                   'model_hashes': {name: entry['sha256'] for name, entry in package.manifest['files'].items()},
                   'data_date': None, 'last_signal_date': None, 'new_sessions': None, 'downloaded_at': None}
        try:
            gate = verify_gate(regression_receipt, package)
            verify_main_package(package.root, check_runtime=True)
            current = store.current()
            history = (pd.read_csv(current / 'prices.csv', float_precision='round_trip')
                       if current else seed.copy())
            history = validate_prices(history)
            prepare_price_history(package, history)  # frozen training hash, before any network call
            eligible = calendar.eligible(now)
            last = history.date.iloc[-1]
            attempt.update(data_date=last.date().isoformat(), last_signal_date=last.date().isoformat())
            overlap_start = last - pd.Timedelta(days=10)
            # Coverage and next-session checks happen before contacting the provider.
            calendar.sessions(overlap_start, eligible)
            target = calendar.next_session(eligible)
            fetched = provider.fetch(overlap_start, eligible)
            attempt['downloaded_at'] = now.isoformat()
            combined, new_count = merge_new_sessions(history, fetched, calendar, eligible, overlap_start)
            if combined.date.iloc[-1] != eligible:
                raise ValueError('Latest eligible close missing: cannot publish a current signal.')
            data_hash = canonical_price_hash(combined)
            version = hashlib.sha256(json.dumps({'data': data_hash, 'model': package.manifest_sha256,
                      'code': pipeline_hashes(), 'calendar': calendar.digest}, sort_keys=True).encode()).hexdigest()
            if current and current.name == version:
                attempt.update(status='unchanged', data_date=last.date().isoformat(), new_sessions=0,
                               version=version, last_signal_date=last.date().isoformat())
                store.status(attempt)
                return attempt
            tables = build_history(package, combined)
            latest = infer_main_signals(package, combined)
            date = eligible.date().isoformat()
            latest.update(generated_at=now.isoformat(), target_session_date=target.date().isoformat(),
                          freshness={'status': 'current_at_generation', 'expected_data_date': date,
                                     'checked_at': now.isoformat(), 'calendar_id': calendar.config['calendar_id']})
            latest['provenance'].update(source=provider.source, live_market_freshness_verified=bool(getattr(provider, 'is_live', False)),
                                         source_mode='live' if getattr(provider, 'is_live', False) else 'offline_simulation',
                                         operational_version=version)
            # Batch history and single-observation inference must agree before promotion.
            row = tables['signals'].iloc[-1]
            for key, column in [('regime_based', 'target_exposure_regime_based'),
                                ('ml_hard', 'target_exposure_ml_hard'),
                                ('ml_probability_weighted', 'target_exposure_ml_proba')]:
                if abs(latest['target_exposures'][key] - float(row[column])) > 1e-12:
                    raise ValueError('Batch and latest signal disagree.')
            manifest = {'schema_version': 1, 'engine': 'MAIN', 'status': 'validated', 'version': version,
                        'data_date': date, 'downloaded_at': now.isoformat(), 'generated_at': now.isoformat(),
                        'source': provider.source, 'new_sessions': new_count, 'last_signal_date': date,
                        'target_session_date': target.date().isoformat(), 'package_id': latest['package_id'],
                        'model_manifest_sha256': package.manifest_sha256,
                        'model_hashes': latest['provenance']['component_sha256'],
                        'implementation_sha256': pipeline_hashes(), 'price_sha256': data_hash,
                        'calendar_sha256': calendar.digest, 'calendar': calendar.config,
                        'regression_receipt_sha256': digest(regression_receipt),
                        'provenance': 'frozen MAIN parameters; causal-v1 predictions; training-only CVaR; no fit',
                        'cost_rate': .001, 'return_convention': 'log; target(t-1) times return(t); first OOS dropped',
                        'previous_version': current.name if current else None}
            store.publish(dict(prices=combined, **tables), latest, manifest, version)
            attempt.update(status='published', version=version, data_date=date, new_sessions=new_count,
                           last_signal_date=date)
            store.status(attempt)
            return attempt
        except Exception as exc:
            attempt.update(status='failed', error_type=type(exc).__name__, error=str(exc))
            try:
                store.status(attempt)
            except OSError:
                pass  # Existing current pointer remains authoritative even if status disk is unavailable.
            raise
