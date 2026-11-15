"""Read-only production probe. JSON output, exit 0 healthy, 1 action needed.

No alert destination or updater invocation. A separate operator-installed monitor
may consume this exit status; it must never invoke the market-data scheduler.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent


def events_from_logs(raw):
    events = []
    for line in raw.splitlines():
        try:
            timestamp, payload = line.split(' ', 1)
            events.append((datetime.fromisoformat(timestamp.replace('Z', '+00:00')), json.loads(payload)))
        except (ValueError, TypeError):
            continue
    return events


def assess(containers, publication, events, disk, now, calendar, public=False):
    issues = []
    expected = ['api', 'dashboard', 'updater'] + (['caddy'] if public else [])
    for service in expected:
        info = containers.get(service)
        if not info or not info['State'].get('Running'):
            issues.append(f'{service}: stopped or missing')
            continue
        health = info['State'].get('Health', {}).get('Status')
        if (service in ('api', 'dashboard') and health != 'healthy') or health == 'unhealthy':
            issues.append(f'{service}: health check is not healthy')
        if info.get('RestartCount', 0):
            issues.append(f'{service}: restart count is nonzero; inspect logs')
        started = datetime.fromisoformat(info['State']['StartedAt'].replace('Z', '+00:00'))
        if now - started < timedelta(minutes=10):
            issues.append(f'{service}: started recently; continuity not yet established')
    if not publication:
        issues.append('publication: API unavailable or response invalid')
    else:
        if not publication.get('is_current') or publication.get('freshness') != 'current':
            issues.append('publication: stale or unverified; expected session is missing')
        if (publication.get('update_status') or {}).get('status') == 'failed':
            issues.append('updater: latest pipeline attempt failed')
    # Every calendar day has timer slots, including weekends. Allow 35 minutes
    # for the existing 30-minute timeout and startup/network overhead.
    local = now.astimezone(ZoneInfo('Europe/Madrid'))
    slots = [datetime(local.year, local.month, local.day, hour, 15, tzinfo=local.tzinfo)
             - timedelta(days=day) for day in (0, 1) for hour in (20, 21, 22)]
    due = max(slot for slot in slots if slot <= local - timedelta(minutes=35))
    results = [(stamp, event) for stamp, event in events if event.get('event') == 'timer_result']
    if not results or max(stamp for stamp, _ in results) < due:
        issues.append('scheduler: no completion evidence for the latest elapsed slot')
    if results and max(results, key=lambda row: row[0])[1].get('exit_code') != 0:
        issues.append('scheduler: latest invocation failed or timed out')
    if disk.free / disk.total < 0.15 or disk.free < 2 * 1024**3:
        issues.append('disk: less than 15% or 2 GiB free')
    if local.year not in calendar.get('years', []):
        issues.append('calendar: current year is not covered')
    else:
        remaining = (datetime(max(calendar['years']) + 1, 1, 1, tzinfo=local.tzinfo) - local).days
        if remaining <= 45:
            issues.append('calendar: reviewed coverage expires within 45 days')
    return issues


def run(command):
    return subprocess.check_output(command, text=True, timeout=45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk-path', type=Path, required=True)
    parser.add_argument('--public', action='store_true', help='Also require Caddy running')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        config = json.loads(run(['sh', str(HERE / 'compose.sh'), '--profile', 'scheduled',
                                 '--profile', 'public', 'config', '--format', 'json']))
        containers, events, publication, calendar = {}, [], None, {}
        extra = []
        for service in ['api', 'dashboard', 'updater'] + (['caddy'] if args.public else []):
            ids = run(['sh', str(HERE / 'compose.sh'), 'ps', '-a', '-q', service]).split()
            if len(ids) != 1:
                extra.append(f'{service}: expected exactly one container')
                continue
            info = json.loads(run(['docker', 'inspect', ids[0]]))[0]
            containers[service] = info
            if service == 'updater':
                events = events_from_logs(run(['docker', 'logs', '--timestamps', '--since', '30h', ids[0]]))
        # Requests are made inside the existing dashboard, never expose API on host.
        code = ('import urllib.request,json; '
                'urllib.request.urlopen("http://api:8000/health",timeout=10).read(); '
                'urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health",timeout=10).read(); '
                'd=json.load(urllib.request.urlopen("http://api:8000/latest-risk",timeout=30)); '
                'print(json.dumps(d["publication"]))')
        try:
            publication = json.loads(run(['sh', str(HERE / 'compose.sh'), 'exec', '-T',
                                          'dashboard', 'python', '-B', '-c', code]))
        except (subprocess.SubprocessError, ValueError):
            extra.append('API/dashboard HTTP probe failed')
        # Read the actual image calendar, not a potentially different host checkout.
        try:
            calendar = json.loads(run(['sh', str(HERE / 'compose.sh'), 'exec', '-T', 'api',
                                       'cat', '/app/config/bme-2026.json']))
        except (subprocess.SubprocessError, ValueError):
            extra.append('calendar: runtime coverage could not be checked')
        paths = {args.disk_path.resolve()}
        for service in config['services'].values():
            for volume in service.get('volumes', []):
                if volume['type'] == 'bind':
                    paths.add(Path(volume['source']).resolve())
        issues = extra
        for path in paths:
            disk = shutil.disk_usage(path)
            issues += [f'{path}: {issue}' for issue in assess(
                {}, None, [], disk, now, calendar) if issue.startswith('disk:')]
        issues += assess(containers, publication, events, shutil.disk_usage(args.disk_path),
                         now, calendar, args.public)
        result = {'checked_at': now.isoformat(), 'ok': not issues, 'issues': sorted(set(issues)),
                  'data_date': (publication or {}).get('data_date'),
                  'expected_data_date': (publication or {}).get('expected_data_date')}
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result = {'checked_at': now.isoformat(), 'ok': False,
                  'issues': ['Probe incomplete: ' + type(exc).__name__]}
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
