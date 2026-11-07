# RISKBEX

Understand risk. Adapt exposure.

Monitor IBEX 35 risk through market regimes, Machine Learning and Conditional
Value at Risk. Explore quantitative signals, compare strategies and analyse their
historical performance. Author: Alejandro Palomo Morales.

The platform uses English exclusively. `dashboard.py` is the main Streamlit
interface, with six sections: Monitor, Explore, Results, Models, Research and Tail
Risk. MAIN is the only operational engine; ROBUST is an academic reference.
There is no cost simulator in v0.1.

## Run locally

From `backend`, using the existing environment and installed dependencies:

```bash
uvicorn main:app --reload
```

In another terminal:

```bash
streamlit run dashboard.py
```

`RISKBEX_API_URL` defaults to `http://127.0.0.1:8000`.
The API reads validated versioned MAIN publications from `runtime/main`, or
`RISKBEX_OPERATIONAL_DIR` when configured. If no usable publication exists, the
interface reports unavailable data; academic results are not presented as live.
Launching the interface does not download prices or retrain models. The manual
Update Market Data control invokes the existing operational update endpoint.

## Interface checks

```bash
python -B -m unittest discover -s tests -p 'test_dashboard_ui.py' -v
```

[Product navigation, implementation and future cost specification](docs/sprint-4c.md).
Historical methodology and acceptance records are preserved in their original form:

- [Sprint 1A: training interpretation, CVaR mapping and equivalence](docs/sprint-1a.md).
- [Sprint 1B: ML, historical strategies and model recovery](docs/sprint-1b.md).
- [Sprint 1C: purged XGBoost models, provenance and validation](docs/sprint-1c.md).
- [Sprint 1D: Markov reconstruction and ROBUST compatibility](docs/sprint-1d.md).
- [Sprint 2: frozen MAIN engine and incremental release plan](docs/sprint-2.md).
- [Sprint 3: versioned MAIN pipeline and operational commands](docs/sprint-3.md).

Frozen MAIN artifacts are in `model_packages/main-v1/`. Operational updates use
these models without retraining. Daily/full pipeline scripts require explicit
arguments, a valid regression receipt and a separate output directory. Legacy
scripts remain available for manual research use. Do not regenerate historical
artifacts as part of interface work. Scheduling and deployment require separate
authorisation.
