# Sprint 6B — Reproducible local Docker infrastructure

## Services and storage

The existing API and dashboard Dockerfiles are retained. Both use Python
**3.11.14** and `requirements-docker.lock`. The six quantitative library pins
match the frozen MAIN manifest exactly. The remaining runtime dependencies are
pinned from local package metadata, with web packages taken from the existing
web environment. No packages were installed to prepare this configuration.
Notebook and training tools are excluded. The API image includes the unchanged
MAIN package, source, scripts and reviewed calendar. Its build verifies package
integrity and runtime compatibility, and runs `pip check`; no inference, market
retrieval or training runs during the build. `libgomp1` supports the frozen
XGBoost binary. OS/base image digests and wheel hashes are not locked; this is
version reproducibility, not a bit-for-bit image guarantee. Actual Linux wheel
resolution still requires the local build below.

`api` reads `/app/runtime/main` from one persistent host bind volume.
`dashboard` reads that same publication through `http://api:8000`; it does not
maintain a second store. The optional `updater` reuses the API image and is the
only container with write access to this store. The existing atomic VersionStore,
flock, immutable versions and regression gate are unchanged. The full store,
including `current.json`, `versions/`, `attempts/` and `status.json`, survives
container removal and restart. Never mount only `current.json`, move the versions
to a different filesystem, or edit the pointer manually. Failed promotion retains
the last valid pointer under the existing pipeline contract.

Existing validated stores can be selected directly using `RISKBEX_STORE`.
Prefer a backup or stopped-writer copy for initial Docker evaluation. Mounts fail
if source paths do not exist. Ensure the selected UID/GID can read the entire
store and models and write the store when enabling updates. The ignored
`backend/runtime/` tree is the default location; custom paths inside the repository
must be ignored before use. Seeds and receipts are read-only files, not secrets
baked into images. Build context excludes runtime data, environments and secrets.
The original academic `backend/data` mount remains read-only and dashboard figures
remain bundled; no academic artifacts are regenerated or overwritten.

Only `127.0.0.1:8501` is published. API port 8000 is internal. `/run-update`
continues to return 403, with no public writable update route. All services run as
an unprivileged UID/GID with read-only root filesystems, dropped capabilities,
no-new-privileges and a temporary `/tmp`. API `/health` and Streamlit
`/_stcore/health` are liveness checks, not evidence of a current publication.
Without a usable publication, operational API requests return 503 and the
existing dashboard displays its unavailable-publication state.

## Local startup (no scheduler)

Run from the repository root on a Docker host with Compose and daemon access:

```bash
cp -n .env.example .env
# Review .env; point RISKBEX_STORE to an existing validated store if available.
export RISKBEX_UID="$(id -u)"
export RISKBEX_GID="$(id -g)"
# Create the default empty store only if not selecting an existing store.
mkdir -p backend/runtime/docker-main backend/data backend/figures/chapter2
docker compose --profile scheduled config --quiet
docker compose build api dashboard
docker compose up -d --wait api dashboard
docker compose ps
```

Open <http://127.0.0.1:8501>. An empty store does not initiate a download.
No scheduler is enabled by these commands. Do not run with UID 0. Image builds
require registry/package-network access; they never request market data.

## Optional daily updater activation

This profile is an explicit operator action that authorizes live Yahoo retrieval.
Before activating it, select a complete validated seed and a successful, current
regression receipt in `.env` (`RISKBEX_SEED`, `RISKBEX_REGRESSION_RECEIPT`), and
verify permissions and calendar coverage. Never manufacture or edit a receipt to
pass the gate. The model, quantitative source and pipeline hashes are unchanged.

Stop any Sprint 6A host timer before activating the container scheduler:

```bash
systemctl --user disable --now riskbex-daily.timer
# Confirm no host/manual update is currently running before proceeding.
docker compose --profile scheduled up -d updater
docker compose --profile scheduled logs --tail=30 updater
```

On hosts without that timer, verify that no other host scheduling mechanism is
active instead. Do not enable both mechanisms. The container holds a lifetime
`container-scheduler.lock` on the shared store to reject duplicate container
timers; the original `update.lock` serializes actual jobs and manual invocations.

