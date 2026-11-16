"""Opt-in Sprint 11B checks against the real, immutable Cloud release candidate.

Run in a clean environment from repository root with PYTHONPATH=backend.
No operational writes, providers or model packages are invoked.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / 'cloud/release-candidates/rc-20261116-7aa57e336352'
SEAL = '0d5b6d863ca2e342c24631a7b37cde7437eaa7513bd7afad8f6fa347f0b538bb'
SOURCE = ROOT / 'backend/runtime/main-wsl-test'
PAGES = ['Welcome / Home', 'Overview', 'Performance', 'Investment Simulator',
         'Risk Monitor', 'Research & Methodology']


@contextmanager
def offline():
    original = socket.socket.connect

    def guarded(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise AssertionError('External connection forbidden during Cloud browsing')
        return original(sock, address)

    with patch('socket.socket.connect', guarded), \
         patch('requests.sessions.Session.request', side_effect=AssertionError('HTTP backend forbidden')):
        yield


class RealCloudCandidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CANDIDATE.exists():
            raise unittest.SkipTest('The explicitly exported Sprint 11B candidate is not present.')

    def setUp(self):
        self.env = patch.dict(os.environ, {
            'RISKBEX_SNAPSHOT_DIR': str(CANDIDATE), 'RISKBEX_SNAPSHOT_SHA256': SEAL,
            'RISKBEX_PRESENTATION_MODE': 'snapshot',
            'RISKBEX_OPERATIONAL_DIR': str(CANDIDATE / 'store'),
            'RISKBEX_DATA_DIR': str(CANDIDATE / 'data'),
            'RISKBEX_FIGURES_DIR': str(CANDIDATE / 'figures'),
            'RISKBEX_PRESENTATION_PACKAGE_DIR': str(CANDIDATE / 'package'),
            'RISKBEX_CALENDAR': str(ROOT / 'backend/config/bme-2026.json'),
            'RISKBEX_API_URL': 'http://api:8000',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clock = patch('src.riskbex.api.operational.utc_now',
                           return_value=pd.Timestamp('2026-11-16T22:00Z'))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        st.cache_data.clear()

    def get(self, path, params=None):
        from src.riskbex.dashboard_transport import get
        result = get('http://api:8000' + path, params=params)
        self.assertEqual(result.status_code, 200, result.text[:250])
        return result.json()

    def app(self, language='en', view=PAGES[0]):
        app = AppTest.from_file(str(ROOT / 'cloud/streamlit_app.py'), default_timeout=45)
        app.query_params.update(lang=language, view=view)
        return app

    def healthy(self, app):
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(len(app.error), 0, [x.value for x in app.error])
        for warning in app.warning:
            self.assertFalse(any(word in warning.value.lower() for word in
                                 ['unavailable', 'no disponible', 'no están disponibles', 'could not']), warning.value)

    def test_01_inventory_source_identity_and_public_review(self):
        from src.riskbex.cloud_snapshot import verify_bundle, FIGURES, RESEARCH
        from src.riskbex.pipeline.store import VersionStore, digest
        inventory = verify_bundle(CANDIDATE, SEAL)
        self.assertEqual(len(inventory['files']), 29)
        self.assertEqual(sum(p.stat().st_size for p in CANDIDATE.rglob('*') if p.is_file()), 7838662)
        source = VersionStore(SOURCE).current()
        self.assertEqual(source.name, inventory['version'])
        for name in ['manifest.json', *json.loads((source / 'manifest.json').read_text())['files']]:
            self.assertEqual(digest(source / name), digest(CANDIDATE / 'store/versions' / source.name / name))
        for name in RESEARCH:
            self.assertEqual(digest(ROOT / 'backend/data/processed' / name),
                             digest(CANDIDATE / 'data/processed' / name))
        for name in FIGURES:
            self.assertEqual(digest(ROOT / 'backend/figures/chapter2' / name),
                             digest(CANDIDATE / 'figures/chapter2' / name))
        import re
        forbidden = re.compile(r'/home/|/Users/|/root/|[A-Z]:\\|-----BEGIN .*PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|(?:password|api_key|access_token|secret_key)\s*[=:]', re.I)
        for path in CANDIDATE.rglob('*'):
            if not path.is_file():
                continue
            self.assertNotIn(path.suffix, ['.pkl', '.pickle', '.ubj', '.joblib', '.env'])
            self.assertFalse(path.is_symlink())
            self.assertLess(path.stat().st_size, 2_000_000)
            if path.suffix in ['.json', '.csv']:
                self.assertIsNone(forbidden.search(path.read_text()), str(path))
        from PIL import Image
        for name in FIGURES:
            with Image.open(CANDIDATE / 'figures/chapter2' / name) as image:
                image.verify()

    def test_02_real_entrypoint_all_views_both_languages(self):
        with offline():
            for language in ['en', 'es']:
                for view in PAGES:
                    with self.subTest(language=language, view=view):
                        st.cache_data.clear()
                        app = self.app(language, view).run()
                        self.healthy(app)
                        self.assertEqual(app.session_state['ui_language'], language)
                        self.assertEqual(app.session_state['current_page'], view)
                        if view == PAGES[0]:
                            self.assertGreater(len(app.get('vega_lite_chart')), 0)
                            self.assertEqual(app.metric[2].value, '16 / 11 / 2026')
                        if view == 'Performance':
                            self.assertGreater(len(app.dataframe), 0)
                        if view == 'Risk Monitor':
                            self.assertGreater(len(app.metric), 0)
                            self.assertGreater(len(app.get('vega_lite_chart')), 0)
                        if view == 'Research & Methodology':
                            self.assertGreater(len(app.get('imgs')), 0)
            from src.riskbex.paths import DATA_DIR
            self.assertEqual(DATA_DIR, CANDIDATE / 'data')
            self.assertFalse(any(name in sys.modules for name in
                                 ['yfinance', 'xgboost', 'statsmodels', 'src.riskbex.engine.service',
                                  'src.riskbex.pipeline.service', 'src.riskbex.pipeline.provider']))

    def test_03_latest_history_performance_and_freshness(self):
        with offline():
            latest = self.get('/latest-risk')
            history = self.get('/historical-risk?limit=all')
            comparison = self.get('/backtesting/comparison')
            self.assertEqual(latest['date'], '2026-11-16')
            self.assertEqual(history[-1]['date'], latest['date'])
            for key in ['regime_label', 'cvar_95_60d', 'vol_20d', 'drawdown']:
                self.assertEqual(history[-1][key], latest[key])
            self.assertEqual(history[-1]['ibex_close'], latest['signal']['market']['ibex_close'])
            regimes = self.get('/regimes/history?limit=all')[-1]
            self.assertEqual(regimes['regime'], latest['signal']['markov']['regime'])
            for i in range(3):
                self.assertEqual(regimes[f'p_regime_{i}'], latest['signal']['markov']['probabilities'][str(i)])
            self.assertTrue(latest['publication']['is_current'])
            self.assertEqual(latest['publication'], comparison['publication'])
            self.assertEqual(len(comparison['metrics']), 7)
            self.assertEqual(len(comparison['turnover']), 3)
            self.assertEqual(comparison['results'][-1]['date'], latest['date'])
            with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-17T22:00Z')):
                stale = self.get('/latest-risk')['publication']
                self.assertFalse(stale['is_current'])
                self.assertEqual(stale['freshness'], 'stale')

    def test_04_simulator_exact_equivalence_all_strategies_and_bases(self):
        with offline():
            dates = self.get('/decision-explorer')['sessions']
            for strategy in ['benchmark', 'regime_based', 'ml_hard', 'ml_proba']:
                for basis in ['gross', 'net']:
                    with self.subTest(strategy=strategy, basis=basis):
                        params = dict(initial_capital=10000., start_date=dates[0]['date'],
                                      end_date=dates[-1]['date'], strategy=strategy, basis=basis)
                        exported = self.get('/investment-simulation', params)
                        with patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': str(SOURCE)}):
                            source = self.get('/investment-simulation', params)
                        # Operational attempt diagnostics are deliberately excluded from the bundle.
                        # Preserve strict equality for every other field, including every number.
                        self.assertIsNone(exported['publication']['update_status'])
                        source['publication']['update_status'] = None
                        self.assertEqual(exported, source)
            for language in ['en', 'es']:
                app = self.app(language, 'Investment Simulator').run()
                self.healthy(app)
                app.button(key='sim_submit').click().run()
                self.healthy(app)
                result = app.session_state['investment_simulation_result']
                self.assertEqual(result['publication']['version'], json.loads((CANDIDATE / 'snapshot.json').read_text())['version'])
                self.assertGreater(len(result['series']), 1)

    def test_05_research_endpoints_and_every_original_image(self):
        with offline():
            for path in ['/regimes/summary', '/regimes/model-selection', '/regimes/transitions',
                         '/regimes/durations', '/tail-risk/metrics', '/tail-risk/thresholds',
                         '/backtesting/academic/metrics']:
                self.assertTrue(self.get(path), path)
            for sample in ['main', 'robust']:
                for prefix in ['/tail-risk/events', '/tail-risk/latest', '/backtesting/academic/results',
                               '/backtesting/academic/latest']:
                    self.assertTrue(self.get(prefix + '?sample=' + sample))
                self.assertTrue(self.get('/regimes/history?split=' + sample.upper() + '&limit=all'))
            app = self.app(view='Research & Methodology').run()
            self.healthy(app)
            choices = list(app.radio(key='figure_selector').options)
            for choice in choices:
                app.radio(key='figure_selector').set_value(choice).run()
                self.healthy(app)
                self.assertGreater(len(app.get('imgs')), 0)

    def test_06_unavailable_api_missing_bundle_and_bad_checksum(self):
        with offline():
            # Proves the real bundle works while external API connections are forbidden.
            self.healthy(self.app(view='Overview').run())
            with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'RISKBEX_SNAPSHOT_DIR': temp}):
                app = self.app().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 1)
            with patch.dict(os.environ, {'RISKBEX_SNAPSHOT_SHA256': '0' * 64}):
                app = self.app().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 1)
            import requests
            with patch.dict(os.environ, {'RISKBEX_PRESENTATION_MODE': 'api'}), \
                 patch('requests.get', side_effect=requests.ConnectionError('Docker API absent')):
                st.cache_data.clear()
                app = AppTest.from_file(str(ROOT / 'backend/dashboard.py'), default_timeout=30).run()
                self.assertEqual(len(app.exception), 0)
                self.assertGreater(len(app.warning), 0)


if __name__ == '__main__':
    unittest.main()
