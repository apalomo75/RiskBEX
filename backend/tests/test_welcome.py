"""Sprint 10F: publication-only landing, offline HTTP and UI checks."""
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import pyarrow as pa
import streamlit as st

import test_dashboard_ui
import test_operational_api
from src.riskbex.welcome import welcome_assessment, welcome_history
from src.riskbex.i18n import translate

ROOT = Path(__file__).resolve().parents[1]


class WelcomeTests(unittest.TestCase):
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

    def published(self):
        latest = self.request('/latest-risk')
        history = self.request('/historical-risk?limit=all')
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(history.status_code, 200)
        return latest.json(), history.json()

    def test_real_publication_price_mapping_and_no_signal_shift(self):
        latest, rows = self.published()
        original = copy.deepcopy(rows)
        selected = welcome_history(pd.DataFrame(rows), latest)
        decisions = self.request('/decision-explorer').json()
        mapping = {row['regime']: row['economic_label'] for row in decisions['mapping']}
        by_date = {row['date']: row for row in decisions['sessions']}
        self.assertEqual(len(selected), 252)
        for row in selected.to_dict('records'):
            session = row['date'].strftime('%Y-%m-%d')
            source = by_date[session]
            self.assertEqual(row['ibex_close'], source['ibex_close'])
            self.assertEqual(row['regime_label'], mapping[source['regime']])
            self.assertLessEqual(session, latest['publication']['data_date'])
        self.assertEqual(rows, original)
        # A separately cached publication, future row or invalid label must never enter.
        extra = [dict(rows[-1], date='2099-01-01'),
                 dict(rows[-1], publication={'version': 'other'}),
                 dict(rows[-1], regime_label='unknown')]
        pd.testing.assert_frame_equal(selected.reset_index(drop=True),
            welcome_history(pd.DataFrame(rows + extra), latest).reset_index(drop=True))
        self.assertTrue(welcome_history(pd.DataFrame(), latest).empty)
        self.assertTrue(welcome_history(pd.DataFrame(rows), None).empty)
        self.assertTrue(welcome_history(pd.DataFrame(rows).drop(columns='ibex_close'), latest).empty)

    def test_latest_target_is_published_not_forecast_or_label_derived(self):
        latest, _ = self.published()
        signal = latest['signal']
        label, target = welcome_assessment(latest)
        self.assertEqual(label, 'Medium Risk')
        self.assertEqual(target, signal['target_exposures']['regime_based'])
        changed = copy.deepcopy(latest)
        changed['signal']['xgboost'] = {'economic_label': 'high_risk', 'probabilities': {'1': 1}}
        changed['signal']['target_exposures']['ml_hard'] = 0
        self.assertEqual(welcome_assessment(changed), (label, target))
        changed['signal']['target_exposures']['regime_based'] = .4321
        self.assertEqual(welcome_assessment(changed), (label, .4321))
        for invalid in [None, {}, {'publication': latest['publication'], 'signal': {}}]:
            self.assertEqual(welcome_assessment(invalid), ('Unavailable', None))
        changed['signal']['last_valid_session'] = '2020-01-01'
        self.assertEqual(welcome_assessment(changed), ('Unavailable', None))

    def test_full_width_welcome_chart_bilingual_and_stale(self):
        latest, history = self.published()
        latest['publication'].update(freshness='stale', is_current=False)
        def get(url, **kwargs):
            return Mock(json=lambda: latest if '/latest-risk' in url else history if '/historical-risk' in url else [],
                        raise_for_status=lambda: None)
        app = self.run_app(get)
        self.assertEqual(len(app.get('vega_lite_chart')), 1)
        # Hero and chart live directly in the main block, outside any column/card.
        main_chart = app.main.get('vega_lite_chart')[0]
        self.assertEqual(main_chart, app.get('vega_lite_chart')[0])
        self.assertFalse(any(col.get('vega_lite_chart') for col in app.get('column')))
        self.assertEqual(len(app.metric), 3)
        metric_columns = [col for col in app.get('column') if col.metric]
        self.assertEqual([len(col.metric) for col in metric_columns], [1, 1, 1])
        self.assertEqual(app.metric[2].value, pd.Timestamp(latest['publication']['data_date']).strftime('%d / %m / %Y'))
        spec = json.loads(app.get('vega_lite_chart')[0].proto.spec)
        self.assertEqual(spec['height'], 250)
        self.assertEqual(spec['layer'][1]['encoding']['color']['legend']['orient'], 'bottom')
        self.assertEqual(len(spec['layer'][1]['encoding']['tooltip']), 3)
        values = pa.ipc.open_stream(app.get('vega_lite_chart')[0].proto.datasets[0].data.data).read_all().to_pylist()
        self.assertEqual(len(values), 252)
        self.assertEqual(values[-1]['IBEX 35 Close'], history[-1]['ibex_close'])
        self.assertEqual([b.key for b in app.button], ['welcome_' + page for page in
            ['Overview', 'Performance', 'Investment Simulator', 'Risk Monitor', 'Research & Methodology']])
        self.assertIn('**Stale**', [x.value for x in app.markdown])
        metrics = {m.label: m.value for m in app.metric}
        self.assertEqual(metrics['Current Market Regime · Filtered'], 'Medium Risk')
        self.assertEqual(metrics['Regime-Based Target Exposure'], f"{latest['signal']['target_exposures']['regime_based']:.0%}")
        with patch('requests.get', side_effect=get):
            next(w for w in app.get('button_group') if w.key == 'ui_language').set_value('es').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.current_page, 'Welcome / Home')
        self.assertIn(translate('Current Market Regime · Filtered', 'es'), [m.label for m in app.metric])
        self.assertIn('**' + translate('Stale', 'es') + '**', [m.value for m in app.markdown])
        spanish = json.dumps(json.loads(app.get('vega_lite_chart')[0].proto.spec), ensure_ascii=False)
        for label in ['Low Risk', 'Medium Risk', 'High Risk', 'IBEX 35 Close', 'Session']:
            self.assertIn(translate(label, 'es'), spanish)

    def test_unavailable_never_shows_fake_chart_or_exposure(self):
        app = self.run_app(lambda *a, **k: Mock(json=lambda: {}, raise_for_status=lambda: None))
        self.assertFalse(app.get('vega_lite_chart'))
        self.assertEqual([m.value for m in app.metric], ['Unavailable', 'Unavailable', 'Unavailable'])
        self.assertTrue(any('chart unavailable' in c.value for c in app.caption))
