# Sprint 6A — Unattended daily market updates

The live-only entry point is `scripts/run_scheduled_update.py`. It calls the
existing `update_main` service with Yahoo, the frozen MAIN package and a reviewed
calendar. There is no file provider, simulated clock, training or legacy pipeline
option. No scheduler has been installed or enabled by this sprint.

## Runtime and command

Run from `backend` using the existing approved model environment (Python 3.11.14
and the versions pinned in `model_packages/main-v1/manifest.json`). In this
checkout that executable is
`/home/apalo/miniconda3/envs/fin-forecasting/bin/python`; `backend/venv` currently
uses Python 3.13 and is unsuitable for frozen MAIN inference. Runtime validation
fails closed. No dependencies need to be installed by the scheduler.

```bash
/home/apalo/miniconda3/envs/fin-forecasting/bin/python -B scripts/run_scheduled_update.py \
  --fetch --seed /absolute/path/validated-prices.csv \
  --store /home/apalo/projects/RiskBEX/backend/runtime/main-wsl-test \
  --calendar /home/apalo/projects/RiskBEX/backend/config/bme-2026.json \
  --regression-receipt /absolute/path/approved-regression.json
```

Select an existing successful regression receipt matching the current package and
implementation hashes. Never edit a receipt to bypass the gate. This sprint does
not change any hash-covered pipeline or quantitative module. The seed must remain
a validated complete history even when a current publication exists. Use the same
store for the scheduler and `RISKBEX_OPERATIONAL_DIR` in FastAPI.

## Optional local systemd setup

Templates are in `config/systemd/`. They assume the repository is under
`%h/projects/RiskBEX`; adjust both paths if needed. The service invokes Python
without activating a shell environment. Create `~/.config/riskbex/daily.env` with
absolute paths, for example (replace the seed and receipt paths):

```ini
RISKBEX_PYTHON=/home/apalo/miniconda3/envs/fin-forecasting/bin/python
RISKBEX_SEED=/absolute/path/validated-prices.csv
RISKBEX_OPERATIONAL_DIR=/home/apalo/projects/RiskBEX/backend/runtime/main-wsl-test
RISKBEX_REGRESSION_RECEIPT=/absolute/path/approved-regression.json
RISKBEX_CALENDAR=/home/apalo/projects/RiskBEX/backend/config/bme-2026.json
```

After reviewing the paths and explicitly authorizing activation, the operator can
run from `backend`:

```bash
mkdir -p ~/.config/systemd/user
cp config/systemd/riskbex-daily.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now riskbex-daily.timer
systemctl --user list-timers riskbex-daily.timer
journalctl --user -u riskbex-daily.service -o cat
```

The timer attempts daily at **20:15, 21:15 and 22:15 Europe/Madrid**, after the
calendar's conservative 20:00 availability threshold. Explicit timezone scheduling
handles CET/CEST automatically. Later attempts retry delayed data and failed runs;
there is no tight retry loop. Weekends and holidays resolve to the latest eligible
trading session, revalidate provider overlap and return `unchanged` if already
published. A timer trigger is never proof of data availability. A persistent timer
makes one recovery attempt when the timer next starts after missed triggers; it
does not replay every missed invocation. Even a morning recovery uses only the
latest session eligible at that time.

WSL must support and run systemd. WSL shutdown, Windows sleep, logout and a stopped
user manager can prevent execution. `Persistent=true` cannot wake Windows or WSL.
Start WSL and the user timer to recover; user-manager persistence may require
operator-managed linger. For production, use an always-on Linux host with an
approved runtime, persistent storage, service-account systemd scheduling and
monitoring of failed attempts and stale publications. No host is provisioned here.

## Safety, recovery and evidence

The existing nonblocking flock prevents concurrent updates, including manual
updates. Systemd also serializes this service. Exit codes are **0** for published
or unchanged, **1** for configuration/provider/validation/publication failure,
**2** for invalid CLI arguments, and **75** for an update already running.
A 30-minute systemd timeout terminates a stuck job; the next timer can retry.

Every download requests overlap plus **all** sessions from the last stored close
to the eligible session. Exact calendar continuity, unchanged historical overlap,
frozen training history, the regression gate, model integrity and batch/latest
agreement are required. Missing intermediate or latest dates fail the attempt;
no partial catch-up is published. The next attempt requests the entire gap again.
Calendar coverage expiry also fails closed, including next-session coverage.

Download, inference and pre-promotion write failures preserve the previous valid
`current.json`. Immutable versions and atomic promotion are reused. Interruption
before promotion leaves the old pointer; after promotion the new version has
already passed validation. A crash after pointer replacement but before status
completion may leave a valid new publication with an ambiguous attempt status:
inspect the pointer and manifest before recovery. A killed process can leave a
`.stage-*` directory or validated orphan version; retain these for diagnosis and
review before manual cleanup. The existing publisher verifies matching orphan
versions on retry. Do not modify historical artifacts or reset the current pointer
to bypass validation. Provider price revisions require operator review.

Each normal invocation emits two JSON journal events with UTC start/end times,
eligible target session (the latest close eligible for ingestion), market
information date, new-session count, publication version, status and error type.
Unknown values are null, including new-session count on failure. The signal's
next trading session remains recorded separately in the existing publication.
Journal events omit exception text, configuration values and credentials. Existing
pipeline `attempts/*.json` and `status.json` retain detailed failure context; treat
these local diagnostics as private. Failures before pipeline entry and lock
rejections are recorded in the journal. Forced termination may have only a start
event; systemd records timeout/exit state. Configure journal persistence and disk
retention on the production host; no credentials are needed by this public source.

## Validation and remaining limits

`tests/test_scheduled_update.py` exercises JSON events, exit codes, live-only
execution, duplicate outcomes, Madrid DST boundaries, weekends, holidays, calendar
expiry and multi-session catch-up with an interior gap. Selected existing daily
pipeline tests additionally exercise actual frozen inference with fitting blocked,
flock exclusion, continuity, corrupted publications, provider/write/pointer failure,
recovery and the absence of changes to past signals after future extension.
All provider responses are fixtures or mocks; no downloads or training are run.

Validation result: **26 targeted tests passed** (six scheduler tests, twelve
existing calendar/provider tests and eight selected frozen pipeline tests).
`git diff --check` passed. `systemd-analyze calendar` accepted the timer expression;
full user-unit verification was restricted by unavailable system-bus access in
the execution sandbox. The initial scheduler test invocation from the repository
root failed to import `scripts`; running from `backend`, as documented, passed.
The complete quantitative suite was not run.

The supplied calendar covers only **2026** and must be reviewed and extended before
coverage expires. Yahoo remains a single external source whose delivery is not
guaranteed; an unavailable or revised close prevents promotion. Scheduler activation,
real download validation, user-session lifecycle validation, persistent journaling,
backup/retention and production monitoring remain operator tasks. No automatic
schedule or deployment has been activated.
