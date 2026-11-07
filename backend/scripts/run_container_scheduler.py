"""Opt-in container timer for the unchanged Sprint 6A live entry point."""
from datetime import datetime, timedelta
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys
import threading
from zoneinfo import ZoneInfo

MADRID = ZoneInfo('Europe/Madrid')
HOURS = (20, 21, 22)
STORE = Path('/app/runtime/main')
STOP = threading.Event()


def next_trigger(now):
    local = now.astimezone(MADRID)
    for offset in (0, 1):
        day = local.date() + timedelta(days=offset)
        for hour in HOURS:
            candidate = datetime(day.year, day.month, day.day, hour, 15, tzinfo=MADRID)
            if candidate > local:
                return candidate
    raise RuntimeError('No next trigger')


def main():
    if sys.version_info[:3] != (3, 11, 14):
        raise RuntimeError('Container updater requires Python 3.11.14')
    for path in ('/inputs/seed.csv', '/inputs/receipt.json'):
        if not Path(path).is_file():
            raise ValueError('Validated seed and regression receipt are required')
    # A separate lifetime lock prevents duplicate container timers. The existing
    # update.lock continues to protect each publication, including manual jobs.
    with (STORE / 'container-scheduler.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from src.riskbex.engine.package import load_main_package
        from src.riskbex.pipeline.service import verify_gate
        from src.riskbex.pipeline.calendar import SessionCalendar
        package = load_main_package('/app/model_packages/main-v1')
        verify_gate('/inputs/receipt.json', package)
        calendar = SessionCalendar.load('/app/config/bme-2026.json')
        calendar.eligible(datetime.now(MADRID))
        if calendar.config['timezone'] != 'Europe/Madrid':
            raise ValueError('Expected Europe/Madrid calendar')
        child = None

        def stop(signum, frame):
            STOP.set()
            if child is not None:
                child.terminate()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        while not STOP.is_set():
            target = next_trigger(datetime.now(MADRID))
            print(json.dumps({'event': 'timer_wait', 'next_trigger': target.isoformat()}), flush=True)
            # Recheck the wall clock to tolerate host sleep and clock corrections.
            while not STOP.is_set() and datetime.now(MADRID) < target:
                STOP.wait(min(30, max(0, (target - datetime.now(MADRID)).total_seconds())))
            if STOP.is_set():
                break
            child = subprocess.Popen([
                sys.executable, '-B', '/app/scripts/run_scheduled_update.py', '--fetch',
                '--seed', '/inputs/seed.csv', '--store', str(STORE),
                '--regression-receipt', '/inputs/receipt.json',
            ], cwd='/app')
            try:
                code = child.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:
                    child.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                code = 124
            finally:
                child = None
            print(json.dumps({'event': 'timer_result', 'exit_code': code}), flush=True)
    return 0


if __name__ == '__main__':
    # Match the existing scheduled entry point when invoked by absolute script path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    sys.exit(main())
