"""Explicit candidate/live CLI with gated publication; never used by offline Actions."""
import argparse
import json
import os
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.riskbex.actions_update import candidate, promote
from scripts.run_daily_update import FileProvider
from src.riskbex.pipeline.provider import YahooProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--provider-file', type=Path)
    group.add_argument('--fetch', action='store_true')
    parser.add_argument('--now')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--expected-head')
    args = parser.parse_args()
    if args.fetch and args.now:
        parser.error('Simulated time is offline only.')
    if args.publish and (not args.fetch or not args.expected_head or
                         os.getenv('RISKBEX_PUBLIC_DISTRIBUTION_APPROVED') != 'true'):
        parser.error('Publishing requires live fetch, expected head and explicit distribution approval.')
    provider = YahooProvider() if args.fetch else FileProvider(args.provider_file) if args.provider_file else None
    result = candidate(ROOT, args.work, now=args.now or pd.Timestamp.now(tz='UTC'), provider=provider)
    if args.publish and result['status'] != 'unchanged':
        result['publication'] = promote(ROOT, args.work, args.expected_head)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
