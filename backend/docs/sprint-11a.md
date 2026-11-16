# Sprint 11A — Streamlit Community Cloud preparation

## Architecture and scope

Use **A: the existing FastAPI response contracts through an in-process read-only
ASGI adapter**. Streamlit calls existing GET routes using HTTPX ASGITransport;
there is no listening API server, Docker Compose, external API dependency, market
provider or model inference. FastAPI still applies its response schemas and error
codes. The Investment Simulator invokes the existing endpoint and the same
`simulate_investment` implementation. No independent quantitative engine was added.

Alternative B (reading CSVs directly in the UI) saves FastAPI/HTTPX dependencies
but duplicates schema conversions, provenance, freshness, strategy and simulation
validation. It is a larger and less safe change. HTTPX is the sole new direct
production dependency; it was already available for the existing API tests.

`backend/dashboard.py` remains the main six-view bilingual application. Its
transport defaults to ordinary HTTP, preserving Docker and VPS configuration.
Only `cloud/streamlit_app.py` selects snapshot mode. Missing/corrupt bundles stop
with an explicit error. Direct API mode still handles an unavailable API through
the existing UI warnings. Browsing cannot start an updater; the adapter only
issues GET requests and `/run-update` remains disabled.

## Inspected inputs and blockers

The configured local store is `backend/runtime/main-wsl-test` (not the default
`backend/runtime/main`). Its selected version passed VersionStore verification:
`7aa57e33635247917fa6b2e375fe2581eed428283e4509a39a00c201a0b46819`.
No real snapshot has been exported. The store must remain ignored and unchanged.
The local data/figures are ignored too, so a Git checkout alone is insufficient.

Required file sizes inspected: publication 3,276,588 bytes; research tables
2,843,651 bytes; six figures 1,708,660 bytes. Total about 7.8 MB, plus small
package metadata. This is reasonable for a reviewed, static Git snapshot. It is
not a reason to version the entire runtime or daily changes in main. Confirm
redistribution rights for historical market data and research images before
public release; integrity verification does not establish those rights.

The exchange calendar covers **2026 only**. Beyond its coverage the existing API
fails closed; it must receive a reviewed calendar before expiry. The frozen
publication's embedded calendar and provenance must never be rewritten.

Cloud's working directory is the repository root. The entrypoint inserts the
absolute backend import path and sets absolute bundle paths before loading the
dashboard/API. No model package loading is needed: only the original model
manifest and its verified CVaR mapping JSON are bundled, without model binaries.
Research endpoints read existing historical MAIN/ROBUST CSVs; ROBUST remains an
academic reference. All six existing chapter-2 figures are required.

Cloud dependency pins reflect the installed runtime used for offline tests,
including Streamlit 1.56.0, FastAPI 0.136.1 and HTTPX 0.28.1. Python 3.13 is the
recommended Cloud presentation interpreter; frozen quantitative Docker remains on 3.11. This environment's test interpreter is Python
3.13.5; a clean dependency installation was **not** performed (dependency
installation was not authorized). The separate existing Python 3.11 quantitative
environment lacks FastAPI/pytest. Therefore clean Cloud dependency resolution and hosted
smoke validation remain release gates. Docker locks and images are unchanged.
No yfinance, XGBoost, statsmodels, notebooks or training dependencies are needed
for presentation. Transitive dependencies are resolved by pip; this is a pinned
direct-dependency manifest, not a complete transitive lock.

Streamlit documents approximate resources of 690 MB–2.7 GB memory and up to 2 CPU
cores, subject to change. No Cloud memory/concurrency benchmark was performed.
Local Cloud storage must be treated as disposable: it is neither the authoritative
publication store nor the updater's persistence layer. Matplotlib and Streamlit
may use temporary caches; publication data is read-only by application behavior.

## Reproducible snapshot procedure — approval required before execution

The following is a **procedure only**, not executed in Sprint 11A:

```bash
python backend/scripts/export_cloud_snapshot.py \
  --store backend/runtime/main-wsl-test \
  --destination cloud/publication
```

The destination must be new and outside the operational store. The exporter:

1. Resolves and verifies `current.json` once, including the original manifest and
   every published artifact hash, dates and model provenance.
2. Copies exact bytes of `manifest.json`, `prices.csv`, `features.csv`,
   `signals.csv`, `backtest.csv`, `metrics.csv`, `turnover.csv`, `latest.json` into
   `store/versions/<version>/`, with a pointer pinned to that version even if the
   operational pointer advances during export.
