"""Offline bilingual presentation checks; no providers, inference or containers."""
import ast
import copy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.riskbex.i18n import EN, ES, LANGUAGES, chart_spec, display_frame, translate
from src.riskbex.performance_story import comparison_stories, participation_stories
from src.riskbex.simulator_ui import series_chart
import test_simulator_ui as simulator_tests

ROOT = Path(__file__).resolve().parents[1]


def visible(app):
    values = []
    for kind in ('title', 'header', 'subheader', 'markdown', 'caption', 'info', 'warning', 'error', 'success'):
        values.extend(item.value for item in app.get(kind))
    return '\n'.join(values)


class CatalogTests(unittest.TestCase):
    def test_catalog_completeness_and_placeholder_integrity(self):
        self.assertEqual(EN.keys(), ES.keys())
        self.assertGreater(len(ES), 500)
        for key, value in ES.items():
            self.assertTrue(value.strip(), key)
            self.assertEqual(sorted(re.findall(r'\{\d+\}', key)), sorted(re.findall(r'\{\d+\}', value)), key)
            self.assertEqual(translate(key, 'en'), key)
        self.assertEqual(translate('unknown future key', 'es'), 'unknown future key')
        self.assertEqual(translate('Overview', 'fr'), 'Overview')

    def test_terminology_and_required_hero(self):
        expected = {'Volatility': 'Volatilidad', 'Drawdown': 'Caída desde máximos (drawdown)',
                    'Market Regime': 'Régimen de mercado', 'Exposure': 'Exposición al mercado',
                    'Regime-Based': 'Estrategia basada en regímenes',
                    'ML Hard': 'Estrategia ML por clasificación',
                    'ML Probability-Weighted': 'Estrategia ML ponderada por probabilidades'}
        for source, target in expected.items():
            self.assertEqual(translate(source, 'es'), target)
        self.assertEqual(translate('Pursue market returns. Manage downside risk.', 'es'),
                         'Busca rentabilidad en bolsa. Gestiona el riesgo de pérdidas.')
        self.assertEqual(translate('What if Machine Learning could help investors adapt to changing market risk?', 'es'),
                         '¿Y si el Machine Learning pudiera ayudar a los inversores a adaptar su exposición al riesgo del mercado?')

    def test_direct_visible_literals_have_spanish_translations(self):
        # Check every direct rendering literal, including HTML text nodes. This
        # catches new English notices instead of silently accepting EN fallback.
        methods = {'title', 'header', 'subheader', 'markdown', 'caption', 'info', 'warning',
                   'error', 'success', 'expander', 'spinner', 'button', 'form_submit_button',
                   'number_input', 'radio', 'selectbox', 'multiselect', 'segmented_control'}
        protected = {'RISKBEX', 'ℹ', 'shift(1)', 'ret_1d'}
        missing = []
        for filename in ('dashboard.py', 'src/riskbex/simulator_ui.py'):
            tree = ast.parse((ROOT / filename).read_text())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in methods and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    continue
                source = node.args[0].value
                if '<style>' in source:
                    continue
                for part in re.split(r'<[^>]+>', source):
                    part = ' '.join(part.split())
                    if part and part not in protected and re.search('[A-Za-z]{3}', part):
                        if translate(part, 'es') == part:
                            missing.append((filename, node.lineno, part))
        self.assertEqual(missing, [])

    def test_dynamic_stories_keep_numbers_and_translate_clauses(self):
        rows = [dict(Strategy=name, **{'Total Return': ret, 'Annualized Volatility': .1,
                 'Expected Shortfall (95%)': -.02, 'Maximum Drawdown': -.2,
                 'Total Transaction Costs (Log Return)': .01})
                for name, ret in [('Buy & Hold', .2), ('Regime-Based', .1), ('ML Hard', .15)]]
        stories = comparison_stories(rows, ['ML Hard'], [])
        stories += participation_stories([dict(benchmark_return=-.1, ml_hard_return=-.05,
                                               strategy_exposure_ml_hard=.5)], ['ML Hard'], False)
        for source in stories:
            target = translate(source, 'es')
            self.assertEqual(re.findall(r'[+-]?\d+(?:[.,]\d+)*', source),
                             re.findall(r'[+-]?\d+(?:[.,]\d+)*', target))
            for english in ('versus', 'higher return', 'lower return', 'percentage points',
                            'unavailable', 'log-return points', 'down-market', 'up-market'):
                self.assertNotIn(english, target)
        self.assertIn('Crecimiento acumulado', translate('**Cumulative Growth · Gross**', 'es'))
        formula = translate('**ML Probability-Weighted:** Σ P(next-session state) × CVaR target = 0.25 + 0.75 = 1.00%.', 'es')
        self.assertNotIn('next-session state', formula)
        self.assertIn('0.25 + 0.75 = 1.00%', formula)
        self.assertNotIn('buy & hold', translate('less severe than buy & hold by 1.00%.', 'es'))

    def test_frames_and_chart_values_are_copied_not_recalculated(self):
        frame = pd.DataFrame({'Strategy': ['ML Hard'], 'Total Return': [.123456789]})
        original = frame.copy(deep=True)
        with patch('src.riskbex.i18n.language', return_value='es'):
            translated = display_frame(frame)
            pd.testing.assert_frame_equal(frame, original)
            self.assertEqual(translated['Rentabilidad total'].iloc[0], frame['Total Return'].iloc[0])
            records = [{'date': '2026-11-02', 'capital': 10000.123456789}]
            chart = series_chart(records, {'capital': 'Selected Strategy'}, 'Portfolio Value (EUR)')
            spec = chart_spec(chart)
            cells = next(iter(spec['datasets'].values()))
            self.assertEqual(cells[0]['Value'], records[0]['capital'])
            self.assertEqual(cells[0]['Series'], 'Estrategia seleccionada')
            self.assertEqual(spec['layer'][0]['encoding']['x']['title'], 'Sesión histórica')
        self.assertEqual(records[0]['capital'], 10000.123456789)

    def test_docker_import_and_catalog_packaging(self):
        dockerfile = (ROOT / 'Dockerfile.dashboard').read_text()
        self.assertIn('COPY src ./src', dockerfile)
        self.assertIn('!src/**', (ROOT / '.dockerignore').read_text())
        self.assertTrue((ROOT / 'src/riskbex/translations_es.json').is_file())
        self.assertNotIn('requests', (ROOT / 'src/riskbex/i18n.py').read_text())


class LanguageNavigationTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        payload = {'date': '2026-11-10', 'publication': {'data_date': '2026-11-10', 'freshness': 'stale', 'is_current': False}, 'signal': {'last_valid_session': '2026-11-10'}} if '/latest-risk' in url else [{'date': '2026-11-10'}] if '/historical-risk' in url else []
        return Mock(json=lambda: payload, raise_for_status=lambda: None)

    def run_app(self, app=None):
        app = app if app is not None else AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
        with patch('requests.get', side_effect=self.get), patch('requests.post') as post:
            app.run()
            post.assert_not_called()
        self.assertFalse(app.exception, str(app.exception))
        return app

    def test_default_flags_switch_back_and_cache(self):
        app = self.run_app()
        selector = next(w for w in app.get('button_group') if w.key == 'ui_language')
        self.assertEqual(selector.value, 'en')
        self.assertEqual(selector.options, ['English', 'Español'])
        self.assertEqual([o.content_icon for o in selector.proto.options], ['🇬🇧', '🇪🇸'])
        self.assertFalse(any(w.key == 'ui_language' for w in app.radio))
        calls = len(self.calls)
        next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('es')
        self.run_app(app)
        self.assertIn('Busca rentabilidad en bolsa.', visible(app))
        self.assertIn('Desarrollado por Alejandro Palomo Morales', visible(app))
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(len(app.button), 5)
        next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('en')
        self.run_app(app)
        self.assertIn('Pursue market returns.', visible(app))
        self.assertEqual(len(self.calls), calls)

    def test_clearing_language_segment_keeps_valid_language(self):
        from types import SimpleNamespace
        from src.riskbex.i18n import _select_language
        state = SimpleNamespace(ui_language=None, _last_ui_language='es')
        params = {'view': 'Investment Simulator'}
        with patch('src.riskbex.i18n.streamlit.session_state', state), patch(
                'src.riskbex.i18n.streamlit.query_params', params):
            _select_language()
        self.assertEqual(state.ui_language, 'es')
        self.assertEqual(params, {'view': 'Investment Simulator', 'lang': 'es'})

    def test_url_initialized_language_survives_selection_reruns_and_navigation(self):
        # AppTest sends widget state directly. It does not perform DOM hit testing
        # and cannot detect a transparent header intercepting a browser click.
        app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
        app.query_params.update(lang='en')
        self.run_app(app)

        def selector():
            return next(w for w in app.get('button_group') if w.key == 'ui_language')

        self.assertEqual(selector().value, 'en')
        selector().set_value('es')
        self.run_app(app)
        self.assertEqual(selector().value, 'es')
        self.assertEqual(app.query_params['lang'], ['es'])
        self.assertIn('Busca rentabilidad en bolsa.', visible(app))
        self.run_app(app)
        self.assertEqual(selector().value, 'es')
        app.button(key='welcome_Performance').click()
        self.run_app(app)
        self.assertEqual(selector().value, 'es')
        self.assertEqual(app.query_params['view'], ['Performance'])
        selector().set_value('en')
        self.run_app(app)
        self.assertEqual(selector().value, 'en')
        self.assertEqual(app.query_params['lang'], ['en'])
        self.assertEqual(app.query_params['view'], ['Performance'])
        self.run_app(app)
        self.assertEqual(selector().value, 'en')

    def test_transparent_header_passes_pointer_events_to_selector(self):
        # Structural safeguard only: confirm actual hit testing manually in Chrome.
        source = (ROOT / 'dashboard.py').read_text()
        for target in ('[data-testid="stHeader"]',
                       '[data-testid="stHeader"] [data-testid="stToolbar"]'):
            rule = source.split(target + ' {', 1)[1].split('}', 1)[0]
            self.assertIn('pointer-events: none;', rule)
        controls = source.split('[data-testid="stHeader"] :is(button, a, input, [role="button"]) {', 1)[1].split('}', 1)[0]
        self.assertIn('pointer-events: auto;', controls)

    def test_all_six_views_and_five_same_tab_cards(self):
        app = self.run_app()
        next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('es')
        self.run_app(app)
        for page in ['Overview', 'Performance', 'Investment Simulator', 'Risk Monitor', 'Research & Methodology']:
            self.assertEqual(app.button(key='welcome_' + page).label, translate('Explore ' + page, 'es'))
            app.button(key='welcome_' + page).click()
            self.run_app(app)
            self.assertEqual(app.query_params['view'], [page])
            self.assertEqual(app.radio(key='primary_section').value, page)
            self.assertEqual(next(w for w in app.get('button_group') if w.key == 'ui_language').value, 'es')
            self.assertFalse(app.get('link_button'))
            body = visible(app)
            for source in ('Market history is unavailable', 'No regime history is available.',
                           'No tail events are available.', 'Published trading sessions are unavailable.'):
                self.assertNotIn(source, body)
            next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('en')
            self.run_app(app)
            self.assertEqual(app.query_params['view'], [page])
            next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('es')
            self.run_app(app)
            app.button(key='home').click()
            self.run_app(app)
            self.assertEqual(len(app.button), 5)

    def test_populated_performance_and_monitor_translate_without_changing_metrics(self):
        publication = dict(version='fixture-version', data_date='2026-11-10',
                           freshness='stale', is_current=False, expected_data_date='2026-11-13',
                           target_session_date='2026-11-11')
        history = [dict(date=day, ibex_close=100 + i, regime_label='medium_risk',
                        cvar_95_60d=-.02, drawdown=-.03, vol_20d=.01)
                   for i, day in enumerate(['2026-11-09', '2026-11-10'])]
        latest = dict(history[-1], publication=publication, signal=dict(
            market={'ibex_close': 101.},
            markov={'economic_label': 'medium_risk', 'probabilities': {'0': .1, '1': .2, '2': .7}},
            xgboost={'economic_label': 'medium_risk', 'probabilities': {'0': .2, '1': .1, '2': .7}},
            target_exposures={'regime_based': .59, 'ml_hard': .59, 'ml_probability_weighted': .63}))
        records = []
        for point in history:
            row = {'date': point['date'], 'benchmark_cum': 1.02, 'benchmark_return': -.01}
            for key in ['regime_based', 'ml_hard', 'ml_proba']:
                row.update({key + '_cum': 1.01, key + '_cum_net': 1.009,
                            key + '_return': -.005, key + '_return_net': -.006,
                            'strategy_exposure_' + key: .5})
            records.append(row)
        metrics = [dict(strategy=name, total_return=.01, annualized_volatility=.1,
                        CVaR_95=-.02, max_drawdown=-.1, total_transaction_cost=.001)
                   for name in ['Buy & Hold', 'Regime-based gross', 'Regime-based net of costs',
                                'ML Hard gross', 'ML Hard net of costs',
                                'ML Probability-Weighted gross', 'ML Probability-Weighted net of costs']]
        payload = dict(publication=publication, results=records, metrics=metrics,
                       turnover=[], conventions={'cost_rate': .001})
        before = copy.deepcopy(payload)
        def get(url, **kwargs):
            answer = (latest if '/latest-risk' in url else history if '/historical-risk' in url else
                      payload if '/backtesting/comparison' in url else {} if '/latest' in url else [])
            return Mock(json=lambda: answer, raise_for_status=lambda: None)
        for page in ['Performance', 'Risk Monitor']:
            st.cache_data.clear()
            app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
            app.query_params.update(view=page)
            with patch('requests.get', side_effect=get):
                app.run()
                self.assertFalse(app.exception, str(app.exception))
                metric_values = [m.value for m in app.metric]
                next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('es').run()
                self.assertFalse(app.exception, str(app.exception))
            self.assertEqual([m.value for m in app.metric], metric_values)
            for phrase in ['Historical exposure uses', 'Comparisons use the same', 'Common Evaluation Period',
                           'This publication does not represent', 'Target exposures from',
                           'Total Return:', 'Daily CVaR', 'versus', 'log-return points']:
                self.assertNotIn(phrase, visible(app))
            if page == 'Performance':
                self.assertIn('Rentabilidad total', app.dataframe[0].value.columns)
                self.assertEqual(app.radio(key='performance_basis').value, 'Gross')
        self.assertEqual(payload, before)

    def test_deep_links_language_and_invalid_language(self):
        for lang, expected in [('es', 'es'), ('xx', 'en')]:
            app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
            app.query_params.update(view='Monitor', lang=lang)
            self.run_app(app)
            self.assertEqual(next(w for w in app.get('button_group') if w.key == 'ui_language').value, expected)
            self.assertEqual(app.radio(key='primary_section').value, 'Risk Monitor')

    def test_offline_and_stale_notices_are_spanish(self):
        app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
        app.query_params.update(lang='es')
        with patch('requests.get', side_effect=__import__('requests').ConnectionError('offline')):
            app.run()
        self.assertFalse(app.exception)
        self.assertIn('No disponible', visible(app))
        st.cache_data.clear()
        publication = {'data_date': '2026-11-10', 'is_current': False, 'freshness': 'stale'}
        def get(url, **kwargs):
            data = {'publication': publication, 'signal': {'last_valid_session': '2026-11-10'}} if '/latest-risk' in url else []
            return Mock(json=lambda: data, raise_for_status=lambda: None)
        with patch('requests.get', side_effect=get):
            app.run()
        self.assertIn('**Desactualizada**', visible(app))
        self.assertNotIn('**Stale**', visible(app))
        app.query_params['view'] = 'Risk Monitor'
        with patch('requests.get', side_effect=get), patch('src.riskbex.presentation_status.local_scheduler_active', return_value=None):
            app.run()
        self.assertIn('Diagnóstico de actualización', [x.label for x in app.expander])
        self.assertIn('Estado del programador: No verificado', visible(app))
        self.assertIn('Vigencia de la publicación: Desactualizada', visible(app))


