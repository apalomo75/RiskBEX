"""Live-only scheduler entry point; JSON events go to the scheduler journal."""
import argparse
import json
from pathlib import Path
import sys

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.run_daily_update import validate_store_path
from src.riskbex.engine.package import load_main_package
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.provider import YahooProvider
from src.riskbex.pipeline.service import update_main
from src.riskbex.pipeline.store import VersionStore


def utc_now():
    return pd.Timestamp.now(tz='UTC')


def emit(event):
    print(json.dumps(event, sort_keys=True), flush=True)


def run(args):
    event = dict(event='daily_update', started_at=utc_now().isoformat(),
                 ended_at=None, market_information_date=None, eligible_target_session=None,
                 new_sessions=None, publication_version=None, status='running', error=None)
    emit(event)
    try:
        validate_store_path(args.store)
        calendar = SessionCalendar.load(args.calendar)
        if calendar.config['timezone'] != 'Europe/Madrid':
            raise ValueError('Scheduled updates require Europe/Madrid.')
        now = pd.Timestamp(event['started_at'])
        event['eligible_target_session'] = calendar.eligible(now).date().isoformat()
        store = VersionStore(args.store)
        current = store.current()
        if current:
            manifest = json.loads((current / 'manifest.json').read_text())
            event.update(market_information_date=manifest['data_date'], publication_version=current.name)
        package = load_main_package(args.package)
        result = update_main(package, pd.read_csv(args.seed, float_precision='round_trip'),
                             YahooProvider(), calendar, store, now=now,
                             regression_receipt=args.regression_receipt)
        event.update(status=result['status'], market_information_date=result['data_date'],
                     new_sessions=result['new_sessions'], publication_version=result['version'])
        code = 0
    except Exception as exc:
        # Provider exception text can contain URLs or credentials. Detailed pipeline
        # evidence is retained locally in store/attempts; journal only records type.
        contention = isinstance(exc, RuntimeError) and str(exc) == 'Another MAIN update is running.'
        event.update(status='busy' if contention else 'failed', error=type(exc).__name__)
        code = 75 if contention else 1
    event['ended_at'] = utc_now().isoformat()
    event['exit_code'] = code
    emit(event)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--regression-receipt', type=Path, required=True)
    parser.add_argument('--calendar', type=Path, default=BACKEND / 'config/bme-2026.json')
    parser.add_argument('--package', type=Path, default=BACKEND / 'model_packages/main-v1')
    parser.add_argument('--fetch', action='store_true', required=True,
                        help='Authorize live Yahoo retrieval; simulated providers are unavailable')
    return run(parser.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
