"""Targeted stored-decision checks. No model inference, training or downloads."""
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import requests
import streamlit as st
from fastapi import HTTPException

import test_dashboard_ui
import test_operational_api
from src.riskbex.api.operational import snapshot
from src.riskbex.api.decisions import decision_snapshot
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DecisionExplorerTests(unittest.TestCase):
    request = test_operational_api.OperationalApiTests.request
    run_app = test_dashboard_ui.DashboardUI.run_app

    def setUp(self):
        st.cache_data.clear()
        env = patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': str(ROOT / 'runtime/main-wsl-test')})
        env.start(); self.addCleanup(env.stop)
        clock = patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-07T22:00Z'))
        clock.start(); self.addCleanup(clock.stop)

    def test_mapping_reconstruction_previous_and_first_session(self):
        with patch('src.riskbex.api.operational.snapshot', wraps=snapshot) as read:
            response = self.request('/decision-explorer')
        self.assertEqual(response.status_code, 200, response.text)
        read.assert_called_once()
        body = response.json()
        mapping = {r['regime']: r for r in body['mapping']}
        self.assertEqual({k: r['economic_label'] for k, r in mapping.items()},
                         {0: 'low_risk', 2: 'medium_risk', 1: 'high_risk'})
        sessions = body['sessions']
        self.assertEqual(len(sessions), 1497)
        self.assertEqual(sessions[-1]['next_session_date'], '2026-11-09')
        self.assertEqual(sessions[-1]['ibex_close'], 19369.5)
        for i, row in enumerate(sessions):
            expected = sum(row[f'proba_{k}'] * r['target_exposure'] for k, r in mapping.items())
            self.assertAlmostEqual(row['target_exposure_ml_proba'], expected, places=12)
            self.assertEqual(row['economic_label'], mapping[row['regime']]['economic_label'])
            if i < len(sessions) - 1:
                self.assertEqual(row['next_session_date'], sessions[i + 1]['date'])
            for key in ['regime_based', 'ml_hard', 'ml_proba']:
                if not i:
                    self.assertIsNone(row[f'previous_target_{key}'])
                    self.assertIsNone(row[f'change_pp_{key}'])
                    self.assertEqual(row[f'direction_{key}'], 'N/A')
                else:
                    previous = sessions[i - 1][f'target_exposure_{key}']
                    self.assertAlmostEqual(row[f'previous_target_{key}'], previous)
                    diff = (row[f'target_exposure_{key}'] - previous) * 100
                    self.assertAlmostEqual(row[f'change_pp_{key}'], diff, places=10)
                    expected_direction = 'Unchanged' if abs(diff) < 1e-10 else 'Increase' if diff > 0 else 'Decrease'
                    self.assertEqual(row[f'direction_{key}'], expected_direction)

    def test_session_selection_and_invalid_dates(self):
        response = self.request('/decision-explorer?session=2026-11-06')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['selected']['date'], '2026-11-06')
        for date in ['2026-11-07', 'not-a-date', '1990-01-01', '2026-11-06T00:00:00']:
            self.assertEqual(self.request('/decision-explorer?session=' + date).status_code, 404)

    def test_missing_mapping_version_and_incomplete_data(self):
        for mode in ['package', 'mapping', 'signals', 'probabilities', 'targets']:
            data = snapshot()
            if mode == 'package': data['manifest']['model_manifest_sha256'] = '0' * 64
            elif mode == 'mapping': data['manifest']['model_hashes']['markov/cvar_mapping.json'] = '0' * 64
            elif mode == 'signals': data['history'] = data['history'].iloc[:0]
            elif mode == 'probabilities': data['history'].loc[0, 'proba_0'] = np.nan
            else: data['history'].loc[0, 'target_exposure_ml_proba'] = .75
            with self.subTest(mode=mode), self.assertRaises(HTTPException) as exc:
                decision_snapshot(data)
            self.assertEqual(exc.exception.status_code, 503)
        with tempfile.TemporaryDirectory() as empty, patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': empty}):
            self.assertEqual(self.request('/decision-explorer').status_code, 503)

    def test_optional_close_and_api_backward_compatibility(self):
        data = snapshot()
        data['features'] = data['features'].drop(columns=['ibex_close'])
        self.assertIsNone(decision_snapshot(data)['sessions'][-1]['ibex_close'])
        for path in ['/latest-risk', '/historical-risk?limit=1', '/backtesting/comparison']:
            response = self.request(path)
            self.assertEqual(response.status_code, 200, response.text[:100])
        from src.riskbex.api.schemas import HistoricalRiskPoint, LatestRiskResponse
        LatestRiskResponse.model_validate(self.request('/latest-risk').json())
        HistoricalRiskPoint.model_validate(self.request('/historical-risk?limit=1').json()[0])

    def test_dashboard_selector_comparison_and_chart(self):
        with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-09T22:00Z')):
            payload = self.request('/decision-explorer').json()
        def get(url, **kwargs):
            value = payload if '/decision-explorer' in url else ({} if '/latest' in url else [])
            return Mock(json=lambda: value, raise_for_status=lambda: None)
        app = self.run_app(get, 'Explore')
        selector = app.selectbox(key='decision_session')
        self.assertEqual(selector.options, [row['date'] for row in payload['sessions']])
        self.assertNotIn('2026-11-07', selector.options)
        self.assertEqual(selector.value, '2026-11-06')
        self.assertTrue(any('stale or non-current' in w.value for w in app.warning))
        self.assertTrue(any(w.value == 'Historical Backtest — Not Live Trading Records.' for w in app.info))
        self.assertTrue(app.get('vega_lite_chart'))
        with patch('requests.get', side_effect=get), patch('requests.post') as post:
            app.selectbox(key='decision_session').set_value(selector.options[0]).run()
            app.selectbox(key='decision_chart_strategy').set_value('ML Probability-Weighted').run()
            post.assert_not_called()
        self.assertFalse(app.exception, str(app.exception))
        tables = [w.value for w in app.dataframe if 'Previous Target' in w.value.columns]
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]['Previous Target'].tolist(), ['N/A'] * 3)
        self.assertEqual(tables[0]['Direction'].tolist(), ['N/A'] * 3)
        self.assertTrue(any(m.label == 'Market Information Date' and m.value == selector.options[0] for m in app.metric))

    def test_dashboard_missing_data(self):
        def get(url, **kwargs):
            if '/decision-explorer' in url:
                raise requests.ConnectionError('offline')
            return Mock(json=lambda: {} if '/latest' in url else [], raise_for_status=lambda: None)
        app = self.run_app(get, 'Explore')
        self.assertTrue(any('Verified decision history is unavailable' in w.value for w in app.warning))
