"""Offline runner bootstrap, replay and atomic Git publication contract tests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.run_daily_update import FileProvider
from src.riskbex.actions_update import approved_bundle, bootstrap, candidate, promote, BRANCH
from src.riskbex.cloud_snapshot import export_bundle, verify_bundle
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.service import update_main
from src.riskbex.pipeline.store import VersionStore, digest, write_json

ROOT = Path(__file__).resolve().parents[2]


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.clean = Path(cls.temp.name) / 'checkout'
        # Only Git-tracked inputs plus this sprint's explicit new trust artifacts.
        tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z'], text=True).split('\0')
        for name in tracked + ['cloud/approval.json', 'backend/config/actions-regression.json']:
            if name and name.startswith(('cloud/publication/', 'backend/model_packages/main-v1/',
                                         'backend/config/', 'backend/src/', 'cloud/approval.json')):
                src, dst = ROOT / name, cls.clean / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'checkout'
        shutil.copytree(self.clean, self.root)
        self.work = self.base / 'work'

    def test_fresh_checkout_and_no_network_noop(self):
        with patch.object(FileProvider, 'fetch', side_effect=AssertionError('no network')):
            result = candidate(self.root, self.work, now='2026-11-16T22:00Z', provider=FileProvider('unused'))
        self.assertEqual(result['status'], 'unchanged')
        self.assertFalse((self.work / 'candidate').exists())
        self.assertFalse((self.root / 'backend/runtime').exists())
        self.assertEqual(approved_bundle(self.root)['version'], result['version'])

    def test_missing_and_corrupt_bootstrap_inputs(self):
        for name in ['backend/model_packages/main-v1/xgboost/model.ubj',
                     'backend/config/actions-regression.json', 'cloud/publication/snapshot.json']:
            path = self.root / name
            original = path.read_bytes()
            for corrupt in [False, True]:
                with self.subTest(name=name, corrupt=corrupt):
                    if corrupt:
                        path.write_bytes(b'corrupt')
                    else:
                        path.unlink()
                    with self.assertRaises((OSError, ValueError, KeyError)):
                        bootstrap(self.root, self.work)
                    self.assertFalse(self.work.exists())
                    path.write_bytes(original)
        version = approved_bundle(self.root)['version']
        (self.root / 'cloud/publication/store/versions' / version / 'prices.csv').unlink()
        with self.assertRaises((OSError, ValueError)):
            bootstrap(self.root, self.work)

    def test_regression_rejection(self):
        path = self.root / 'backend/config/actions-regression.json'
        data = json.loads(path.read_text()); data['status'] = 'failed'; write_json(path, data)
        with self.assertRaisesRegex(ValueError, 'regression'):
            bootstrap(self.root, self.work)

    def test_wrong_approval_and_expired_calendar(self):
        approval = self.root / 'cloud/approval.json'
        data = json.loads(approval.read_text()); data['snapshot_sha256'] = '0' * 64
        write_json(approval, data)
        with self.assertRaisesRegex(ValueError, 'identity'):
            bootstrap(self.root, self.work)
        shutil.copyfile(self.clean / 'cloud/approval.json', approval)
        with self.assertRaisesRegex(ValueError, 'coverage'):
            candidate(self.root, self.work, now='2027-01-05T22:00Z')

    def test_market_clock_dst_weekends_holidays(self):
        cal = SessionCalendar.load(self.root / 'backend/config/bme-2026.json')
        for now, expected in [('2026-03-30T17:59Z', '2026-03-27'),
                              ('2026-03-30T18:01Z', '2026-03-30'),
                              ('2026-10-26T18:59Z', '2026-10-23'),
                              ('2026-10-26T19:01Z', '2026-10-26'),
                              ('2026-04-06T22:00Z', '2026-04-02'),
                              ('2026-11-15T22:00Z', '2026-11-13')]:
            with self.subTest(now=now):
                self.assertEqual(str(cal.eligible(now).date()), expected)

    def test_real_frozen_replay_and_git_promotion(self):
        package, receipt = bootstrap(self.root, self.base / 'restore')
        assets = self.base / 'restore/assets'
        prices = pd.read_csv(self.base / 'restore/seed.csv', float_precision='round_trip')
        provider_path = self.base / 'provider.csv'; prices.to_csv(provider_path, index=False)
        # Two missing sessions; previous closed session is Thursday 12 November.
        seed = prices.loc[prices.date <= '2026-11-12']
        store = VersionStore(self.base / 'baseline-store')
        result = update_main(package, seed, FileProvider(provider_path),
                             SessionCalendar.load(self.root / 'backend/config/bme-2026.json'), store,
                             now='2026-11-12T22:00Z', regression_receipt=receipt)
        shutil.rmtree(self.root / 'cloud/publication')
        seal = export_bundle(store.root, self.root / 'cloud/publication', assets)
        write_json(self.root / 'cloud/approval.json', dict(format=1, snapshot_sha256=seal,
                   version=result['version'], data_date=result['data_date']))
        old = approved_bundle(self.root)
        # Fit is forbidden, and provider failure leaves source approval untouched.
        with patch.object(FileProvider, 'fetch', side_effect=RuntimeError('provider unavailable')):
            with self.assertRaises(RuntimeError):
                candidate(self.root, self.base / 'failed', now='2026-11-16T22:00Z', provider=FileProvider(provider_path))
        self.assertEqual(approved_bundle(self.root), old)
        import xgboost
        import statsmodels.api as sm
        with patch.object(xgboost.XGBClassifier, 'fit', side_effect=AssertionError('fit forbidden')), \
             patch.object(sm.tsa.MarkovRegression, 'fit', side_effect=AssertionError('fit forbidden')):
            result = candidate(self.root, self.work, now='2026-11-16T22:00Z', provider=FileProvider(provider_path))
        self.assertEqual(result['new_sessions'], 2)
        self.assertEqual(approved_bundle(self.root), old)
        inv = verify_bundle(self.work / 'candidate', digest(self.work / 'candidate/snapshot.json'))
        self.assertNotEqual(inv['version'], old['version'])
        # Prices, probabilities and exposures agree with the original live publication.
        original = VersionStore(self.clean / 'cloud/publication/store').current()
        replay = VersionStore(self.work / 'candidate/store').current()
        for name in ['prices', 'features', 'signals', 'backtest', 'metrics', 'turnover']:
            pd.testing.assert_frame_equal(pd.read_csv(original / (name + '.csv')),
                                          pd.read_csv(replay / (name + '.csv')))
        head = 'a' * 40
        # Every Git command is simulated, including setup and local commits.
        calls = []
        def controlled(args, **kwargs):
            command = args[3:]
            calls.append(command)
            if command == ['branch', '--show-current']:
                return BRANCH
            if command == ['rev-parse', 'HEAD']:
                return head
            if command[0] in ('status', 'add', 'commit', 'push'):
                return ''
            raise AssertionError('Unexpected Git command: ' + str(command))
        with patch('subprocess.check_output', side_effect=controlled):
            with self.assertRaisesRegex(ValueError, 'branch/head'):
                promote(self.root, self.work, '0' * 40)
            self.assertEqual(promote(self.root, self.work, head), 'published')
        self.assertEqual([c[0] for c in calls if c[0] in ('commit', 'push')], ['commit', 'push'])
        self.assertNotIn('--force', str(calls))
        self.assertEqual(approved_bundle(self.root)['data_date'], '2026-11-16')
        # Actual Cloud entrypoint reads the next real replay publication while a
        # visitor retains the old identity and Streamlit has an obsolete secret.
        from types import SimpleNamespace
        st = SimpleNamespace(secrets={'RISKBEX_SNAPSHOT_SHA256': 'obsolete'},
                             session_state={'_riskbex_snapshot_version': old['version']},
                             cache_data=SimpleNamespace(clear=unittest.mock.Mock()),
                             error=unittest.mock.Mock(), stop=unittest.mock.Mock(side_effect=AssertionError('Cloud stopped')))
        with patch.dict(os.environ, {}, clear=True), patch.dict('sys.modules', {'streamlit': st}), \
             patch('runpy.run_path') as dashboard:
            exec(compile((ROOT / 'cloud/streamlit_app.py').read_text(), 'streamlit_app.py', 'exec'),
                 {'__file__': str(self.root / 'cloud/streamlit_app.py')})
            self.assertEqual(dashboard.call_count, 1)
            self.assertEqual(st.session_state['_riskbex_snapshot_version'], result['version'])
            st.cache_data.clear.assert_called_once()
        # Old delayed candidate cannot replace the now newer snapshot.
        write_json(self.work / 'approval.json', old)
        shutil.rmtree(self.work / 'candidate')
        shutil.copytree(store.root, self.base / 'unused-store')
        export_bundle(store.root, self.work / 'candidate', assets)
        with patch('subprocess.check_output', side_effect=controlled):
            with self.assertRaisesRegex(ValueError, 'Non-advancing'):
                promote(self.root, self.work, head)

    def test_workflow_constraints(self):
        workflow = (ROOT / '.github/workflows/daily-update.yml').read_text()
        self.assertNotIn('\n  schedule:', workflow)
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('ref: ' + BRANCH, workflow)
        self.assertIn('contents: read', workflow)
        self.assertIn("python-version: '3.11.14'", workflow)
        self.assertIn('cancel-in-progress: false', workflow)
        self.assertNotIn('--fetch', workflow)
        self.assertNotIn('git push', workflow)


if __name__ == '__main__':
    unittest.main()