The timer uses Python zoneinfo with pinned tzdata, at **20:15, 21:15 and 22:15
Europe/Madrid**, including CET/CEST changes. Startup checks the exact Python
runtime, model, receipt and calendar before waiting. Startup performs no download
and waits for the next future slot; unlike the host persistent timer, it does not
replay a slot missed while the container was stopped. If the host sleeps through
a pending slot while the process remains alive, it makes one recovery attempt on
waking, then computes the next future slot. A failed update is retried at the next
slot, with JSON exit events in Docker logs and diagnostics in the store. A job
has a 30-minute timeout with terminate/kill cleanup. SIGTERM stops the child.
Host uptime, log retention and stale-publication monitoring remain operator duties.

Stop container scheduling without deleting publications:

```bash
docker compose --profile scheduled stop updater
```

## Exact local container validation commands

After startup, verify runtime and dashboard-to-API connectivity without downloads:

```bash
docker compose exec api python -c "from src.riskbex.engine.package import verify_main_package; verify_main_package('model_packages/main-v1', check_runtime=True); print('MAIN runtime verified')"
docker compose exec dashboard python -c "import urllib.request; print(urllib.request.urlopen('http://api:8000/health', timeout=5).read().decode())"
docker compose exec dashboard python -c "import urllib.request, urllib.error; r=urllib.request.Request('http://api:8000/run-update', method='POST'); exec('try:\n urllib.request.urlopen(r, timeout=5)\n raise AssertionError(\"Update route enabled\")\nexcept urllib.error.HTTPError as e:\n assert e.code == 403')"
curl --fail http://127.0.0.1:8501/_stcore/health
```

For an existing validated store, stop the updater first (if active), then check
persistence across recreation. API and dashboard reads do not alter the store:

```bash
docker compose exec -T api cat /app/runtime/main/current.json > /tmp/riskbex-before.json
docker compose up -d --force-recreate --wait api dashboard
docker compose exec -T api cat /app/runtime/main/current.json > /tmp/riskbex-after.json
cmp /tmp/riskbex-before.json /tmp/riskbex-after.json
docker compose exec dashboard python -c "import urllib.request; print(urllib.request.urlopen('http://api:8000/latest-risk', timeout=10).status)"
```

Check missing-publication behavior using a separate empty store; no updater runs:

```bash
mkdir -p backend/runtime/docker-empty
RISKBEX_STORE=./backend/runtime/docker-empty docker compose up -d --force-recreate --wait api dashboard
docker compose exec dashboard python -c "import urllib.request, urllib.error; exec('try:\n urllib.request.urlopen(\"http://api:8000/latest-risk\", timeout=10)\n raise AssertionError(\"Expected unavailable publication\")\nexcept urllib.error.HTTPError as e:\n assert e.code == 503')"
# Restore the store configured in .env afterwards.
docker compose up -d --force-recreate --wait api dashboard
```

Check updater configuration without starting a timer or performing a download:

```bash
docker compose --profile scheduled config --quiet
docker compose run --rm --no-deps api python -c "from datetime import datetime; from scripts.run_container_scheduler import next_trigger, MADRID; print(next_trigger(datetime.now(MADRID)))"
```

## Validation performed and remaining limits

- Compose v5.1.0 accepted the complete configuration, including the optional profile.
- Static assertions verified shared source paths, reader/writer permissions,
  internal API URL, port bindings, security settings, health checks and profile.
- All 67 pins satisfy the available local dependency metadata and Python 3.11.14
  requirements; MAIN's quantitative pins match the manifest.
- Four new timer tests, six Sprint 6A scheduler tests, four frozen pipeline tests
  (idempotence/no fitting and provider/write/pointer failure preservation), and six
  operational API tests passed: **20 tests**. Quantitative tests used the approved
  Python 3.11.14 environment; API-only fixture tests used the existing web venv,
  without inference. No full quantitative suite ran. Initial test invocations had
  path/import errors; these were corrected, and only the affected tests rerun.
- `git diff --check` passed. No training, market download, dependency installation,
  scheduler activation, cloud deployment or commit was performed.

Docker client and Compose are installed, but `docker info` was denied access to
`/var/run/docker.sock`. **No image build or container execution was verified.**
Image resolution, actual container networking, health and restart persistence must
be checked with the commands above on an authorized Docker host. Before public
hosting: validate those checks and a separately authorized live update, review
calendar coverage beyond 2026, provide TLS/access controls, backups and recovery,
log retention, monitoring and an always-on host. Public port exposure and cloud
infrastructure are outside Sprint 6B.
