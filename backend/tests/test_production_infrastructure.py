"""Production safeguards tested with temporary fixtures; never operate containers."""
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / 'deploy/production'


def module(name):
    spec = importlib.util.spec_from_file_location(name, PROD / (name + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


storage = module('storage')
monitor = module('monitor')


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / 'store'
        self.version = 'a' * 64
        version = self.store / 'versions' / self.version
        version.mkdir(parents=True)
        for name in storage.REQUIRED:
            (version / name).write_text('{}' if name.endswith('json') else 'date,value\n2026-11-10,1\n')
        manifest = {'version': self.version, 'engine': 'MAIN', 'status': 'validated',
                    'files': {name: storage.digest(version / name) for name in storage.REQUIRED}}
        (version / 'manifest.json').write_text(json.dumps(manifest))
        (self.store / 'current.json').write_text(json.dumps({
            'version': self.version, 'manifest_sha256': storage.digest(version / 'manifest.json')}))
        (self.store / 'update.lock').touch()
        (self.store / 'container-scheduler.lock').touch()
        (self.store / '.staging').mkdir()
        (self.store / '.staging/partial').write_text('must not restore')
        (self.store / 'attempts').mkdir()
        (self.store / 'attempts/one.json').write_text('{"status":"unchanged"}')
        (self.store / 'status.json').write_text('{"status":"unchanged"}')
        self.inputs = self.root / 'inputs'
        self.inputs.mkdir()
        self.seed, self.receipt = self.inputs / 'seed.csv', self.inputs / 'receipt.json'
        self.seed.write_text('date,ibex_close\n2026-11-10,100\n')
        self.receipt.write_text('{"validated":true}')
        self.output = self.root / 'backup.tar.gz'

    def create(self):
        return storage.backup(self.store, self.seed, self.receipt, self.output)

    def test_round_trip_preserves_state_and_excludes_transient_files(self):
        before = {str(p): storage.digest(p) for p in self.store.rglob('*') if p.is_file()}
        result = self.create()
        destination = self.root / 'restored'
        storage.restore(self.output, destination, result['sha256'])
        self.assertEqual(storage.verify_store(destination / 'store'), self.version)
        self.assertEqual((destination / 'inputs/seed.csv').read_bytes(), self.seed.read_bytes())
        self.assertEqual((destination / 'inputs/receipt.json').read_bytes(), self.receipt.read_bytes())
        self.assertEqual((destination / 'store/status.json').read_bytes(), (self.store / 'status.json').read_bytes())
        self.assertTrue((destination / 'store/attempts/one.json').exists())
        self.assertFalse((destination / 'store/.staging').exists())
        self.assertFalse((destination / 'store/container-scheduler.lock').exists())
        self.assertTrue((destination / 'store/update.lock').exists())
        self.assertEqual(before, {str(p): storage.digest(p) for p in self.store.rglob('*') if p.is_file()})

    def test_locked_update_rejects_backup_without_output(self):
        with (self.store / 'update.lock').open('r+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.create()
        self.assertFalse(self.output.exists())

    def test_corruption_rejected_before_backup(self):
        (self.store / 'versions' / self.version / 'prices.csv').write_text('corrupt')
        with self.assertRaises(ValueError):
            self.create()
        self.assertFalse(self.output.exists())

    def test_restore_refuses_existing_and_bad_archive_digest(self):
        result = self.create()
        with self.assertRaises(ValueError):
            storage.restore(self.output, self.store, result['sha256'])
        with self.assertRaises(ValueError):
            storage.restore(self.output, self.root / 'new', '0' * 64)
        self.assertFalse((self.root / 'new').exists())
        with self.assertRaises(ValueError):
            self.create()

    def test_archive_traversal_and_links_rejected(self):
        for kind in ('../escape', 'state/link'):
            with self.subTest(kind=kind):
                path = self.root / 'unsafe.tar.gz'
                with tarfile.open(path, 'w:gz') as archive:
                    member = tarfile.TarInfo(kind)
                    if kind.endswith('link'):
                        member.type = tarfile.SYMTYPE
                        member.linkname = '/etc/passwd'
                    archive.addfile(member, io.BytesIO(b''))
                with self.assertRaises(ValueError):
                    storage.restore(path, self.root / 'new', storage.digest(path))
                self.assertFalse((self.root / 'escape').exists())

    def test_member_inventory_tampering_rejected(self):
        result = self.create()
        changed = self.root / 'tampered.tar.gz'
        with tarfile.open(self.output, 'r:gz') as source, tarfile.open(changed, 'w:gz') as target:
            for member in source.getmembers():
                data = source.extractfile(member).read() if member.isfile() else None
                if member.name == 'state/inputs/seed.csv':
                    data = b'changed'
                    member.size = len(data)
                target.addfile(member, io.BytesIO(data) if data is not None else None)
        with self.assertRaises(ValueError):
            storage.restore(changed, self.root / 'new', storage.digest(changed))
        self.assertFalse((self.root / 'new').exists())

    @unittest.skipUnless(shutil.which('docker'), 'Docker Compose CLI unavailable')
    def test_preflight_on_isolated_migration_and_public_placeholder_rejection(self):
        data = self.root / 'historical'
        data.mkdir()
        tls = self.root / 'tls'
        (tls / 'data').mkdir(parents=True)
        (tls / 'config').mkdir()
        values = {
            'RISKBEX_UID': str(os.geteuid()), 'RISKBEX_GID': str(os.getegid()),
            'RISKBEX_RELEASE': 'abcdef123456', 'RISKBEX_DOMAIN': 'example.invalid',
            'RISKBEX_STORE': str(self.store), 'RISKBEX_SEED': str(self.seed),
            'RISKBEX_REGRESSION_RECEIPT': str(self.receipt),
            'RISKBEX_HISTORICAL_DATA': str(data),
            'RISKBEX_TLS_DATA': str(tls / 'data'), 'RISKBEX_TLS_CONFIG': str(tls / 'config'),
        }
        if os.geteuid() == 0:
            self.skipTest('Production deliberately rejects root identity')
        envfile = self.root / 'prod.env'
        envfile.write_text('\n'.join(f'{k}={v}' for k, v in values.items()) + '\n')
        envfile.chmod(0o600)
        env = {k: v for k, v in os.environ.items() if not k.startswith(('RISKBEX_', 'COMPOSE_'))}
        env['RISKBEX_PROD_ENV'] = str(envfile)
        command = [os.sys.executable, '-B', str(PROD / 'preflight.py')]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(command + ['--public'], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('actual DNS hostname', result.stderr)
        envfile.chmod(0o644)
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('0600', result.stderr)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)
        self.containers = {name: {'State': {'Running': True,
                           'StartedAt': (self.now - timedelta(days=1)).isoformat(),
                           'Health': {'Status': 'healthy'}}, 'RestartCount': 0}
                           for name in ('api', 'dashboard', 'updater')}
        self.publication = {'is_current': True, 'freshness': 'current',
                            'update_status': {'status': 'unchanged'}}
        self.events = [(self.now - timedelta(minutes=44), {'event': 'timer_result', 'exit_code': 0})]
        self.disk = SimpleNamespace(total=40 * 1024**3, free=20 * 1024**3)
        self.calendar = {'years': [2026]}

    def assess(self):
        return monitor.assess(self.containers, self.publication, self.events,
                              self.disk, self.now, self.calendar)

    def test_healthy_requires_data_and_scheduler_evidence(self):
        self.assertEqual(self.assess(), [])
        self.events.clear()
        self.assertTrue(any('no completion' in s for s in self.assess()))

    def test_failures_staleness_disk_restarts_and_calendar(self):
        self.publication.update(is_current=False, freshness='stale', update_status={'status': 'failed'})
        self.containers['api']['State']['Running'] = False
        self.containers['dashboard']['RestartCount'] = 3
        self.events[-1][1]['exit_code'] = 124
        self.disk.free = 1024**3
        self.calendar = {'years': [2025]}
        issues = self.assess()
        for word in ('stopped', 'restart', 'stale', 'pipeline', 'timed out', 'disk', 'calendar'):
            self.assertTrue(any(word in issue for issue in issues), (word, issues))

    def test_log_parser_uses_docker_timestamps(self):
        rows = monitor.events_from_logs('junk\n2026-11-10T21:15:04.737718486Z {"event":"timer_result","exit_code":0}')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0].hour, 21)

    def test_no_api_response_and_recent_start_never_healthy(self):
        self.publication = None
        self.containers['updater']['State']['StartedAt'] = self.now.isoformat()
        self.assertTrue(any('unavailable' in s for s in self.assess()))
        self.assertTrue(any('recently' in s for s in self.assess()))


@unittest.skipUnless(shutil.which('docker'), 'Docker Compose CLI unavailable')
class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.envfile = Path(self.temp.name) / 'prod.env'
        self.envfile.write_text((PROD / '.env.example').read_text().replace('replace-with-reviewed-git-sha', 'abcdef123456'))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('RISKBEX_', 'COMPOSE_'))}
        self.env['RISKBEX_PROD_ENV'] = str(self.envfile)

    def config(self):
        return json.loads(subprocess.check_output(['sh', str(PROD / 'compose.sh'), '--profile', 'scheduled',
                           '--profile', 'public', 'config', '--format', 'json'], env=self.env, text=True))

    def test_production_ports_permissions_inputs_logging_and_schedule(self):
        config = self.config()
        self.assertEqual(config['name'], 'riskbex-prod')
        services = config['services']
        for name in ('api', 'dashboard', 'updater'):
            self.assertFalse(services[name].get('ports'))
        self.assertEqual({str(p['published']) for p in services['caddy']['ports']}, {'80', '443'})
        for name, service in services.items():
            self.assertTrue(service['read_only'])
            self.assertEqual(service['restart'], 'unless-stopped')
            self.assertEqual(service['cap_drop'], ['ALL'])
            self.assertIn('no-new-privileges:true', service['security_opt'])
            self.assertEqual(service['logging']['options'], {'max-size': '10m', 'max-file': '3'})
            self.assertGreater(int(service['mem_limit']), 0)
            for volume in service.get('volumes', []):
                self.assertNotIn('docker.sock', volume.get('source', ''))
                self.assertFalse(volume.get('bind', {}).get('create_host_path', False))
        api = {v['target']: v for v in services['api']['volumes']}
        updater = {v['target']: v for v in services['updater']['volumes']}
        self.assertEqual(api['/app/runtime/main']['source'], updater['/app/runtime/main']['source'])
        self.assertTrue(api['/app/runtime/main']['read_only'])
        self.assertFalse(updater['/app/runtime/main'].get('read_only', False))
        for name in ('seed.csv', 'receipt.json'):
            self.assertTrue(updater['/inputs/' + name]['read_only'])
        self.assertEqual(services['updater']['environment']['TZ'], 'Europe/Madrid')
        self.assertEqual(services['updater']['command'], ['python', '-B', 'scripts/run_container_scheduler.py'])
        self.assertEqual(services['caddy']['profiles'], ['public'])
        self.assertEqual(services['updater']['profiles'], ['scheduled'])
        self.assertEqual(services['dashboard']['environment']['RISKBEX_API_URL'], 'http://api:8000')
        self.assertNotEqual(services['api']['image'], 'riskbex-api:local')

    def test_missing_required_production_env_rejected(self):
        self.envfile.write_text('RISKBEX_DOMAIN=example.invalid\n')
        result = subprocess.run(['sh', str(PROD / 'compose.sh'), 'config', '--quiet'],
                                env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('required', result.stderr.lower())

    def test_local_compose_keeps_loopback_and_opt_in_scheduler(self):
        result = json.loads(subprocess.check_output(['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'),
                             '--profile', 'scheduled', 'config', '--format', 'json'], env=self.env, text=True))
        self.assertEqual(result['services']['dashboard']['ports'][0]['host_ip'], '127.0.0.1')
        self.assertFalse(result['services']['api'].get('ports'))
        self.assertEqual(result['services']['updater']['profiles'], ['scheduled'])


if __name__ == '__main__':
    unittest.main()
