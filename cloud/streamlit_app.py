"""Streamlit Community Cloud entrypoint. No updater, inference or network backend."""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from src.riskbex.cloud_snapshot import verify_bundle, verify_approved_bundle
import streamlit as st

bundle = Path(os.environ.get('RISKBEX_SNAPSHOT_DIR', ROOT / 'cloud/publication')).resolve()
expected_digest = os.getenv('RISKBEX_SNAPSHOT_SHA256')
approval_path = ROOT / 'cloud/approval.json'
approved_date = None
try:
    legacy_secret = st.secrets['RISKBEX_SNAPSHOT_SHA256']
except (KeyError, FileNotFoundError):
    legacy_secret = None
try:
    if bundle == (ROOT / 'cloud/publication').resolve():
        # Default bundle always needs its independent Git approval. Streamlit
        # also exports root-level secrets into os.environ: that legacy value
        # must not accidentally become a permanent operator pin.
        approval = verify_approved_bundle(bundle, approval_path)
        approved_date = approval['data_date']
        previous_date = st.session_state.get('_riskbex_snapshot_data_date')
        if previous_date and approved_date < previous_date:
            raise ValueError('Publication regressed within this visitor session.')
        if expected_digest and expected_digest != legacy_secret and expected_digest != approval['snapshot_sha256']:
            raise ValueError('Explicit environment pin differs from approval.')
        expected_digest = approval['snapshot_sha256']
    else:
        expected_digest = expected_digest or legacy_secret
    if not expected_digest:
        raise ValueError('An approved snapshot identity is required.')
    inventory = verify_bundle(bundle, expected_digest)
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error('A complete verified publication snapshot is required. Contact the application operator.')
    st.stop()

if approved_date:
    st.session_state['_riskbex_snapshot_data_date'] = approved_date
if st.session_state.get('_riskbex_snapshot_version') != inventory['version']:
    st.cache_data.clear()
    st.session_state['_riskbex_snapshot_version'] = inventory['version']

os.environ.update(
    RISKBEX_PRESENTATION_MODE='snapshot',
    RISKBEX_OPERATIONAL_DIR=str(bundle / 'store'),
    RISKBEX_DATA_DIR=str(bundle / 'data'),
    RISKBEX_FIGURES_DIR=str(bundle / 'figures'),
    RISKBEX_PRESENTATION_PACKAGE_DIR=str(bundle / 'package'),
    RISKBEX_CALENDAR=str(ROOT / 'backend/config/bme-2026.json'),
)
runpy.run_path(str(ROOT / 'backend/dashboard.py'), run_name='__main__')
