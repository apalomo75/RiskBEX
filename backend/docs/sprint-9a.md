# Sprint 9A — Autonomous update readiness

## Readiness and blockers

Assessed on 2026-11-09. Scheduling remains **inactive/unverified**, not production
ready. No live download, Docker execution, installation, training or activation
was performed. No quantitative engine, scheduler, historical artifact or receipt
was changed. Compose configuration validation passed.

- The approved host executable `/home/apalo/miniconda3/envs/fin-forecasting/bin/python`
  is Python 3.11.14; loading MAIN validates its package and required library versions.
  The default shell Python is 3.13.5 and must not run frozen inference.
- The API Dockerfile pins Python 3.11.14 and validates MAIN during build. Actual
  image/runtime checks remain blocked by Docker socket permission denial.
- `.env` selects `backend/runtime/main-wsl-test`. Its current publication verifies,
  records Yahoo as its source and ends on 2026-11-06. This is existing evidence,
  not a live download validated in Sprint 9A. The host user and configured container
  identity are UID/GID 1000; the store is writable by that host identity. Container
  bind permissions and persistence still require actual container validation.
- Both configured inputs are absent: `backend/runtime/inputs/seed.csv` and
  `backend/runtime/inputs/receipt.json`. Bind mounts deliberately fail for missing
  inputs. Select an independently validated complete price history, including the
  exact frozen training prefix; do not substitute a downloaded fragment or fixture.
- `backend/reports/sprint3/regression.json` fails `verify_gate`: its
  `pipeline/loaders.py` hash differs. Never edit/copy hashes to make it pass.
  A separately authorized run of the existing regression checker can produce a
  new receipt **only after the actual regression passes**, without overwriting the
  historical receipt:

  ```bash
  cd backend
  /home/apalo/miniconda3/envs/fin-forecasting/bin/python -B scripts/check_daily_regression.py \
    --output runtime/inputs/receipt.json
  ```

  This was not run; it is a prerequisite remediation, not part of the targeted
  scheduler tests. Select the reviewed seed and successful new receipt in `.env`.
- The reviewed exchange calendar covers 2026 only. Coverage includes current
  sessions, but publication requires a covered **next** session too; extend it
  through the existing review process before the final 2026 trading session.
  Do not silently extrapolate holidays. Container calendar changes require rebuilding
  the image so readers and updater use the same reviewed calendar.
- No updater process was found by the local process query. Systemd user-bus and
  cron access were denied; duplicate host scheduling therefore cannot be ruled out.
  Check all host timers/cron jobs and other Docker projects before activation.

These blockers require operator action. No broad engine investigation was opened.

## Existing execution and recovery contract

The container waits for 20:15, 21:15 and 22:15 Europe/Madrid with CET/CEST handling.
It invokes `run_scheduled_update.py --fetch`, which uses Yahoo `^IBEX`, daily adjusted
closes and the existing MAIN pipeline. The 20:00 eligibility policy is conservative;
provider completeness remains mandatory. Overlap and every missing session are
requested, including multiple missed days. Missing/latest/interior sessions,
non-trading provider rows and revised historical overlap fail closed. Weekends and
holidays revalidate the latest eligible session and can return `unchanged`.

The existing flow computes 11 features, frozen MAIN inference, regime probabilities,
target exposures and realised history. The receipt, package/runtime, training prefix,
batch/latest agreement and artifact integrity are checked before atomic promotion.
There is no training or operational simulation fallback. API, Performance and
Investment Simulator consume the same publication through the API; freshness is
recomputed at read time. Failed attempts never make an old session current.

The lifetime container lock rejects another container timer on the same store;
`update.lock` excludes overlapping actual updates. This does not prohibit an
alternating host timer: explicitly remove that duplicate schedule. Provider,
incomplete-data and promotion failures retain the previous valid publication and
retry at the next slot. A 30-minute timeout terminates/kills a stuck child. On restart,
the timer waits for the next future slot, whose request catches up missing sessions.
It does not replay stopped-time slots immediately. Interrupted promotion can leave
staging/orphan artifacts; retain them for diagnosis, never reset the pointer manually.

## Operator-controlled validation and activation

