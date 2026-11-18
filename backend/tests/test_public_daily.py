"""Public automation orchestration; no live retrieval or real Git writes."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_public_daily import execute

ENV = dict(GITHUB_REPOSITORY='apalomo75/RiskBEX', GITHUB_REF='refs/heads/main',
           RISKBEX_PUBLICATION_ENABLED='true')


class PublicDailyTests(unittest.TestCase):
    def test_disabled_before_provider_or_git(self):
        with patch.dict(os.environ, {}, clear=True), patch('scripts.run_public_daily.YahooProvider') as provider, \
             patch('scripts.run_public_daily.verify_predecessor') as predecessor:
            with self.assertRaisesRegex(ValueError, 'disabled'):
                execute('.', '/tmp/unused', 'a' * 40, now='2026-11-17T22:00Z')
            provider.assert_not_called()
            predecessor.assert_not_called()

    def test_single_switch_keeps_repository_and_branch_guards(self):
        for change in [dict(RISKBEX_PUBLICATION_ENABLED='false'),
                       dict(GITHUB_REPOSITORY='other/repo'), dict(GITHUB_REF='refs/heads/other')]:
            with self.subTest(change=change), patch.dict(os.environ, dict(ENV, **change), clear=True), \
                 patch('scripts.run_public_daily.verify_predecessor') as predecessor:
                with self.assertRaisesRegex(ValueError, 'disabled'):
                    execute('.', '/tmp/unused', 'a' * 40, now='2026-11-17T22:00Z')
                predecessor.assert_not_called()

    def test_noop_never_promotes(self):
        def noop(*args, public_summary, **kwargs):
            public_summary.update(update='skipped', run_status='success')
        with patch.dict(os.environ, ENV), patch('scripts.run_public_daily.verify_predecessor'), \
             patch('scripts.run_public_daily.run', side_effect=noop), \
             patch('scripts.run_public_daily.promote') as promote:
            result = execute('.', '/tmp/unused', 'a' * 40, provider=object(), now='2026-11-17T22:00Z')
            self.assertEqual(result['publication'], 'unchanged')
            promote.assert_not_called()

    def test_generated_requires_live_promotion_and_confirms_remote(self):
        def generated(*args, public_summary, **kwargs):
            public_summary.update(update='generated', run_status='success')
        for remote in ['b' * 40, 'c' * 40]:
            with self.subTest(remote=remote), patch.dict(os.environ, ENV), \
                 patch('scripts.run_public_daily.verify_predecessor'), \
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

    def test_fixture_runs_full_public_path_then_repeat_without_commit(self):
        # Only the provider response, wall clock and Git transport are simulated.
        import shutil
        import pandas as pd
        from scripts.run_daily_update import FileProvider
        from src.riskbex.actions_update import approved_bundle, BRANCH
        from src.riskbex.pipeline.provider import YahooProvider
        from src.riskbex.pipeline.store import VersionStore
        from src.riskbex.publication_control import verify_provenance

        source = Path(__file__).resolve().parents[2]
        now = '2026-11-17T22:00Z'
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'release'
            for name in ['cloud/publication', 'backend/model_packages/main-v1']:
                shutil.copytree(source / name, root / name)
            shutil.copyfile(source / 'cloud/approval.json', root / 'cloud/approval.json')
            config = root / 'backend/config'
            config.mkdir()
            for name in ['actions-regression.json', 'bme-2026.json']:
                shutil.copyfile(source / 'backend/config' / name, config / name)
            prices = pd.read_csv(VersionStore(root / 'cloud/publication/store').current() / 'prices.csv',
                                 float_precision='round_trip')
            extra = pd.read_csv(source / 'backend/tests/fixtures/live-dry-run/extension.csv')
            provider_file = base / 'prices.csv'
            pd.concat([prices, extra]).to_csv(provider_file, index=False)
            remote = {'head': 'a' * 40}
            calls = []

            def git(command, **kwargs):
                args = command[3:]
                calls.append(args)
                if args == ['branch', '--show-current']: return BRANCH
                if args == ['rev-parse', 'HEAD']: return remote['head']
                if args[0] in {'status', 'add'}: return ''
                if args[0] == 'commit':
                    remote['head'] = 'b' * 40
                    return ''
                if args == ['push', 'origin', 'HEAD:refs/heads/' + BRANCH]: return ''
                if args == ['ls-remote', '--exit-code', 'origin', 'refs/heads/' + BRANCH]:
                    return remote['head'] + '\trefs/heads/' + BRANCH
                raise AssertionError(args)

            with patch.dict(os.environ, ENV, clear=True), \
                 patch.object(YahooProvider, 'fetch', side_effect=FileProvider(provider_file).fetch) as fetch, \
                 patch('subprocess.check_output', side_effect=git), \
                 patch('src.riskbex.publication_control.verify_provenance',
                       side_effect=lambda *a, **kw: verify_provenance(*a, **kw, now=now)):
                first = execute(root, base / 'first', 'a' * 40, now=now)
                self.assertEqual(first['publication'], 'published')
                self.assertEqual(first['published_session'], '2026-11-17')
                self.assertEqual(approved_bundle(root)['version'], first['published_version'])
                fetch.assert_called_once()
                fetch.reset_mock()
                second = execute(root, base / 'repeat', 'b' * 40, now=now)
                self.assertEqual(second['publication'], 'unchanged')
                fetch.assert_not_called()
            self.assertEqual(sum(c[0] == 'commit' for c in calls), 1)
            self.assertEqual([c for c in calls if c[0] == 'push'],
                             [['push', 'origin', 'HEAD:refs/heads/' + BRANCH]])
