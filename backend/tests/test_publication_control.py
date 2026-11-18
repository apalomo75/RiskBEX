"""Offline publication guards; only synthetic data and disposable Git repositories."""
import json
import io
import os
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.run_actions_live_dry_run import run
from scripts.run_daily_update import FileProvider
from src.riskbex.actions_update import promote, approved_bundle, BRANCH
from src.riskbex.publication_control import verify_provenance
from src.riskbex.pipeline.store import VersionStore, write_json, digest

ROOT = Path(__file__).resolve().parents[2]


class SummaryTests(unittest.TestCase):
    def test_noop_before_cutoff_has_zero_sessions_and_no_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = {}
            with patch.object(FileProvider, 'fetch', side_effect=AssertionError('No network')):
                run(ROOT, Path(temp) / 'work', provider=FileProvider('unused'),
                    now='2026-11-17T13:27:19Z', public_summary=summary)
            self.assertEqual(summary['previous_approved_session'], '2026-11-16')
            self.assertEqual(summary['latest_validated_candidate_session'], '2026-11-16')
            self.assertEqual(summary['new_trading_sessions'], 0)
            self.assertEqual(summary['update'], 'skipped')
            self.assertEqual(summary['run_status'], 'success')
            self.assertEqual(summary['regression_gate'], 'passed')
            self.assertEqual(summary['integrity_gate'], 'passed')
            self.assertGreaterEqual(summary['duration_seconds'], 0)

    def test_final_source_check_failure_revokes_success_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = {}
            with patch('scripts.run_actions_live_dry_run.snapshot_identity', side_effect=[{}, OSError('PRIVATE')]):
                with self.assertRaisesRegex(AssertionError, 'unreadable'):
                    run(ROOT, Path(temp) / 'work', provider=None,
                        now='2026-11-17T13:27:19Z', public_summary=summary)
            self.assertEqual(summary['run_status'], 'failed')
            self.assertEqual(summary['integrity_gate'], 'failed')
            self.assertIsNone(summary['new_trading_sessions'])

    def test_failed_provider_reports_no_validated_candidate_or_count(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = {}
            with patch.object(FileProvider, 'fetch', side_effect=RuntimeError('PRIVATE_PRICE')):
                with self.assertRaises(RuntimeError):
                    run(ROOT, Path(temp) / 'work', provider=FileProvider('unused'),
                        now='2026-11-17T22:00Z', public_summary=summary)
            self.assertEqual(summary['run_status'], 'failed')
            self.assertEqual(summary['update'], 'failed')
            self.assertIsNone(summary['new_trading_sessions'])
            self.assertIsNone(summary['latest_validated_candidate_session'])
            self.assertNotIn('PRIVATE_PRICE', json.dumps(summary))

    def test_candidate_integrity_failure_is_reported_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = {}
            with patch('scripts.run_actions_live_dry_run.candidate', return_value={'status': 'published'}), \
                 patch('scripts.run_actions_live_dry_run.verify_approved_bundle', side_effect=ValueError('PRIVATE')):
                with self.assertRaises(ValueError):
                    run(ROOT, Path(temp) / 'work', provider=None,
                        now='2026-11-17T22:00Z', public_summary=summary)
            self.assertEqual(summary['integrity_gate'], 'failed')
            self.assertEqual(summary['run_status'], 'failed')
            self.assertIsNone(summary['latest_validated_candidate_session'])

    def test_failed_regression_is_not_reported_passed(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = {}
            with patch('scripts.run_actions_live_dry_run.verify_gate', side_effect=ValueError('PRIVATE')):
                with self.assertRaises(ValueError):
                    run(ROOT, Path(temp) / 'work', provider=None, now='2026-11-17T22:00Z', public_summary=summary)
            self.assertEqual(summary['regression_gate'], 'failed')
            self.assertEqual(summary['run_status'], 'failed')


class TransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        current = VersionStore(ROOT / 'cloud/publication/store').current()
        history = pd.read_csv(current / 'prices.csv', float_precision='round_trip')
        extension = pd.read_csv(ROOT / 'backend/tests/fixtures/live-dry-run/extension.csv')
        provider = cls.base / 'provider.csv'
        pd.concat([history, extension]).to_csv(provider, index=False)
        cls.work = cls.base / 'work'
        cls.summary = {}
        with patch('yfinance.download', side_effect=AssertionError('Network forbidden')):
            run(ROOT, cls.work, provider=FileProvider(provider), now='2026-11-17T22:00Z',
                public_summary=cls.summary)

    def test_generated_summary_has_only_allowlisted_metadata(self):
        self.assertEqual(self.summary['new_trading_sessions'], 1)
        self.assertEqual(self.summary['latest_validated_candidate_session'], '2026-11-17')
        self.assertEqual(self.summary['update'], 'generated')
        self.assertEqual(set(self.summary), {'format', 'previous_approved_session',
            'latest_validated_candidate_session', 'new_trading_sessions', 'update', 'integrity_gate',
            'regression_gate', 'run_status', 'duration_seconds'})

    def test_offline_candidate_cannot_claim_live_provenance(self):
        with self.assertRaisesRegex(ValueError, 'Live candidate'):
            verify_provenance(ROOT, self.work, approved_bundle(ROOT), require_live=True)

    def test_protected_approval_delay_cannot_publish_stale_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            shutil.copytree(self.work / 'candidate', work / 'candidate')
            store = work / 'candidate/store'
            current = VersionStore(store).current()
            latest_path, manifest_path = current / 'latest.json', current / 'manifest.json'
            latest = json.loads(latest_path.read_text())
            latest['provenance'].update(source_mode='live', live_market_freshness_verified=True)
            write_json(latest_path, latest)
            manifest = json.loads(manifest_path.read_text())
            manifest['source'] = 'yahoo-finance:^IBEX:1d:auto_adjust=True'
            manifest['files']['latest.json'] = digest(latest_path)
            write_json(manifest_path, manifest)
            write_json(store / 'current.json', dict(version=current.name, manifest_sha256=digest(manifest_path)))
            verify_provenance(ROOT, work, approved_bundle(ROOT), require_live=True, now='2026-11-17T22:00Z')
            with self.assertRaisesRegex(ValueError, 'became stale'):
                verify_provenance(ROOT, work, approved_bundle(ROOT), require_live=True, now='2026-11-18T22:00Z')

    def test_normal_push_rejection_and_concurrent_commit_preserve_remote(self):
        # Simulate transport: the guarded gate never creates commits or pushes.
        for mode in ['success', 'rejected', 'concurrent']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'source'
                for name in ['cloud/publication', 'backend/model_packages/main-v1', 'backend/config']:
                    shutil.copytree(ROOT / name, root / name)
                shutil.copyfile(ROOT / 'cloud/approval.json', root / 'cloud/approval.json')
                head = 'a' * 40
                remote = {'head': 'b' * 40 if mode == 'concurrent' else head,
                          'approval': approved_bundle(ROOT)}
                previous = dict(remote)
                calls = []
                def transport(command, **kwargs):
                    args = command[3:]
                    calls.append(args)
                    if args == ['branch', '--show-current']: return BRANCH
                    if args == ['rev-parse', 'HEAD']: return head
                    if args[0] in {'status', 'add', 'commit'}: return ''
                    if args[0] == 'push':
                        if mode == 'rejected' or remote['head'] != head:
                            raise subprocess.CalledProcessError(1, command)
                        remote.update(head='c' * 40, approval=approved_bundle(root))
                        return ''
                    raise AssertionError(args)
                with patch('subprocess.check_output', side_effect=transport):
                    if mode == 'success':
                        self.assertEqual(promote(root, self.work, head), 'published')
                        self.assertEqual(remote['approval']['data_date'], '2026-11-17')
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):
                            promote(root, self.work, head)
                        self.assertEqual(remote, previous)
                pushes = [c for c in calls if c[0] == 'push']
                self.assertEqual(pushes, [['push', 'origin', 'HEAD:refs/heads/' + BRANCH]])


class CustodyTests(unittest.TestCase):
    def test_ciphertext_roundtrip_and_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'gnupg'
            home.mkdir(mode=0o700)
            source, encrypted, restored = base / 'fixture.txt', base / 'fixture.gpg', base / 'restored.txt'
            source.write_text('SYNTHETIC CUSTODY PAYLOAD')
            key = b'a' * 64
            command = ['gpg', '--homedir', str(home), '--batch', '--pinentry-mode', 'loopback', '--passphrase-fd', '0']
            def execute(*args):
                return subprocess.run(command + list(args), input=key, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, check=False)
            result = execute('--symmetric', '--cipher-algo', 'AES256', '--output', str(encrypted), str(source))
            self.assertEqual(result.returncode, 0)
            result = execute('--output', str(restored), '--decrypt', str(encrypted))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(restored.read_bytes(), source.read_bytes())
            corrupted = bytearray(encrypted.read_bytes())
            corrupted[-10] ^= 1
            encrypted.write_bytes(corrupted)
            restored.unlink()
            result = execute('--output', str(restored), '--decrypt', str(encrypted))
            self.assertNotEqual(result.returncode, 0)
            # Workflow's -euo pipefail prevents extraction even if GPG wrote partial plaintext.

    def test_binding_mismatch_and_tampered_approval_never_promote(self):
        from scripts.run_cloud_publication import main
        for tamper in ['run_id', 'approval_sha256']:
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as temp:
                work = Path(temp)
                write_json(work / 'approval.json', {'snapshot_sha256': 'a' * 64})
                binding = dict(format=1, source_head='b' * 40, controller='c' * 40,
                               run_id='42', run_attempt='1', repository='fixture/repo',
                               approval_sha256=digest(work / 'approval.json'), snapshot_sha256='a' * 64)
                binding[tamper] = 'INVALID'
                write_json(work / 'custody.json', binding)
                output = io.StringIO()
                argv = ['publish', 'promote', '--root', str(ROOT), '--work', str(work),
                        '--head', 'b' * 40, '--controller', 'c' * 40]
                with patch('sys.argv', argv), patch.dict(os.environ, {'GITHUB_RUN_ID': '42',
                        'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_REPOSITORY': 'fixture/repo'}), \
                     patch('scripts.run_cloud_publication.promote') as promote_mock, redirect_stdout(output):
                    self.assertEqual(main(), 1)
                promote_mock.assert_not_called()
                self.assertEqual(json.loads(output.getvalue())['run_status'], 'failed')
                self.assertNotIn('INVALID', output.getvalue())


class CalendarAndWorkflowTests(unittest.TestCase):
    def test_expiry_blocks_final_session_target_before_network(self):
        from src.riskbex.actions_update import candidate
        with tempfile.TemporaryDirectory() as temp, patch.object(FileProvider, 'fetch') as fetch:
            with self.assertRaisesRegex(ValueError, 'coverage'):
                candidate(ROOT, Path(temp) / 'work', now='2026-12-31T22:00Z', provider=FileProvider('unused'))
            fetch.assert_not_called()

    def test_schedule_template_is_dormant_and_resolves_current_heads(self):
        template = ROOT / '.github/retired/cloud-publication-autonomous.yml.disabled'
        self.assertNotEqual(template.parent, ROOT / '.github/workflows')
        text = template.read_text()
        for item in ["17 19 * * 1-5", "47 21 * * 1-5", 'RISKBEX_AUTONOMOUS_AUTHORIZED',
                     'needs.candidate.outputs.release_sha', 'needs.candidate.outputs.controller_sha',
                     'publication-candidate-auto', 'public-publication-auto']:
            self.assertIn(item, text)

    def test_public_workflow_validates_offline_with_one_publication_switch(self):
        workflow = (ROOT / '.github/workflows/cloud-publication.yml').read_text()
        self.assertNotIn('\n  schedule:', workflow)
        for item in ['workflow_dispatch:', "vars.RISKBEX_PUBLICATION_ENABLED == 'true'",
                     'contents: write', 'contents: read',
                     'riskbex-protected-publication-v2', 'run_public_daily.py',
                     'persist-credentials: false', '17 20 * * 1-5', '17 22 * * 1-5',
                     'RELEASE=$(git rev-parse HEAD)', '--head "$RELEASE"']:
            self.assertIn(item, workflow)
        job_guard = workflow.split('  daily:\n', 1)[1].split('    permissions:', 1)[0]
        self.assertNotIn('vars.', job_guard)
        self.assertIn("if: vars.RISKBEX_PUBLICATION_ENABLED == 'true'", workflow)
        self.assertIn('Report validation-only execution', workflow)
        for forbidden in ['RISKBEX_LIVE_DOWNLOAD_AUTHORIZED', 'environment:', 'state/main-daily', 'private-state', 'inputs.release_sha',
                          'upload-artifact', '--force', '2026-11-16']:
            self.assertNotIn(forbidden, workflow)
        self.assertFalse((ROOT / '.github/workflows/private-daily.yml').exists())
