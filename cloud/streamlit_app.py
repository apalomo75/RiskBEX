"""Streamlit Community Cloud entrypoint. No updater, inference or network backend."""
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from src.riskbex.cloud_snapshot import verify_bundle
import streamlit as st

bundle = Path(os.environ.get('RISKBEX_SNAPSHOT_DIR', ROOT / 'cloud/publication')).resolve()
expected_digest = os.getenv('RISKBEX_SNAPSHOT_SHA256')
if not expected_digest:
    try:
        expected_digest = st.secrets['RISKBEX_SNAPSHOT_SHA256']
    except (KeyError, FileNotFoundError):
        pass
try:
    verify_bundle(bundle, expected_digest)
except (OSError, ValueError, KeyError, TypeError) as exc:
    st.error('A complete verified publication snapshot is required. Contact the application operator.')
    st.stop()

os.environ.update(
    RISKBEX_PRESENTATION_MODE='snapshot',
    RISKBEX_OPERATIONAL_DIR=str(bundle / 'store'),
    RISKBEX_DATA_DIR=str(bundle / 'data'),
    RISKBEX_FIGURES_DIR=str(bundle / 'figures'),
    RISKBEX_PRESENTATION_PACKAGE_DIR=str(bundle / 'package'),
    RISKBEX_CALENDAR=str(ROOT / 'backend/config/bme-2026.json'),
)
runpy.run_path(str(ROOT / 'backend/dashboard.py'), run_name='__main__')