class SimulatorLanguageTests(unittest.TestCase):
    def test_inputs_result_and_request_preserved_across_languages_and_home(self):
        helper = simulator_tests.SimulatorUITests()
        helper.setUp()
        helper.sessions["mapping"] = [{"regime": 0, "target_exposure": .5}]
        app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=30)
        app.query_params.update(view='Investment Simulator', lang='en')
        def get(url, **kwargs):
            if url.endswith('/latest-risk') or '/historical-risk' in url:
                return Mock(json=lambda: {}, raise_for_status=lambda: None)
            return helper.get(url, **kwargs)
        def run():
            with patch('requests.get', side_effect=get), patch('requests.post') as post:
                app.run()
                post.assert_not_called()
            self.assertFalse(app.exception, str(app.exception))
        run()
        app.button(key='sim_submit').click()
        run()
        original = copy.deepcopy(app.session_state['investment_simulation_result'])
        numbers = [m.value for m in app.metric]
        app.number_input(key='sim_capital').set_value(15000.)
        app.selectbox(key='sim_strategy').set_value('ML Hard')
        app.selectbox(key='sim_start').set_value('2026-11-02')
        app.selectbox(key='sim_end').set_value('2026-11-03')
        app.radio(key='sim_basis').set_value('Gross')
        run()
        for lang in ['es', 'en', 'es']:
            next(w for w in app.get('button_group') if w.key == 'ui_language').set_value(lang)
            run()
            self.assertEqual(app.session_state['investment_simulation_result'], original)
            self.assertEqual([m.value for m in app.metric], numbers)
            self.assertEqual(app.number_input(key='sim_capital').value, 15000.)
            self.assertEqual(app.selectbox(key='sim_strategy').value, 'ML Hard')
            self.assertEqual(app.radio(key='sim_basis').value, 'Gross')
            self.assertEqual(app.selectbox(key='sim_start').value, '2026-11-02')
            self.assertEqual(app.selectbox(key='sim_end').value, '2026-11-03')
            self.assertEqual(len(helper.calls), 1)
        body = visible(app)
        for phrase in ('The selected strategy', 'Buy & Hold has', 'log-return points', 'not current market', 'Historical daily'):
            self.assertNotIn(phrase, body)
        app.button(key='home').click()
        run()
        app.button(key='welcome_Investment Simulator').click()
        run()
        self.assertEqual(app.number_input(key='sim_capital').value, 15000.)
        self.assertEqual(app.session_state['investment_simulation_result'], original)
        self.assertEqual(len(helper.calls), 1)


if __name__ == '__main__':
    unittest.main()
