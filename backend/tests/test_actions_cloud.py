"""Cloud approval discovery, strict pins and visitor cache invalidation offline."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import shutil
from src.riskbex.cloud_snapshot import verify_bundle

ROOT = Path(__file__).resolve().parents[2]


class Stopped(Exception):
    pass


class CloudApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'cloud/publication', self.root / 'cloud/publication')
        shutil.copyfile(ROOT / 'cloud/approval.json', self.root / 'cloud/approval.json')
        self.st = SimpleNamespace(secrets={'RISKBEX_SNAPSHOT_SHA256': 'obsolete-manual-secret'},
                                  session_state={'_riskbex_snapshot_version': 'previous'},
                                  cache_data=SimpleNamespace(clear=Mock()), error=Mock(),
                                  stop=Mock(side_effect=Stopped))

    def run_entry(self, extra=None):
        source = (ROOT / 'cloud/streamlit_app.py').read_text()
        with patch.dict(os.environ, extra or {}, clear=True), \
             patch.dict('sys.modules', {'streamlit': self.st}), \
             patch('runpy.run_path') as dashboard:
            exec(compile(source, 'streamlit_app.py', 'exec'),
                 {'__file__': str(self.root / 'cloud/streamlit_app.py')})
            self.assertEqual(dashboard.call_count, 1)

    def test_git_approval_supersedes_stale_secret_and_invalidates_cache(self):
        self.run_entry()
        version = json.loads((self.root / 'cloud/approval.json').read_text())['version']
        self.assertEqual(self.st.session_state['_riskbex_snapshot_version'], version)
        self.st.cache_data.clear.assert_called_once()
        self.run_entry()
        self.st.cache_data.clear.assert_called_once()

    def test_wrong_explicit_pin_rejected(self):
        with self.assertRaises(Stopped):
            self.run_entry({'RISKBEX_SNAPSHOT_SHA256': '0' * 64})

    def test_legacy_secret_exported_to_environment_is_not_a_permanent_pin(self):
        self.run_entry({'RISKBEX_SNAPSHOT_SHA256': 'obsolete-manual-secret'})
        self.assertEqual(self.st.session_state['_riskbex_snapshot_data_date'], '2026-11-16')

    def test_current_deployed_secret_remains_compatible(self):
        approval = json.loads((self.root / 'cloud/approval.json').read_text())
        seal = approval['snapshot_sha256']
        self.st.secrets['RISKBEX_SNAPSHOT_SHA256'] = seal
        self.run_entry({'RISKBEX_SNAPSHOT_SHA256': seal})

    def test_malformed_or_inconsistent_approval_rejected_even_with_valid_pin(self):
        path = self.root / 'cloud/approval.json'
        original = json.loads(path.read_text())
        invalid = [[], dict(original, format=True), dict(original, version='0' * 64),
                   dict(original, data_date='2026-11-13'), dict(original, data_date='invalid')]
        for value in invalid:
            with self.subTest(value=value):
                path.write_text(json.dumps(value))
                with self.assertRaises(Stopped):
                    self.run_entry({'RISKBEX_SNAPSHOT_SHA256': original['snapshot_sha256']})

    def test_session_date_regression_rejected(self):
        self.st.session_state['_riskbex_snapshot_data_date'] = '2026-11-17'
        with self.assertRaises(Stopped):
            self.run_entry()

    def test_corrupt_approval_or_payload_fails_closed(self):
        path = self.root / 'cloud/approval.json'
        original = path.read_bytes()
        path.write_text('{}')
        with self.assertRaises(Stopped): self.run_entry()
        path.write_bytes(original)
        data = json.loads(path.read_text()); data['snapshot_sha256'] = None
        path.write_text(json.dumps(data))
        with self.assertRaises(Stopped): self.run_entry()
        path.write_bytes(original)
        (self.root / 'cloud/publication/snapshot.json').write_text('{}')
        with self.assertRaises(Stopped): self.run_entry()

    def test_absent_default_approval_rejected_even_with_valid_pin(self):
        approval = json.loads((self.root / 'cloud/approval.json').read_text())
        (self.root / 'cloud/approval.json').unlink()
        with self.assertRaises(Stopped): self.run_entry()
        with self.assertRaises(Stopped): self.run_entry({'RISKBEX_SNAPSHOT_SHA256': approval['snapshot_sha256']})
        self.st.secrets = {}
        with self.assertRaises(Stopped): self.run_entry()


if __name__ == '__main__':
    unittest.main()