Run from the repository root after resolving the prerequisites. Commands below
are procedures, not commands executed by this sprint. Use the existing Sprint 6B
build/runtime/persistence checks before any market access. An image build needs
separate authorization if not already approved. Do not run as UID 0.

Inspect host scheduling with `systemctl --user list-timers --all`, `crontab -l`,
applicable system/service-account schedules, `docker ps` and process listings.
Disable the known host timer if installed:

```bash
systemctl --user disable --now riskbex-daily.timer
# Confirm that its service and any manual updater have finished.
systemctl --user is-active riskbex-daily.service
docker compose --profile scheduled config --quiet
```

Once prerequisites pass and live access is available, propose **one explicitly
authorized** end-to-end validation through the existing entry point, while all
schedulers are stopped. This command performs a real Yahoo download:

```bash
docker compose --profile scheduled run --rm --no-deps updater \
  python -B scripts/run_scheduled_update.py --fetch \
  --seed /inputs/seed.csv --store /app/runtime/main \
  --regression-receipt /inputs/receipt.json
```

Inspect the resulting publication and API consumers. Only after operator approval,
the exact activation command is:

```bash
docker compose --profile scheduled up -d updater
```

Do not claim unattended operation from the one-shot command. Observe an actual
future scheduled attempt complete without operator intervention, recording its
`timer_wait`, `daily_update` completion and `timer_result`, then verify the published
session and API freshness. WSL stops updating when Windows/WSL is shut down or the
host is off/asleep. Restart policies cannot wake it; unattended operation requires
host uptime, a running Docker daemon and persistent mounted storage.

## Monitoring and safe shutdown

```bash
docker compose --profile scheduled ps updater
docker compose --profile scheduled logs --timestamps --tail=100 updater
docker compose --profile scheduled logs --follow updater
# Last attempt and detailed private pipeline failure reason:
docker compose exec -T api cat /app/runtime/main/status.json
# Pointer and immutable versions survive container removal:
docker compose exec -T api cat /app/runtime/main/current.json
# Last successful publication, market session, freshness and latest pipeline status:
docker compose exec -T dashboard python -c "import json, urllib.request; d=json.load(urllib.request.urlopen('http://api:8000/latest-risk', timeout=30)); print(json.dumps(d['publication'], indent=2))"
# Safe shutdown; keep publications and diagnostic files:
docker compose --profile scheduled stop updater
```

The latest `timer_wait.next_trigger` is the next scheduled attempt. UTC start/end,
exit status and error type are in updater logs, including failures before pipeline
entry. `status.json` describes the last completed pipeline attempt, not necessarily
the last invocation; inspect logs for lock, startup, runtime and forced-termination
failures. `attempts/*.json` retain detailed private pipeline diagnostics. Publication
metadata supplies `last_successful_update` and `data_date`; an unchanged retry does
not regenerate the publication. `/health` only proves liveness. Alert on failed or
missing attempts, stale/unavailable publications and calendar expiry. Arrange Docker
log retention and store backup/retention before continuous operation.

## Validation evidence

Executed with the approved Python 3.11.14 environment: **31 tests passed**:
all container/scheduled-update tests, all CalendarAndProviderTests, and these
PipelineTests: success/idempotence/no-fit, provider failure, write failure, pointer
failure/recovery, incomplete response, multi-session catch-up/interior gap, stale
gate rejection, corrupt publication and future-extension invariance.

Executed with the existing web venv: **10 passed, 2 errored** across operational
API, selected publication integration, Performance and Simulator checks. Passing
checks include all six operational API tests, stale-publication handling,
Performance API compatibility, simulator single-snapshot/no-write behavior and
full dashboard simulator publication visibility. Two existing UI assertions are
outdated: `test_real_publication_http_and_monitor` expects exposure labels ending
in “Strategy”, and `test_dashboard_selection_gross_net_and_stale` expects an
“Overview” tab under the former Results layout. The current dashboard uses shorter
labels and separate Overview/Performance pages. These failures remain unresolved;
no UI redesign or unrelated test rewrite was undertaken. The live path is not
certified by this partial interface result.

Compose profile configuration and `git diff --check` passed. No complete
quantitative suite ran. Tests use isolated fixtures/mocks, including temporary
test receipts; these are not operational receipts and cannot authorize deployment.
Live Yahoo validation and an observed fully unattended scheduled run remain
**not performed**.
