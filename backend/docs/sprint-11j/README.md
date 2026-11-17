# Sprint 11J — daily state architecture

## Final architecture and audit

| Component | Decision |
| --- | --- |
| `private-daily.yml` | Sole daily computation path; manual only until separate review. Restore private Git state, run frozen MAIN, validate, atomically persist. |
| `cloud-publication.yml` | Separate protected publication; consumes approved private prices without network retrieval. Reuses candidate/export and the existing atomic promoter. Manual, rights gated. |
| Autonomous template | Retired in its existing dormant `.github/*.disabled` location; do not install. Its second retrieval path and schedule are obsolete. |
| Live diagnostic workflow | Retired under `.github/retired/`; adapter retained as the shared guarded candidate runner and its offline tests retained. |
| `daily-update.yml` | Retain as the single manual offline acceptance workflow. |
| `main-offline-recovery.yml`, `runner-diagnostic.yml` | Temporary manual diagnostics. Remove after the consolidated gate succeeds on hosted Actions and runner availability is confirmed. |

No new workflow is introduced. Production YAML contains no schedules. The historical
Sprint 11I activation instructions are superseded by this document.

## Persisted state and trust

Use `state/main-daily` **only inside a private repository**. The branch starts from
a reviewed checkout containing frozen models, regression receipt, exchange calendar,
`cloud/approval.json` and `cloud/publication`. The cloud path names are retained
internally to reuse existing validation/export code; this branch is not a Streamlit
publication source. Each successful update commits the bundle and its approval in
one commit. No prices, reports or plaintext candidates enter Actions artifacts or
caches. Repository access controls protect historical private commits; deletion of
a later branch does not revoke access already granted.

The workflow captures the branch head after checkout rather than pinning a permanent
publication head. The promoter requires the exact captured local predecessor, clean
checkout, exact private/public branch, advancing date, matching previous version,
full inventory, unchanged historical prefix, calendar completeness and quantitative
provenance. Frozen model identity is pinned to the reviewed controller manifest;
model files are independently hashed by the loader. Private calendar and regression
receipt must match controller bytes. Inference uses controller Python code, never
restored private branch code. Existing runtime/model/regression gates remain intact.

Normal pushes never force or rebase. A concurrent remote descendant or rejected
commit/push leaves remote state unchanged; discard the disposable checkout on any
failure. Workflow serialization handles ordinary runs; `VersionStore.lock` excludes
concurrent local computations. Failed validation and incomplete sessions never
promote. Repeated runs avoid retrieval. Missed sessions are downloaded together and
must be complete; calendar holidays/weekends resolve to the latest eligible close.
Outcomes are `updated`, `unchanged`, `failed`; persistence is reported separately.
If acknowledgement is lost after an accepted push, inspect the remote approval
before retrying: a transport error cannot prove that the server rejected the push.

Public preparation reconstructs a candidate against the *current public* predecessor
from sealed private prices, so multiple private days can be published together.
It does not copy a private approval over the public approval. Protected promotion
rechecks live provenance, latest eligible date, custody, predecessor and rights.
The existing atomic publisher remains the only publisher.

## Exact installation sequence (operator actions; not performed)

1. Review this working-tree patch together with the pre-existing Sprint 11G–11I
   files. Install the controller on `main`, and the publication scripts, tests,
   configuration and offline gate on `release/streamlit-rc1` using the normal
   reviewed change process. Do not change quantitative artifacts or receipts.
   Required new test: `backend/tests/test_daily_state.py`. Retired files must stay
   outside `.github/workflows`. No schedule belongs in this installation.
2. Before any live run, set repository variables to literal `false`:

   ```bash
   gh variable set RISKBEX_PRIVATE_DAILY_ENABLED --body false
   gh variable set RISKBEX_PRIVATE_STORAGE_AUTHORIZED --body false
   gh variable set RISKBEX_PUBLICATION_ENABLED --body false
   ```

3. Confirm repository visibility is private. If the Streamlit source repository
   must be public, this same-repository storage design must not be enabled; a
   separately reviewed private repository and scoped transport are required.
   Create protected environments `private-daily`, `publication-candidate`, and
   `public-publication`; require reviewers and restrict each to `main`.
   Allow `GITHUB_TOKEN` contents write for the two persistence/promotion jobs.
   Restrict state and release branches to the intended workflow/operator; prohibit
   force pushes/deletion. Ensure branch rules permit the intended bot normal push.
4. In a disposable private-repository clone, seed state from the reviewed release:

   ```bash
   git fetch origin main release/streamlit-rc1
   git switch -c state/main-daily origin/release/streamlit-rc1
   git push origin state/main-daily
   ```

   Verify the initial approved snapshot and model identities before authorizing
   private storage. This is an explicit later operator action, not a sprint action.