3. Copies only the 12 historical CSVs enumerated by `RESEARCH` in
   `cloud_snapshot.py`, six explicitly named chapter-2 PNGs, the model manifest
   and its CVaR mapping. No pickle, model binary, secret, status file, update lock,
   attempt log, receipt or seed is included. Historical research files are copied
   unchanged; their export hashes preserve byte identity, not a new TFM audit.
4. Checks mapping hashes against the original package and publication manifests,
   writes `snapshot.json` with version and complete file hashes, verifies the
   destination, then promotes the staged directory. It never replaces an existing
   destination and never writes to the operational store.
5. Prints the snapshot manifest SHA-256. Record this as the approved identity.

Before release, review the inventory, provenance and data availability, and run
all six views against the exported bundle in a fresh process. Set
`RISKBEX_SNAPSHOT_SHA256` to the approved digest. Bundle startup verifies that seal
when configured, all file hashes, exact public allowlist, publication pointer and
mapping provenance. Hashes detect corruption; the externally reviewed digest
anchors identity. They are not signatures.

`cloud/publication/` remains ignored. Publishing these data requires explicit
approval and deliberate staging after inventory review; no runtime folder should
be force-added. A reviewed snapshot can be included in a deployment branch while
leaving main free of data churn. GitHub repository checkout may still contain
already tracked frozen model files; this sprint neither removes nor changes them.
The exporter exposes no additional model binaries.

External object storage is preferable if redistribution restrictions, growing
history or frequent updates make a Git snapshot unsuitable. That alternative
needs a separately authorized bounded HTTPS downloader, digest-pinned manifest,
atomic local cache and prior-valid fallback. **That remote loader is not
implemented in this sprint.** Private storage credentials belong in Cloud secrets,
never the snapshot or repository. GitHub Actions artifacts are not a durable
public data-serving origin.

## Exact deployment settings — do not deploy during this sprint

| Setting | Value |
| --- | --- |
| Repository | `apalomo75/RiskBEX` |
| Branch | `main` after an explicitly approved code/snapshot publication; alternatively the reviewed deployment branch |
| Main file path | `cloud/streamlit_app.py` |
| Python | `3.13`, selected in Advanced settings |
| Dependency file | `cloud/requirements.txt` (entrypoint directory is searched first) |
| Streamlit config | existing root `.streamlit/config.toml`, unchanged dark theme |
| Secrets | `RISKBEX_SNAPSHOT_SHA256 = "<approved snapshot.json SHA-256>"` |
| Snapshot location | default `cloud/publication`; optional environment `RISKBEX_SNAPSHOT_DIR` |
| API URL | none required; `http://api:8000` is never contacted in snapshot mode |
| App visibility | public, after approval of data and source exposure |
| Custom subdomain | select an available name at deployment; not reserved by this sprint |

Local preview after export approval: `streamlit run cloud/streamlit_app.py` from
the repository root, with the digest environment variable set. Docker continues
to run `backend/dashboard.py` with `RISKBEX_API_URL=http://api:8000`.

Freshness is recomputed from the reviewed session calendar on API reads; existing
30-second UI caches retain their behavior. Historical/simulated provenance can
never become current merely because the file was recently copied. Snapshot mode
explicitly reports that scheduling is not enabled. The snapshot omits operational
status logs; publication generation time remains visible separately. Expired
calendar coverage returns unavailable rather than a fabricated freshness state.

## Separate daily-update design — not activated

Use an independent GitHub-hosted Linux runner and external versioned object
storage, not Streamlit's filesystem. The frozen pipeline already has provider
validation, regression gates, immutable versions, locking and atomic promotion.
Reuse `backend/scripts/run_scheduled_update.py --fetch`, the reviewed seed,
regression receipt and MAIN package. The UI environment and the quantitative
runner have separate dependency manifests; do not install the Cloud UI manifest
as a substitute for the frozen MAIN runtime.

Proposed sequence:

1. Schedule retries at 20:17, 21:17 and 22:17 Europe/Madrid. Current GitHub docs
   support an IANA `timezone: Europe/Madrid` schedule; alternatively use UTC
   triggers plus a ZoneInfo local-time gate. The existing calendar's 20:00
   eligibility policy, holidays and CET/CEST decide the target, not the cron alone.
   Use explicit manual recovery too. No exact-minute execution is guaranteed;
   scheduled events can be delayed/dropped and inactive public repositories can
   lose scheduled execution after 60 days.
2. Retrieve the last validated version, canonical seed and compatible regression
   receipt from durable storage. Authenticate with narrowly scoped OIDC/storage
   permissions. Set job concurrency to a single publisher with
   `cancel-in-progress: false`; retain the store's own update lock. Consider
   manual/external publishers: storage pointer promotion also needs compare-and-swap.
