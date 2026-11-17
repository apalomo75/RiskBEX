"""Fail-closed distribution rights and frozen candidate provenance checks."""
from datetime import date
import json
from pathlib import Path

import pandas as pd

from src.riskbex.engine.package import load_main_package, canonical_price_hash
from src.riskbex.engine.service import prepare_price_history
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.service import verify_gate, pipeline_hashes
from src.riskbex.pipeline.store import VersionStore, digest

SCOPES = {'raw_history', 'returns', 'reconstructible_charts', 'derived_signals', 'research_assets',
          'public_git_redistribution', 'automated_retrieval'}


def verify_rights(root, *, today=None):
    root = Path(root)
    rights = json.loads((root / 'backend/config/publication-rights.json').read_text())
    today = today or date.today()
    if (rights.get('status') not in {'verified', 'owner_authorized'} or rights.get('provider') != 'Yahoo Finance / IBEX 35'
            or set(rights.get('scopes', [])) != SCOPES
            or date.fromisoformat(rights['valid_until']) < today
            or not rights.get('reviewed_by') or not rights.get('licence_reference')):
        raise ValueError('Public distribution rights unresolved or expired.')
    if rights['status'] == 'owner_authorized':
        if (rights.get('authorized_by') != 'apalomo75'
                or rights.get('repository') != 'apalomo75/RiskBEX'
                or not rights.get('permission_basis')
                or date.fromisoformat(rights['authorized_on']) > today):
            raise ValueError('Owner authorization is incomplete or not applicable.')
    evidence = root / 'backend/config/publication-rights-evidence.txt'
    if digest(evidence) != rights.get('evidence_sha256'):
        raise ValueError('Distribution rights evidence differs.')
    return rights


def verify_provenance(root, work, old, *, require_live=False, now=None):
    root, work = Path(root), Path(work)
    package = load_main_package(root / 'backend/model_packages/main-v1')
    receipt = root / 'backend/config/actions-regression.json'
    verify_gate(receipt, package)
    current = VersionStore(work / 'candidate/store').current()
    manifest = json.loads((current / 'manifest.json').read_text())
    latest = json.loads((current / 'latest.json').read_text())
    calendar = SessionCalendar.load(root / 'backend/config/bme-2026.json')
    prices = pd.read_csv(current / 'prices.csv', float_precision='round_trip')
    prepare_price_history(package, prices)
    expected = dict(model_hashes={k: v['sha256'] for k, v in package.manifest['files'].items()},
                    model_manifest_sha256=package.manifest_sha256,
                    implementation_sha256=pipeline_hashes(), calendar_sha256=calendar.digest,
                    regression_receipt_sha256=digest(receipt), price_sha256=canonical_price_hash(prices),
                    previous_version=old['version'], engine='MAIN', status='validated')
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError('Candidate frozen provenance differs.')
    sessions = calendar.sessions(old['data_date'], manifest['data_date'])
    count = sum(sessions > pd.Timestamp(old['data_date']))
    if manifest['new_sessions'] != count or count < 1:
        raise ValueError('Candidate session count differs.')
    if manifest['target_session_date'] != str(calendar.next_session(manifest['data_date']).date()):
        raise ValueError('Candidate target session differs.')
    if require_live and (manifest.get('source') != 'yahoo-finance:^IBEX:1d:auto_adjust=True'
                         or latest['provenance'].get('source_mode') != 'live'
                         or latest['provenance'].get('live_market_freshness_verified') is not True):
        raise ValueError('Live candidate provenance required.')
    if require_live and manifest['data_date'] != str(calendar.eligible(now if now is not None else pd.Timestamp.now(tz='UTC')).date()):
        raise ValueError('Candidate became stale while awaiting publication approval.')
    old_current = VersionStore(root / 'cloud/publication/store').current()
    old_prices = pd.read_csv(old_current / 'prices.csv', float_precision='round_trip')
    prefix = prices.loc[prices.date <= old['data_date']]
    if canonical_price_hash(prefix) != canonical_price_hash(old_prices):
        raise ValueError('Approved price history changed.')
    return manifest
