"""Offline authorization, calendar and truthful daily reporting checks."""
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.run_private_daily import authorized, execute
from src.riskbex.pipeline.calendar import SessionCalendar

ROOT = Path(__file__).resolve().parents[2]


class PrivateDailyTests(unittest.TestCase):
    def test_authorization(self):
        env = dict(RISKBEX_PRIVATE_DAILY_ENABLED='true', GITHUB_EVENT_NAME='schedule',
                   GITHUB_REF='refs/heads/main', GITHUB_REPOSITORY='owner/repo',
                   RISKBEX_EXPECTED_REPOSITORY='owner/repo')
        for event in ['schedule', 'workflow_dispatch']:
            self.assertTrue(authorized(dict(env, GITHUB_EVENT_NAME=event)))
        for key, value in [('RISKBEX_PRIVATE_DAILY_ENABLED', 'false'),
                           ('GITHUB_EVENT_NAME', 'push'), ('GITHUB_REF', 'refs/heads/other'),
                           ('RISKBEX_EXPECTED_REPOSITORY', 'other/repo')]:
            self.assertFalse(authorized(dict(env, **{key: value})))

    def test_calendar_dst_weekends_holidays_and_expiry(self):
        calendar = SessionCalendar.load(ROOT / 'backend/config/bme-2026.json')
        for now, expected in [('2026-11-17T18:59Z', '2026-11-16'),
                              ('2026-11-17T19:00Z', '2026-11-17'),
                              ('2026-07-07T17:59Z', '2026-07-06'),
                              ('2026-07-07T18:00Z', '2026-07-07'),
                              ('2026-11-22T22:17Z', '2026-11-20'),
                              ('2026-12-25T20:17Z', '2026-12-24')]:
            self.assertEqual(str(calendar.eligible(now).date()), expected)
        with self.assertRaises(ValueError):
            calendar.eligible('2027-01-05T20:17Z')

    def test_truthful_noop_update_failure_and_regression_failure(self):
        for count, gate, failure in [(0, 'passed', False), (2, 'passed', False),
                                      (None, 'failed', True)]:
            summary = {}
            def fake(*args, **kwargs):
                kwargs['public_summary'].update(previous_approved_session='2026-11-16',
                    latest_validated_candidate_session='2026-11-17', new_trading_sessions=count,
                    integrity_gate='passed', regression_gate=gate, run_status='success')
                if failure:
                    raise ValueError('private provider or regression details')
            with patch('scripts.run_private_daily.run', side_effect=fake):
                if failure:
                    with self.assertRaises(ValueError):
                        execute('.', '/tmp/unused', provider=None, now=None, summary=summary)
                else:
                    execute('.', '/tmp/unused', provider=None, now=None, summary=summary)
            self.assertEqual(summary['outcome'], 'failed' if failure else 'updated' if count else 'unchanged')
            self.assertNotIn('private provider', str(summary))

    def test_workflow_gates_and_schedules(self):
        workflow = (ROOT / '.github/retired/private-daily.yml.disabled').read_text()
        for required in ['riskbex-private-daily-v1', 'state/main-daily',
                         "vars.RISKBEX_PRIVATE_DAILY_ENABLED == 'true'", 'contents: read',
                         'run_actions_offline.py', '3.11.14', 'if: always()',
                         'RISKBEX_PRIVATE_STORAGE_AUTHORIZED', '--persist-head', '.private']:
            self.assertIn(required, workflow)
        for forbidden in ['\n  schedule:', 'upload-artifact', 'actions/cache',
                          '3cffc6b377a4010272788c9e434111c12258aeea']:
            self.assertNotIn(forbidden, workflow)
