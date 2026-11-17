"""Public automation orchestration; no live retrieval or real Git writes."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_public_daily import execute
from src.riskbex.publication_control import verify_rights, SCOPES
from src.riskbex.pipeline.store import write_json, digest

ENV = dict(GITHUB_REPOSITORY='apalomo75/RiskBEX', GITHUB_REF='refs/heads/main',
           RISKBEX_PUBLICATION_ENABLED='true', RISKBEX_LIVE_DOWNLOAD_AUTHORIZED='true')


class PublicDailyTests(unittest.TestCase):
    def test_disabled_before_provider_or_git(self):
        with patch.dict(os.environ, {}, clear=True), patch('scripts.run_public_daily.YahooProvider') as provider, \
             patch('scripts.run_public_daily.verify_predecessor') as predecessor:
            with self.assertRaisesRegex(ValueError, 'disabled'):
                execute('.', '/tmp/unused', 'a' * 40, now='2026-11-17T22:00Z')
            provider.assert_not_called()
            predecessor.assert_not_called()

    def test_rights_failure_before_retrieval(self):
        with patch.dict(os.environ, ENV), patch('scripts.run_public_daily.verify_predecessor'), \
             patch('scripts.run_public_daily.verify_rights', side_effect=ValueError('blocked')), \
             patch('scripts.run_public_daily.run') as run:
            with self.assertRaises(ValueError):
                execute('.', '/tmp/unused', 'a' * 40, now='2026-11-17T22:00Z')
            run.assert_not_called()

    def test_noop_never_promotes(self):
        def noop(*args, public_summary, **kwargs):
            public_summary.update(update='skipped', run_status='success')
        with patch.dict(os.environ, ENV), patch('scripts.run_public_daily.verify_predecessor'), \
             patch('scripts.run_public_daily.verify_rights'), patch('scripts.run_public_daily.run', side_effect=noop), \
             patch('scripts.run_public_daily.promote') as promote:
            result = execute('.', '/tmp/unused', 'a' * 40, provider=object(), now='2026-11-17T22:00Z')
            self.assertEqual(result['publication'], 'unchanged')
            promote.assert_not_called()

    def test_generated_requires_live_promotion_and_confirms_remote(self):
        def generated(*args, public_summary, **kwargs):
            public_summary.update(update='generated', run_status='success')
        for remote in ['b' * 40, 'c' * 40]:
            with self.subTest(remote=remote), patch.dict(os.environ, ENV), \
                 patch('scripts.run_public_daily.verify_predecessor'), patch('scripts.run_public_daily.verify_rights'), \
                 patch('scripts.run_public_daily.run', side_effect=generated), \
                 patch('scripts.run_public_daily.promote', return_value='published') as promote, \
                 patch('scripts.run_public_daily.approved_bundle', return_value=dict(version='new', data_date='2026-11-17')), \
                 patch('subprocess.check_output', side_effect=['b' * 40, remote + '\trefs/heads/release/streamlit-rc1']):
                if remote == 'b' * 40:
                    self.assertEqual(execute('.', '/tmp/unused', 'a' * 40, provider=object(),
                                             now='2026-11-17T22:00Z')['published_version'], 'new')
                else:
                    with self.assertRaisesRegex(ValueError, 'confirmation'):
                        execute('.', '/tmp/unused', 'a' * 40, provider=object(), now='2026-11-17T22:00Z')
                promote.assert_called_once_with('.', '/tmp/unused', 'a' * 40, require_live=True)

    def test_owner_authorization_requires_real_bound_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / 'backend/config'
            config.mkdir(parents=True)
            evidence = config / 'publication-rights-evidence.txt'
            evidence.write_text('SYNTHETIC TEST ONLY: permission reference')
            receipt = dict(status='owner_authorized', provider='Yahoo Finance / IBEX 35',
                           scopes=sorted(SCOPES), valid_until='2099-01-01', reviewed_by='fixture',
                           licence_reference='synthetic', authorized_by='apalomo75',
                           repository='apalomo75/RiskBEX', permission_basis='synthetic fixture',
                           authorized_on='2026-11-17', evidence_sha256=digest(evidence))
            from datetime import date
            for change in [{}, dict(repository='another/repo'), dict(permission_basis=''),
                           dict(evidence_sha256='0' * 64), dict(authorized_on='2099-01-01')]:
                write_json(config / 'publication-rights.json', dict(receipt, **change))
                if change:
                    with self.assertRaises(ValueError):
                        verify_rights(root, today=date(2026, 11, 17))
                else:
                    verify_rights(root, today=date(2026, 11, 17))
