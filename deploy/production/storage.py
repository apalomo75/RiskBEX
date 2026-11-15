"""Offline consistent state backup/restore. Standard library; never calls a provider.

Run as the store owner. Archives and restored trees are private (umask 077).
The archive contains operational data: encrypt it before off-server storage.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

REQUIRED = {'prices.csv', 'features.csv', 'signals.csv', 'backtest.csv',
            'metrics.csv', 'turnover.csv', 'latest.json'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regular_tree(root):
    for path in root.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError('Symlinks and special files are not accepted')


def verify_store(store):
    """Verify pointer and all retained versions, not quantitative semantics."""
    regular_tree(store)
    pointer = json.loads((store / 'current.json').read_text())
    version = pointer['version']
    if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
        raise ValueError('Invalid active version')
    active = store / 'versions' / version
    if digest(active / 'manifest.json') != pointer['manifest_sha256']:
        raise ValueError('Active manifest checksum mismatch')
    for directory in (store / 'versions').iterdir():
        if not directory.is_dir():
            raise ValueError('Unexpected versions entry')
        manifest = json.loads((directory / 'manifest.json').read_text())
        if (manifest['status'] != 'validated' or manifest['engine'] != 'MAIN'
                or manifest['version'] != directory.name or set(manifest['files']) != REQUIRED):
            raise ValueError('Invalid retained publication manifest')
        for name, expected in manifest['files'].items():
            if digest(directory / name) != expected:
                raise ValueError('Publication file checksum mismatch')
    return version


@contextmanager
def locked(store):
    # Never create or replace a store or its lock while preparing a backup.
    with (store / 'update.lock').open('r+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def backup(store, seed, receipt, output):
    store, seed, receipt, output = map(lambda p: Path(p).resolve(), (store, seed, receipt, output))
    if output.exists() or not output.parent.is_dir() or output.is_relative_to(store):
        raise ValueError('Backup requires a new archive outside the store in an existing directory')
    for path in (seed, receipt):
        if not path.is_file() or output.is_relative_to(path.parent):
            raise ValueError('Inputs must exist; keep backups outside input directories')
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.riskbex-backup-') as temporary:
        staging = Path(temporary)
        state = staging / 'state'
        (state / 'inputs').mkdir(parents=True)
        with locked(store):
            verify_store(store)
            target = state / 'store'
            target.mkdir()
            # Immutable committed versions + pointer + diagnostics. Exclude locks,
            # staging and orphan temporary files; never prune the source store.
            shutil.copytree(store / 'versions', target / 'versions')
            for name in ('current.json', 'status.json'):
                if (store / name).exists():
                    shutil.copy2(store / name, target / name)
            if (store / 'attempts').exists():
                shutil.copytree(store / 'attempts', target / 'attempts')
            shutil.copy2(seed, state / 'inputs/seed.csv')
            shutil.copy2(receipt, state / 'inputs/receipt.json')
            version = verify_store(target)
        regular_tree(state)
        inventory = {str(p.relative_to(staging)): digest(p) for p in sorted(state.rglob('*')) if p.is_file()}
        metadata = {'schema': 1, 'active_version': version,
                    'created_at': datetime.now(timezone.utc).isoformat(), 'files': inventory}
        (staging / 'backup.json').write_text(json.dumps(metadata, indent=2) + '\n')
        archive = staging / 'archive.tar.gz'
        with tarfile.open(archive, 'w:gz') as stream:
            stream.add(state, arcname='state')
            stream.add(staging / 'backup.json', arcname='backup.json')
        # Exclusive final creation prevents overwriting an existing backup.
        with output.open('xb') as dest, archive.open('rb') as source:
            shutil.copyfileobj(source, dest)
            dest.flush()
            os.fsync(dest.fileno())
    return {'archive': str(output), 'sha256': digest(output), 'active_version': version}


def restore(archive, destination, expected_sha256):
    archive, destination = Path(archive).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
        raise ValueError('Restore destination must be new, with an existing parent')
    if digest(archive) != expected_sha256:
        raise ValueError('Archive checksum mismatch')
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='.riskbex-restore-') as temporary:
        staging = Path(temporary)
        with tarfile.open(archive, 'r:gz') as stream:
            seen = set()
            for member in stream.getmembers():
                name = Path(member.name)
                if (name.is_absolute() or '..' in name.parts or member.name in seen
                        or not (member.isfile() or member.isdir())
                        or name.parts[0] not in {'state', 'backup.json'}):
                    raise ValueError('Unsafe archive member')
                seen.add(member.name)
                path = staging / name
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(member) as source, path.open('xb') as target:
                        shutil.copyfileobj(source, target)
        metadata = json.loads((staging / 'backup.json').read_text())
        state = staging / 'state'
        actual = {str(p.relative_to(staging)): digest(p) for p in state.rglob('*') if p.is_file()}
        if metadata['schema'] != 1 or actual != metadata['files']:
            raise ValueError('Backup inventory mismatch')
        for name in ('seed.csv', 'receipt.json'):
            if not (state / 'inputs' / name).is_file():
                raise ValueError('Backup lacks validated input')
        if verify_store(state / 'store') != metadata['active_version']:
            raise ValueError('Backup active version mismatch')
        # mkdir is exclusive; never overwrite an existing operational tree.
        destination.mkdir(mode=0o700)
        # A copy failure leaves this new destination for diagnosis; it never
        # removes or modifies an existing operational tree.
        shutil.copytree(state, destination, dirs_exist_ok=True)
        (destination / 'store/update.lock').touch(mode=0o600)
        verify_store(destination / 'store')
    return {'restored': str(destination), 'active_version': metadata['active_version']}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('backup')
    for name in ('store', 'seed', 'receipt', 'output'):
        create.add_argument('--' + name, required=True, type=Path)
    recover = commands.add_parser('restore')
    for name in ('archive', 'destination', 'sha256'):
        recover.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            result = backup(args.store, args.seed, args.receipt, args.output)
        else:
            result = restore(args.archive, args.destination, args.sha256)
        print(json.dumps(result))
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        parser.exit(1, f'Operation failed: {type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
