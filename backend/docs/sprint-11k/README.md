# Public daily automation — installation and activation

This supersedes the Sprint 11J private-repository installation. The only production
workflow is `.github/workflows/cloud-publication.yml`, controlled by `main` in
`apalomo75/RiskBEX`. It reads the latest clean `release/streamlit-rc1` checkout and
its verified approval on every attempt. That branch is the only persistent daily
state. No separate repository, persistence branch, artifact transport, custody key,
server, database or daily reviewer is required. Historical private implementations
and their tests remain available; their workflows are retired outside workflows/.

The controller runs the existing offline acceptance gate in Python 3.11.14 using
`backend/requirements-docker.lock`, then invokes `run_public_daily.py` against the
release checkout. The existing candidate adapter verifies the approved bundle,
frozen MAIN package and receipt, checks calendar coverage, retrieves with the
existing Yahoo provider, rejects missing/revised/future observations and performs
frozen inference. No training is permitted. Promotion rechecks live provenance,
historical prefix, latest eligible date and predecessor, and commits the bundle
and approval together. A normal push rejects concurrent remote changes. Never
retry by rebasing or forcing; start a fresh run from the latest approved release.
No-op runs do not promote or commit. Provider diagnostics are captured, not logged.
Only the daily job has write permission; the token is exposed only to its publication
step, with ephemeral askpass credentials. There is no environment approval queue.

A failure before successful push leaves the previous remote publication intact.
A confirmation failure after a successful push can mean publication succeeded:
inspect the remote approval before retrying. Streamlit refresh is asynchronous;
remote-head confirmation establishes Git publication, not successful app startup.

## Rights and remaining acceptance requirements

The owner's confirmation is recorded in the task, but no underlying licence or
permission evidence has been supplied in this checkout. The receipt remains
`blocked`; no evidence file or verified-rights claim was created. This is a real
publication blocker, independent of the disabled workflow switches.

The gate accepts the existing `verified` receipt or `owner_authorized`. Both require
provider `Yahoo Finance / IBEX 35`, all scopes in `publication_control.SCOPES`, an
unexpired ISO `valid_until`, `reviewed_by`, `licence_reference`, and `evidence_sha256`
matching `backend/config/publication-rights-evidence.txt`. Owner authorization also
requires `authorized_by: apalomo75`, `repository: apalomo75/RiskBEX`, ISO
`authorized_on` no later than today, and a nonempty `permission_basis` identifying
the actual grant. Record a real reviewable permission reference/attestation and
relevant evidence; do not place confidential agreements in public Git. A hash binds
reviewed evidence bytes; it does not independently verify the legal grant. Review
coverage of automated retrieval, raw history, returns, reconstructible charts,
derived signals, research assets and public Git redistribution. Do not activate if
any scope is missing. Never create placeholder evidence to satisfy the gate.

Calendar coverage is currently limited to 2026 and fails closed before retrieval
when the eligible or next target session is outside coverage. A reviewed extension
is required before year-end. Hosted execution, token/branch rules and Streamlit
refresh still need real acceptance; none was tested by dispatch during this task.

## Reviewed installation (operator actions, not executed here)

Review the complete worktree first: earlier Sprint 11 changes were already
uncommitted when this task began. Stage only reviewed files; do not use `git add .`.
Install the controller code, tests, retirement changes and receipt/evidence on
`main` through the normal review process. Keep the release runtime compatible with
the controller's frozen lockfile, package, calendar and regression receipt. Deploy
any required code/configuration through a separate reviewed release change while
preserving the current `cloud/publication` and `cloud/approval.json` bytes. Daily
publication commits themselves change only those two paths.

The prepared release compatibility change must be reviewed and merged first,
through a PR to `release/streamlit-rc1`. Merge the prepared controller PR to `main`
second, through existing protections. Never push directly to deployed branches or
force-push. Revalidate if either reviewed target base advances unexpectedly.
The final English-only corrections add `cloud/streamlit_app.py` and
`backend/src/riskbex/i18n.py` to the original release scope (five files total);
main also includes the adapter correction (33 files total).

Main has no approved publication snapshot. Run offline acceptance on a disposable
checkout of the reviewed release, including its staged compatibility changes, with
main's `backend/scripts`, `backend/src`, `backend/tests`, `backend/config` and
`.github` overlaid exactly as the production workflow does. Use Python 3.11.14 and
`backend/requirements-docker.lock`; invoke `run_actions_offline.py` with the full
release base SHA. Require zero failures and zero skips. Do not run this gate in the
bare main tree, or alter the clean publication checkout to make acceptance pass.
Keep publication and live-download switches disabled during installation.


## First publication and automatic execution (not executed here)

After supplying and reviewing genuine evidence, installing reviewed code and
passing offline acceptance, the following switches authorize subsequent live
downloads and publication. They default to disabled when absent; no remote settings were changed:

```bash
gh variable set RISKBEX_LIVE_DOWNLOAD_AUTHORIZED --repo apalomo75/RiskBEX --body true
gh variable set RISKBEX_PUBLICATION_ENABLED --repo apalomo75/RiskBEX --body true
gh workflow run cloud-publication.yml --repo apalomo75/RiskBEX --ref main
gh run list --repo apalomo75/RiskBEX --workflow cloud-publication.yml --limit 5
```