3. Download Yahoo data only in the authorized runner; invoke existing frozen
   MAIN inference and validation. Do not train, backfill synthetic rows, silently
   accept revisions or rebuild historical research. Missing prerequisites fail.
4. Verify VersionStore, performance and decision contracts; export the same
   allowlisted snapshot. Upload objects under immutable version/digest keys;
   verify uploaded sizes/hashes before conditionally promoting a small current
   manifest. Preserve the prior pointer on any failure and retain prior snapshots
   under an explicit storage lifecycle policy. Record scheduler health separately.
5. A future Cloud remote loader polls the pointer with a bounded TTL, downloads a
   complete candidate to staging, verifies provenance and hashes, then swaps its
   cached snapshot. Existing readers finish on their selected version; invalidate
   UI caches by publication identity. On failure retain and label the previous
   valid publication with accurate freshness. Never combine files across versions.

GitHub-hosted jobs have a documented six-hour maximum. The existing orchestration
uses a 30-minute child timeout, so the design is plausibly compatible, but timeout
configuration is not a runtime benchmark. No authorized fresh download/inference
or runner execution was performed, so wall time, peak RAM, Yahoo accessibility,
receipt portability and account minutes/storage quota remain unproven. Measure a
single explicitly authorized workflow_dispatch run before enabling schedules.
Do not push daily data to main: it causes repository growth, Cloud rebuilds,
review noise and risks to source permissions. External atomic snapshots separate
code releases from publication updates.

## Validation and remaining release gates

Focused test results are recorded in the Sprint 11A delivery. Tests cover the
six views in both languages using the verified local publication, offline ASGI
contracts, simulator equality, missing store, missing Cloud bundle, corruption,
path traversal, approved identity and a synthetic-only exporter round trip.
Existing simulator and language suites are run separately. No real data export,
market download, training, installation, Docker restart, workflow activation,
commit, push or deployment is part of this sprint.

Before publication: approve export/data distribution; create and review the real
bundle; exercise the actual Cloud entrypoint against it in a clean Python 3.13
process; confirm dependency installation and memory on Cloud; review/stage code
and snapshot deliberately; obtain publication authorization. Autonomous updates
remain a later sprint. Extend calendar coverage before 2027.

## Official references consulted

- [Cloud file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
- [Cloud dependencies and search precedence](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Deployment and Python selection](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Resource limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- [GitHub scheduling and timezones](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [Scheduled execution delays](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)
- [Inactive scheduled workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)
- [Actions job limits](https://docs.github.com/en/actions/reference/limits)

### Executed checks

- Nine Cloud test cases passed across focused runs, including 12 view/language
  combinations, GET contract equality, exact simulator-response equality,
  missing/corrupt inputs, seal/traversal rejection, synthetic export and freshness.
- Existing investment-simulation and i18n suites: 27 tests passed.
- Existing simulator UI suite: 10 tests passed.
- Total: 46 distinct focused tests passed; `git diff --check` passed. The first
  contract comparison exposed non-fixed check timestamps; it passed with a fixed
  test clock. The initial freshness expectation incorrectly assumed today's
  publication was old; checking the next eligible session confirmed staleness.
- Tests used installed Python 3.13.5. Initial attempts in the separate Python 3.11
  environment could not collect tests because pytest/FastAPI were absent; no
  packages were installed. Existing Streamlit deprecation/font-cache warnings
  did not fail the checks. No Docker runtime or hosted smoke test was executed.
- Git's tracked-file inventory contains none of the inspected runtime, `.env`,
  Streamlit secrets or snapshot paths. No files were staged or committed.

### File inventory

Created: `cloud/streamlit_app.py`, `cloud/requirements.txt`,
`backend/src/riskbex/dashboard_transport.py`,
`backend/src/riskbex/cloud_snapshot.py`,
`backend/scripts/export_cloud_snapshot.py`,
`backend/tests/test_cloud_deployment.py`, and this document.
Modified: `.gitignore`, `backend/dashboard.py`,
`backend/src/riskbex/api/decisions.py`, `backend/src/riskbex/simulator_ui.py`,
`backend/src/riskbex/translations_es.json`.
The root and backend Streamlit configuration, FastAPI route schemas, model
artifacts, quantitative implementation, Docker and VPS files remain unchanged.
Cloud Home explicitly describes the read-only snapshot and replaces the existing
"Automated Daily Pipeline" feature badge; both languages retain local-mode copy.
