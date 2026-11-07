"""Read the existing real publication through HTTP serialization and Streamlit."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests
import streamlit as st

import test_dashboard_ui
import test_operational_api

ROOT = Path(__file__).resolve().parents[1]


class OperationalIntegrationTests(unittest.TestCase):
    request = test_operational_api.OperationalApiTests.request
    run_app = test_dashboard_ui.DashboardUI.run_app

    def setUp(self):
        st.cache_data.clear()
        env = patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': str(ROOT / 'runtime/main-wsl-test')})
        env.start()
        self.addCleanup(env.stop)
        clock = patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-07T22:00Z'))
        clock.start()
        self.addCleanup(clock.stop)

    def test_real_publication_http_and_monitor(self):
        response = self.request('/latest-risk')
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        signal = body['signal']
        self.assertEqual(body['publication']['data_date'], '2026-11-06')
        self.assertEqual(body['publication']['freshness'], 'current')
        self.assertEqual(body['publication']['last_successful_update'], signal['generated_at'])
        self.assertEqual(signal['target_session_date'], '2026-11-09')
        self.assertEqual(signal['market']['ibex_close'], 19369.5)
        for key, probability in [('markov', .9150), ('xgboost', .8968)]:
            self.assertEqual(signal[key]['economic_label'], 'medium_risk')
            self.assertAlmostEqual(signal[key]['probabilities']['2'], probability, places=4)
        for key, target in [('regime_based', .5906), ('ml_hard', .5906), ('ml_probability_weighted', .6325)]:
            self.assertAlmostEqual(signal['target_exposures'][key], target, places=4)
        history = self.request('/historical-risk?limit=90')
        self.assertEqual(history.status_code, 200, history.text)
        def get(url, **kwargs):
            if '/latest-risk' in url:
                return response
            if '/historical-risk' in url:
                return history
            return Mock(json=lambda: {} if '/latest' in url else [], raise_for_status=lambda: None)
        app = self.run_app(get, 'Monitor')
        metrics = {m.label: m.value for m in app.metric}
        self.assertEqual(metrics['Last Market Close · IBEX 35'], '19,369.50')
        self.assertEqual(metrics['Last Market Data Date'], '2026-11-06')
        self.assertEqual(metrics['Forecast Target Session'], '2026-11-09')
        self.assertEqual(metrics['Target Portfolio Exposure Regime-Based Strategy'], '59.06%')
        self.assertEqual(metrics['Target Portfolio Exposure ML Hard Strategy'], '59.06%')
        self.assertEqual(metrics['Target Portfolio Exposure Probability-Weighted Strategy'], '63.25%')
        text = ' '.join(m.value for m in app.markdown)
        for expected in ['Medium Risk', '91.50%', '89.68%', '2026-11-06']:
            self.assertIn(expected, text)
        self.assertTrue(next(b for b in app.button if b.label == 'Update Market Data').disabled)

    def test_real_publication_becomes_stale_after_next_session(self):
        with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-09T22:00Z')):
            response = self.request('/latest-risk')
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['publication']['freshness'], 'stale')
        self.assertFalse(body['publication']['is_current'])
        self.assertEqual(body['publication']['expected_data_date'], '2026-11-09')
        def get(url, **kwargs):
            return response if '/latest-risk' in url else Mock(json=lambda: [], raise_for_status=lambda: None)
        app = self.run_app(get, 'Monitor')
        self.assertTrue(any('Stale Market Data' in w.value for w in app.warning))

    def test_missing_publication(self):
        with tempfile.TemporaryDirectory() as empty, patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': empty}):
            response = self.request('/latest-risk')
        self.assertEqual(response.status_code, 503)
        missing = requests.Response()
        missing.status_code = response.status_code
        missing._content = response.content
        missing.url = 'http://test/latest-risk'
        app = self.run_app(lambda *a, **k: missing, 'Monitor')
        self.assertTrue(any('No usable operational MAIN publication' in w.value for w in app.warning))

    def test_unavailable_fastapi(self):
        def unavailable(*args, **kwargs):
            raise requests.ConnectionError('offline')
        app = self.run_app(unavailable, 'Monitor')
        self.assertTrue(any('FastAPI is unavailable' in w.value for w in app.warning))

    def test_legacy_payload_cannot_supply_header_date(self):
        def get(url, **kwargs):
            payload = {'date': '2026-05-15'} if '/latest-risk' in url else ({} if '/latest' in url else [])
            return Mock(json=lambda: payload, raise_for_status=lambda: None)
        app = self.run_app(get, 'Monitor')
        self.assertNotIn('2026-05-15', ' '.join(m.value for m in app.markdown))
        self.assertTrue(app.warning)
