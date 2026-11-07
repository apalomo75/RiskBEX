# Sprint 5B — Operational publication integration

The API defaults to `backend/runtime/main`, which has no publication in this
checkout. The validated Yahoo Finance publication is in `runtime/main-wsl-test`.
Setting the store exposed an adapter error: `risk_points` removed `regime_label`
before reading it. The adapter now retains that column. Publication pointers,
manifest hashes and artifact integrity checks remain enforced.

## Local startup

Run these commands from `~/projects/RiskBEX/backend` in separate terminals.
Stop any previous API instance on port 8000 first so the dashboard cannot connect
to an older process serving academic payloads.

API terminal:

```bash
cd ~/projects/RiskBEX/backend
export RISKBEX_OPERATIONAL_DIR="$PWD/runtime/main-wsl-test"
export RISKBEX_CALENDAR="$PWD/config/bme-2026.json"
venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Dashboard terminal:

```bash
cd ~/projects/RiskBEX/backend
export RISKBEX_API_URL=http://127.0.0.1:8000
venv/bin/streamlit run dashboard.py
```

`.env.example` documents configuration; it is not automatically loaded. Streamlit
reads publications exclusively through FastAPI. It does not select a second store.
A response without publication metadata and the validated signal is rejected,
preventing an academic date from appearing in the operational header. Missing or
invalid publications return HTTP 503; API connection failures remain visible.

## Dates and freshness

Last market data date comes from the publication, independently of generation
time and the next-session target. Last successful update is the validated
publication generation timestamp; the latest attempt status is shown separately,
so a subsequent failed attempt cannot imply a successful refresh. No separate
completion timestamp is recorded by the existing publisher.

The reference publication contains the November 6, 2026 close of 19,369.50,
Medium Risk probabilities of 91.50% (Markov) and 89.68% (XGBoost), targets of
59.06%, 59.06% and 63.25%, and a November 9 target session. These values are read
from stored results. On November 7, November 6 is the latest eligible session;
after the November 9 availability cutoff the same publication is stale.
Freshness is recalculated by the API using the reviewed exchange calendar, with
Streamlit responses cached for at most 30 seconds. Calendar coverage expiry
fails closed. No data is downloaded to determine freshness.

The Update Market Data button is disabled with an explanation. The legacy
`/run-update` endpoint remains disabled. No scheduling or deployment is enabled.

## Targeted validation

```bash
venv/bin/python -B -m unittest discover -s tests -p test_operational_integration.py -v
```

Tests use the existing publication, ASGI HTTP routing/serialization and Streamlit
AppTest with mocked transport. They cover real signal rendering, missing
publications, stale data, unavailable FastAPI and rejection of legacy payloads.
No models are loaded for inference and no training or downloads are invoked.
