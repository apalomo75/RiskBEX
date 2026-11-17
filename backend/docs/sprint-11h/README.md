# Sprint 11H — Controlled cloud publication preparation

## State and execution evidence

No remote settings, schedules, dispatches, snapshots, models or repository commits
were changed by this sprint. Local Git transaction tests use temporary repositories.
The workflow is manual-only and additionally requires a repository enable variable;
the committed rights policy is blocked. Naming environments alone does not protect
them: enforce required reviewers, prevent self-review, restrict deployment to main,
and verify the repository plan supports those protections before activation.

[Run 44092452719](https://github.com/apalomo75/RiskBEX/actions/runs/44092452719)
passed 45 tests. The live step ran at 13:27:19–13:27:20 UTC on November 17
(14:27 Madrid), before the 20:00 local eligibility threshold. Given the approved
November 16 session, `candidate()` returned unchanged before calling the provider.
Thus it was a no-op, not evidence that November 17 live data was ingested. This is
an inference from logs plus reviewed code, not recovery of the deleted report.
The generic success message did not distinguish branches; stdout/stderr were
suppressed and both candidate and detailed report were deleted. They cannot now
be reconstructed from surviving artifacts.

The new allowlisted JSON reports previous approved session, latest validated
session, new-session count, generated/skipped/failed outcome, integrity/regression
gates, status and monotonic duration. On a no-op the latest validated session is
the approved session; there is no newly exported candidate. On failure the candidate
session/count remain null, never a fabricated zero. Gates not reached are not_run.
Duration covers the adapter, not dependency installation or environment review.
Private table rows, provider errors and full outputs stay out of the JSON/logs.
Abrupt runner termination can prevent a final summary: use the Actions conclusion
as authoritative in that case. Dry-run JSON remains in logs after cleanup.

## Publication and custody

`.github/workflows/cloud-publication.yml` has distinct read-only candidate and
protected write promotion jobs. Both execute an exact reviewed release SHA, with
frozen runtime and existing offline gates; the controller SHA must match main's
executing commit. Code for this sprint must be reviewed and installed on BOTH
branches before use; the workflow never overlays files onto the clean release.
No training or Docker is involved.

Only candidate/, approval.json and custody.json cross jobs, as one authenticated
GPG AES256 encrypted artifact, retained for one day. The detailed private report,
seed, restore tree and attempts are excluded. A high-entropy custody key is scoped
to the two protected environments, never Streamlit. Configure the SAME random
value for PUBLICATION_CUSTODY_KEY in each environment. Upload of encrypted data
still requires organizational approval of GitHub storage and the licensor's
storage terms. No plaintext artifact may be uploaded, including on failure.

The promotion job downloads only its own run/attempt artifact name, verifies the
ciphertext SHA from its upstream job, checks GPG integrity, extracts regular files
with traversal filtering, and checks custody binding to repository, run, attempt,
controller SHA, release predecessor, approval and snapshot digests. Retrying failed
jobs alone increments run_attempt and deliberately rejects old custody: rerun the
whole workflow with newly reviewed current heads. No trust in ephemeral runner
files is assumed. Runner cleanup and artifact expiry are separate safeguards.

`actions_update.promote` reuses bundle allowlist/hash verification and checks rights,
regression receipt, model/implementation/calendar identity, frozen training prefix,
full approved price prefix, candidate session count, target date, predecessor and
strictly advancing approval date. The workflow additionally requires live provenance and rejects a candidate that
becomes stale while awaiting protected approval.
The one commit stages ONLY cloud/publication and cloud/approval.json. Normal push
updates the remote ref atomically. Copy/commit/push failure leaves the remote
snapshot unchanged; discard the dirty disposable checkout. A simultaneous remote
commit causes rejection, with no rebase/force/retry. A network disconnect AFTER a
server accepted a push is ambiguous: inspect the remote head and approval before
retrying. A failed job must never imply rollback of an already accepted push.

`contents:write` exists only in the protected promotion job; Actions artifact access
uses same-run built-in credentials. Git credentials are not persisted by checkout
and are exposed only to the publish step. A GitHub token cannot be path-scoped:
branch rules, environment reviewers and reviewed code supply the additional boundary.
Branch rules must explicitly support this bot's normal fast-forward push; do not
silently bypass required PR rules. Protected environment approval authorizes the
reviewed policy and encrypted candidate; it does not expose private candidate rows.

The existing Cloud entrypoint reads Git-versioned approval, validates the payload,
and clears stale caches by version, including with an obsolete legacy Secret.
The existing Cloud regression test exercises that path. No daily Streamlit Secrets
edit is needed. Hosted deployment recognition is a separate first-publication check;
this sprint does not claim a hosted end-to-end deployment was exercised.

## Rights inventory: all six public views

Inspected dashboard renderers and simulator UI; no public presentation was changed.
The histories have user-selectable windows, so a short default chart does not bound
what can be reconstructed. Table cells, chart tooltips and image assets all count.

| View | Provider observations / reconstructible history | Derived content requiring scope review |
|---|---|---|
| Welcome / Home | Dated ibex_close series in price/regime chart and hover values | Filtered state, regime exposure, publication session/freshness |
| Overview | Latest IBEX close, dated price/regime series | Filtered Markov and next-session XGBoost probabilities/states; CVaR exposure targets |
| Performance | Buy & Hold growth and drawdown reconstruct normalized provider returns; archived backtest table exposes benchmark/strategy returns and curves (last 250 rows) | Gross/net strategy growth, drawdowns, exposure, turnover/costs, annualized return/volatility, Sharpe/Sortino, CVaR and comparison metrics |
| Investment Simulator | Selectable published session history; Buy & Hold capital/equity curves reconstruct normalized returns for selected windows | Strategy capital, profit/loss, returns, drawdown, costs, exposure and performance/risk comparisons based on user capital |
| Risk Monitor | Selected historical ibex_close in Decision Explorer; price chart/hover data | Current/history CVaR, drawdown, volatility, risk_score, skewness; regime/ML probabilities, mapping, previous/current targets and exposure changes |
| Research & Methodology | daily_returns_ibex35 image; tail ret_1d timeline/worst-session table; benchmark cumulative curves and return/drawdown history | Markov/ROBUST academic comparisons, transition/duration and uncertainty; VaR/CVaR, downside/total volatility, skewness, return/risk images; thresholds, tail metrics and strategy results |

Raw open/high/low/volume provider diagnostics are not explicitly rendered by these
views. Published CSVs and Git blobs are an ADDITIONAL distribution surface: the
allowlist includes complete prices.csv, features.csv, signals.csv, backtest.csv,
metrics.csv, turnover.csv, latest.json, model mapping, thirteen research CSVs and
six chapter-2 figures, not merely the UI's selected rows. A licence limited to
visual display is insufficient for the current public Git architecture.

[Primary-source review evidence](evidence/source-review.json) records URLs and
observations, including the inaccessible Yahoo terms. [yfinance's notice](https://github.com/ranaroussi/yfinance)
does not grant data rights. [BME's current contract framework](https://www.bolsasymercados.es/en/bme-exchange/prices-and-markets/market-data-services/documentation/data-feeds.html)
identifies display and non-display licensing effective August 23, 2026; obsolete
2023 agreements are not relied upon as current permission. No supplied licence
establishes public rights for ANY Yahoo/IBEX observation or derived category above.
Independently authored explanatory prose/code is distinct from market-data rights;
that does not authorize publishing the data-bearing bundle.

Required written confirmation: automated collection, IBEX index usage, historical
coverage back to 2000, non-display model processing, public display, derived products,
reconstructible histories, images, retention and unrestricted public Git redistribution.
Obtain it from the relevant rights holders/authorized vendor and verify the whole
chain, not just a website provider's assent. If unavailable, migrate to a provider
with explicit permitted scope, through a separately authorized frozen-prefix and
methodology compatibility review; provider replacement is not silently safe.
No derived indicator/probability/signal is assumed exempt. This is a rights
assessment of available evidence, not a legal determination of a contract not held.

`backend/config/publication-rights.json` is blocked. Missing/malformed/expired
receipts, incomplete scope, absent reviewer/licence reference or mismatched evidence
fail before mutation. To unblock requires a reviewed status=verified receipt with
provider exactly 'Yahoo Finance / IBEX 35', all scopes listed in publication_control.SCOPES,
valid_until (ISO date), reviewed_by, licence_reference, and evidence_sha256 matching
backend/config/publication-rights-evidence.txt. Use a non-sensitive, legally reviewed
attestation reference; keep confidential contracts in approved private storage.
Do not set verified merely because an owner approves publication. A replacement
provider needs an explicit code/policy change and new review.

## Calendar and dormant scheduling plan

The [official BME page](https://www.bolsasymercados.es/es/bme-exchange/negociar/calendario-del-mercado.html)
still describes 2026; targeted official-domain searches did not verify 2027 dates.
No 2027 dates are installed or inferred from TARGET/weekdays. Evidence records
known 2026 holidays and 14:00 half days. Existing coverage fails closed, including
December 31, 2026 when a next-session target would enter 2027.

When an authoritative BME circular exists: archive its URL, retrieval/publication
dates and exact PDF hash, obtain a named review, extend the versioned operational
calendar to 2026+2027 with official holidays/half days, and test every published
closure, half day, December/January next-session rollover, DST boundaries and
coverage expiry. Existing historical manifests stay unchanged. Changing calendar.py
would invalidate implementation-bound regression receipts; obtain fresh offline
regression evidence rather than editing a hash to bypass a stale receipt.

Dormant UTC plan: 19:17 UTC every weekday (20:17 CET / 21:17 CEST), with recovery
at 21:47 UTC. These both follow the 20:00 Europe/Madrid policy year-round; Python's
calendar remains authoritative for holidays/half days and delayed execution. Do not
add active cron yet. Avoid an 18:xx UTC winter trigger. Delivery is still validated;
the 20:00 policy is neither exchange close time nor a provider guarantee.

[GitHub documents](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
that schedules can be delayed/dropped and inactive public repos can lose schedules.
The dormant `.github/cloud-publication-autonomous.yml.disabled` template prepares schedule events:
it uses the executing reviewed main SHA and freshly fetched approved release head,
rechecks it in both jobs, and requires RISKBEX_AUTONOMOUS_AUTHORIZED in addition to the publication enable flag.
Do not simply paste cron into the manual workflow: its required dispatch inputs
are deliberately absent on scheduled events. The template is outside workflows/ and cannot run; installing it remains a reviewed activation diff.

For unattended publication, human environment review cannot remain required on
each run: after the first manual acceptance, separately approve a protected
automation environment/policy (branch restrictions, no unreviewed controller changes,
least permissions, licence expiry gate, same custody binding). If those controls
cannot be enforced under the repository plan, remain manual. No unattended approval
bypass is prepared or activated here.

Enable Actions failure notifications for named operators and verify receipt.
The workflow emits error annotations on promotion failure; it does not send messages
or provision alert services. Before autonomy, configure an independently hosted
dead-man freshness monitor (not the user's PC/VPS) to compare the approved session
with the calendar after the recovery deadline; a GitHub-only schedule cannot detect
its own complete outage. Alert on missing runs, provider/gate/rights/calendar failure,
rejected push and hosted snapshot failing to advance. Expose only dates/status.

A missed-session run downloads the full missing interval from the last approved
session with overlap; the existing pipeline rejects gaps/revisions and recomputes
causal history. Never publish partial history or roll back to recover. A failed
primary run can recover on the later whole-workflow run with fresh custody/heads;
a weekend/holiday retry is a truthful no-op. Persistent failure keeps last approval
and stale status; operator inspects the first failing gate. Do not retry bad data,
licence or calendar failures blindly.

## First manually approved publication — exact operator sequence

1. Resolve the written-rights blocker and review the complete receipt/evidence;
   resolve calendar coverage for the intended session. Do not proceed otherwise.
2. Review and commit/push this implementation through the separately authorized
   process onto main and the release branch, WITHOUT changing cloud/publication
   or approval. Record full controller and current release SHAs. No such commit or
   push was performed here. Review runtime locks and pinned actions before use.
3. Verify enforced environments publication-candidate and public-publication,
   main-only deployment, required reviewers, no self-review, supported branch rules,
   and identical high-entropy PUBLICATION_CUSTODY_KEY secrets in both environments.
   Approve encrypted GitHub artifact storage/one-day retention. Configure operator
   failure notifications; leave all schedules absent.
4. Separately authorize one live download AND one public publication. Set repository
   variable RISKBEX_PUBLICATION_ENABLED=true only for this authorized trial. In
   Actions select MAIN protected cloud publication, main, controller_sha=<reviewed
   main SHA>, release_sha=<current reviewed release SHA>, authorize_live_download=true.
   Dispatch only after the 20:00 Madrid threshold for the intended session.
5. Approve candidate environment after checking hashes/scope. Review the safe JSON;
   generated must show the intended validated session and passed gates. If skipped,
   there is no artifact/promotion and no new-data success claim. Approve publication
   environment only after the successful candidate job and matching run/predecessor.
6. Check one normal release commit changed only snapshot and approval. Read remote
   approval and verify hosted Cloud shows that session/version, healthy six views,
   refreshed cache and unchanged MAIN/ROBUST roles. No daily Secrets edits.
   A hosted failure is an alert, not grounds for automatic rollback.
7. Set RISKBEX_PUBLICATION_ENABLED=false after the trial. Record actual hosted and
   conflict/notification evidence before requesting autonomous operation approval.

## Enabling autonomous operation afterward

1. Resolve calendar, rights, environment-plan, encrypted-storage, hosted smoke and
   notification/dead-man-monitor acceptance; first manual advancing run must pass.
2. Review the dormant .github/cloud-publication-autonomous.yml.disabled template as
   a separate activation diff, with UTC cron 17 19 * * 1-5 and recovery cron
   47 21 * * 1-5, schedule-aware SHA/input resolution, timeout and freshness alerts.
   Preserve isolated concurrency group riskbex-protected-publication-v2; never use
   anomalously blocked riskbex-cloud-publication.
3. Obtain explicit authorization for recurring downloads and publications and the
   protected unattended approval policy. Install the reviewed diff on main, enable
   that policy, RISKBEX_PUBLICATION_ENABLED and RISKBEX_AUTONOMOUS_AUTHORIZED,
   replacing the manual workflow with the reviewed template under workflows/; verify first scheduled result,
   holiday/no-op and recovery behavior. Inspect Cloud recognition against remote
   approval. Disable the variable immediately if any gate/monitor misbehaves.
4. After recovery evidence is retained, separately authorize disabling/removing
   runner-diagnostic.yml and main-offline-recovery.yml and their temporary notes.
   Keep the old blocked group isolated; do not dispatch it to test cleanup. Retain
   daily-update offline gates and the manual dry-run until replacement acceptance.

## Prioritized remaining blockers

1. No verified market-data distribution rights: hard block on any new publication.
2. The successful live run was pre-cutoff no-op: an authorized post-cutoff advancing
   live run and first hosted publication are still required.
3. Enforced environments, encrypted custody secret/storage acceptance, bot branch
   permission and real hosted recognition have not been configured/tested remotely.
4. Official 2027 calendar unverified; final 2026 target rollover remains blocked.
5. Installing the dormant schedule template and independent alerts require a separately
   reviewed authorized activation diff. Cron reliability is not an availability SLA.

## Focused validation results

Existing Python 3.11.14 fin-forecasting environment; numerical thread limits all 1.
No dependency installation, live retrieval, external push or historical full-suite run.

- Initial affected batch: test_publication_control, test_live_dry_run,
  test_actions_update, test_daily_pipeline, test_actions_cloud: **55 passed**,
  zero skips, 153.331 seconds. Quantitative integrity and no-look-ahead gates included.
- A later live-source check initially rejected synthetic replay fixtures (one failure,
  four errors in the intermediate 17-case batch). Corrected by requiring Yahoo source
  only in protected live mode; no gate was removed or weakened. The affected replay,
  simulated-live rejection and real temporary-Git transaction cases passed on retry.
- Subsequent affected/new checks: **11 passed** across batches of 5, 2, 1, 2 and 1
  (34.217s, 0.372s, 7.961s, 1.642s, 1.042s). They cover custody binding/digest rejection,
  final source verification failure revoking success, candidate integrity failure,
  rights rejection before Git mutation, stale approval, dormant schedule resolution,
  and actual GPG roundtrip/tamper rejection with synthetic bytes.
- Final suite inventory is **62 distinct tests** (17 publication controls + 45 existing
  affected tests). All have passing coverage through the initial batch and targeted
  follow-ups; the entire final inventory was not rerun redundantly as one batch.
- Workflow and dormant-template YAML parsed; changed Python sources parsed; Git
  whitespace validation passed. Publication/model paths have no tracked diff.
- Real Git tests use temporary local bare repositories: advancing push creates one
  commit; hook rejection and concurrent commit reject publication and preserve the
  remote approval. No claim of remote GitHub or hosted Streamlit acceptance is made.
