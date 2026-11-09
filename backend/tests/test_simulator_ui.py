"""Form/API/chart presentation checks; no market retrieval or inference."""
import ast
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.riskbex.simulator_ui import money, percentage, series_chart
from test_dashboard_ui import SPANISH
from test_investment_simulation import fixture, replay

APP = '''
import requests
import streamlit as st
from src.riskbex.simulator_ui import render_investment_simulator
@st.cache_data(ttl=30)
def sessions():
    response = requests.get('http://test/decision-explorer')
    response.raise_for_status()
    return response.json()
technical = {}
render_investment_simulator('http://test', sessions, technical)
with st.expander('Technical Details'):
    st.json(technical)
'''


class SimulatorUITests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.path = fixture([-.02, .03, -.01], [.5, 1., .25])
        self.result = replay(self.path, initial_capital=10000., basis='net')
        self.result['publication'].update(version='publication-hash-sentinel', model_version='package-sentinel', data_date='2026-11-04')
        self.sessions = {'sessions': [{'date': d} for d in ['2026-10-30', '2026-11-02', '2026-11-03', '2026-11-04']],
                         'publication': self.result['publication']}
        self.calls = []
        self.error = None
        self.answer = self.result

    def get(self, url, **kwargs):
        if url.endswith('/decision-explorer'):
            return Mock(json=lambda: self.sessions, raise_for_status=lambda: None)
        self.assertTrue(url.endswith('/investment-simulation'))
        self.calls.append(kwargs['params'])
        if self.error:
            raise self.error
        return Mock(json=lambda: self.answer, raise_for_status=lambda: None)

    def run_app(self, app=None):
        app = app or AppTest.from_string(APP, default_timeout=20)
        with patch('requests.get', side_effect=self.get), patch('requests.post') as post, \
             patch('src.riskbex.backtesting.simulation.simulate_investment', side_effect=AssertionError('No local engine')):
            app.run()
            post.assert_not_called()
        self.assertFalse(app.exception, str(app.exception))
        return app

    def test_submission_default_mapping_results_and_no_automatic_requests(self):
        app = self.run_app()
        self.assertEqual(self.calls, [])
        self.assertEqual(app.number_input(key='sim_capital').value, 10000.)
        self.assertEqual(app.selectbox(key='sim_start').options, [r['date'] for r in self.sessions['sessions']])
        app.button(key='sim_submit').click()
        app = self.run_app(app)
        self.assertEqual(self.calls, [dict(initial_capital=10000., start_date='2026-10-30', end_date='2026-11-04', strategy='regime_based', basis='net')])
        values = {m.label: m.value for m in app.metric}
        self.assertEqual(values['Final Portfolio Value'], money(self.result['portfolio']['final_capital_eur']))
        self.assertEqual(values['Cumulative Return'], percentage(self.result['portfolio']['cumulative_return']))
        self.assertEqual(values['Difference vs Buy & Hold'], money(self.result['comparison_minus_buy_hold']['final_capital_eur']))
        self.assertEqual(len(app.get('vega_lite_chart')), 3)
        self.assertTrue(any('non-current' in w.value for w in app.warning))
        visible = ' '.join(w.value for w in app.markdown) + ' '.join(w.value for w in app.caption)
        self.assertNotIn('publication-hash-sentinel', visible)
        self.assertNotIn('package-sentinel', visible)
        self.assertIn('publication-hash-sentinel', str(app.json[0].value))
        app.number_input(key='sim_capital').set_value(15000.)
        app.selectbox(key='sim_strategy').select('ML Hard')
        self.run_app(app)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(app.metric[0].value, '€10,000.00')

    def test_gross_and_all_strategy_mappings(self):
        app = self.run_app()
        for label, key in [('Buy & Hold', 'benchmark'), ('Regime-Based', 'regime_based'), ('ML Hard', 'ml_hard'), ('ML Probability-Weighted', 'ml_proba')]:
            self.answer = replay(self.path, initial_capital=12345., strategy=key, basis='gross')
            app.number_input(key='sim_capital').set_value(12345.)
            app.selectbox(key='sim_strategy').select(label)
            app.radio(key='sim_basis').set_value('Gross')
            app.button(key='sim_submit').click()
            self.run_app(app)
            self.assertEqual(self.calls[-1]['strategy'], key)
            self.assertEqual(self.calls[-1]['basis'], 'gross')
            self.assertEqual(self.calls[-1]['initial_capital'], 12345.)
            self.assertFalse(app.error)

    def test_capital_and_date_validation(self):
        app = self.run_app()
        app.number_input(key='sim_capital').set_value(0.)
        app.button(key='sim_submit').click()
        self.run_app(app)
        self.assertEqual(self.calls, [])
        self.assertTrue(any('strictly positive' in x.value for x in app.error))
        app.number_input(key='sim_capital').set_value(10000.)
        app.selectbox(key='sim_start').select('2026-11-04')
        app.selectbox(key='sim_end').select('2026-10-30')
        app.button(key='sim_submit').click()
        self.run_app(app)
        self.assertEqual(self.calls, [])
        self.assertTrue(any('on or before' in x.value for x in app.error))

    def test_errors_clear_previous_results(self):
        app = self.run_app()
        app.button(key='sim_submit').click()
        self.run_app(app)
        for error in [requests.ConnectionError('offline'), requests.Timeout('timeout'),
                      requests.HTTPError(response=Mock(status_code=422)), requests.HTTPError(response=Mock(status_code=503)),
                      requests.HTTPError(response=Mock(status_code=500))]:
            self.error = error
            app.button(key='sim_submit').click()
            self.run_app(app)
            self.assertTrue(app.error)
            self.assertEqual(len(app.metric), 0)
            self.assertNotIn('investment_simulation_result', app.session_state)

    def test_invalid_response_alignment_and_missing_values(self):
        app = self.run_app()
        for change in ['anchor', 'dates', 'inputs', 'summary', 'nonfinite', 'chart', 'missing']:
            self.answer = copy.deepcopy(self.result)
            if change == 'anchor': self.answer['series'][0]['buy_hold_value_eur'] = 999.
            elif change == 'dates': self.answer['series'][-1]['date'] = '2026-11-05'
            elif change == 'inputs': self.answer['inputs']['basis'] = 'gross'
            elif change == 'summary': self.answer['portfolio']['final_capital_eur'] = 500.
            elif change == 'nonfinite': self.answer['portfolio']['annualized_volatility'] = float('nan')
            elif change == 'chart': self.answer['series'][1]['portfolio_drawdown'] = float('inf')
            else: self.answer = {}
            app.button(key='sim_submit').click()
            self.run_app(app)
            self.assertTrue(app.error)
            self.assertEqual(len(app.metric), 0)

    def test_missing_sessions_and_optional_series(self):
        self.sessions = {}
        app = self.run_app()
        self.assertEqual(len(app.button), 0)
        self.assertTrue(app.warning)
        self.sessions = {'sessions': [{'date': d} for d in ['2026-10-30', '2026-11-02', '2026-11-03', '2026-11-04']]}
        st.cache_data.clear()
        app = self.run_app()
        self.answer = copy.deepcopy(self.result)
        for row in self.answer['series']:
            for key in ['portfolio_drawdown', 'buy_hold_drawdown', 'applied_exposure', 'cash_exposure']:
                row.pop(key)
        self.answer['portfolio']['annualized_volatility'] = None
        app.button(key='sim_submit').click()
        self.run_app(app)
        self.assertEqual(len(app.get('vega_lite_chart')), 1)
        self.assertTrue(any('unavailable' in x.value.lower() for x in app.info))
        self.assertEqual(app.dataframe[0].value.iloc[0]['Selected Strategy'], 'Unavailable')

    def test_short_sample_nonnegative_cvar_and_empty_history(self):
        app = self.run_app()
        self.answer = replay(fixture([.02, .03, .01], [.5, .5, .5]), initial_capital=10000.,
                             start_date='2026-11-02', end_date='2026-11-03', basis='net')
        app.selectbox(key='sim_start').select('2026-11-02')
        app.selectbox(key='sim_end').select('2026-11-03')
        app.button(key='sim_submit').click()
        self.run_app(app)
        self.assertTrue(any('Both tail means are non-negative' in w.value for w in app.markdown))
        self.assertEqual(app.dataframe[0].value.iloc[0]['Selected Strategy'], 'Unavailable')
        self.answer = replay(initial_capital=10000., start_date='2026-11-03', end_date='2026-11-03', basis='net')
        app.selectbox(key='sim_start').select('2026-11-03')
        app.button(key='sim_submit').click()
        self.run_app(app)
        self.assertEqual(app.metric[1].value, '€10,000.00')
        self.assertTrue(any('Applied exposure is unavailable' in w.value for w in app.info))

    def test_chart_values_are_exact_api_series(self):
        for fields in [dict(portfolio_value_eur='Selected Strategy', buy_hold_value_eur='Buy & Hold'),
                       dict(portfolio_drawdown='Selected Strategy', buy_hold_drawdown='Buy & Hold'),
                       dict(applied_exposure='Equity Exposure', cash_exposure='Uninvested Cash')]:
            spec = series_chart(self.result['series'], fields, 'Test').to_dict()
            data = next(iter(spec['datasets'].values()))
            expected = [(r['date'], name, r[key]) for key, name in fields.items() for r in self.result['series'] if r[key] is not None]
            actual = [(r['date'][:10], r['Series'], r['Value']) for r in data]
            self.assertEqual(actual, expected)
            self.assertIn('interval', json.dumps(spec))

    def test_full_dashboard_with_stored_publication(self):
        import os
        import test_operational_api
        root = Path(__file__).resolve().parents[1]
        with patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': str(root / 'runtime/main-wsl-test')}):
            request = lambda url: test_operational_api.OperationalApiTests.request(self, url)
            decisions = request('/decision-explorer').json()
            params = dict(initial_capital=10000., start_date=decisions['sessions'][0]['date'],
                          end_date=decisions['sessions'][-1]['date'], strategy='regime_based', basis='net')
            answer = request('/investment-simulation?' + '&'.join(f'{k}={v}' for k, v in params.items())).json()
        calls = []
        def get(url, **kwargs):
            if url.endswith('/investment-simulation'):
                calls.append(kwargs['params'])
                value = answer
            elif url.endswith('/decision-explorer'):
                value = decisions
            else:
                value = {} if '/latest' in url else []
            return Mock(json=lambda: value, raise_for_status=lambda: None)
        app = AppTest.from_file(str(root / 'dashboard.py'), default_timeout=30)
        app.query_params.update(view='Investment Simulator')
        with patch('requests.get', side_effect=get), patch('requests.post') as post:
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual(calls, [])
            app.button(key='sim_submit').click().run()
            post.assert_not_called()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(calls, [params])
        simulator = app
        self.assertEqual(len(simulator.get('vega_lite_chart')), 3)
        self.assertTrue(any(m.label == 'Final Portfolio Value' and
                            m.value == money(answer['portfolio']['final_capital_eur']) for m in simulator.metric))
        self.assertFalse(app.json)
        self.assertEqual(app.session_state['investment_simulation_result']['publication']['version'], answer['publication']['version'])
        with patch('requests.get', side_effect=get):
            app.number_input(key='sim_capital').set_value(15000.).run()
            app.button(key='home').click().run()
            app.button(key='welcome_Investment Simulator').click().run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.number_input(key='sim_capital').value, 15000.)
        self.assertEqual(len(app.get('vega_lite_chart')), 3)
        self.assertEqual(calls, [params])

    def test_formatting_english_and_no_financial_recalculation(self):
        self.assertEqual(money(-1234.56), '€-1,234.56')
        self.assertEqual(percentage(-.12345), '-12.35%')
        self.assertEqual(money(None), 'Unavailable')
        self.assertEqual(percentage(float('nan')), 'Unavailable')
        source = Path(__file__).resolve().parents[1] / 'src/riskbex/simulator_ui.py'
        tree = ast.parse(source.read_text())
        self.assertFalse([n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and SPANISH.search(n.value)])
        forbidden = {'exp', 'cumsum', 'cumprod', 'cummax', 'pct_change', 'simulate_investment', 'infer_main_signals'}
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                          ((isinstance(n.func, ast.Attribute) and n.func.attr in forbidden) or
                           (isinstance(n.func, ast.Name) and n.func.id in forbidden))])
