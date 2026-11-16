"""Explicit immutable export of public presentation assets; never modifies a store."""
import json
from pathlib import Path
import shutil
import tempfile

from src.riskbex.pipeline.store import VersionStore, digest

RESEARCH = (
    'regime_dataset.csv', 'model_selection.csv', 'regime_summary.csv',
    'transition_matrix.csv', 'duration_summary.csv',
    'adaptive_backtest_main.csv', 'adaptive_backtest_robust.csv',
    'adaptive_backtest_metrics.csv', 'tail_analysis_main.csv',
    'tail_analysis_robust.csv', 'tail_metrics.csv', 'tail_thresholds.csv',
)
FIGURES = ('daily_returns_ibex35.png', 'volatility_vs_downside_60d.png',
           'var_cvar_60d.png', 'drawdown_ibex35.png', 'skew_60d_series.png',
           'ret_risk_60d_series.png')


def verify_bundle(root, expected_sha256=None):
    root = Path(root).resolve()
    seal = root / 'snapshot.json'
    if expected_sha256 and digest(seal) != expected_sha256:
        raise ValueError('Snapshot identity differs from the approved digest.')
    inventory = json.loads(seal.read_text())
    if inventory['format'] != 1:
        raise ValueError('Unsupported snapshot format.')
    for name, expected in inventory['files'].items():
        path = (root / name).resolve()
        if root not in path.parents or not path.is_file() or digest(path) != expected:
            raise ValueError(f'Snapshot integrity failure: {name}')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(inventory['files']) | {'snapshot.json'}:
        raise ValueError('Unexpected or missing snapshot files.')
    version = VersionStore(root / 'store').current()
    if version is None or version.name != inventory['version']:
        raise ValueError('Snapshot publication version differs.')
    required = {f'data/processed/{name}' for name in RESEARCH}
    required |= {f'figures/chapter2/{name}' for name in FIGURES}
    if not required.issubset(inventory['files']):
        raise ValueError('Incomplete research assets.')
    manifest = json.loads((version / 'manifest.json').read_text())
    package_root = root / 'package'
    package = json.loads((package_root / 'manifest.json').read_text())
    mapping = package['components']['cvar_mapping']
    mapping_path = (package_root / mapping).resolve()
    if (package_root not in mapping_path.parents
            or digest(package_root / 'manifest.json') != manifest['model_manifest_sha256']
            or digest(mapping_path) != manifest['model_hashes'][mapping]
            or digest(mapping_path) != package['files'][mapping]['sha256']):
        raise ValueError('Snapshot mapping provenance differs.')
    allowed = required | {'store/current.json', 'package/manifest.json', f'package/{mapping}'}
    allowed |= {f'store/versions/{version.name}/{name}' for name in ['manifest.json', *manifest['files']]}
    if set(inventory['files']) != allowed:
        raise ValueError('Snapshot inventory differs from the public allowlist.')
    return inventory


def export_bundle(store_root, destination, backend):
    """Call only after approval. Copy exact bytes from one verified version."""
    store_root, destination, backend = map(lambda p: Path(p).resolve(),
                                           (store_root, destination, backend))
    if destination.exists() or store_root == destination or store_root in destination.parents:
        raise ValueError('Destination must be new and outside the operational store.')
    source = VersionStore(store_root).current()
    if source is None:
        raise ValueError('No validated publication to export.')
    manifest = json.loads((source / 'manifest.json').read_text())
    package = backend / 'model_packages/main-v1'
    package_manifest = json.loads((package / 'manifest.json').read_text())
    mapping = package_manifest['components']['cvar_mapping']
    mapping_path = (package / mapping).resolve()
    if package.resolve() not in mapping_path.parents:
        raise ValueError('Invalid mapping path.')
    if (digest(package / 'manifest.json') != manifest['model_manifest_sha256']
            or digest(mapping_path) != manifest['model_hashes'][mapping]
            or digest(mapping_path) != package_manifest['files'][mapping]['sha256']):
        raise ValueError('Published mapping provenance differs.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=destination.parent) as temp:
        stage = Path(temp) / 'bundle'
        target = stage / 'store/versions' / source.name
        target.mkdir(parents=True)
        for name in ['manifest.json', *manifest['files']]:
            shutil.copyfile(source / name, target / name)
        # Pin the resolved version even if the live pointer advances during export.
        (stage / 'store/current.json').write_text(json.dumps({
            'version': source.name, 'manifest_sha256': digest(target / 'manifest.json')}))
        assets = [(backend / 'data/processed' / n, stage / 'data/processed' / n) for n in RESEARCH]
        assets += [(backend / 'figures/chapter2' / n, stage / 'figures/chapter2' / n) for n in FIGURES]
        assets += [(package / 'manifest.json', stage / 'package/manifest.json'),
                   (mapping_path, stage / 'package' / mapping)]
        for src, dst in assets:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        inventory = {'format': 1, 'version': source.name,
                     'files': {p.relative_to(stage).as_posix(): digest(p)
                               for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage / 'snapshot.json').write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
        verify_bundle(stage)
        stage.rename(destination)
    return digest(destination / 'snapshot.json')
