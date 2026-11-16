# Sprint 11D — First hosted offline run / Primera ejecución offline en GitHub

Prepared only. No commits, pushes, dispatches, settings changes or market downloads
performed. Instructions below require further authorization. / Solo preparación;
las operaciones remotas y commits requieren autorización posterior.

## Review / Revisión

Read-only GitHub inspection confirmed default branch `main` at `ad76a0b5f3e5174c7db935fe48ecbcf09c845bd0`
and deployed branch `release/streamlit-rc1` at `df03b90ed8c649a80e3bd4a3676d0a477a399cb1`.
Local refs match. Sprint 11C remains uncommitted. The remote main workflow still
contains `0 18 * * *`, and it is the only workflow file on main. Last three visible
runs were successful **old** scheduled runs on 13–15 July 2026; they do not prove
current MAIN updates. A read-only `gh api` fallback confirmed workflow state
**disabled_inactivity**. No currently queued or in-progress runs were returned
during this review; recheck before rollout.

El cron remoto sigue definido; la copia local no lo elimina. Los runs antiguos no
validan el sistema actual. Confirmar estado y colas otra vez antes de actuar.

Branch list reports `protected:false` for both branches; repository rulesets query
returned `[]`. Detailed protection endpoint returned 403 for the integration.
No protection changes are proposed. Connected-user administration rights are not
the workflow token's rights. Read-only Actions settings inspection confirmed
`enabled:true`, `allowed_actions:all`, `default_workflow_permissions:read` and
`can_approve_pull_request_reviews:false`. No production secrets were inspected;
no settings were changed. Recheck these settings immediately before rollout.

The old workflow can still be scheduled if enabled; its current updater invocation
omits mandatory inputs and should fail argument parsing. Do not rely on that failure
as a safety gate. A release push can refresh the Streamlit **code**, even though the
snapshot bytes remain unchanged. Replace main's workflow first to remove the cron
window; replacement does not cancel already queued old jobs.

Primero sustituir el workflow de `main`; después publicar el código release. El push
de release puede reiniciar Streamlit, pero no debe cambiar el snapshot ni sus datos.

## Exact file assignments / Archivos por rama

**main: exactly one file / exactamente un archivo**:
`.github/workflows/daily-update.yml`. No merge/cherry-pick of the release commit.

**release/streamlit-rc1: explicit reviewed list / lista explícita**:

```text
.github/workflows/daily-update.yml
backend/config/actions-regression.json
backend/src/riskbex/actions_update.py
backend/src/riskbex/cloud_snapshot.py
backend/scripts/run_actions_update.py
backend/scripts/run_actions_offline.py
backend/tests/test_actions_update.py
backend/tests/test_actions_cloud.py
backend/tests/test_actions_offline.py
backend/docs/sprint-11c/README.md
backend/docs/sprint-11c/daily-update.yml.disabled
backend/docs/sprint-11d/README.md
cloud/approval.json
cloud/streamlit_app.py
```

`cloud/publication` is already tracked and **must not be staged or changed**. The
production template remains outside `.github` with a `.disabled` extension; it is
not a trigger. No changes to Docker, requirements, original receipt, mathematical
implementation, frozen models or deployment coordinates are included.

## Safety and approval / Seguridad y aprobación

Manual `workflow_dispatch` only; job accepts `main` only and checks out the deployed
branch. Required `release_sha` input must match checkout HEAD; the controller checks
this and a clean tree before installing or executing release code, and the offline
script checks the SHA again. A changed branch fails preflight. Pinned
checkout/setup-python actions, Ubuntu 24.04, Python 3.11.14,
20-minute timeout, `contents:read`, credentials not persisted, no production secrets,
no reusable/live workflow invocation and no upload/publication steps.

The offline-only script has no live/publish option. It verifies package/runtime,
receipt and approval, blocks real yfinance downloads, network sockets and real Git
mutations during tests. Promotion tests simulate **all** Git commands: they no
longer create temporary commits. Replay writes only disposable directories. It
compares all source snapshot files and Git status/HEAD before/after and fails on
changes, failures or skipped required checks. Dependency installation needs Internet;
“offline” means no market/API retrieval, not an air-gapped package install.

El test no puede acceder al modo de publicación mediante argumentos. Los datos se
reproducen con fixtures; no hay commits ni pushes reales, tampoco en repos temporales.

Default Cloud bundle now always requires a well-formed independent approval, even
with a valid legacy checksum. Schema, SHA, market date, version, allowlist and every
payload hash are checked by the shared lightweight verifier. Current approved
snapshot remains:

```text
Market session: 2026-11-16
Version: 7aa57e33635247917fa6b2e375fe2581eed428283e4509a39a00c201a0b46819
Snapshot SHA256: 0d5b6d863ca2e342c24631a7b37cde7437eaa7513bd7afad8f6fa347f0b538bb
```

