"""Authorized live retrieval into disposable storage; no publication capability."""
import argparse
from contextlib import ExitStack, contextmanager, redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import resource
import sys
import time
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from scripts.run_actions_offline import snapshot_identity, check_git_command
from src.riskbex.actions_update import approved_bundle, candidate
from src.riskbex.cloud_snapshot import verify_approved_bundle, verify_bundle
from src.riskbex.pipeline.provider import YahooProvider
from src.riskbex.pipeline.store import VersionStore, digest, write_json


@contextmanager
def dry_run_guards():
    import subprocess
    import xgboost
    import statsmodels.api as sm
    original = subprocess.Popen
    def process(command, *args, **kwargs):
        check_git_command(command)
        if kwargs.get('shell'):
            raise AssertionError('Shell subprocess forbidden.')
        return original(command, *args, **kwargs)
    with ExitStack() as stack:
        stack.enter_context(patch('subprocess.Popen', side_effect=process))
        stack.enter_context(patch.object(xgboost.XGBClassifier, 'fit', side_effect=AssertionError('Training forbidden.')))
        stack.enter_context(patch.object(sm.tsa.MarkovRegression, 'fit', side_effect=AssertionError('Training forbidden.')))
        yield


def describe(bundle):
    version = VersionStore(Path(bundle) / 'store').current()
    manifest = json.loads((version / 'manifest.json').read_text())
    tables = {}
    for name in ['prices', 'features', 'signals', 'backtest', 'metrics', 'turnover']:
        path = version / (name + '.csv')
        frame = pd.read_csv(path)
        tables[name] = dict(sha256=digest(path), rows=len(frame),
                            last_row=json.loads(frame.tail(1).to_json(orient='records')))
    return dict(manifest=manifest, latest=json.loads((version / 'latest.json').read_text()), tables=tables)


def run(root, work, *, provider, now):
    root, work = Path(root).resolve(), Path(work).resolve()
    before = snapshot_identity(root)
    old = approved_bundle(root)
    approval_bytes = (root / 'cloud/approval.json').read_bytes()
    started = time.monotonic()
    try:
        with dry_run_guards():
            result = candidate(root, work, now=now, provider=provider)
        report = dict(format=1, mode='live_data_dry_run' if getattr(provider, 'is_live', False) else 'offline_fixture',
                      publication='disabled', old=old, result=result, old_outputs=describe(root / 'cloud/publication'))
        if result['status'] != 'unchanged':
            new = verify_approved_bundle(work / 'candidate', work / 'approval.json')
            inventory = verify_bundle(work / 'candidate', new['snapshot_sha256'])
            outputs = describe(work / 'candidate')
            manifest = outputs['manifest']
            if new['data_date'] <= old['data_date'] or manifest['previous_version'] != old['version']:
                raise ValueError('Candidate must advance its approved predecessor.')
            if manifest['model_manifest_sha256'] != report['old_outputs']['manifest']['model_manifest_sha256']:
                raise ValueError('Frozen model identity changed.')
            report.update(new=new, new_outputs=outputs, inventory=inventory,
                          snapshot_file_sha256=digest(work / 'candidate/snapshot.json'),
                          approval_file_sha256=digest(work / 'approval.json'))
        report.update(elapsed_seconds=time.monotonic() - started,
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write_json(work / 'dry-run-report.json', report)
        return report
    finally:
        if snapshot_identity(root) != before or (root / 'cloud/approval.json').read_bytes() != approval_bytes:
            raise AssertionError('Approved source changed.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--authorize-live-download', action='store_true')
    args = parser.parse_args(argv)
    if not args.authorize_live_download or os.getenv('RISKBEX_LIVE_DRY_RUN_AUTHORIZED') != 'true':
        parser.error('Separate live dry-run authorization is required.')
    # Provider/library diagnostics may contain market observations: retain no public logs.
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            run(args.source_root, args.work, provider=YahooProvider(), now=pd.Timestamp.now(tz='UTC'))
    except Exception:
        print('Live dry run failed; no candidate published. Private workspace will be removed.', file=sys.stderr)
        return 1
    print('Live dry run verified; candidate and report remain private and ephemeral. No publication performed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
