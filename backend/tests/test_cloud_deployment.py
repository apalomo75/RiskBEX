"""Focused offline Cloud transport, integrity and presentation checks."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.riskbex.dashboard_transport import get
from src.riskbex.cloud_snapshot import verify_bundle
from src.riskbex.pipeline.store import digest
import test_operational_api

ROOT = Path(__file__).resolve().parents[1]


class CloudDeploymentTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        env = patch.dict(os.environ, {
            'RISKBEX_PRESENTATION_MODE': 'snapshot',
            'RISKBEX_OPERATIONAL_DIR': str(ROOT / 'runtime/main-wsl-test'),
        })
        env.start()
        self.addCleanup(env.stop)

    def test_local_mode_keeps_http(self):
        with patch.dict(os.environ, {'RISKBEX_PRESENTATION_MODE': 'api'}), patch('requests.get') as remote:
            get('http://api:8000/latest-risk', timeout=10)
            remote.assert_called_once_with('http://api:8000/latest-risk', timeout=10)

    def test_missing_store_handles_unavailable_api(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'RISKBEX_OPERATIONAL_DIR': temp}):
            result = get('http://api:8000/latest-risk')
            self.assertEqual(result.status_code, 503)
            with self.assertRaises(requests.HTTPError):
                result.raise_for_status()

    def test_contracts_and_simulation_equal_existing_api(self):
        import pandas as pd
        with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-16T22:00Z')), \
             patch('requests.get', side_effect=AssertionError('Network forbidden')):
            for path in ['/latest-risk', '/historical-risk?limit=all', '/decision-explorer',
                         '/backtesting/comparison']:
                result = get('http://api:8000' + path)
                self.assertEqual(result.status_code, 200, result.text[:200])
                self.assertEqual(result.json(), test_operational_api.OperationalApiTests.request(self, path).json())
            history = get('http://api:8000/decision-explorer').json()['sessions']
            params = dict(initial_capital=10000., start_date=history[0]['date'],
                          end_date=history[-1]['date'], strategy='ml_proba', basis='net')
            result = get('http://api:8000/investment-simulation', params=params)
            from urllib.parse import urlencode
            reference = test_operational_api.OperationalApiTests.request(
                self, '/investment-simulation?' + urlencode(params))
            self.assertEqual(result.status_code, 200, result.text[:200])
            self.assertEqual(result.json(), reference.json())

    def test_all_six_views_bilingual_offline(self):
        for language in ['en', 'es']:
            for view in ['Welcome / Home', 'Overview', 'Performance', 'Investment Simulator',
                         'Risk Monitor', 'Research & Methodology']:
                with self.subTest(language=language, view=view):
                    st.cache_data.clear()
                    app = AppTest.from_file(str(ROOT / 'dashboard.py'), default_timeout=40)
                    app.query_params['view'] = view
                    app.query_params['lang'] = language
                    with patch('requests.get', side_effect=AssertionError('Network forbidden')), \
                         patch('src.riskbex.engine.service.infer_main_signals', side_effect=AssertionError('Inference forbidden')):
                        app.run()
                    self.assertEqual(len(app.exception), 0, str(app.exception))
                    if view == 'Welcome / Home':
                        rendered = ' '.join(item.value for item in app.markdown)
                        self.assertNotIn('Automated Daily Pipeline', rendered)
                        self.assertIn('Validated Read-Only Publication' if language == 'en'
                                      else 'Publicación validada de solo lectura', rendered)
                    self.assertFalse(any('unavailable' in w.value.lower() for w in app.warning),
                                     [w.value for w in app.warning])

    def test_entrypoint_without_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'RISKBEX_SNAPSHOT_DIR': temp}):
            app = AppTest.from_file(str(ROOT.parent / 'cloud/streamlit_app.py')).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.error), 1)

    def test_corrupt_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data.csv').write_text('original')
            (root / 'snapshot.json').write_text(json.dumps({'format': 1, 'version': 'fixture',
                'files': {'data.csv': digest(root / 'data.csv')}}))
            (root / 'data.csv').write_text('corrupt')
            with self.assertRaisesRegex(ValueError, 'integrity failure'):
                verify_bundle(root)

    def test_snapshot_seal_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'snapshot.json').write_text(json.dumps({'format': 1, 'files': {'../private': 'bad'}}))
            with self.assertRaises(ValueError):
                verify_bundle(root)
            with self.assertRaisesRegex(ValueError, 'identity'):
                verify_bundle(root, '0' * 64)

    def test_export_synthetic_fixture_only_and_refuses_overwrite(self):
        from src.riskbex.cloud_snapshot import export_bundle, RESEARCH, FIGURES
        helper = test_operational_api.OperationalApiTests('test_routes_contracts_and_dates')
        helper.setUp()
        try:
            source = helper.publish()
            with tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                backend = base / 'backend'
                package = backend / 'model_packages/main-v1'
                package.mkdir(parents=True)
                (package / 'mapping.json').write_text('[]')
                model = {'components': {'cvar_mapping': 'mapping.json'},
                         'files': {'mapping.json': {'sha256': digest(package / 'mapping.json')}}}
                (package / 'manifest.json').write_text(json.dumps(model))
                manifest = json.loads((source / 'manifest.json').read_text())
                latest = json.loads((source / 'latest.json').read_text())
                manifest['model_manifest_sha256'] = digest(package / 'manifest.json')
                manifest['model_hashes'] = {'mapping.json': digest(package / 'mapping.json')}
                latest['provenance']['manifest_sha256'] = manifest['model_manifest_sha256']
                (source / 'latest.json').write_text(json.dumps(latest))
                manifest['files']['latest.json'] = digest(source / 'latest.json')
                (source / 'manifest.json').write_text(json.dumps(manifest))
                (helper.root / 'current.json').write_text(json.dumps({'version': source.name,
                    'manifest_sha256': digest(source / 'manifest.json')}))
                for name in RESEARCH:
                    path = backend / 'data/processed' / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('synthetic,test\n1,2\n')
                for name in FIGURES:
                    path = backend / 'figures/chapter2' / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'synthetic image fixture')
                before = digest(helper.root / 'current.json')
                destination = base / 'export'
                seal = export_bundle(helper.root, destination, backend)
                self.assertEqual(verify_bundle(destination, seal)['version'], source.name)
                self.assertEqual(digest(helper.root / 'current.json'), before)
                self.assertFalse((destination / 'store/status.json').exists())
                with patch.dict(os.environ, {'RISKBEX_SNAPSHOT_DIR': str(destination),
                                             'RISKBEX_SNAPSHOT_SHA256': seal}), \
                     patch('requests.get', side_effect=AssertionError('Network forbidden')):
                    app = AppTest.from_file(str(ROOT.parent / 'cloud/streamlit_app.py'),
                                            default_timeout=30).run()
                    self.assertEqual(len(app.exception), 0, str(app.exception))
                with self.assertRaises(ValueError):
                    export_bundle(helper.root, destination, backend)
                (destination / 'data/processed' / RESEARCH[0]).write_text('corrupted')
                with self.assertRaises(ValueError):
                    verify_bundle(destination, seal)
        finally:
            helper.doCleanups()

    def test_snapshot_freshness_uses_calendar_and_provenance(self):
        import pandas as pd
        with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2026-11-17T22:00Z')):
            result = get('http://api:8000/latest-risk')
            self.assertEqual(result.status_code, 200)
            publication = result.json()['publication']
            self.assertFalse(publication['is_current'])
            self.assertIn(publication['freshness'], ['stale', 'historical', 'simulated'])
            self.assertEqual(publication['expected_data_date'], '2026-11-17')
        with patch('src.riskbex.api.operational.utc_now', return_value=pd.Timestamp('2027-01-05T22:00Z')):
            self.assertEqual(get('http://api:8000/latest-risk').status_code, 503)
