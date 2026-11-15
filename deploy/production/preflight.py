"""Read-only checks on the future VPS. Does not start services or fetch data."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from storage import verify_store

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', action='store_true')
    args = parser.parse_args()
    try:
        env = Path(os.environ['RISKBEX_PROD_ENV'])
        if stat.S_IMODE(env.stat().st_mode) != 0o600:
            raise ValueError('Production env must have mode 0600')
        config = json.loads(subprocess.check_output(
            ['sh', str(HERE / 'compose.sh'), '--profile', 'scheduled', '--profile', 'public',
             'config', '--format', 'json'], text=True, timeout=30))
        services = config['services']
        if config['name'] != 'riskbex-prod':
            raise ValueError('Unexpected Compose project')
        for name in ('api', 'dashboard', 'updater'):
            service = services[name]
            if service.get('ports') or not service['read_only'] or service['user'].startswith('0:'):
                raise ValueError('Unsafe service ports or permissions')
            if not re.search(r':[0-9a-f]{7,40}$', service['image']):
                raise ValueError('Release tag must be a reviewed Git SHA')
            for mount in service.get('volumes', []):
                if mount['type'] != 'bind':
                    continue
                path = Path(mount['source'])
                if not path.is_absolute() or not path.exists():
                    raise ValueError('Required mount missing or not absolute: ' + str(path))
                if path.is_relative_to(HERE.parents[1]):
                    raise ValueError('Production runtime must be outside the checkout')
                if mount['target'] in ('/inputs/seed.csv', '/inputs/receipt.json') and not path.is_file():
                    raise ValueError('Input must be an existing file')
        mounts = {m['target']: m for m in services['updater']['volumes']}
        store = Path(mounts['/app/runtime/main']['source'])
        seed = Path(mounts['/inputs/seed.csv']['source'])
        receipt = Path(mounts['/inputs/receipt.json']['source'])
        uid, gid = map(int, services['updater']['user'].split(':'))
        if os.geteuid() != uid or os.getegid() != gid:
            raise ValueError('Run preflight as the configured UID/GID')
        if not os.access(store, os.R_OK | os.W_OK | os.X_OK):
            raise ValueError('Store is not writable by the configured identity')
        for root in (store, seed.parent):
            for path in [root, *root.rglob('*')]:
                if path.is_symlink() or path.stat().st_mode & 0o022:
                    raise ValueError('Symlink or group/world writable operational path')
                if not os.access(path, os.R_OK):
                    raise ValueError('Unreadable operational path')
        version = verify_store(store)
        if not (store / 'update.lock').is_file():
            raise ValueError('Existing update lock required')
        for name in ('api', 'dashboard', 'updater', 'caddy'):
            log = services[name]['logging']
            if log['options'].get('max-size') != '10m' or log['options'].get('max-file') != '3':
                raise ValueError('Missing bounded Docker logging')
        for mount in services['caddy']['volumes']:
            path = Path(mount['source'])
            if not path.exists():
                raise ValueError('Caddy mount missing')
            if mount['target'] in ('/data', '/config') and not os.access(path, os.W_OK):
                raise ValueError('TLS directories are not writable')
        if args.public:
            domain = services['caddy']['environment']['RISKBEX_DOMAIN']
            if (domain.endswith(('.invalid', '.example', '.test', '.localhost'))
                    or not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', domain)
                    or '.' not in domain):
                raise ValueError('Configure an actual DNS hostname before public startup')
        print(json.dumps({'ok': True, 'active_version': version,
                          'note': 'Filesystem checks only; runtime/package/gate verification still required'}))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Preflight failed: {exc}\n')


if __name__ == '__main__':
    main()
