"""Synthetic extension only; real provider calls are forbidden in this suite."""
import io
import json
import os
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from scripts.run_actions_live_dry_run import run, main, dry_run_guards
from scripts.run_daily_update import FileProvider
from src.riskbex.actions_update import approved_bundle
from src.riskbex.pipeline.store import VersionStore

ROOT = Path(__file__).resolve().parents[2]


class LiveDryRunTests(unittest.TestCase):
    def test_consent_required_before_download(self):
        with patch('scripts.run_actions_live_dry_run.YahooProvider') as provider:
            with self.assertRaises(SystemExit):
                main(['--source-root', str(ROOT), '--work', '/tmp/never-created'])
            provider.assert_not_called()

    def test_live_cli_redacts_provider_diagnostics(self):
        for failure in [False, True]:
            with self.subTest(failure=failure):
                output, errors = io.StringIO(), io.StringIO()
                def fake_run(*args, **kwargs):
                    print('PRIVATE_MARKET_OBSERVATION')
                    if failure:
                        raise RuntimeError('PRIVATE_MARKET_OBSERVATION')
                    return {'private': 'PRIVATE_MARKET_OBSERVATION'}
                with patch.dict(os.environ, {'RISKBEX_LIVE_DRY_RUN_AUTHORIZED': 'true'}), \
                     patch('scripts.run_actions_live_dry_run.run', side_effect=fake_run), \
                     redirect_stdout(output), redirect_stderr(errors):
                    result = main(['--source-root', str(ROOT), '--work', '/tmp/unused',
                                   '--authorize-live-download'])
                self.assertEqual(result, 1 if failure else 0)
                self.assertNotIn('PRIVATE_MARKET_OBSERVATION', output.getvalue() + errors.getvalue())

    def test_git_mutation_forbidden(self):
        import subprocess
        with dry_run_guards():
            for args in [['git', 'commit'], ['git', 'push']]:
                with self.assertRaises(AssertionError):
                    subprocess.check_output(args)

    def test_synthetic_candidate_and_private_report(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            before = approved_bundle(ROOT)
            current = VersionStore(ROOT / 'cloud/publication/store').current()
            history = pd.read_csv(current / 'prices.csv', float_precision='round_trip')
            extension = pd.read_csv(ROOT / 'backend/tests/fixtures/live-dry-run/extension.csv')
            provider_file = base / 'provider.csv'
            pd.concat([history, extension]).to_csv(provider_file, index=False)
            with patch('yfinance.download', side_effect=AssertionError('Network forbidden')):
                report = run(ROOT, base / 'work', provider=FileProvider(provider_file), now='2026-11-17T22:00Z')
            self.assertEqual(report['mode'], 'offline_fixture')
            self.assertEqual(report['new']['data_date'], '2026-11-17')
            self.assertEqual(report['new_outputs']['manifest']['previous_version'], before['version'])
            self.assertEqual(report['new_outputs']['tables']['prices']['rows'], len(history) + 1)
            self.assertEqual(report['snapshot_file_sha256'], report['new']['snapshot_sha256'])
            self.assertTrue(report['inventory']['files'])
            self.assertEqual(approved_bundle(ROOT), before)
            self.assertEqual(json.loads((base / 'work/dry-run-report.json').read_text())['publication'], 'disabled')

    def test_workflow_is_manual_read_only_and_no_exposure(self):
        workflow = (ROOT / '.github/workflows/live-data-dry-run.yml').read_text()
        for forbidden in ['\n  schedule:', 'uses: actions/upload-artifact', 'git push', '--publish', 'contents: write']:
            self.assertNotIn(forbidden, workflow)
        for required in ['workflow_dispatch:', 'contents: read', 'persist-credentials: false',
                         'riskbex-live-dry-run-v1', 'if: always()', 'environment: live-data-dry-run']:
            self.assertIn(required, workflow)


if __name__ == '__main__':
    unittest.main()
