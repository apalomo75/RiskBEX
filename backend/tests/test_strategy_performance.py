"""Stored MAIN performance and interface checks; no inference or providers."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import streamlit as st

import test_dashboard_ui
import test_operational_api
from src.riskbex.api.operational import snapshot, performance_snapshot
from src.riskbex.pipeline.store import digest
from src.riskbex.backtesting.costs import summarize_returns

ROOT = Path(__file__).resolve().parents[1]


class StrategyPerformanceTests(unittest.TestCase):
    request = test_operational_api.OperationalApiTests.request
    run_app = test_dashboard_ui.DashboardUI.run_app

    def setUp(self):
        st.cache_data.clear()
        env = patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': str(ROOT / 'runtime/main-wsl-test')})
        env.start(); self.addCleanup(env.stop)
        clock = patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-07T22:00Z'))
        clock.start(); self.addCleanup(clock.stop)

    def test_current_mapping_alignment_costs_and_metrics(self):
        data = snapshot()
        signals, bt = data['history'], data['backtest']
        path = ROOT / 'model_packages/main-v1/markov/cvar_mapping.json'
        self.assertEqual(digest(path), data['manifest']['model_hashes']['markov/cvar_mapping.json'])
        metadata_path = ROOT / 'model_packages/main-v1/xgboost/metadata.json'
        self.assertEqual(digest(metadata_path), data['manifest']['model_hashes']['xgboost/metadata.json'])
        metadata = json.loads(metadata_path.read_text())
        self.assertGreater(signals.date.iloc[0], metadata['trained_through'])
        mapping = pd.DataFrame(json.loads(path.read_text()))
        exposures = mapping.set_index('regime').target_exposure
        np.testing.assert_allclose(signals.target_exposure_regime_based, signals.regime.map(exposures))
        np.testing.assert_allclose(signals.target_exposure_ml_hard, signals.regime_pred.map(exposures))
        np.testing.assert_allclose(signals.target_exposure_ml_proba,
                                   sum(signals[f'proba_{int(k)}'] * v for k, v in exposures.items()))
        self.assertEqual(bt.date.tolist(), signals.date.iloc[1:].tolist())
        self.assertEqual(bt.date.iloc[0], '2021-01-05')
        np.testing.assert_allclose(bt.benchmark_return, bt.ret_1d)
        for key, label in [('regime_based', 'Regime-based'), ('ml_hard', 'ML Hard'), ('ml_proba', 'ML Probability-Weighted')]:
            exposure = bt[f'strategy_exposure_{key}']
            np.testing.assert_allclose(exposure, signals[f'target_exposure_{key}'].iloc[:-1])
            np.testing.assert_allclose(bt[f'{key}_return'], exposure * bt.ret_1d)
            costs = exposure.diff().abs().fillna(0) * data['manifest']['cost_rate']
            np.testing.assert_allclose(bt[f'transaction_cost_{key}'], costs, atol=1e-15)
            np.testing.assert_allclose(bt[f'{key}_return_net'], bt[f'{key}_return'] - costs)
            for suffix, metric_suffix in [('', ' gross'), ('_net', ' net of costs')]:
                returns = bt[f'{key}_return{suffix}']
                np.testing.assert_allclose(bt[f'{key}_cum{suffix}'], np.exp(returns.cumsum()))
                expected = summarize_returns(returns, bt.date, sample='main', strategy=label + metric_suffix)
                row = data['metrics'].set_index('strategy').loc[label + metric_suffix]
                for col in ['total_return', 'annualized_volatility', 'CVaR_95', 'max_drawdown']:
                    self.assertAlmostEqual(row[col], expected[col], places=12)
            turn_label = 'ML Hard Classification' if key == 'ml_hard' else label
            row = data['turnover'].set_index('strategy').loc[turn_label]
            self.assertAlmostEqual(row.total_turnover, exposure.diff().abs().sum())

    def test_snapshot_api_and_compatibility(self):
        response = self.request('/backtesting/comparison')
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body['metrics']), 7)
        self.assertEqual(len(body['turnover']), 3)
        self.assertEqual(len(body['results']), 1496)
        self.assertEqual(body['conventions']['cost_rate'], .001)
        for key in ['regime_based', 'ml_hard', 'ml_proba']:
            r = self.request('/backtesting/results?strategy=' + key)
            self.assertEqual(r.status_code, 200, r.text[:200])
            self.assertEqual(r.json()[0]['date'], body['results'][0]['date'])
        for path in ['/backtesting/academic/results?sample=main', '/backtesting/academic/results?sample=robust',
                     '/backtesting/academic/metrics', '/backtesting/academic/latest?sample=main']:
            academic = self.request(path)
            self.assertEqual(academic.status_code, 200, academic.text[:200])
        with patch('src.riskbex.api.routes.backtesting.load_adaptive_backtest_results',
                   side_effect=AssertionError('academic data must not be read')):
            self.assertEqual(self.request('/backtesting/comparison').status_code, 200)

    def test_incomplete_and_missing_publication(self):
        for field in ['backtest', 'metrics', 'history', 'turnover']:
            with self.subTest(field=field):
                data = snapshot()
                data[field] = data[field].iloc[:0]
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as exc:
                    performance_snapshot(data)
                self.assertEqual(exc.exception.status_code, 503)
        for field, column in [('metrics', 'total_transaction_cost'), ('turnover', 'total_turnover')]:
            data = snapshot()
            data[field].loc[0, column] = np.nan
            with self.assertRaises(HTTPException):
                performance_snapshot(data)
        with tempfile.TemporaryDirectory() as empty, patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': empty}):
            self.assertEqual(self.request('/backtesting/comparison').status_code, 503)

    def test_dashboard_selection_gross_net_and_stale(self):
        with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-09T22:00Z')):
            payload = self.request('/backtesting/comparison').json()
        def get(url, **kwargs):
            value = payload if '/backtesting/comparison' in url else ({} if '/latest' in url else [])
            return Mock(json=lambda: value, raise_for_status=lambda: None)
        app = self.run_app(get, 'Results')
        overview = next(t for t in app.tabs if t.label == 'Overview')
        performance = next(t for t in app.tabs if t.label == 'Performance')
        overview_table = next(w.value for w in overview.dataframe if 'Total Return' in w.value.columns)
        self.assertEqual(len(overview_table), 4)
        for name in ['Buy & Hold', 'Regime-Based', 'ML Hard', 'ML Probability-Weighted']:
            self.assertTrue(any(name in w.value for w in overview.markdown))
            self.assertTrue(any(name in w.value for w in performance.markdown))
        expected = pd.DataFrame(payload['metrics']).set_index('strategy')
        for name, stored in [('Buy & Hold', 'Buy & Hold'), ('Regime-Based', 'Regime-based net of costs'),
                             ('ML Hard', 'ML Hard net of costs'), ('ML Probability-Weighted', 'ML Probability-Weighted net of costs')]:
            row = overview_table.loc[overview_table.Strategy == name].iloc[0]
            for label, key in [('Total Return', 'total_return'), ('Annualized Volatility', 'annualized_volatility'),
                               ('Expected Shortfall (95%)', 'CVaR_95'), ('Maximum Drawdown', 'max_drawdown')]:
                self.assertEqual(row[label], f'{expected.loc[stored, key]:.2%}')
        self.assertTrue(any('ML Hard versus Regime-Based' in w.value for w in performance.markdown))
        self.assertTrue(any(w.value == 'What the Results Mean' for w in performance.subheader))
        gross_story = next(w.value for w in performance.markdown if 'ML Hard versus Regime-Based' in w.value)
        self.assertIn('Transaction Costs: +0.00 log-return points', gross_story)
        self.assertTrue(any('ML Probability-Weighted versus ML Hard' in w.value for w in performance.markdown))
        simulator = next(t for t in app.tabs if t.label == 'Investment Simulator')
        self.assertEqual(len(simulator.metric), 0)
        self.assertEqual(len(simulator.button), 0)
        self.assertEqual(len(simulator.slider), 0)
        selector = next(w for w in app.multiselect if w.label == 'Strategies')
        self.assertEqual(len(selector.value), 4)
        self.assertTrue(any('stale or non-current' in w.value for w in app.warning))
        with patch('requests.get', side_effect=get), patch('requests.post') as post:
            app.multiselect(key='performance_strategies').set_value(['ML Hard']).run()
            app.radio(key='performance_basis').set_value('Net of Transaction Costs').run()
            post.assert_not_called()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        tables = [w.value for w in app.dataframe if 'Total Return' in w.value.columns]
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[1].iloc[0]['Strategy'], 'ML Hard')
        self.assertEqual(tables[1].iloc[0]['Total Return'], '74.52%')
        performance = next(t for t in app.tabs if t.label == 'Performance')
        ml = expected.loc['ML Hard net of costs']
        regime = expected.loc['Regime-based net of costs']
        delta = (ml.total_return - regime.total_return) * 100
        self.assertTrue(any(f'ML Hard versus Regime-Based — Total Return: {delta:+.2f} percentage points' in w.value
                            for w in performance.markdown))
        self.assertTrue(any('ML Hard versus Buy & Hold' in w.value for w in performance.markdown))
        net_story = next(w.value for w in performance.markdown if 'ML Hard versus Regime-Based' in w.value)
        cost_delta = (ml.total_transaction_cost - regime.total_transaction_cost) * 100
        self.assertIn(f'Transaction Costs: {cost_delta:+.2f} log-return points (higher costs)', net_story)
        frame = pd.DataFrame(payload['results'])
        falling = frame.loc[frame.benchmark_return < 0]
        loss_difference = (falling.ml_hard_return_net - falling.benchmark_return).sum() * 100
        self.assertTrue(any(f'{len(falling):,} down-market sessions' in w.value and
                            f'{loss_difference:+.2f} log-return points (less loss than Buy & Hold)' in w.value
                            for w in performance.markdown))
        self.assertTrue(any('not continuous-period returns' in w.value for w in performance.caption))
        self.assertTrue(any('Academic Reference — Original TFM Methodology' in w.label for w in app.expander))

    def test_dashboard_missing_comparison(self):
        def get(url, **kwargs):
            if '/backtesting/comparison' in url:
                import requests
                raise requests.ConnectionError('offline')
            return Mock(json=lambda: {} if '/latest' in url else [], raise_for_status=lambda: None)
        app = self.run_app(get, 'Results')
        self.assertTrue(any('complete validated operational strategy comparison is unavailable' in w.value for w in app.info))
