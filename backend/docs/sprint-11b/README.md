# Sprint 11B — Validated Cloud release candidate

## Result and release boundary

The first real Cloud candidate was exported and tested locally in a clean Python
3.13 environment. It is **not deployed, staged, committed or pushed**. Public
release still requires an explicit decision to redistribute the bundled market
data and research, followed by authorization to publish. No market downloads,
inference, training, scheduler activation or Docker restarts were performed.
Existing Docker/VPS configuration, the updater and quantitative calculations were
preserved. Sprint 11A changes remain uncommitted alongside this sprint's work.

## Snapshot identity

| Property | Value |
| --- | --- |
| Candidate directory | `cloud/release-candidates/rc-20261116-7aa57e336352` |
| Publication | `7aa57e33635247917fa6b2e375fe2581eed428283e4509a39a00c201a0b46819` |
| Last market session | `2026-11-16` |
| Next target session | `2026-11-17` |
| Generated at | `2026-11-16T19:15:03.113219+00:00` |
| Source mode | `live`, from the existing published provenance |
| Bytes | `7,838,662` (7.839 MB / 7.476 MiB) |
| File count | `30` (29 payload files plus `snapshot.json`) |
| Largest file | `features.csv`, 1,878,656 bytes |
| SHA-256 of `snapshot.json` | `0d5b6d863ca2e342c24631a7b37cde7437eaa7513bd7afad8f6fa347f0b538bb` |

The configured source is `backend/runtime/main-wsl-test`, selected by `.env`'s
`RISKBEX_STORE`. VersionStore verified the active pointer and artifact hashes
before export. The existing exporter was invoked once:

```bash
python backend/scripts/export_cloud_snapshot.py \
  --store backend/runtime/main-wsl-test \
  --destination cloud/release-candidates/rc-20261116-7aa57e336352
```

The candidate passed verification after export and after the browsing tests. The
original source pointer retained SHA-256
`c72bd2c0e5e2f97fc78d509ae1607e2a9a6aba2c473d749744a0c847443cf578`.
Every copied publication artifact, research table and image matches its source
bytes. The candidate is frozen by version, exact inventory and the approved
manifest digest; application browsing writes no publication files. Re-exporting
to the same destination is refused. Do not edit candidate files or regenerate its
manifest to conceal a mismatch; export a new candidate instead.

## Included and excluded files

The full path/size/hash inventory is in [snapshot-review.json](snapshot-review.json)
and the candidate's own `snapshot.json`.

Included:

- `store/current.json` and one `store/versions/<version>/` directory containing
  the original publication manifest, prices, features, signals, backtest, metrics,
  turnover and latest signal.
- Twelve academic CSVs: regime dataset, model selection, summary, transitions,
  durations, MAIN/ROBUST adaptive backtests, backtest metrics, MAIN/ROBUST tail
  analysis, tail metrics and thresholds.
- Six original chapter-2 research PNGs, byte-identical to local archived figures.
- The original MAIN package manifest and its verified CVaR mapping JSON. No
  inference parameters or binary model files are required to browse the snapshot.

Published data coverage:

| Artifact | Rows | First date | Last date |
| --- | ---: | --- | --- |
| Prices | 6,836 | 2000-01-04 | 2026-11-16 |
| Features | 6,777 | 2000-03-28 | 2026-11-16 |
| MAIN signals | 1,503 | 2021-01-04 | 2026-11-16 |
| Realized backtest | 1,502 | 2021-01-05 | 2026-11-16 |
| Performance metrics | 7 | shared evaluation window | shared evaluation window |
| Turnover summaries | 3 | shared evaluation window | shared evaluation window |

Excluded: other versions, attempts, `status.json`, locks, seeds, regression receipt
files, logs, `.env`, Streamlit secrets, credentials, notebooks, model binaries and
unrelated processed data. Existing immutable manifests retain relative source
paths, implementation/component hashes, the prior version, download/generation
times and a receipt **hash** as provenance. Removing these would alter original
validated manifests. They contain no private host paths in the reviewed candidate.

## Public content review

The exact allowlist and file hashes passed. Text scans for private absolute paths,
private keys and common credential/token patterns found no matches. The JSON
manifests were reviewed for provenance versus operational logs. No symlinks or
binary model files are present; all files are below 2 MB. PNG decoding succeeded
for all six originals; embedded metadata contains Matplotlib software and DPI,
with no private paths. Pattern scanning is heuristic, not a guarantee about legal
rights or a substitute for the final publication review.

**Public release decision required:** the snapshot includes historical IBEX prices,
derived features, signals, strategy results and original research images. The
publication records Yahoo Finance as its live data source. Neither successful
hash checks nor public hosting establishes redistribution rights. The owner must
explicitly approve what may be redistributed before staging data for GitHub. No
redaction or missing record has been fabricated to bypass this decision.

