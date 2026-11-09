"""Targeted replay checks; no training, inference, retrieval or historical writes."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pydantic import ValidationError

from src.riskbex.api.operational import snapshot, performance_snapshot
from src.riskbex.backtesting.simulation import (
    simulate_investment, SimulationInputError, SimulationDataError,
)
from src.riskbex.pipeline.store import VersionStore
import test_operational_api

ROOT = Path(__file__).resolve().parents[1]


def fixture(returns=(0., 0., 0.), exposures=(.5, .5, .5)):
    dates = ['2026-11-02', '2026-11-03', '2026-11-04'][:len(returns)]
    rows = []
    for i, (day, ret, exposure) in enumerate(zip(dates, returns, exposures)):
        change = abs(exposure - exposures[i - 1]) if i else 0.
        row = dict(date=day, benchmark_return=ret)
        for key in ['regime_based', 'ml_hard', 'ml_proba']:
            row.update({f'{key}_return': exposure * ret,
                        f'{key}_return_net': exposure * ret - .001 * change,
                        f'transaction_cost_{key}': .001 * change,
                        f'exposure_change_{key}': change,
                        f'strategy_exposure_{key}': exposure})
        rows.append(row)
    return {'publication': {'version': 'fixture', 'model_version': 'main-v1', 'freshness': 'historical', 'is_current': False},
            'conventions': {'cost_rate': .001}, 'results': rows}


def replay(payload=None, **overrides):
    args = dict(initial_session='2026-10-30', initial_capital=1000., start_date='2026-10-30',
                end_date='2026-11-04', strategy='regime_based', basis='gross')
    args.update(overrides)
    return simulate_investment(fixture() if payload is None else payload, **args)


class SimulationMathTests(unittest.TestCase):
    def test_zero_returns(self):
        result = replay()
        self.assertEqual([p['portfolio_value_eur'] for p in result['series']], [1000.] * 4)
        for key in ['profit_loss_eur', 'cumulative_return', 'maximum_drawdown', 'annualized_volatility', 'daily_cvar_95']:
            self.assertEqual(result['portfolio'][key], 0.)
        self.assertEqual(result['costs_and_turnover']['total_turnover_exposure_units'], 0.)

    def test_constant_log_returns_and_initial_anchor(self):
        for ret in [.01, -.01]:
            with self.subTest(ret=ret):
                result = replay(fixture([ret] * 3, [1.] * 3))
                expected = 1000 * np.exp(np.arange(4) * ret)
                np.testing.assert_allclose([p['portfolio_value_eur'] for p in result['series']], expected)
                self.assertAlmostEqual(result['portfolio']['cumulative_return'], np.exp(3 * ret) - 1)
                self.assertAlmostEqual(result['portfolio']['daily_cvar_95'], ret)
                self.assertAlmostEqual(result['portfolio']['annualized_volatility'], 0.)
                self.assertAlmostEqual(result['portfolio']['maximum_drawdown'], np.exp(3 * ret) - 1 if ret < 0 else 0.)

    def test_mid_history_and_end_inclusion(self):
        payload = fixture([.5, .01, -.02], [1.] * 3)
        result = replay(payload, start_date='2026-11-02', end_date='2026-11-03')
        self.assertEqual([p['date'] for p in result['series']], ['2026-11-02', '2026-11-03'])
        self.assertEqual(result['series'][0]['portfolio_value_eur'], 1000.)
        self.assertAlmostEqual(result['portfolio']['final_capital_eur'], 1000 * np.exp(.01))
        self.assertEqual(result['portfolio']['return_observations'], 1)
        self.assertIsNone(result['portfolio']['annualized_volatility'])
        self.assertAlmostEqual(result['portfolio']['daily_cvar_95'], .01)
        self.assertEqual(result['portfolio'], result['buy_hold'])

    def test_empty_return_window_has_no_invented_risk_metrics(self):
        result = replay(start_date='2026-11-03', end_date='2026-11-03')
        self.assertEqual(len(result['series']), 1)
        self.assertEqual(result['portfolio']['final_capital_eur'], 1000.)
        self.assertEqual(result['portfolio']['maximum_drawdown'], 0.)
        self.assertIsNone(result['portfolio']['annualized_volatility'])
        self.assertIsNone(result['portfolio']['daily_cvar_95'])
        self.assertIsNone(result['effective_dates']['first_return_session'])

    def test_net_costs_preserve_published_boundary_and_not_double_counted(self):
        payload = fixture([.01, .02, -.01], [.5, 1., .25])
        gross = replay(payload, start_date='2026-11-02')
        net = replay(payload, start_date='2026-11-02', basis='net')
        expected_cost = .001 * (.5 + .75)
        self.assertAlmostEqual(net['portfolio']['final_capital_eur'], gross['portfolio']['final_capital_eur'] * np.exp(-expected_cost))
        info = net['costs_and_turnover']
        self.assertEqual(info['total_turnover_exposure_units'], 1.25)
        self.assertEqual(info['deducted_cost_log_return'], expected_cost)
        self.assertFalse(info['entry_cost_included'])
        self.assertEqual(gross['costs_and_turnover']['deducted_cost_log_return'], 0.)
        self.assertEqual(gross['costs_and_turnover']['published_cost_log_return'], expected_cost)
        for basis in ['gross', 'net']:
            result = replay(payload, strategy='benchmark', basis=basis)
            self.assertEqual(result['portfolio'], result['buy_hold'])
            self.assertEqual(result['costs_and_turnover']['deducted_cost_log_return'], 0.)

    def test_api_chart_series_and_participation_are_aligned(self):
        payload = fixture([-.02, .03, -.01], [.5, 1., .25])
        result = replay(payload, basis='net')
        series = result['series']
        self.assertEqual(series[0]['portfolio_drawdown'], 0.)
        self.assertEqual(series[0]['buy_hold_drawdown'], 0.)
        self.assertIsNone(series[0]['applied_exposure'])
        self.assertIsNone(series[0]['cash_exposure'])
        self.assertEqual([r['applied_exposure'] for r in series[1:]], [.5, 1., .25])
        self.assertEqual([r['cash_exposure'] for r in series[1:]], [.5, 0., .75])
        for field, metrics in [('portfolio_drawdown', 'portfolio'), ('buy_hold_drawdown', 'buy_hold')]:
            self.assertAlmostEqual(min(r[field] for r in series), result[metrics]['maximum_drawdown'])
        down, up = result['participation']['down_market'], result['participation']['up_market']
        self.assertEqual(down['sessions'], 2)
        self.assertEqual(down['average_applied_exposure'], .375)
        self.assertAlmostEqual(down['log_return_difference_vs_buy_hold'], .01 + .0075 - .00075)
        self.assertEqual(up['sessions'], 1)
        self.assertAlmostEqual(up['log_return_difference_vs_buy_hold'], -.0005)
        benchmark = replay(payload, strategy='benchmark', basis='net')
        self.assertTrue(all(r['applied_exposure'] == 1. for r in benchmark['series'][1:]))
        self.assertEqual(benchmark['participation']['down_market']['log_return_difference_vs_buy_hold'], 0.)
        empty = replay(start_date='2026-11-03', end_date='2026-11-03')
        self.assertEqual(empty['participation']['down_market']['sessions'], 0)
        self.assertIsNone(empty['participation']['down_market']['log_return_difference_vs_buy_hold'])

    def test_missing_dates_invalid_capital_and_limits(self):
        for day in ['2026-11-01', '2026-10-29']:
            with self.subTest(day=day), self.assertRaises(SimulationInputError):
                replay(start_date=day)
        with self.assertRaises(SimulationInputError):
            replay(end_date='2026-11-05')
        for capital in [0, -1, float('nan'), float('inf'), True, 1e13]:
            with self.subTest(capital=capital), self.assertRaises(ValidationError):
                replay(initial_capital=capital)
        for args in [dict(start_date='invalid'), dict(start_date='2026-11-04', end_date='2026-11-02'),
                     dict(strategy='robust'), dict(basis='other')]:
            with self.subTest(args=args), self.assertRaises(ValidationError):
                replay(**args)
        with patch('src.riskbex.backtesting.simulation.MAX_RETURN_SESSIONS', 2), self.assertRaises(SimulationInputError):
            replay()

    def test_missing_nonfinite_and_inconsistent_history(self):
        for column, value in [('ml_hard_return_net', None), ('benchmark_return', float('nan')),
                              ('transaction_cost_ml_hard', .5), ('strategy_exposure_ml_hard', 1.1)]:
            payload = fixture()
            payload['results'][1][column] = value
            with self.subTest(column=column), self.assertRaises(SimulationDataError):
                replay(payload, strategy='ml_hard', basis='net')
        payload = fixture()
        payload['results'][1]['date'] = payload['results'][0]['date']
        with self.assertRaises(SimulationDataError):
            replay(payload)
        payload = fixture()
        del payload['results'][0]['regime_based_return']
        with self.assertRaises(SimulationDataError):
            replay(payload)

    def test_no_lookahead_or_exposure_reapplication_or_mutation(self):
        payload = fixture([-.1, .1, .5], [.5, 1., .25])
        before = copy.deepcopy(payload)
        result = replay(payload, end_date='2026-11-03')
        self.assertAlmostEqual(result['portfolio']['final_capital_eur'], 1000 * np.exp(-.05 + .1))
        self.assertEqual(payload, before)
        payload['results'][-1]['regime_based_return'] = -100.
        payload['results'][-1]['strategy_exposure_regime_based'] = .99
        self.assertEqual(replay(payload, end_date='2026-11-03'), result)


class SimulationPublicationTests(unittest.TestCase):
    request = test_operational_api.OperationalApiTests.request

    def setUp(self):
        env = patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': str(ROOT / 'runtime/main-wsl-test')})
        env.start(); self.addCleanup(env.stop)
        self.data = snapshot()
        self.comparison = performance_snapshot(self.data)
        self.args = dict(initial_session=self.data['history'].date.iloc[0], initial_capital=10000.,
                         start_date=self.data['history'].date.iloc[0], end_date=self.data['backtest'].date.iloc[-1])

    def test_full_window_matches_stored_results_and_metrics(self):
        labels = {'benchmark': 'Buy & Hold', 'regime_based': 'Regime-based',
                  'ml_hard': 'ML Hard', 'ml_proba': 'ML Probability-Weighted'}
        for strategy, label in labels.items():
            for basis in ['gross', 'net']:
                with self.subTest(strategy=strategy, basis=basis):
                    result = simulate_investment(self.comparison, **self.args, strategy=strategy, basis=basis)
                    suffix = '_net' if strategy != 'benchmark' and basis == 'net' else ''
                    values = 10000 * self.data['backtest'][strategy + '_cum' + suffix]
                    np.testing.assert_allclose([p['portfolio_value_eur'] for p in result['series'][1:]], values, rtol=1e-12)
                    stored = label if strategy == 'benchmark' else label + (' net of costs' if basis == 'net' else ' gross')
                    row = self.data['metrics'].set_index('strategy').loc[stored]
                    for key, column in [('cumulative_return', 'total_return'), ('annualized_volatility', 'annualized_volatility'),
                                        ('daily_cvar_95', 'CVaR_95')]:
                        self.assertAlmostEqual(result['portfolio'][key], row[column], places=12)
                    anchored = np.r_[10000., values]
                    self.assertAlmostEqual(result['portfolio']['maximum_drawdown'], np.min(anchored / np.maximum.accumulate(anchored) - 1))
                    self.assertLessEqual(result['portfolio']['maximum_drawdown'], row.max_drawdown + 1e-12)
                    json.dumps(result, allow_nan=False)

    def url(self, **overrides):
        args = {k: v for k, v in self.args.items() if k != 'initial_session'}
        args.update(strategy='ml_hard', basis='net')
        args.update(overrides)
        return '/investment-simulation?' + '&'.join(f'{k}={v}' for k, v in args.items())

    def test_one_snapshot_no_inference_download_or_writes(self):
        from src.riskbex.engine import service
        original = VersionStore.current
        reads = []
        def track(store):
            reads.append(True)
            return original(store)
        with patch.object(VersionStore, 'current', track), \
             patch.object(VersionStore, 'publish', side_effect=AssertionError('write')), \
             patch.object(service, 'infer_main_signals', side_effect=AssertionError('inference')), \
             patch('src.riskbex.pipeline.store.write_json', side_effect=AssertionError('write')), \
             patch('requests.get', side_effect=AssertionError('download')):
            response = self.request(self.url())
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertEqual(len(reads), 1)
        body = response.json()
        self.assertEqual(body['publication']['version'], self.data['publication']['version'])
        self.assertEqual(body['publication']['model_version'], self.data['publication']['model_version'])
        self.assertEqual(len(body['series']), len(self.data['backtest']) + 1)
        self.assertEqual(body['inputs']['basis'], 'net')

    def test_api_invalid_inputs_missing_publication_and_compatibility(self):
        for args in [dict(initial_capital=0), dict(initial_capital='nan'), dict(initial_capital='inf'),
                     dict(strategy='robust'), dict(basis='other'), dict(start_date='2026-11-07'),
                     dict(end_date='2020-01-01'), dict(start_date='invalid')]:
            with self.subTest(args=args):
                self.assertEqual(self.request(self.url(**args)).status_code, 422)
        with patch('src.riskbex.backtesting.simulation.MAX_RETURN_SESSIONS', 1):
            self.assertEqual(self.request(self.url()).status_code, 422)
        with tempfile.TemporaryDirectory() as empty, patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': empty}):
            self.assertEqual(self.request(self.url()).status_code, 503)
        self.assertEqual(self.request('/backtesting/comparison').json(), self.comparison)
