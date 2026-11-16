"""Read-only landing evidence, separate from pipeline and scheduler execution."""
import json
import os
from pathlib import Path


def read_update_status(root):
    """Read only the configured runtime, never search historical or test stores."""
    try:
        value = json.loads((root / 'status.json').read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def local_scheduler_active(root, proc=Path('/proc')):
    """Positive evidence only: the known timer owns this runtime's lifetime lock.

    A lock file alone can survive shutdown. Absence from /proc can also mean the
    scheduler runs in another PID namespace, so absence is unknown, not inactive.
    No lock is acquired and no process or scheduler command is executed.
    """
    try:
        stat = (root / 'container-scheduler.lock').stat()
        identity = (os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino)
        for line in (proc / 'locks').read_text().splitlines():
            fields = line.split()
            if len(fields) < 6 or fields[1:4] != ['FLOCK', 'ADVISORY', 'WRITE']:
                continue
            major, minor, inode = fields[5].split(':')
            if (int(major, 16), int(minor, 16), int(inode)) != identity:
                continue
            command = (proc / fields[4] / 'cmdline').read_bytes().split(b'\0')
            if any(Path(os.fsdecode(arg)).name == 'run_container_scheduler.py' for arg in command):
                return True
    except (OSError, ValueError):
        pass
    return None
