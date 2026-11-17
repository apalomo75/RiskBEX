"""Protected workflow entrypoint. No schedule or activation is installed here."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_actions_live_dry_run import run
from src.riskbex.actions_update import promote, approved_bundle
from src.riskbex.publication_control import verify_rights
from src.riskbex.pipeline.store import write_json, digest, VersionStore
from src.riskbex.engine.package import load_main_package


class PrivateStateProvider:
    """Read an approved private live history; never fetch market data."""
    is_live = True
    source = 'yahoo-finance:^IBEX:1d:auto_adjust=True'

    def __init__(self, private_root, public_root):
        approved_bundle(private_root)
        current = VersionStore(Path(private_root) / 'cloud/publication/store').current()
        manifest = json.loads((current / 'manifest.json').read_text())
        package = load_main_package(Path(public_root) / 'backend/model_packages/main-v1')
        latest = json.loads((current / 'latest.json').read_text())
        if (latest['provenance'].get('source_mode') != 'live'
                or latest['provenance'].get('live_market_freshness_verified') is not True
                or manifest['model_manifest_sha256'] != package.manifest_sha256
                or manifest.get('source') != self.source):
            raise ValueError('Private state frozen identity or source differs.')
        self.prices = pd.read_csv(current / 'prices.csv', float_precision='round_trip')

    def fetch(self, start, end):
        dates = pd.to_datetime(self.prices.date)
        return self.prices.loc[dates.between(start, end)].copy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['candidate', 'promote'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--controller', required=True)
    parser.add_argument('--private-root', type=Path)
    args = parser.parse_args()
    summary = {}
    try:
        verify_rights(args.root)
        binding = dict(format=1, source_head=args.head, controller=args.controller,
                       run_id=os.environ['GITHUB_RUN_ID'], run_attempt=os.environ['GITHUB_RUN_ATTEMPT'],
                       repository=os.environ['GITHUB_REPOSITORY'])
        if args.mode == 'candidate':
            if args.private_root is None:
                raise ValueError('Approved private state required; publication never downloads.')
            provider = PrivateStateProvider(args.private_root, args.root)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                report = run(args.root, args.work, provider=provider,
                             now=pd.Timestamp.now(tz='UTC'), public_summary=summary)
            if summary['update'] == 'generated':
                binding.update(approval_sha256=digest(args.work / 'approval.json'),
                               snapshot_sha256=report['new']['snapshot_sha256'])
                write_json(args.work / 'custody.json', binding)
        else:
            custody = json.loads((args.work / 'custody.json').read_text())
            approval = json.loads((args.work / 'approval.json').read_text())
            if (any(custody.get(k) != v for k, v in binding.items())
                    or custody.get('approval_sha256') != digest(args.work / 'approval.json')
                    or custody.get('snapshot_sha256') != approval['snapshot_sha256']):
                raise ValueError('Candidate custody differs.')
            result = promote(args.root, args.work, args.head, require_live=True)
            summary = dict(run_status='success', publication=result)
    except Exception:
        # Never log private exception text, dataframes or provider diagnostics.
        summary.update(run_status='failed')
        print(json.dumps(summary, sort_keys=True))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
