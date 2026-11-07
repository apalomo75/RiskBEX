"""Scheduler contract tests: offline mocks, real calendar and continuity rules."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from scripts import run_scheduled_update as runner
from src.riskbex.pipeline.provider import merge_new_sessions
from src.riskbex.pipeline.calendar import SessionCalendar

BACKEND = Path(__file__).resolve().parents[1]


class ScheduledTests(unittest.TestCase):
    def setUp(self):
        self.calendar = SessionCalendar.load(BACKEND / 'config/bme-2026.json')
        self.args = argparse.Namespace(store=Path('/tmp/riskbex-scheduler-test'), seed=Path('seed.csv'),
            package=BACKEND / 'model_packages/main-v1', calendar=BACKEND / 'config/bme-2026.json',
            regression_receipt=Path('receipt.json'))

    def invoke(self, result=None, error=None, now='2026-11-06T20:15Z'):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), \
             patch.object(runner, 'utc_now', return_value=pd.Timestamp(now)), \
             patch.object(runner, 'load_main_package'), \
             patch.object(runner.pd, 'read_csv', return_value=pd.DataFrame()), \
             patch.object(runner.VersionStore, 'current', return_value=None), \
             patch.object(runner, 'update_main', return_value=result, side_effect=error) as update:
            code = runner.run(self.args)
        return code, [json.loads(line) for line in output.getvalue().splitlines()], update

    def test_success_and_duplicate(self):
        for status, count in [('published', 3), ('unchanged', 0)]:
            with self.subTest(status=status):
                code, events, update = self.invoke(dict(status=status, data_date='2026-11-06',
                                                       new_sessions=count, version='a' * 64))
                self.assertEqual(code, 0)
                self.assertEqual(events[-1]['new_sessions'], count)
                self.assertEqual(events[-1]['status'], status)
                self.assertTrue(events[-1]['ended_at'])
                self.assertTrue(update.call_args.args[2].is_live)

    def test_failure_codes_and_redaction(self):
        for error, expected in [(RuntimeError('provider https://secret:token@host'), 1),
                                (ValueError('missing sessions'), 1), (OSError('disk full'), 1),
                                (RuntimeError('Another MAIN update is running.'), 75)]:
            with self.subTest(error=type(error).__name__):
                code, events, _ = self.invoke(error=error)
                self.assertEqual(code, expected)
                self.assertNotIn('secret', json.dumps(events))
                self.assertIsNone(events[-1]['publication_version'])

    def test_calendar_weekend_holiday_and_dst(self):
        cases = {'2026-04-06T20:15Z': '2026-04-02',
                 '2026-11-07T20:15Z': '2026-11-06',
                 '2026-03-27T18:59Z': '2026-03-26',
                 '2026-03-27T19:00Z': '2026-03-27',
                 '2026-03-30T17:59Z': '2026-03-27',
                 '2026-03-30T18:00Z': '2026-03-30',
                 '2026-10-23T18:00Z': '2026-10-23',
                 '2026-10-26T18:59Z': '2026-10-23',
                 '2026-10-26T19:00Z': '2026-10-26'}
        for now, expected in cases.items():
            with self.subTest(now=now):
                self.assertEqual(self.calendar.eligible(now).date().isoformat(), expected)

    def test_expired_calendar_fails_before_provider(self):
        code, events, update = self.invoke(now='2027-02-01T20:15Z')
        self.assertEqual(code, 1)
        update.assert_not_called()

    def test_catchup_requires_every_session(self):
        dates = self.calendar.sessions('2026-04-20', '2026-04-24')
        prices = pd.DataFrame({'date': dates, 'ibex_close': range(100, 105)})
        history = prices.iloc[:1]
        combined, count = merge_new_sessions(history, prices, self.calendar, dates[-1], dates[0])
        self.assertEqual(count, 4)
        self.assertEqual(len(combined), 5)
        with self.assertRaisesRegex(ValueError, 'missing exchange sessions'):
            merge_new_sessions(history, prices.drop(index=2), self.calendar, dates[-1], dates[0])

    def test_simulated_cli_is_unavailable(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            runner.main(['--seed', 'seed', '--store', '/tmp/store', '--regression-receipt', 'receipt',
                         '--fetch', '--provider-file', 'simulated.csv'])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
