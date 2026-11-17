"""Guarded daily inference with separately authorized atomic private persistence."""
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
from src.riskbex.pipeline.provider import YahooProvider
from src.riskbex.actions_update import promote, verify_predecessor
from src.riskbex.engine.package import load_main_package
from src.riskbex.pipeline.store import digest


def authorized(env):
    return (env.get('RISKBEX_PRIVATE_DAILY_ENABLED') == 'true'
            and env.get('GITHUB_EVENT_NAME') in {'schedule', 'workflow_dispatch'}
            and env.get('GITHUB_REF') == 'refs/heads/main'
            and env.get('GITHUB_REPOSITORY') == env.get('RISKBEX_EXPECTED_REPOSITORY')
            and bool(env.get('GITHUB_REPOSITORY')))


def execute(root, work, *, provider, now, summary):
    internal = {}
    summary.update(previous_approved_session=None, latest_processed_session=None,
                   new_sessions_processed=None, outcome='failed', verification_status='failed',
                   state_policy='independent_recomputation_from_unchanged_approved_snapshot')
    try:
        return run(root, work, provider=provider, now=now, public_summary=internal)
    finally:
        summary['previous_approved_session'] = internal.get('previous_approved_session')
        verified = (internal.get('run_status') == 'success'
                    and internal.get('integrity_gate') == 'passed'
                    and internal.get('regression_gate') == 'passed')
        if verified:
            count = internal['new_trading_sessions']
            summary.update(latest_processed_session=internal['latest_validated_candidate_session'],
                           new_sessions_processed=count,
                           outcome='updated' if count else 'unchanged', verification_status='passed')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--persist-head', help='Exact private predecessor SHA; enables atomic private persistence')
    parser.add_argument('--controller-root', type=Path)
    args = parser.parse_args(argv)
    if not authorized(os.environ):
        parser.error('Private daily execution is not enabled for this repository, event and branch.')
    summary = {}
    code = 0
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            if args.persist_head:
                if not args.controller_root or os.getenv('RISKBEX_PRIVATE_STORAGE_AUTHORIZED') != 'true':
                    raise ValueError('Separate private storage authorization required.')
                verify_predecessor(args.source_root, args.persist_head, private=True)
                trusted = load_main_package(args.controller_root / 'backend/model_packages/main-v1')
                restored = load_main_package(args.source_root / 'backend/model_packages/main-v1')
                for name in ['actions-regression.json', 'bme-2026.json']:
                    relative = Path('backend/config') / name
                    if digest(args.controller_root / relative) != digest(args.source_root / relative):
                        raise ValueError('Private state configuration differs from controller.')
                if trusted.manifest_sha256 != restored.manifest_sha256:
                    raise ValueError('Private frozen identity differs from controller.')
            execute(args.source_root, args.work, provider=YahooProvider(),
                    now=pd.Timestamp.now(tz='UTC'), summary=summary)
            if args.persist_head and summary['outcome'] == 'updated':
                summary['persistence'] = promote(args.source_root, args.work, args.persist_head,
                                                 require_live=True, private=True)
                summary['state_policy'] = 'atomic_private_git_predecessor'
            elif args.persist_head:
                summary['persistence'] = 'unchanged'
    except Exception:
        code = 1
        summary.update(outcome='failed', verification_status='failed')
    safe = json.dumps(summary, sort_keys=True)
    print(safe)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write('Private MAIN daily execution\n\n```json\n' + safe + '\n```\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
