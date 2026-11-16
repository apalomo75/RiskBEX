"""Ephemeral runner adapter. Reuses MAIN; never edits a source store or trains."""
import json
from pathlib import Path
import shutil
import subprocess

import pandas as pd

from src.riskbex.cloud_snapshot import export_bundle, verify_bundle, verify_approved_bundle
from src.riskbex.engine.package import load_main_package
from src.riskbex.engine.service import prepare_price_history
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.service import update_main, verify_gate
from src.riskbex.pipeline.store import VersionStore, digest, write_json

BRANCH = 'release/streamlit-rc1'


def approved_bundle(root):
    """Trust anchor is the reviewed Git checkout, independently of snapshot payload."""
    root = Path(root)
    return verify_approved_bundle(root / 'cloud/publication', root / 'cloud/approval.json')


def bootstrap(root, work):
    root, work = Path(root).resolve(), Path(work).resolve()
    # copytree/new-directory semantics protect both caller state and original store.
    if work.exists() or root == work or root in work.parents:
        raise ValueError('Workspace must be new and outside the checkout.')
    approved_bundle(root)
    package = load_main_package(root / 'backend/model_packages/main-v1')
    receipt = root / 'backend/config/actions-regression.json'
    verify_gate(receipt, package)
    bundle = root / 'cloud/publication'
    current = VersionStore(bundle / 'store').current()
    prices = pd.read_csv(current / 'prices.csv', float_precision='round_trip')
    prepare_price_history(package, prices)
    work.mkdir(parents=True)
    shutil.copytree(bundle / 'store', work / 'store')
    # Exporter expects the original layout. Restore approved research bytes only.
    assets = work / 'assets'
    shutil.copytree(bundle / 'data', assets / 'data')
    shutil.copytree(bundle / 'figures', assets / 'figures')
    shutil.copytree(root / 'backend/model_packages/main-v1', assets / 'model_packages/main-v1')
    shutil.copyfile(current / 'prices.csv', work / 'seed.csv')
    return package, receipt


def candidate(root, work, *, now, provider=None):
    root, work = Path(root), Path(work)
    package, receipt = bootstrap(root, work)
    store = VersionStore(work / 'store')
    calendar = SessionCalendar.load(root / 'backend/config/bme-2026.json')
    current = store.current()
    manifest = json.loads((current / 'manifest.json').read_text())
    eligible = calendar.eligible(now)
    calendar.next_session(eligible)  # fail closed before network on expiry
    last = pd.Timestamp(manifest['data_date'])
    if last > eligible:
        raise ValueError('Current publication is newer than eligible session.')
    if last == eligible:
        return {'status': 'unchanged', 'data_date': manifest['data_date'], 'version': current.name}
    if provider is None:
        raise ValueError('Missing explicit provider consent.')
    result = update_main(package, pd.read_csv(work / 'seed.csv', float_precision='round_trip'),
                         provider, calendar, store, now=now, regression_receipt=receipt)
    seal = export_bundle(work / 'store', work / 'candidate', work / 'assets')
    write_json(work / 'approval.json', dict(format=1, snapshot_sha256=seal,
               version=result['version'], data_date=result['data_date']))
    return result


def promote(root, work, expected_head):
    """Explicit future publishing operation, never invoked by the offline workflow.

    One Git commit contains the complete payload and trust anchor. Normal push is
    compare-and-swap: an intervening remote commit rejects it; never rebase/force.
    Call in a disposable clean release checkout with contents:write only.
    """
    root, work = Path(root).resolve(), Path(work).resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    if git('branch', '--show-current') != BRANCH or git('rev-parse', 'HEAD') != expected_head:
        raise ValueError('Unexpected publication branch/head.')
    if git('status', '--porcelain'):
        raise ValueError('Publication checkout must be clean.')
    old = approved_bundle(root)
    new = json.loads((work / 'approval.json').read_text())
    inventory = verify_bundle(work / 'candidate', new['snapshot_sha256'])
    if inventory['version'] != new['version']:
        raise ValueError('Candidate approval version differs.')
    path = VersionStore(work / 'candidate/store').current()
    manifest = json.loads((path / 'manifest.json').read_text())
    if manifest['data_date'] != new['data_date']:
        raise ValueError('Candidate approval date differs.')
    if new['data_date'] <= old['data_date']:
        if new == old:
            return 'unchanged'
        raise ValueError('Non-advancing publication rejected.')
    if manifest['previous_version'] != old['version']:
        raise ValueError('Candidate does not extend current publication.')
    # Local failures leave remote unchanged. Discard failed disposable checkout.
    shutil.rmtree(root / 'cloud/publication')
    shutil.copytree(work / 'candidate', root / 'cloud/publication')
    shutil.copyfile(work / 'approval.json', root / 'cloud/approval.json')
    approved_bundle(root)
    git('add', '-f', '--', 'cloud/publication', 'cloud/approval.json')
    git('commit', '-m', 'Publish validated MAIN session ' + new['data_date'])
    git('push', 'origin', 'HEAD:refs/heads/' + BRANCH)
    return 'published'