Streamlit exports root secrets as environment variables. A legacy environment value
matching `st.secrets.RISKBEX_SNAPSHOT_SHA256` is therefore superseded by Git approval;
a distinct explicit environment pin remains strict. Custom bundle paths still need
a valid pin. No live secret edits are required for this snapshot/code rollout.
A visitor who has seen a later market date cannot silently move backwards in the
same session. Future `promote` rejects non-advancing dates and wrong predecessors.
A fresh process cannot independently detect replacement of **both** bundle and
approval by an older, valid, trusted Git revision; Git write/review control remains
the rollback authority. Intentional rollback needs a reviewed commit; affected
existing sessions must be restarted. No independent anti-replay service is claimed.

Una aprobación antigua no valida un bundle nuevo ni corrupto. Restaurar a la vez un
bundle y su aprobación anteriores es una decisión Git explícita, no algo que un
verificador sin estado pueda distinguir de un rollback autorizado.

## Proposed operations — DO NOT execute yet / Operaciones propuestas, no ejecutadas

Run each phase only after its authorization; inspect every diff before committing.
Stop on divergence or unexpected files, do not force/reset/rebase. Commands assume
repository root, Bash and an existing authenticated `gh` CLI; do not install or
configure credentials as part of this procedure.

### 1. Local release commit / Commit local release

```bash
set -euo pipefail
cd /home/apalo/projects/RiskBEX
test "$(git branch --show-current)" = 'release/streamlit-rc1'
git diff --cached --quiet
git fetch origin main release/streamlit-rc1
test "$(git rev-parse origin/main)" = 'ad76a0b5f3e5174c7db935fe48ecbcf09c845bd0'
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/release/streamlit-rc1)"
release_snapshot_tree=$(git rev-parse HEAD:cloud/publication)
git add -- .github/workflows/daily-update.yml \
  backend/config/actions-regression.json \
  backend/src/riskbex/actions_update.py backend/src/riskbex/cloud_snapshot.py \
  backend/scripts/run_actions_update.py backend/scripts/run_actions_offline.py \
  backend/tests/test_actions_update.py backend/tests/test_actions_cloud.py \
  backend/tests/test_actions_offline.py \
  backend/docs/sprint-11c/README.md \
  backend/docs/sprint-11c/daily-update.yml.disabled \
  backend/docs/sprint-11d/README.md cloud/approval.json cloud/streamlit_app.py
git diff --cached --check
git diff --cached --exit-code -- cloud/publication
git diff --cached --stat
git diff --cached --name-only
# Review exact 14-file list above before the separately authorized commit.
git commit -m 'Prepare guarded offline GitHub Actions validation'
release_sha=$(git rev-parse HEAD)
test "$(git rev-parse HEAD:cloud/publication)" = "$release_snapshot_tree"
```

### 2. Remove main cron before the release push / Quitar cron antes del push release

```bash
project_dir=/home/apalo/projects/RiskBEX
main_worktree=/tmp/riskbex-11d-main
# This must be a NEW path. Work from the latest fetched origin/main only.
test ! -e "$main_worktree"
git worktree add --detach "$main_worktree" origin/main
git show "$release_sha:.github/workflows/daily-update.yml" > "$main_worktree/.github/workflows/daily-update.yml"
git -C "$main_worktree" add -- .github/workflows/daily-update.yml
test "$(git -C "$main_worktree" diff --cached --name-only)" = '.github/workflows/daily-update.yml'
git -C "$main_worktree" diff --cached --check
git -C "$main_worktree" diff --cached
# Authorize this single-file commit and normal push separately.
git -C "$main_worktree" commit -m 'Replace legacy cron with manual offline validation'
main_sha=$(git -C "$main_worktree" rev-parse HEAD)
git -C "$main_worktree" push origin HEAD:refs/heads/main
# Verify remote file is byte-for-byte the reviewed manual workflow.
remote_workflow_blob=$(gh api 'repos/apalomo75/RiskBEX/contents/.github/workflows/daily-update.yml?ref=main' --jq '.sha')
test "$remote_workflow_blob" = "$(git rev-parse "$release_sha:.github/workflows/daily-update.yml")"
gh api 'repos/apalomo75/RiskBEX/contents/.github/workflows?ref=main' --jq '.[].name'
gh api 'repos/apalomo75/RiskBEX/actions/workflows/daily-update.yml' --jq '{state,path}'
gh run list --repo apalomo75/RiskBEX --workflow daily-update.yml --limit 20 \
  --json databaseId,event,status,headSha
```

Inspect main's reviewed YAML: only workflow_dispatch, no schedule/push trigger.
If an old scheduled run is queued/running, stop and request authorization to cancel
it before continuing. The workflow was disabled for inactivity during this review.
Enabling the **verified manual-only replacement** requires explicit authorization;
do not enable the legacy cron. After that authorization and the blob comparison:

```bash
gh workflow enable daily-update.yml --repo apalomo75/RiskBEX
```

Do not infer cron removal merely from an inactive workflow state.

### 3. Release push and unchanged snapshot check / Push release y snapshot idéntico