The model manifest names and hashes already describe the frozen components; the
actual binaries are excluded from this export. This does not remove any model
artifacts already tracked elsewhere in the repository. The existing strategy,
training cutoff and methodology metadata remain visible by design.

## Clean Python 3.13 compatibility

An isolated venv was created under `/tmp/riskbex-11b-py313`, without system site
packages. Only `cloud/requirements.txt` and its resolved dependencies were
installed. This scoped installation was part of the requested clean-environment
smoke test; the operational environment was not modified.

```bash
python -m venv /tmp/riskbex-11b-py313
/tmp/riskbex-11b-py313/bin/python -m pip install -r cloud/requirements.txt
/tmp/riskbex-11b-py313/bin/python -m pip check
```

Python **3.13.5 on Linux x86_64** installed all eleven direct pins successfully.
Their installed versions and `Requires-Python` metadata accept Python 3.13.5.
`pip check` returned `No broken requirements found`. All real-data tests below
ran in that clean environment, which has no yfinance, XGBoost, statsmodels or
frozen inference runtime. The UI did not import those modules, engine orchestration
or provider services. See [python-compatibility.json](python-compatibility.json)
for direct metadata and all 54 installed distributions (including pip).

Python 3.13 compatibility is demonstrated for this read-only presentation stack.
The frozen operational engine retains its original Python 3.11.14 requirements;
no inference compatibility with Python 3.13 is claimed or needed. The Cloud file
pins direct dependencies; the recorded transitive resolution is evidence, not a
new enforced lock. A future changed transitive resolution may require a new
clean smoke test. No fallback Python version is currently necessary.

Community Cloud supports selecting Python in Advanced settings and searches for
a requirements file in the entrypoint directory first. References:
[deployment settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy),
[dependency selection](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).
The hosted build, memory limits and multiple simultaneous public users have not
been exercised; a local clean venv is not a hosted deployment.

## Real-data validation

Command used for the initial targeted suite:

```bash
PYTHONPATH=backend /tmp/riskbex-11b-py313/bin/python -m unittest discover \
  -s backend/tests -p test_cloud_release_candidate.py -v
```

All **six test methods** passed across focused runs, with only failed methods
repeated after correcting test assumptions. No historical 46-test suite was
repeated. Coverage:

1. Real snapshot seal, allowlist, source byte equality, 30-file inventory,
   credential/path scan, maximum file size, and all six PNG decodes.
2. Actual `cloud/streamlit_app.py`, all six views in both English and Spanish,
   real Welcome price/regime visualization and publication date, Performance
   table, Risk Monitor metrics/chart, research image, and preserved page/language
   state. The data loader resolves to the candidate's `data/`, not local originals.
3. Latest/history risk metrics and close agreement, MAIN regime/probability
   agreement, complete seven-row performance and three-row turnover summaries,
   matching publication identities and final backtest date. Existing comparison
   validation also verifies prior-close exposure alignment. Freshness is current
   at `2026-11-16T22:00Z` and stale at `2026-11-17T22:00Z`; both clocks are fixed
   in the test, not fabricated publication dates.
4. Exact numerical simulator equality between the original store and candidate
   for all four strategies × gross/net, plus actual UI form submission in both
   languages. Comparison normalizes only the intentionally excluded operational
   `publication.update_status`; every numerical value, series and other metadata
   field remains strictly equal.
5. Academic MAIN/ROBUST and tail-risk endpoints, regime research endpoints,
   nonempty historical tables and successful UI selection of all six images.
6. Working Cloud views while external network/API connections are forbidden;
   missing bundle and wrong approved checksum fail closed. Explicit local HTTP
   mode handles a missing Docker API with warnings and no application exception.

During browsing, IPv4/IPv6 socket connections and requests HTTP sessions were
blocked by test guards. No FastAPI listener or Docker service was required.
The initial new test assertions used the wrong Streamlit chart element name and
assumed fields not present in the existing latest-risk schema; these were aligned
with the established chart/schema contracts. The simulator comparison initially
included operational update diagnostics, which are deliberately absent from a
public snapshot. No product behavior or mathematical implementation was changed.
Streamlit emitted existing deprecation/widget warnings; these did not prevent
rendering or change financial results. `git diff --check` also passed.

## Exact publication procedure — future actions, not executed

Obtain approval for the data inventory above and for committing, pushing and
public deployment. These commands are instructions only. Run from the repository
root. They intentionally publish a reviewed copy to the default Cloud bundle path;
the original release candidate remains unchanged and ignored.

1. Review the Sprint 11A/11B working diff. Create the release branch only after
   authorization:

   ```bash
   git switch -c release/streamlit-rc1
   ```

