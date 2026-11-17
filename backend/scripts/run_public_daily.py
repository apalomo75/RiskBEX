"""Single public-repository daily path; explicit switches required before retrieval."""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_actions_live_dry_run import run
from src.riskbex.actions_update import approved_bundle, promote, verify_predecessor
from src.riskbex.pipeline.provider import YahooProvider
from src.riskbex.publication_control import verify_rights


def execute(root, work, head, *, now, provider=None):
    if (os.getenv('GITHUB_REPOSITORY') != 'apalomo75/RiskBEX'
            or os.getenv('GITHUB_REF') != 'refs/heads/main'
            or any(os.getenv(key) != 'true' for key in
                   ['RISKBEX_PUBLICATION_ENABLED', 'RISKBEX_LIVE_DOWNLOAD_AUTHORIZED'])):
        raise ValueError('Public daily activation is disabled.')
    verify_predecessor(root, head)
    verify_rights(root)
    summary = {}
    run(root, work, provider=provider if provider is not None else YahooProvider(),
        now=now, public_summary=summary)
    if summary['update'] == 'skipped':
        return dict(summary, publication='unchanged')
    publication = promote(root, work, head, require_live=True)
    approval = approved_bundle(root)
    # Confirm the remote still points at the exact normal commit just pushed.
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    committed = git('rev-parse', 'HEAD')
    remote = git('ls-remote', '--exit-code', 'origin', 'refs/heads/release/streamlit-rc1')
    if remote.split()[0] != committed:
        raise ValueError('Remote publication confirmation differs; inspect before retry.')
    return dict(summary, publication=publication, published_head=committed,
                published_version=approval['version'], published_session=approval['data_date'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--head', required=True)
    args = parser.parse_args(argv)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = execute(args.root, args.work, args.head, now=pd.Timestamp.now(tz='UTC'))
    except Exception:
        print(json.dumps(dict(run_status='failed', publication='inspect_release_before_retry')))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