5. Create a 64-hex-character `PUBLICATION_CUSTODY_KEY` environment secret in both
   publication environments with the same value; do not log it. Keep rights blocked
   until documentary evidence covers every required scope. The rights receipt and
   evidence must be reviewed on the release branch, never fabricated.
6. Run manual `daily-update.yml` against the full installed release SHA. It installs
   `backend/requirements-docker.lock`, runs `pip check`, and executes the complete
   guarded gate on Python 3.11.14. Private runs also run this gate on the controller.
   No skips are allowed. Installation of dependencies requires operator authorization.

## Minimal activation and rollback

After hosted offline acceptance, review private persistence separately, including
repository visibility, credentials, branch rules, and retrieval authorization. Set
both private variables to `true`, manually dispatch `private-daily.yml`, and approve
its environment. Inspect approved state across two sessions and a repeated run.
A successful computation without an acknowledged persistence must not count as an
operational success. No live execution is authorized by this sprint.

Review public publication independently: resolve distribution rights; inspect the
private candidate and public predecessor; authorize `RISKBEX_PUBLICATION_ENABLED`;
dispatch `cloud-publication.yml` with current reviewed controller and release SHAs
and `authorize_publication=true`. Approve both environments. Verify Streamlit reads
the resulting approval and snapshot together. Expired/stale candidates require a
new preparation, never a forced push or custody edit.

Only after **both** end-to-end paths are separately accepted, authorize a future
change adding `17 20 * * *` and `17 22 * * *` to `private-daily.yml` (UTC; after the
configured Madrid availability delay, with daily recovery). Do not add another
workflow. Public publication remains manual unless separately authorized for
scheduling. GitHub timing is best effort. The BME calendar expires at year end 2026;
review its successor before activation extending into 2027.

Disable either path by setting its variables to `false`; cancel an active run
separately. Never reset state to an older snapshot to retry. Recover from the latest
approved remote commit and investigate integrity failures before retrieval.

## Cleanup and blockers

After hosted acceptance, remove temporary recovery/runner diagnostic workflows and
their operator notes through a reviewed patch. Archive remaining dormant templates
and retire the old Sprint 11I runbook links. Keep numerical, integrity and
look-ahead tests. Do not retire the shared dry-run Python adapter.

Blocking external acceptance: hosted runner execution (no dispatch allowed here),
private repository/environment/branch configuration, explicit retrieval/storage
authorization, real two-day persistence acceptance, distribution rights evidence,
and separately approved public/Streamlit end-to-end publication. No deployment,
rights verification, live download, schedule activation or remote write occurred.

## Verification record

Executed locally using `/home/apalo/miniconda3/envs/fin-forecasting/bin/python`
(**Python 3.11.14**, numerical thread limits all 1):

```bash
PYTHONPATH=backend python backend/scripts/run_actions_offline.py \
  --expected-release-sha "$(git rev-parse HEAD)"
PYTHONPATH=backend python -m unittest \
  tests.test_publication_control.RightsTests \
  tests.test_daily_state.PublicationStateTests
python -m pip check
```

Complete offline gate: **70 passed, 0 skipped, 205.693 seconds**. Two additional
publication/private-failure boundary tests were added and passed; the final targeted
check after extracting predecessor verification passed **5 tests, 0 skipped**.
Future complete gates include those two additional tests (72 total). The complete
suite was not unnecessarily repeated after the localized extraction. Existing
quantitative integrity, missed-session, concurrency, incomplete-session and
look-ahead checks passed. `pip check`: no broken requirements. YAML parsing of all
three retained workflows passed; none has a schedule. `git diff --check` passed.

Git commit/push transports in the offline transaction tests are simulated, including
rejections and concurrent predecessor changes. The former disposable Git mutation
test now uses this transport so the entire gate respects the no-commit/no-push
restriction and offline guards. Actual remote Git behavior and protected environment
configuration still need the separately authorized hosted persistence acceptance.
No test was skipped to obtain the gate result. This is exact-runtime **local**
acceptance, not a GitHub run or proof of a fresh lockfile installation. No dependencies
were installed; no remote dispatch was performed.

Changed implementation files: `backend/src/riskbex/actions_update.py`,
`backend/scripts/run_private_daily.py`, `backend/scripts/run_cloud_publication.py`,
`backend/scripts/run_actions_offline.py`; the private/public workflow YAML; private,
live-diagnostic and publication-control tests; and `test_daily_state.py`. The live
diagnostic YAML was moved to `.github/retired/live-data-dry-run.yml.disabled`.
Pre-existing unrelated working-tree changes were retained. Public snapshots,
quantitative code, frozen models and rights status were not modified.