2. Copy the reviewed candidate to a **new** `cloud/publication` directory and verify
   it. `copytree` refuses an existing destination; do not silently overwrite one:

   ```bash
   python - <<'PY'
   from pathlib import Path
   import shutil
   import sys
   sys.path.insert(0, 'backend')
   from src.riskbex.cloud_snapshot import verify_bundle
   expected = '0d5b6d863ca2e342c24631a7b37cde7437eaa7513bd7afad8f6fa347f0b538bb'
   source = Path('cloud/release-candidates/rc-20261116-7aa57e336352')
   verify_bundle(source, expected)
   shutil.copytree(source, 'cloud/publication')
   verify_bundle('cloud/publication', expected)
   PY
   ```

3. Preview locally with the approved digest, then inspect all six views in both
   languages. This is not deployment:

   ```bash
   RISKBEX_SNAPSHOT_SHA256=0d5b6d863ca2e342c24631a7b37cde7437eaa7513bd7afad8f6fa347f0b538bb \
     /tmp/riskbex-11b-py313/bin/streamlit run cloud/streamlit_app.py
   ```

4. Stage the explicit reviewed implementation/documentation paths, then only the
   reviewed public copy. Do **not** use `git add .`, stage `.env` or stage runtime:

   ```bash
   git add -- .gitignore cloud/streamlit_app.py cloud/requirements.txt \
     backend/dashboard.py backend/src/riskbex/api/decisions.py \
     backend/src/riskbex/simulator_ui.py backend/src/riskbex/translations_es.json \
     backend/src/riskbex/dashboard_transport.py backend/src/riskbex/cloud_snapshot.py \
     backend/scripts/export_cloud_snapshot.py backend/tests/test_cloud_deployment.py \
     backend/tests/test_cloud_release_candidate.py backend/docs/sprint-11a.md \
     backend/docs/sprint-11b
   git add -f -- cloud/publication
   git diff --cached --check
   git diff --cached --stat
   git diff --cached --name-only
   ```

   The root `.streamlit/config.toml` is already tracked and unchanged. Confirm
   exactly 30 files under `cloud/publication`, no release-candidate directory,
   `.env`, `secrets.toml`, attempts, runtime folders or model binary additions.
   The checksum evidence is public; it is not a credential. Do not stage secret
   files even when their only current value is a checksum.

5. After approving the concrete staged inventory, commit and push explicitly:

   ```bash
   git commit -m "Prepare RISKBEX validated Streamlit Cloud release candidate"
   git push -u origin release/streamlit-rc1
   ```

6. In Streamlit Community Cloud select Create app / existing GitHub app, then:

   | Setting | Exact value |
   | --- | --- |
   | Repository | `apalomo75/RiskBEX` |
   | Branch | `release/streamlit-rc1` |
   | Main file | `cloud/streamlit_app.py` |
   | Python | `3.13` in Advanced settings |
   | Dependencies | automatically discovered `cloud/requirements.txt` |
   | Theme/config | tracked root `.streamlit/config.toml` |
   | API URL | no external API configuration required |
   | Visibility | public only after the explicit data release decision |

   In Advanced settings / Secrets configure the root TOML value below; do not
   commit `secrets.toml`:

   ```toml
   RISKBEX_SNAPSHOT_SHA256 = "0d5b6d863ca2e342c24631a7b37cde7437eaa7513bd7afad8f6fa347f0b538bb"
   ```

   Leave `RISKBEX_SNAPSHOT_DIR` unset so the entrypoint uses the reviewed
   `cloud/publication` copy. Do not set snapshot mode for local Docker. Save
   settings and deploy **only after deployment authorization**. The subdomain
   must be selected from names actually available at that time; none is reserved.

7. Record the actual HTTPS `*.streamlit.app` URL assigned by Cloud. Check the
   hosted build/runtime logs, open the URL in a signed-out browser, then verify:
   Welcome chart and `16 / 11 / 2026`, Overview, Performance, simulator submission,
   Risk Monitor, all research images, both languages, navigation and source
   information. Freshness must reflect the actual date of deployment: do not
   expect the static 16 November snapshot to remain current. Confirm scheduler
   status says not enabled, no API connectivity warnings, correct version and no
   secret/private path exposure in user-facing output. Check health with
   `curl --fail https://<actual-host>/_stcore/health`, but do not treat health alone
   as proof that the six data views work. Review resource use under a small
   authorized public smoke test. Record the URL only once it really exists.

## Remaining blockers and limitations

- Explicit public redistribution and publication authorization are outstanding.
- The actual hosted install/build/URL and resource/concurrent-user validation are
  intentionally pending. No local FastAPI service is needed for those checks.
- Calendar coverage is 2026 only. Before 2027 supply a reviewed calendar through
  the existing configuration; do not rewrite the frozen publication's provenance.
- The release is a static publication. The source mode describes its origin,
  not an active Cloud scheduler. Autonomous updates remain a separate sprint.
- The candidate and the default publication path are ignored deliberately; the
  instructions above require explicit, reviewed staging of the intended copy.

Sprint 11B added the candidate ignore rule, the real-candidate test module and
this documentation/evidence directory. The exporter and application required no
changes. No quantitative artifact or operational runtime file was modified.
