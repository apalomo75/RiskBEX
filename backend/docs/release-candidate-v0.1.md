# RISKBEX v0.1 — Release candidate validation

Validation date: 2026-11-08. Scope: existing product, stored publications and local
hosting configuration. No inference, training, market downloads, dependency
installation, image builds, scheduling, deployment or commits were performed.
Pre-existing Sprint 6B changes were preserved.

## 1. Passed checks

- The validated MAIN v1 publication ends on **2026-11-06**, was generated on
  **2026-11-07 at 19:54:56 UTC**, and targets **2026-11-09**. Monitor distinguishes
  these dates and displays IBEX close **19,369.50**. Legacy academic payloads
  cannot supply the operational header date.
- Freshness is recalculated using the reviewed calendar: the publication is
  current over the weekend and becomes stale after Monday's availability
  threshold if no new publication exists. Simulated/historical data is labelled.
- Operational API requests read validated snapshots; pointer changes during a
  request do not mix versions. Missing/corrupt publications return 503.
  `POST /run-update` returns **403 disabled**, without invoking a subprocess.
  This route still exists but cannot perform an update; no other write route
  was found in the API route modules.
- Markov filtered probabilities and XGBoost next-session forecasts are distinct.
  Verified mapping: **0 = Low Risk, 2 = Medium Risk, 1 = High Risk**. Final targets:
  Regime-Based **59.06%**, ML Hard **59.06%**, probability-weighted **63.25%**.
- Results uses one publication for Buy & Hold and all three adaptive strategies,
  with **1,496 common evaluation sessions, 2021-01-05 through 2026-11-06**.
  Stored returns, prior-session exposure, probability weighting, costs and metrics
  reconcile. UI discloses the one-session lag, log-return convention, gross/net
  basis, 10 bp exposure-change costs and excluded costs/entry/liquidation.
  Original TFM MAIN/ROBUST results remain separately labelled academic references.
- Decision Explorer verifies all **1,497 published signal sessions**, closing
  prices, next-session dates, mapping, weighted allocation and previous-session
  changes. The first session has N/A comparisons. Invalid sessions return 404;
  missing/inconsistent mapping or targets fail closed. Records are explicitly
  historical backtests, not live executions; unavailable closes remain N/A.
- Offline Streamlit AppTest covers Welcome links, all six tabs, operational
  charts, unavailable/stale states, historical selection and Results controls.
  The added integration check renders real ASGI API responses, visits all six
  Research figure choices and exercises ROBUST selectors in Models, Research
  and Tail Risk. No visible exceptions, missing-figure warnings or API errors
  are accepted. English literal checks pass. Technical figures are preserved.
- Compose validates. API/dashboard use unprivileged users, read-only roots and
  dropped capabilities. API store/data mounts are read-only; dashboard accesses
  the store through the internal API. The persistent host store survives service
  recreation by design. Only dashboard port **127.0.0.1:8501** is published;
  API 8000 is internal. Updater requires the explicit `scheduled` profile.
- Runtime files and `.env` are ignored. Tracked credential-file checks and a
  targeted scan for private keys/AWS access IDs/GitHub token signatures found no
  matches. Docker context uses an allowlist. This is a scoped check of the current
  tree, not an audit of all Git history or every possible secret format.

Publication version:
`729b9de228fd3e9100e95e93a81301590a17341f6033078db6e470a115e31335`.

## 2. Defects found and fixed

No reproducible release-blocking product defect was found. Added
`tests/test_release_candidate.py` to close the real-response UI coverage gap.
During validation its test adapter was corrected to use AppTest's `button_group`
for segmented controls; duplicate imported test discovery was also removed.
Application, quantitative code, model packages and historical artifacts are unchanged.

## 3. Remaining release blockers

No application blocker identified within the tested scope. Public infrastructure
has not been provisioned or validated: TLS/reverse proxy, host access controls,
backups/recovery, logs and stale-publication monitoring remain hosting acceptance
tasks. Keep the API private and updates disabled.

Docker daemon access here is denied at `/var/run/docker.sock`; this is **not a
failed build**. Reused operator evidence from WSL: images built successfully,
`riskbex-api-1` and `riskbex-dashboard-1` healthy, dashboard-to-API `/latest-risk`
HTTP 200, and recreation persistence **“Persistencia OK”**. These are
operator-reported results, not container executions repeated in this environment.
Reader permissions and profile isolation were checked in configuration; actual
host scheduler state cannot be certified here.

The reviewed calendar covers 2026 only. Extend it through a separate reviewed
change before expiry. With scheduling intentionally disabled, continued freshness
requires separately authorised updates; present-day validity is not an uptime promise.

## 4. Non-blocking UX improvements

Reserve responsive layout, typography and chart legibility for manual browser
review. AppTest does not certify pixel layout or embedded image text. Streamlit
emits `use_container_width` deprecation notices; this pinned runtime still renders
the charts. Local font-cache warnings did not prevent rendering. No visual redesign
or figure deletion was performed.

## 5. Evidence and reproducibility

**Result: all 28 distinct targeted tests passed.** The initial invocation ran
33 tests because five imported integration tests were discovered twice: 32 passed
and the new UI check hit the test-adapter error described above. After correcting
the adapter and discovery, only the affected UI test was rerun: **1 passed in
55.177 seconds**. Final suite discovery confirms 28 tests; passing suites were
not rerun. Execution logs: `/tmp/riskbex-6c-tests.log` and
`/tmp/riskbex-6c-ui.log` (local temporary evidence).

Existing web environment; no new packages required. From `backend`:

```bash
PYTHONPATH=.:tests venv/bin/python -m unittest \
  test_operational_api test_operational_integration test_dashboard_ui \
  test_decision_explorer test_strategy_performance test_release_candidate -v
```

Tests read the existing `runtime/main-wsl-test` publication, use temporary stores
for corruption tests, patch the clock and route HTTP through ASGI. Requests from
Streamlit are intercepted; no external market access is needed. The complete
quantitative suite was not run.

From repository root:

```bash
docker compose --profile scheduled config --quiet
git diff --check
git check-ignore backend/runtime/main-wsl-test/current.json .env
git ls-files '*.env*' '*secret*' '*.pem' '*.key'
git grep -l -I -E 'BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}' -- ':!*.ipynb' ':!*.csv' ':!*.lock'
docker info --format '{{.ServerVersion}}'
```

Compose and whitespace checks pass; the signature scan returns exit 1 for no
matches. Docker info returns socket permission denied. Existing Docker
health/network/persistence reproduction commands remain in `sprint-6b.md`;
they need not trigger another build. Do not enable its optional updater profile
as part of release validation.

**Hosting assessment:** the existing read-only RISKBEX v0.1 application is
technically suitable for public hosting preparation. Public launch remains
conditional on the infrastructure acceptance tasks above; no hosting or automatic
updates were activated by Sprint 6C.