```bash
git push origin HEAD:refs/heads/release/streamlit-rc1
test "$(git rev-parse HEAD:cloud/publication)" = "$release_snapshot_tree"
remote_snapshot_sha=$(gh api 'repos/apalomo75/RiskBEX/contents/cloud/publication/snapshot.json?ref=release%2Fstreamlit-rc1' --jq '.sha')
test "$remote_snapshot_sha" = "$(git rev-parse "$release_sha:cloud/publication/snapshot.json")"
# Record release_sha, main_sha and release_snapshot_tree before dispatch.
```

Normal push rejection means another commit intervened: stop, inspect and revalidate.
No history rewriting is allowed. Streamlit may rebuild the code now; the publication
session/version/checksum must remain the baseline above. Use its existing URL and
logs; do not invent a hosted success result or change live settings.

### 4. First manual dispatch / Primera ejecución manual

UI: repository **Actions → MAIN controlled offline validation → Run workflow → main**.
Enter the recorded full `release_sha`. Confirm the displayed workflow is the new
manual-only one. Equivalent command, only after dispatch authorization:

```bash
gh workflow run daily-update.yml --repo apalomo75/RiskBEX --ref main -f release_sha="$release_sha"
gh run list --repo apalomo75/RiskBEX --workflow daily-update.yml --event workflow_dispatch --limit 5
# Substitute the actual run ID after matching main_sha and the recorded start time.
gh run watch RUN_ID --repo apalomo75/RiskBEX --exit-status
gh run view RUN_ID --repo apalomo75/RiskBEX --log
```

Expected evidence: workflow event `workflow_dispatch`, controller SHA `main_sha`,
checkout SHA `release_sha`, Python 3.11.14, successful pinned install and `pip check`,
verified package/receipt/approval, all required tests passed with zero skips, and final
JSON `source_snapshot:unchanged`, `source_checkout:unchanged`, `live_downloads:0`,
`actual_git_commits:0`, `actual_git_pushes:0`. No publication artifact upload or release
commit is expected. Record run URL and duration. A skipped job or green historical
scheduled run does not count.

Afterward, compare remote release HEAD to `release_sha`, verify unchanged snapshot
Git tree/blob and SHA256, then check Streamlit's existing market date, version, six
views and simulator. A hosted build failure is separate from a data change; inspect
logs and stop. Existing stale-data status may change with wall-clock time and must
not be “fixed” by changing dates.

```bash
test "$(gh api 'repos/apalomo75/RiskBEX/git/ref/heads/release/streamlit-rc1' --jq '.object.sha')" = "$release_sha"
remote_snapshot_tree=$(gh api "repos/apalomo75/RiskBEX/git/trees/$release_sha?recursive=1" \
  --jq '.tree[] | select(.path == "cloud/publication") | .sha')
test "$remote_snapshot_tree" = "$release_snapshot_tree"
sha256sum cloud/publication/snapshot.json
```

## Validation and blockers / Pruebas y pendientes

Local guarded runner: **43 passed, zero skips**, 127.594 s test time / 131.11 s wall,
266,448 KiB peak RSS. This includes 3 safety, 7 bootstrap/replay, 25 original MAIN
pipeline (including regression) and 8 approval/Cloud entrypoint tests. Final JSON
confirmed source snapshot/checkout unchanged, no live downloads and no actual Git
commits/pushes. The workflow's additional shell preflight is validated separately
after its addition; no quantitative suite is repeated for that workflow-only change.
No GitHub-hosted execution occurred. Original receipt and model outputs are intact.

Python 3.13 Cloud suite: **6 passed** in 81.752 s, explicitly pointed at the actual
`cloud/publication` path, including six views in both languages, simulator numerical
equivalence, research, freshness, corrupt/missing bundle and wrong-pin behavior.
Total: **49 focused tests passed**. The updated workflow safety method passed again
after the controller-only preflight addition. YAML parsing, Bash syntax and five
simulated controller cases (matching SHA, mismatch, malformed/missing SHA and dirty
checkout) passed. Snapshot file hashes match the pre-test inventory and Git diff
checks pass. No dependency installation was performed. Hosted install remains pending.

Before the first hosted run: authorize commits/pushes/dispatch and enabling the
verified manual replacement, recheck Actions state/old queues, and deliver the same
reviewed workflow in both branches. Fresh hosted dependency
resolution remains unproven and may fail clearly without touching publication.
Redistribution rights and calendar extension remain blockers for **future live
publication**, not for this offline replay of existing approved data. No production
credentials or write token are required for this run.

Antes del primer run: autorización de operaciones, revisión de estado/colas y política
Actions. La instalación limpia es una comprobación pendiente del runner real. No se
activa programación ni publicación de mercado en este sprint.

Sources: [remote main workflow](https://github.com/apalomo75/RiskBEX/blob/main/.github/workflows/daily-update.yml),
[Streamlit root-secret environment behavior](https://docs.streamlit.io/develop/concepts/connections/secrets-management).
