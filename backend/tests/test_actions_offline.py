"""Safety boundaries for the first hosted run; no live requests or Git writes."""
from pathlib import Path
import socket
import subprocess
import unittest

from scripts.run_actions_offline import check_git_command, offline_guards

ROOT = Path(__file__).resolve().parents[2]


class OfflineSafetyTests(unittest.TestCase):
    def test_git_mutations_and_shells_rejected(self):
        for command in ['git commit', ['git', 'push'], ['git', '-C', '/tmp', 'commit'],
                        ['git', 'init'], ['git', 'add', '.'], ['git', 'config', 'user.name', 'x']]:
            with self.subTest(command=command), self.assertRaises(AssertionError):
                check_git_command(command)
        check_git_command(['git', '-C', str(ROOT), 'ls-files', '-z'])
        # These checks fail before spawning a process, even in a temporary repo.
        with offline_guards():
            with self.assertRaises(AssertionError):
                subprocess.check_output(['git', 'commit', '-m', 'forbidden'])
            with self.assertRaises(AssertionError):
                subprocess.check_output('git push', shell=True)

    def test_real_yahoo_and_external_socket_rejected(self):
        with offline_guards():
            import yfinance
            with self.assertRaisesRegex(AssertionError, 'Yahoo'):
                yfinance.download('^IBEX')
            with socket.socket() as sock, self.assertRaisesRegex(AssertionError, 'Network'):
                sock.connect(('127.0.0.1', 9))

    def test_workflow_has_only_reviewed_offline_entrypoint(self):
        workflow = (ROOT / '.github/workflows/daily-update.yml').read_text()
        triggers = workflow.split('\non:\n', 1)[1].split('\npermissions:', 1)[0]
        self.assertIn('workflow_dispatch:', triggers)
        self.assertIn('release_sha:', triggers)
        self.assertNotIn('schedule:', triggers)
        self.assertNotIn('\n  push:', triggers)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn('ref: release/streamlit-rc1', workflow)
        self.assertIn('contents: read', workflow)
        self.assertNotIn('contents: write', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('run_actions_offline.py', workflow)
        self.assertIn('${{ inputs.release_sha }}', workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_RELEASE_SHA"', workflow)
        self.assertIn('test -z "$(git status --porcelain)"', workflow)
        self.assertLess(workflow.index('Verify reviewed release'), workflow.index('Install pinned frozen runtime'))
        for forbidden in ['run_actions_update.py', '--publish', '--fetch', 'secrets.', 'git push', 'git commit']:
            self.assertNotIn(forbidden, workflow)
        self.assertEqual(workflow.count('      - uses:'), 2)
        for line in workflow.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'@[0-9a-f]{40} ')


if __name__ == '__main__':
    unittest.main()
