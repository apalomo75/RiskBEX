"""Single MAIN update entrypoint. Explicit inputs and fetch consent; no import side effects."""
import argparse
import json
from pathlib import Path
import sys
import pandas as pd
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from src.riskbex.engine.package import load_main_package
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.provider import YahooProvider
from src.riskbex.pipeline.service import update_main
from src.riskbex.pipeline.store import VersionStore


class FileProvider:
    def __init__(self, path):
        self.path = path
        self.source = 'local-simulated-provider:' + str(path)

    def fetch(self, start, end):
        frame = pd.read_csv(self.path, float_precision='round_trip')
        dates = pd.to_datetime(frame.date)
        return frame.loc[dates.between(start, end), ['date', 'ibex_close']].copy()


def validate_store_path(path):
    # Guard accidental use of the immutable source directories as the output store.
    destination = path.resolve()
    for forbidden in [BACKEND / 'data', BACKEND / 'tests', BACKEND / 'model_packages',
                      BACKEND / 'experiments', BACKEND.parent.parent / 'TMF-Market-Regimes-Risk-Portfolio']:
        if destination == forbidden.resolve() or forbidden.resolve() in destination.parents:
            raise ValueError('Store must be separate from academic, model, fixture and legacy data directories')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True, help='Validated complete local price history; never overwritten')
    parser.add_argument('--store', type=Path, required=True, help='Separate versioned operational directory')
    parser.add_argument('--regression-receipt', type=Path, required=True)
    parser.add_argument('--calendar', type=Path, default=BACKEND / 'config/bme-2026.json')
    parser.add_argument('--package', type=Path, default=BACKEND / 'model_packages/main-v1')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--fetch', action='store_true', help='Explicitly allow one real Yahoo request')
    group.add_argument('--provider-file', type=Path, help='Offline provider response; never contacts network')
    parser.add_argument('--now', help='Timezone-aware simulated generation time; offline only')
    args = parser.parse_args()
    if args.fetch and args.now:
        parser.error('--now is simulation-only and cannot be used for a real download')
    try:
        validate_store_path(args.store)
    except ValueError as exc:
        parser.error(str(exc))
    package = load_main_package(args.package)
    provider = YahooProvider() if args.fetch else FileProvider(args.provider_file)
    result = update_main(package, pd.read_csv(args.seed, float_precision='round_trip'), provider,
                         SessionCalendar.load(args.calendar), VersionStore(args.store),
                         now=args.now or pd.Timestamp.now(tz='UTC'), regression_receipt=args.regression_receipt)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
