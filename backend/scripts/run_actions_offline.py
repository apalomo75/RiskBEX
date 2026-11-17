"""Offline-only acceptance. No CLI path for live retrieval or publishing."""
from contextlib import contextmanager, ExitStack
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def git_read(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def snapshot_identity(root=ROOT):
    bundle = root / 'cloud/publication'
    return {p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(bundle.rglob('*')) if p.is_file()}


def check_git_command(command):
    if isinstance(command, (str, bytes)):
        raise AssertionError('Offline acceptance forbids shell subprocesses.')
    if not command or Path(str(command[0])).name != 'git':
        return
    args = list(command[1:])
    if args[:1] == ['-C']:
        args = args[2:]
    if not args or args[0] not in {'ls-files', 'rev-parse', 'status', 'diff'}:
        raise AssertionError('Offline acceptance forbids Git mutations.')


@contextmanager
def offline_guards():
    original_popen = subprocess.Popen
    original_connect = socket.socket.connect

    def process(command, *args, **kwargs):
        check_git_command(command)
        if kwargs.get('shell'):
            raise AssertionError('Offline acceptance forbids shell subprocesses.')
        return original_popen(command, *args, **kwargs)

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError('Network forbidden during offline acceptance.')
        return original_connect(sock, address)

    with ExitStack() as stack:
        stack.enter_context(patch('subprocess.Popen', side_effect=process))
        stack.enter_context(patch('socket.socket.connect', connect))
        stack.enter_context(patch('yfinance.download', side_effect=AssertionError('Live Yahoo retrieval forbidden.')))
        yield


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-release-sha', required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch('[0-9a-f]{40}', args.expected_release_sha):
        parser.error('Expected a full reviewed release commit SHA.')
    if git_read('rev-parse', 'HEAD') != args.expected_release_sha:
        parser.error('Checkout differs from the reviewed release commit.')
    if sys.version_info[:3] != (3, 11, 14):
        parser.error('Complete offline gate requires Python 3.11.14.')
    before_status = git_read('status', '--porcelain')
    before_snapshot = snapshot_identity()
    from src.riskbex.actions_update import approved_bundle
    from src.riskbex.engine.package import load_main_package
    from src.riskbex.pipeline.service import verify_gate
    approval = approved_bundle(ROOT)
    package = load_main_package(ROOT / 'backend/model_packages/main-v1')
    verify_gate(ROOT / 'backend/config/actions-regression.json', package)
    print(json.dumps(dict(mode='offline_non_publishing', release_sha=args.expected_release_sha,
                          snapshot=approval, frozen_package='verified', regression_receipt='verified')), flush=True)
    with offline_guards():
        suite = unittest.TestSuite()
        for module in ['tests.test_actions_offline', 'tests.test_actions_update',
                       'tests.test_daily_pipeline', 'tests.test_actions_cloud',
                       'tests.test_private_daily', 'tests.test_live_dry_run',
                       'tests.test_publication_control', 'tests.test_daily_state',
                       'tests.test_public_daily']:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    if snapshot_identity() != before_snapshot:
        raise AssertionError('Source snapshot changed during acceptance.')
    if git_read('rev-parse', 'HEAD') != args.expected_release_sha or git_read('status', '--porcelain') != before_status:
        raise AssertionError('Checkout changed during acceptance.')
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit('Offline acceptance failed or skipped required checks.')
    print(json.dumps(dict(status='passed', tests=result.testsRun, skipped=0,
                          source_snapshot='unchanged', source_checkout='unchanged',
                          live_downloads=0, actual_git_commits=0, actual_git_pushes=0)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
