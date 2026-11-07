"""Internal API adapter. Existing HTTP contracts and legacy loaders are unchanged."""
import json
import pandas as pd
from src.riskbex.pipeline.store import VersionStore


def load_operational_results(root, *, calendar, now):
    store = VersionStore(root)
    directory = store.current()  # Resolve once: all files belong to the same immutable version.
    if directory is None:
        raise FileNotFoundError('No validated MAIN publication is available.')
    latest = json.loads((directory / 'latest.json').read_text())
    eligible = calendar.eligible(now).date().isoformat()
    latest['freshness'] = dict(latest['freshness'], status='current' if latest['last_valid_session'] == eligible
                               else 'stale', expected_data_date=eligible, checked_at=pd.Timestamp(now).isoformat())
    status_file = store.root / 'status.json'
    return {'latest': latest, 'manifest': json.loads((directory / 'manifest.json').read_text()),
            'update_status': json.loads(status_file.read_text()) if status_file.exists() else None,
            'history': pd.read_csv(directory / 'signals.csv', float_precision='round_trip'),
            'backtest': pd.read_csv(directory / 'backtest.csv', float_precision='round_trip'),
            'metrics': pd.read_csv(directory / 'metrics.csv', float_precision='round_trip'),
            'turnover': pd.read_csv(directory / 'turnover.csv', float_precision='round_trip')}