Inspect the first run and app before enabling schedules. For unattended operation,
review a main-branch change that uncomments only `schedule:` and its two cron lines
in the existing workflow. These operator commands prepare that explicit change
only after first-publication acceptance:

```bash
python - <<'PYTHON'
from pathlib import Path
p = Path('.github/workflows/cloud-publication.yml')
s = p.read_text()
for line in ["  schedule:", "    - cron: '17 20 * * 1-5'", "    - cron: '17 22 * * 1-5'"]:
    s = s.replace('#' + line, line)
p.write_text(s)
PYTHON
git diff -- .github/workflows/cloud-publication.yml
test "$(git branch --show-current)" = main
git add -- .github/workflows/cloud-publication.yml
git commit -m "Activate reviewed daily MAIN production schedule"
git push origin HEAD:refs/heads/main
```

Primary `17 20 * * 1-5` and recovery `17 22 * * 1-5` are
UTC: 21:17/23:17 Madrid in CET and 22:17/00:17 next day in CEST, both after the
20:00 local availability threshold. Calendar eligibility uses Europe/Madrid;
weekends/holidays/repeats are no-ops. GitHub can delay or omit schedules; recovery
catches failures and the next run retrieves all missing sessions. No guarantee is
made that the provider has complete data at either time. Configure repository
Actions failure notifications and watch calendar expiry and missing runs. Public
repository inactivity may disable scheduled workflows; check Actions status.

To stop new publication/downloads:

```bash
gh variable set RISKBEX_PUBLICATION_ENABLED --repo apalomo75/RiskBEX --body false
gh variable set RISKBEX_LIVE_DOWNLOAD_AUTHORIZED --repo apalomo75/RiskBEX --body false
```

Inspect any already running job separately; variable changes do not cancel it.

## Verify the new approved session

```bash
gh run view RUN_ID --repo apalomo75/RiskBEX --log-failed
gh api repos/apalomo75/RiskBEX/contents/cloud/approval.json?ref=release/streamlit-rc1 \
  --jq .content | base64 --decode
gh api repos/apalomo75/RiskBEX/commits/release/streamlit-rc1 --jq .sha
```

Compare `published_head`, `published_version`, and `published_session` in the safe
run summary with the branch head/approval. Confirm one normal publication commit
contains only the approved bundle and approval. Open the existing Streamlit app,
wait for Cloud reload, and confirm its displayed session/version matches the
approval. Revisit all six tabs and refresh the browser if needed. A repeat run
must succeed as `unchanged` without moving the branch head. If Cloud does not
refresh, inspect Cloud logs and branch/entrypoint settings before another run.

## Local validation

The complete existing offline acceptance gate, extended with public daily tests,
passed **78 tests, zero failures/errors/skips, in 217.163 seconds**. It ran once in
`/tmp/riskbex-11k-runtime`, created with Python **3.11.14** and a fresh installation
of `backend/requirements-docker.lock`. All **67 pinned distributions** matched
exactly; `pip check` reported no broken requirements. The gate verified unchanged
source checkout and approved snapshot, zero live downloads and zero actual Git
commits/pushes. Transport tests simulate normal push, rejection and concurrent
updates; they do not establish hosted branch permissions or Cloud refresh.

Coverage includes consecutive public trading days, repeat/no-op, missing sessions,
holidays/DST, provider/inference/storage failures, stale predecessor, rejected push,
frozen-model identity, historical prefix integrity and future-data independence.
The production YAML parsed successfully: manual trigger only, one job, no reviewer
environment and write permission scoped to that job. `git diff --check` passed.
Initial targeted checks also passed 15 tests. No schedules, switches or remotes
were activated; the existing approved publication and frozen model were unchanged.

After preserving the legacy private-rights assertion in the shared consecutive-day
test, only the two affected consecutive-day tests were rerun: **2 passed in
47.225 seconds**. No other full-suite rerun was necessary.

## Sprint 11K Git installation preparation

The reviewed installation separates controller and release changes. Main has no
approved publication payload: its production workflow creates a disposable Git
worktree from the resolved clean release, overlays the controller scripts, source,
tests, configuration and workflow fixtures, and runs all 78 offline checks there.
The publication checkout remains untouched. This supersedes the direct main-root
acceptance command above, which cannot work without an approved snapshot.

Release compatibility adds only actions_update.py, publication_control.py and the
blocked publication-rights.json receipt. Its existing frozen lockfile, model,
calendar and regression receipt match the controller installation. No deployment
payload or approval is included in either change. Install and review release
compatibility before the controller. Diagnostic/recovery/live trial workflows are
archived outside workflows; daily-update.yml remains a read-only manual regression
workflow. cloud-publication.yml is the sole production publisher, still gated and
without a schedule. Rights evidence, hosted permissions and first-run/Cloud
acceptance remain pending. Historical sprint activation instructions are records,
not authorization to activate them.
