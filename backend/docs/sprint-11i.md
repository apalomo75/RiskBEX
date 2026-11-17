# Sprint 11I — Private daily MAIN computation

The new `private-daily.yml` reuses the live dry-run adapter, frozen MAIN runtime,
regression receipt and approved release snapshot
`3cffc6b377a4010272788c9e434111c12258aeea`. It has read-only repository permission,
no environment approval, no publication command and its own concurrency group
`riskbex-private-daily-v1`. Existing workflows and publication-rights checks are unchanged.

## State and execution contract

Every run independently recomputes from the unchanged approved snapshot. There is
**no persistent private operational history**. No cache or artifact retains provider
prices, signals, models or candidate reports. The disposable candidate is removed
on success or failure; hosted runner disposal is the fallback after cancellation.
An updated result means a verified candidate advanced the approved baseline during
this run, not that persistent state or public data changed. Repeat runs can therefore
report the same updated date and session count. An unchanged result means zero new
sessions relative to the approved baseline, not a successful update.

Schedules are 20:17 UTC (primary) and 22:17 UTC (recovery), every day. These are
21:17/23:17 Madrid in winter and 22:17/00:17 in summer. Both are later than the
reviewed 20:00 local availability policy; the summer recovery occurs the next local
day and selects the previous eligible session. GitHub may delay or omit scheduled
runs; scheduling is not a delivery guarantee. The calendar selects the latest
eligible session on weekends and holidays. Missing intermediate/latest sessions,
provider failures, stale regression receipts and expired calendar coverage fail
closed. Recovery recomputes independently; it does not resume a partial candidate.
The reviewed calendar covers 2026 only; arrange a separately reviewed calendar
and regression process before expiry. No inferred 2027 holiday rules are installed.

Only dates, session count, outcome, verification status and state policy enter the
execution JSON and Actions step summary. Provider diagnostics and detailed exceptions
are suppressed. Failure exits nonzero and reports failed; unchanged exits zero with
outcome unchanged. Setup or offline-gate failures stop before downloads: consult the
failed Actions step (no computation summary is promised before the controller starts).

## Installation and activation (operator only)

No commit, push, variable change or remote run was performed during implementation.
Review the existing uncommitted Sprint 11H prerequisites separately: this sprint
requires the existing dry-run adapter, fixtures and workflow on main. Install those
reviewed prerequisites first if they are not already present remotely. Do not stage
unrelated working-tree changes or publication/approval files.

From the repository, with main checked out and the prerequisites installed:

```bash
gh variable set RISKBEX_PRIVATE_DAILY_ENABLED --body false
git add -- .github/workflows/private-daily.yml backend/scripts/run_private_daily.py backend/tests/test_private_daily.py backend/docs/sprint-11i.md
git diff --cached --check
git diff --cached
git commit -m "Add gated private daily frozen MAIN execution"
git push origin main
```

The workflow is inert until the repository variable equals exactly `true`.
After reviewing the installed main commit, activate and request the first live run:

```bash
gh variable set RISKBEX_PRIVATE_DAILY_ENABLED --body true
gh workflow run private-daily.yml --ref main
gh run list --workflow private-daily.yml --limit 5
```

Activation authorizes private live downloads on subsequent scheduled/manual runs.
No manual environment approval is used. Repository Actions policy and billing/runner
availability must permit execution. Scheduled workflows run from the default branch;
main must be the default branch. GitHub can disable inactive public-repository
schedules; inspect Actions if expected runs are absent.

## Operations and recovery

Inspect the Actions summary: previous approved session, latest processed session,
new sessions processed, updated/unchanged/failed and verification status. A green
unchanged run does not advance the baseline. The approved snapshot remains unchanged
regardless of candidate outcome. For transient provider failure, allow the recovery
schedule or dispatch another run. For missing sessions, do not fill or skip observations.
For integrity, regression or calendar failures, stop and obtain a reviewed correction;
do not alter receipts, models or approval files to bypass gates.

```bash
gh run view RUN_ID --repo OWNER/REPO
gh workflow run private-daily.yml --ref main
# Stop future computation; cancel a currently running job separately if necessary.
gh variable set RISKBEX_PRIVATE_DAILY_ENABLED --body false
gh run cancel RUN_ID --repo OWNER/REPO
```

Public promotion remains a separate, rights-gated operation and is not enabled here.

## Local verification record

The targeted 49-test selection under the available default Python 3.13.5 produced
31 passes, 13 skips, 3 errors and 2 failures. All four new private-daily tests passed.
Frozen integration checks rejected the incompatible runtime (required 3.11.14),
including two expected-error assertions masked by the earlier runtime rejection.
The existing Python 3.11.14 environment lacks yfinance, so guarded integration
execution cannot start there. No dependency was installed and no network retrieval
was performed. Full frozen-runtime acceptance remains pending; activation must wait
until the workflow's exact offline gates pass in the pinned environment. This record
does not claim operational live verification or successful remote execution.
