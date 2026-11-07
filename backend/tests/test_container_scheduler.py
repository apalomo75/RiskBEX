"""Offline container timer checks; never launch the updater or access markets."""
from datetime import datetime
import unittest
from unittest.mock import patch
from scripts import run_container_scheduler as timer


class ContainerTimerTests(unittest.TestCase):
    def test_startup_waits_for_future_slot(self):
        for clock, expected in [
            ('2026-11-06T08:00:00+01:00', '2026-11-06T20:15:00+01:00'),
            ('2026-11-06T20:15:00+01:00', '2026-11-06T21:15:00+01:00'),
            ('2026-11-06T22:16:00+01:00', '2026-11-07T20:15:00+01:00'),
        ]:
            self.assertEqual(timer.next_trigger(datetime.fromisoformat(clock)).isoformat(), expected)

    def test_dst_uses_madrid_wall_time(self):
        for clock, expected in [
            ('2026-03-28T23:00:00+01:00', '2026-03-29T20:15:00+02:00'),
            ('2026-10-24T23:00:00+02:00', '2026-10-25T20:15:00+01:00'),
        ]:
            self.assertEqual(timer.next_trigger(datetime.fromisoformat(clock)).isoformat(), expected)

    def test_python_313_rejected_before_files_or_processes(self):
        with patch.object(timer.sys, 'version_info', (3, 13, 0)), \
             patch.object(timer.subprocess, 'Popen') as child:
            with self.assertRaisesRegex(RuntimeError, '3.11.14'):
                timer.main()
            child.assert_not_called()

    def test_missing_inputs_fail_without_downloads(self):
        with patch.object(timer.sys, 'version_info', (3, 11, 14)), \
             patch.object(timer.Path, 'is_file', return_value=False), \
             patch.object(timer.subprocess, 'Popen') as child:
            with self.assertRaises(ValueError):
                timer.main()
            child.assert_not_called()
