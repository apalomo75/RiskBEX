"""Immutable result versions, flock exclusion and atomic current-pointer publication."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
import pandas as pd


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class VersionStore:
    def __init__(self, root):
        self.root = Path(root)

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / 'update.lock').open('a+') as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Another MAIN update is running.') from exc
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def status(self, value):
        attempts = self.root / 'attempts'
        attempts.mkdir(exist_ok=True)
        write_json(attempts / f'{uuid.uuid4().hex}.json', value)
        sync_dir(attempts)
        temporary = self.root / f'.status-{uuid.uuid4().hex}.json'
        try:
            write_json(temporary, value)
            os.replace(temporary, self.root / 'status.json')
            sync_dir(self.root)
        finally:
            temporary.unlink(missing_ok=True)

    def verify(self, directory):
        directory = Path(directory)
        manifest = json.loads((directory / 'manifest.json').read_text())
        if manifest['status'] != 'validated' or manifest['engine'] != 'MAIN':
            raise ValueError('Result version is not validated MAIN.')
        required = {'prices.csv', 'features.csv', 'signals.csv', 'backtest.csv', 'metrics.csv',
                    'turnover.csv', 'latest.json'}
        if set(manifest['files']) != required:
            raise ValueError('Incomplete artifact inventory.')
        for name, expected in manifest['files'].items():
            if digest(directory / name) != expected:
                raise ValueError(f'Artifact integrity failure: {name}')
        latest = json.loads((directory / 'latest.json').read_text())
        if latest['last_valid_session'] != manifest['data_date'] or latest['package_id'] != manifest['package_id']:
            raise ValueError('Signal and manifest are inconsistent.')
        if latest['provenance']['manifest_sha256'] != manifest['model_manifest_sha256']:
            raise ValueError('Signal model provenance differs.')
        for name in ['prices', 'features', 'signals', 'backtest']:
            frame = pd.read_csv(directory / f'{name}.csv', float_precision='round_trip')
            if frame.empty or frame.date.duplicated().any() or not frame.date.is_monotonic_increasing:
                raise ValueError(f'Invalid artifact dates: {name}')
            if frame.date.iloc[-1] != manifest['data_date']:
                raise ValueError(f'Artifact end date differs: {name}')
        return manifest

    def current(self):
        pointer = self.root / 'current.json'
        if not pointer.exists():
            return None
        entry = json.loads(pointer.read_text())
        version = entry['version']
        if len(version) != 64 or any(c not in '0123456789abcdef' for c in version):
            raise ValueError('Invalid version pointer.')
        directory = self.root / 'versions' / version
        if digest(directory / 'manifest.json') != entry['manifest_sha256']:
            raise ValueError('Published manifest integrity failure.')
        manifest = self.verify(directory)
        if manifest['version'] != version:
            raise ValueError('Manifest version differs from pointer.')
        return directory

    def publish(self, frames, latest, manifest, version):
        versions = self.root / 'versions'
        versions.mkdir(exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=self.root))
        pointer = self.root / f'.pointer-{uuid.uuid4().hex}.json'
        try:
            for name, frame in frames.items():
                path = stage / f'{name}.csv'
                frame.to_csv(path, index=False, date_format='%Y-%m-%d')
                with path.open('rb') as stream:
                    os.fsync(stream.fileno())
            write_json(stage / 'latest.json', latest)
            manifest = dict(manifest, files={p.name: digest(p) for p in stage.iterdir()})
            write_json(stage / 'manifest.json', manifest)
            self.verify(stage)
            sync_dir(stage)
            final = versions / version
            if final.exists():
                # An orphan from an interrupted publication is never silently trusted/replaced.
                self.verify(final)
                existing = self.verify(final)
                for key in ['version', 'price_sha256', 'model_manifest_sha256', 'implementation_sha256', 'calendar_sha256']:
                    if existing[key] != manifest[key]:
                        raise ValueError('Existing orphan version differs; manual review required.')
            else:
                os.replace(stage, final)
                sync_dir(versions)
            write_json(pointer, {'version': version, 'manifest_sha256': digest(final / 'manifest.json')})
            os.replace(pointer, self.root / 'current.json')
            sync_dir(self.root)
            return final
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            pointer.unlink(missing_ok=True)
