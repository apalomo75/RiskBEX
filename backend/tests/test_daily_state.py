"""Consecutive frozen updates and private atomic promotion, no real Git writes."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.run_daily_update import FileProvider
from src.riskbex.actions_update import candidate, promote, approved_bundle, PRIVATE_BRANCH, BRANCH
from src.riskbex.pipeline.store import VersionStore

ROOT = Path(__file__).resolve().parents[2]


class DailyStateTests(unittest.TestCase):
    def test_consecutive_repeat_missing_and_stale_predecessor(self):
        self.check_consecutive_updates(private=True)

    def test_public_consecutive_repeat_missing_and_stale_predecessor(self):
        self.check_consecutive_updates(private=False)

    def check_consecutive_updates(self, *, private):
        branch = PRIVATE_BRANCH if private else BRANCH
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'private'
            for name in ['cloud/publication', 'backend/model_packages/main-v1', 'backend/config']:
                shutil.copytree(ROOT / name, root / name)
            shutil.copyfile(ROOT / 'cloud/approval.json', root / 'cloud/approval.json')
            current = VersionStore(root / 'cloud/publication/store').current()
            prices = pd.read_csv(current / 'prices.csv', float_precision='round_trip')
            extra = pd.read_csv(ROOT / 'backend/tests/fixtures/live-dry-run/extension.csv')
            extra2 = pd.DataFrame({'date': ['2026-11-18'], 'ibex_close': [float(extra.ibex_close.iloc[-1]) + 1]})
            provider = base / 'prices.csv'
            pd.concat([prices, extra, extra2]).to_csv(provider, index=False)
            remote = {'head': 'a' * 40, 'approval': approved_bundle(root)}
            def git(command, **kwargs):
                args = command[3:]
                if args == ['branch', '--show-current']: return branch
                if args == ['rev-parse', 'HEAD']: return remote['head']
                if args[0] in {'status', 'add', 'commit'}: return ''
                if args == ['push', 'origin', 'HEAD:refs/heads/' + branch]:
                    remote.update(head='b' * 40, approval=approved_bundle(root))
                    return ''
                raise AssertionError(args)
            first = base / 'day1'
            candidate(root, first, now='2026-11-17T22:00Z', provider=FileProvider(provider))
            with patch('subprocess.check_output', side_effect=git):
                self.assertEqual(promote(root, first, 'a' * 40, private=private), 'published')
                with self.assertRaisesRegex(ValueError, 'branch/head'):
                    promote(root, first, 'a' * 40, private=private)
            with patch.object(FileProvider, 'fetch', side_effect=AssertionError('Repeated run fetched')):
                repeated = candidate(root, base / 'repeat', now='2026-11-17T22:00Z', provider=FileProvider(provider))
            self.assertEqual(repeated['status'], 'unchanged')
            old = approved_bundle(root)
            incomplete = base / 'missing.csv'
            pd.concat([prices, extra2]).to_csv(incomplete, index=False)
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                candidate(root, base / 'missing', now='2026-11-18T22:00Z', provider=FileProvider(incomplete))
            self.assertEqual(approved_bundle(root), old)
            second = base / 'day2'
            result = candidate(root, second, now='2026-11-18T22:00Z', provider=FileProvider(provider))
            self.assertEqual(result['new_sessions'], 1)
            manifest = json.loads((VersionStore(second / 'candidate/store').current() / 'manifest.json').read_text())
            self.assertEqual(manifest['previous_version'], old['version'])
            with patch('subprocess.check_output', side_effect=git):
                self.assertEqual(promote(root, second, 'b' * 40, private=private), 'published')
            self.assertEqual(remote['approval']['data_date'], '2026-11-18')


class PublicationStateTests(unittest.TestCase):
    def test_public_provider_reads_sealed_history_without_network(self):
        from scripts.run_cloud_publication import PrivateStateProvider
        with patch('yfinance.download', side_effect=AssertionError('No retrieval')):
            provider = PrivateStateProvider(ROOT, ROOT)
            frame = provider.fetch('2026-11-12', '2026-11-16')
        self.assertEqual(list(frame.date), ['2026-11-12', '2026-11-13', '2026-11-16'])
        with patch('scripts.run_cloud_publication.approved_bundle', side_effect=ValueError('Tampered')):
            with self.assertRaisesRegex(ValueError, 'Tampered'):
                PrivateStateProvider(ROOT, ROOT)

    def test_failed_private_push_reports_failure_without_private_details(self):
        import io
        import os
        from contextlib import redirect_stdout
        from scripts.run_private_daily import main
        env = dict(RISKBEX_PRIVATE_DAILY_ENABLED='true',
                   RISKBEX_PRIVATE_STORAGE_AUTHORIZED='true', GITHUB_EVENT_NAME='workflow_dispatch',
                   GITHUB_REF='refs/heads/main', GITHUB_REPOSITORY='owner/repo',
                   RISKBEX_EXPECTED_REPOSITORY='owner/repo')
        def execute(*args, **kwargs):
            kwargs['summary'].update(outcome='updated', verification_status='passed')
        output = io.StringIO()
        with patch.dict(os.environ, env), patch('scripts.run_private_daily.verify_predecessor'), patch('scripts.run_private_daily.execute', side_effect=execute), \
             patch('scripts.run_private_daily.promote', side_effect=RuntimeError('PRIVATE TRANSPORT')), \
             redirect_stdout(output):
            result = main(['--source-root', str(ROOT), '--controller-root', str(ROOT),
                           '--work', '/tmp/not-used', '--persist-head', 'a' * 40])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.getvalue())['outcome'], 'failed')
        self.assertNotIn('PRIVATE TRANSPORT', output.getvalue())
