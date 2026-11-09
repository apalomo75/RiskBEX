"""Small offline interface checks: no inference, providers or quantitative backtests."""
import ast
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(?:riesgo|régimen|exposición|actualizar|bienvenido|sesiones|probabilidad|datos|mercado|costes)\b", re.I)


class DashboardUI(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()

    def run_app(self, response=None, view=None):
        app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
        if view:
            app.query_params.update(enter='1', view=view)
        with patch('requests.get', side_effect=response), patch('requests.post') as post:
            app.run()
            post.assert_not_called()
        self.assertEqual(len(app.exception), 0, str(app.exception))
        return app

    def test_welcome_and_overview_explanations(self):
        app = self.run_app(lambda *a, **k: Mock(json=lambda: {}, raise_for_status=lambda: None))
        self.assertEqual(app.title[0].value, 'RISKBEX')
        self.assertTrue(any('Developed by Alejandro Palomo Morales' in x.value for x in app.markdown))
        pages = ['Overview', 'Performance', 'Investment Simulator', 'Risk Monitor', 'Research & Methodology']
        self.assertEqual([b.label for b in app.button], ['Explore ' + p for p in pages])
        self.assertFalse(app.tabs)
        self.assertFalse(app.radio)
        self.assertFalse(app.get('link_button'))
        self.assertTrue(any('not eliminated' in x.value for x in app.info))
        overview = self.run_app(lambda *a, **k: Mock(json=lambda: {}, raise_for_status=lambda: None), 'Overview')
        headings = [x.value for x in overview.subheader]
        for heading in ['CVaR / Expected Shortfall', 'Volatility', 'Drawdown', 'Market Regimes and Machine Learning']:
            self.assertIn(heading, headings)
        self.assertEqual(len(overview.get('vega_lite_chart')), 2)
        self.assertTrue(any('Market data → Risk indicators' in x.value for x in overview.markdown))
        performance = self.run_app(lambda *a, **k: Mock(json=lambda: {}, raise_for_status=lambda: None), 'Performance')
        self.assertTrue(any('Historical Strategy Performance' == x.value for x in performance.subheader))
        simulator = self.run_app(lambda *a, **k: Mock(json=lambda: {}, raise_for_status=lambda: None), 'Investment Simulator')
        self.assertTrue(any('Investment Simulator' == x.value for x in simulator.subheader))

    def test_unavailable_api_keeps_all_content_sections(self):
        app = self.run_app(lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError('offline')), 'Monitor')
        self.assertEqual([t.label for t in app.tabs], ['Market Risk', 'History & Decision Explorer'])
        self.assertEqual(app.radio(key='primary_section').options, ['Overview', 'Performance', 'Investment Simulator', 'Risk Monitor', 'Research & Methodology'])
        self.assertEqual(app.button(key='home').label, 'Home')
        research = self.run_app(lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError('offline')), 'Research & Methodology')
        self.assertEqual([t.label for t in research.tabs], ['Models', 'Tail Risk', 'Original TFM Research'])
        self.assertFalse(research.json)
        self.assertTrue(any('Decision Explorer' == x.value for x in app.subheader))
        self.assertTrue(any('Verified decision history is unavailable' in x.value for x in app.warning))
        self.assertTrue(app.warning)

    def test_publication_history_and_stale_status(self):
        publication = dict(version='publication-hash-sentinel', model_version='package-id-sentinel', freshness='historical', is_current=False, expected_data_date='2026-11-06',
                           target_session_date='2026-04-24', generated_at='2026-04-23T20:00Z')
        history = [dict(date=d, ibex_close=100+i, regime_label='medium_risk',
                        cvar_95_60d=-.02, drawdown=-.03, vol_20d=.01, skew_60d=0,
                        publication=publication) for i,d in enumerate(['2026-04-21','2026-04-22','2026-04-23'])]
        latest = dict(history[-1], signal=dict(last_valid_session='2026-04-23',
            market={'ibex_close':102}, markov={'economic_label':'medium_risk','probabilities':{'0':.1,'1':.1,'2':.8}},
            xgboost={'economic_label':'medium_risk','probabilities':{'0':.2,'1':.1,'2':.7}},
            target_exposures={'regime_based':.59,'ml_hard':.59,'ml_probability_weighted':.63}))
        regimes = [dict(date=r['date'], risk_order=2, economic_label='medium_risk',
                        p_regime_0=.1,p_regime_1=.1,p_regime_2=.8) for r in history]
        def get(url, **kwargs):
            payload = []
            if '/latest-risk' in url: payload = latest
            elif '/historical-risk' in url: payload = history
            elif '/regimes/history' in url: payload = regimes
            elif '/latest' in url: payload = {}
            return Mock(json=lambda: payload, raise_for_status=lambda: None)
        app = self.run_app(get, 'Explore')
        self.assertTrue(any('does not represent current' in w.value for w in app.warning))
        self.assertTrue(any(m.label == 'Last Market Close · IBEX 35' and m.value == '102.00' for m in app.metric))
        self.assertTrue(any(s.label == 'Observation Period' for s in app.selectbox))
        self.assertEqual(len(app.get('vega_lite_chart')) >= 2, True)
        visible = ' '.join(x.value for x in app.markdown) + ' '.join(x.value for x in app.caption)
        self.assertNotIn('publication-hash-sentinel', visible)
        self.assertNotIn('package-id-sentinel', visible)
        self.assertFalse(app.json)
        monitor = next(t for t in app.tabs if t.label == 'Market Risk')
        self.assertFalse(any('Regime 0' in x.value for x in monitor.markdown))

    def test_card_navigation_and_home_offline(self):
        offline = lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError('offline'))
        app = self.run_app(offline)
        for page in ['Overview', 'Performance', 'Investment Simulator', 'Risk Monitor', 'Research & Methodology']:
            with patch('requests.get', side_effect=offline):
                app.button(key='welcome_' + page).click().run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.query_params['view'], [page])
                self.assertEqual(app.radio(key='primary_section').value, page)
                app.button(key='home').click().run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertFalse(app.radio)
                self.assertFalse(app.tabs)
        with patch('requests.get', side_effect=offline):
            app.button(key='welcome_Overview').click().run()
            app.radio(key='primary_section').set_value('Performance').run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.query_params['view'], ['Performance'])

    def test_responsive_card_structure(self):
        app = self.run_app(lambda *a, **k: Mock(json=lambda: {}, raise_for_status=lambda: None))
        columns = app.get('column')
        self.assertEqual(len(columns), 5)
        for column in columns:
            self.assertEqual(len(column.button), 1)
            self.assertEqual(len(column.subheader), 0)
            self.assertEqual(len(column.markdown), 2)
        source = (ROOT / 'dashboard.py').read_text()
        landing = source[source.index('def show_landing'):source.index('def show_overview')]
        self.assertIn('cards[:3], cards[3:]', landing)
        self.assertIn('st.columns(len(row), border=True)', landing)
        self.assertIn('st.container(height="stretch")', landing)
        self.assertNotIn('link_button', landing)
        self.assertNotIn('window.open', source)

    def test_english_presentation_literals(self):
        # Inspect literal text, including HTML and f-string fragments, without matching identifiers.
        tree = ast.parse((ROOT / 'dashboard.py').read_text())
        offenders = [(n.lineno, n.value[:100]) for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str) and SPANISH.search(n.value)]
        self.assertEqual(offenders, [])
        for filename in ['README.md', 'docs/sprint-4c.md']:
            self.assertIsNone(SPANISH.search((ROOT / filename).read_text()), filename)

    def test_single_dark_theme_configuration(self):
        import tomllib
        configs = [ROOT / '.streamlit/config.toml', ROOT.parent / '.streamlit/config.toml']
        self.assertEqual(configs[0].read_bytes(), configs[1].read_bytes())
        config = tomllib.loads(configs[0].read_text())['theme']
        self.assertEqual(config['base'], 'dark')
        self.assertGreaterEqual(config['baseFontSize'], 16)
        self.assertNotIn('light', config)
        self.assertNotIn('dark', config)
        for key in config:
            self.assertIn('theme.' + key, st.config.get_config_options())
        self.assertIn('COPY .streamlit ./.streamlit', (ROOT / 'Dockerfile.dashboard').read_text())
        self.assertIn('!.streamlit/config.toml', (ROOT / '.dockerignore').read_text())

    def test_optional_close_preserves_historical_contract(self):
        from src.riskbex.api.schemas import HistoricalRiskPoint
        row = dict(date='2026-04-23',vol_20d=.01,vol_60d=.01,var_95_60d=-.01,
                   cvar_95_60d=-.02,drawdown=-.03,skew_60d=0,regime_label='medium_risk',risk_score=None,risk_level=None)
        self.assertIsNone(HistoricalRiskPoint(**row).ibex_close)
        self.assertEqual(HistoricalRiskPoint(**row, ibex_close=100).ibex_close, 100)
