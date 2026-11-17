# Sprint 11G: first live-data dry-run candidate

Status: local implementation only. No remote installation, dispatch, live market
request, publication, schedule, Secrets change, commit or push was performed.
The November 16 approved bundle and frozen quantitative code remain unchanged.

## Hosted evidence and branch separation

Inspected job [134054010001](https://github.com/apalomo75/RiskBEX/actions/runs/44087596327/job/134054010001)
from run 44087596327: completed/success, release
`3cffc6b377a4010272788c9e434111c12258aeea`, Ubuntu 24.04.5,
Python 3.11.14, pinned install and pip check successful. Tests: 43 passed,
zero skips, 50.098 seconds (3 offline safety, 7 runner/bootstrap/replay,
25 pipeline, 8 Cloud approval). Guards reported unchanged source snapshot and
checkout, zero live downloads, zero actual Git commits/pushes. Log timestamps
span 12:54:58.999–12:56:48.352 UTC, approximately 109.35 seconds including
setup/cleanup; acceptance step about 51.2 seconds. No CPU, peak RSS or disk
telemetry is present: earlier local RSS figures must not be attributed to this
hosted run. Three numerical thread limits were 1. New private reports measure
wall time and process peak RSS; these are not total runner resource consumption.

Read-only remote refs on 2026-11-17:

- main: `8fe00f92786431ffb62274fd66702f38abc399ae`
- release/streamlit-rc1: `3cffc6b377a4010272788c9e434111c12258aeea`

The old run 43952004645 jobs API returned an empty list. This does **not** prove
its run state or concurrency lock is cleared. The new workflow uses the separate
`riskbex-live-dry-run-v1` group, cancel-in-progress false. Existing diagnostic
and recovery files were left intact; disabling/deleting them requires a separate
reviewed cleanup. Recheck the old run/queue in Actions before any later reuse.

## Implementation and failure policy

`live-data-dry-run.yml` has workflow_dispatch only, main-only execution,
contents:read, no stored checkout credentials, no upload/cache or publishing step,
a protected-environment reference and an explicit default-false authorization.
The reviewed controller SHA and the independently pinned approved release are
checked before runtime installation. Only the new adapter/tests/fixture/workflow
are copied into the disposable release checkout; quantitative implementation,
model and regression receipt bytes are reused from that release.

`run_actions_live_dry_run.py` has no publication flag/import. It bootstraps a new
workspace outside the checkout, verifies approved inventory, frozen runtime,
training inputs and regression receipt before calling existing YahooProvider and
MAIN candidate(). Training and Git mutations are blocked during candidate work.
Existing pipeline checks chronology, strictly complete trading sessions,
positive unique dated prices, exact historical overlap, frozen training hash,
causal inference, finite/model outputs, batch/latest agreement, and next-session
coverage. Existing regression/no-look-ahead tests execute offline before live
retrieval. Source inventory and approval bytes are checked again on exit.

A candidate is exported once into a new directory; existing exports cannot be
overwritten. The private report records both approvals, dates, versions, manifests,
provenance, old/new latest outputs, table row counts/last rows/SHA-256, complete
inventory, snapshot and approval hashes, elapsed seconds and process peak RSS.
"published" in the underlying result means publication to the **temporary local
VersionStore**, never the Cloud branch. Report publication is explicitly disabled.

Provider errors/empty data, malformed schema, revised overlap, missing interior or
latest session, future/non-market dates, stale gates, expired calendar, inference
or write failure abort with no approved-source changes. No application retries
are added: one bounded provider call (20-second request timeout; library internals
may make additional HTTP requests). Whole job timeout is 20 minutes. Diagnose an
unavailable provider and separately authorize a later manual run; never silently
publish an older close. Weekends/holidays resolve to the last eligible session;
if already approved, candidate() returns unchanged without provider access. The
20:00 Europe/Madrid cutoff is a conservative availability policy, not proof that
the latest close is delivered. Incomplete sessions fail. Delayed runs catch up
all intervening sessions and reject gaps. Calendar next-session coverage is
required before network, including at year end.

## Installation and exact manual launch (future operator action)

Do not execute these steps until separately approved. No changes to the deployment
branch are needed for this dry run.

1. In a clean checkout of **main**, apply only these reviewed additions from this
   task: `.github/workflows/live-data-dry-run.yml`,
   `backend/scripts/run_actions_live_dry_run.py`,
   `backend/tests/test_live_dry_run.py`,
   `backend/tests/fixtures/live-dry-run/extension.csv`, and this document. Review
   and commit/push through the repository's normal approved process. Do not merge
   the release snapshot into main or alter the diagnostic workflows. Record the
   resulting full main SHA as IMPLEMENTATION_SHA. The workflow uses the release
   checkout for frozen runtime and original pipeline tests.
2. Configure environment **live-data-dry-run**, restricted to main, with required
   reviewer and prevention of self-review where supported. Verify that protection
   is actually available/enforced for this repository plan before dispatch. No
   environment secrets or Streamlit Secrets edits are required. If required
   reviewers are unavailable, stop and arrange a separately reviewed authorization
   control; naming an environment alone does not provide approval protection.
3. Read-only check both remote heads. The release must still equal the pinned SHA
   above. If changed, stop: do not replace the pin without another review. Ensure
   the new group has no stale job; the anomalous offline group remains unused.
4. Obtain explicit authorization for **one real Yahoo ^IBEX download for a private
   non-publishing dry run**. This is separate from public redistribution approval.
5. GitHub → Actions → **MAIN live-data dry run** → Run workflow → branch **main** →
   implementation_sha = IMPLEMENTATION_SHA → authorize_live_download = true.
   Approve the environment deployment only after checking the SHA and scope.
   Equivalent CLI, for the authorized operator only:

   ```bash
   gh workflow run live-data-dry-run.yml --repo apalomo75/RiskBEX --ref main \
     -f implementation_sha=IMPLEMENTATION_SHA -F authorize_live_download=true
   ```

Required resources: standard hosted ubuntu-24.04 x64 runner, Python 3.11.14,
pinned requirements-docker.lock; network for checkout, setup-python, package
installation and authorized Yahoo access. Three numerical thread limits are 1.
No GPU, training, Docker, new dependency, contents:write, PAT or Streamlit secret
is needed. Operator needs workflow-dispatch permission and environment approval
permission. Future package installation occurs only in the authorized hosted job;
no dependencies were installed locally for this task.

## Candidate verification and confidentiality

The job checks every inventory entry and the exact allowlist with verify_bundle,
then verifies the separate approval with verify_approved_bundle. It enforces an
advancing data date, matching predecessor and unchanged frozen model identity.
The full JSON comparison is `RUNNER_TEMP/riskbex-live-candidate/dry-run-report.json`;
the bundle is `candidate/`, its approval is `approval.json`. These paths are private
runner-local only. Neither data, outputs, hashes nor provider diagnostics are
printed to Actions logs. Public logs contain only success/failure statements.
The always-cleanup step removes the workspace, including on failure; hosted
runner disposal is a second boundary if forcibly terminated.

The first trial intentionally offers **no downloadable candidate or human access
to its detailed report after the job**. A green live step attests automated checks,
not human inspection of an exported artifact. If detailed human review is required,
separately authorize a private runner/restricted storage and retention mechanism;
do not add upload-artifact to a public repository or print the report. Verify
release head/approval are unchanged after the run. A successful pre-cutoff or
weekend run may be a no-op; only the private structured result distinguishes it.

## Subsequent atomic promotion (prepared existing mechanism, inactive)

Reuse `actions_update.promote`, already covered by disposable/mocked-Git tests.
It requires a clean release checkout at an expected head; verifies old/new bundles,
strictly advancing date and exact previous_version; copies payload plus
cloud/approval.json and creates **one commit**. Normal non-force push atomically
updates the branch. A concurrent remote commit rejects that push; never rebase,
retry-force or recreate the candidate against an unreviewed predecessor. A failed
local copy/verification/commit/push affects only the disposable checkout; the
remote approved snapshot stays intact. Discard that checkout on failure.

For a future reviewed promotion job: use a distinct protected publication
environment, contents:write only there, checkout release with its fetched full
expected head, reverify candidate digest and provenance from approved private
custody, enforce machine-readable rights approval, then invoke promote once.
The live dry-run workflow cannot invoke this path. Existing Cloud trust reads the
Git approval and invalidates stale cache; the legacy Secret is not a daily pin,
so snapshot and approval advance together without daily Secrets edits. Future
promotion integration and a real remote conflict/failure test remain unexecuted.

## Redistribution decision and 2027 calendar

Public updates remain blocked. The [yfinance project notice](https://raw.githubusercontent.com/ranaroussi/yfinance/main/README.md)
limits its intended use to research/education and describes the API as personal
use; the software licence does not grant market-data redistribution rights.
Yahoo's [terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) and
[data-provider help](https://help.yahoo.com/kb/SLN2310.html) could not be retrieved
in this review (HTTP 999/429), so no Yahoo redistribution permission is established.

The route to authorize public publication is a written licence from BME/SIX or an
authorized vendor expressly covering IBEX end-of-day/historical data, non-display
calculation, public website display and downloadable/reconstructable histories,
derived outputs and Git repository distribution. This is a required contractual
confirmation, **not a licence already obtained**. BME's current
[contract documentation](https://www.bolsasymercados.es/en/bme-exchange/prices-and-markets/market-data-services/documentation/data-feeds.html)
identifies Display/Non-display agreements and supporting terms effective August
23, 2026. Obtain the applicable current agreement and written scope confirmation
from the licensor; record licence reference, permitted fields/routes, attribution,
retention and expiry in an auditable approval before enabling promotion. A licence
that permits website display may still prohibit putting CSV histories in public
Git. Derived charts/signals are not assumed exempt. No contact was sent.

The [official BME calendar page](https://www.bolsasymercados.es/es/bme-exchange/negociar/calendario-del-mercado.html)
retrieved on 2026-11-17 yielded no 2027 calendar. Official 2027 session dates could
not be verified; none are guessed or installed. Required auditable extension:
archive the official annual circular/PDF and SHA-256, source URL, publication and
retrieval dates, reviewer and review date; record 2027 holidays/half days and
session conventions in a new versioned calendar covering 2026+2027. Keep the
20:00 policy explicit. Add tests for every official closure, half days, DST,
Dec 2026/Jan 2027 next-session rollover, weekends and expired coverage. Select
that reviewed calendar explicitly in candidate() in a separate minimal change;
do not edit historical manifests or model hashes. Extend before the final 2026
session needing a 2027 target. Merely adding 2027 to `years` is not sufficient.

Autonomous daily operation additionally requires an approved successful private
live trial, licensed publication route, private candidate custody/review,
protected promotion integration, real conflict/failure validation, reviewed
calendar extension, monitoring/recovery policy and separately authorized schedule.

## Local validation results

- Initial invocation accidentally used the default Python 3.13.5: 44 tests,
  2 failures, 3 errors and 13 skips because frozen runtime verification correctly
  rejected it. No checks were weakened. No dependencies were installed.
- Repeated the affected batch in the existing `fin-forecasting` Python 3.11.14
  environment with all three thread limits set to 1:
  `python -m unittest tests.test_live_dry_run tests.test_actions_update tests.test_daily_pipeline tests.test_actions_cloud`.
  **44 passed, zero skips, 114.634 seconds**. Includes the new synthetic November
  17 extension, verified private report, source preservation, original quantitative
  regression, no-look-ahead, provider failures, calendar and mocked atomic Git
  promotion/Cloud approval checks.
- After final workflow isolation changes and adding the diagnostic-redaction test,
  ran only `tests.test_live_dry_run.LiveDryRunTests.test_live_cli_redacts_provider_diagnostics`
  and `tests.test_live_dry_run.LiveDryRunTests.test_workflow_is_manual_read_only_and_no_exposure`:
  **2 passed**, 0.003 seconds. The workflow's future complete gate now contains
  45 tests (the hosted 43-test evidence above concerns the earlier offline run).
- New workflow YAML parsed successfully; both Python files compile; whitespace
  check passed. No full historical suite, live download, hosted candidate run or
  remote promotion was executed. Existing temporary diagnostics remain untouched.
