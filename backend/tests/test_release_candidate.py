"""Release UI integration against stored publications; no inference or network."""
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

import requests

import test_operational_integration


class ReleaseCandidateUI(unittest.TestCase):
    setUp = test_operational_integration.OperationalIntegrationTests.setUp
    request = test_operational_integration.OperationalIntegrationTests.request
    run_app = test_operational_integration.OperationalIntegrationTests.run_app
    def test_all_sections_with_real_api_and_research_controls(self):
        cache = {}

        def get(url, **kwargs):
            parsed = urlsplit(url)
            path = parsed.path + ('?' + parsed.query if parsed.query else '')
            if path not in cache:
                raw = self.request(path)
                self.assertEqual(raw.status_code, 200, path + ': ' + raw.text[:200])
                response = requests.Response()
                response.status_code = raw.status_code
                response._content = raw.content
                response.url = url
                cache[path] = response
            return cache[path]

        app = self.run_app(get, 'Research')
        self.assertEqual([t.label for t in app.tabs],
                         ['Monitor', 'Explore', 'Results', 'Models', 'Research', 'Tail Risk'])
        self.assertGreaterEqual(len(app.get('vega_lite_chart')), 6)
        self.assertFalse(app.error)
        self.assertFalse(app.warning, str(app.warning))
        with patch('requests.get', side_effect=get), patch('requests.post') as post:
            for figure in app.radio(key='figure_selector').options:
                app.radio(key='figure_selector').set_value(figure).run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertFalse(app.warning, str(app.warning))
            for key in ['regime_split_selector', 'backtesting_sample_selector', 'tail_sample_selector']:
                app.button_group(key=key).set_value('ROBUST').run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertFalse(app.error)
                self.assertFalse(app.warning, str(app.warning))
            post.assert_not_called()
