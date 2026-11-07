# RISKBEX v0.1 product interface

English is the default and only presentation language. Preserve internal identifiers,
API fields and historical research artifacts. Use Low Risk / Medium Risk / High Risk;
state identifiers do not imply risk order. Model probabilities remain labelled by
state number unless the frozen package supplies an explicit economic mapping.

## Implemented navigation and reuse

| Section | Reused content and product role |
| --- | --- |
| Welcome | Dark theme; product introduction, author and direct links |
| Monitor | Validated MAIN publication, separated Markov and XGBoost probabilities, three target exposures, market close, effective date, freshness and update status; recent aligned price/regime chart |
| Explore | Existing interactive risk metric chart, observation period selector, MAIN probability history, price/regime chart and adaptive exposure history |
| Results | Existing MAIN/ROBUST backtests, cumulative curves, drawdown, risk tables and raw observations |
| Models | Markov, XGBoost and CVaR explanations; existing regime history, uncertainty, transition heatmaps, durations and MAIN/ROBUST comparison |
| Research | All six original research figure choices and their explanatory text |
| Tail Risk | Existing stress events, tail cumulative curves, CVaR comparison, regime composition, metrics and worst sessions |

The six dashboard tabs remain available. A later navigation consolidation can move
Tail Risk into Research and move heatmaps, persistence and robustness comparisons
from Models into Research. No Simulator tab or placeholder is included.

Monitor labels stale, simulated or historical publications explicitly. Periods in
Explore end at the last available observation, rather than implying live data.
The price chart uses only prices and regime labels in the same MAIN history row.
The API adds optional `ibex_close` to `/historical-risk`; older payloads remain valid.
When close history is absent the chart explains its unavailability.
Original research PNG files already use English and remain unchanged.

## Future cost simulator specification — not implemented

Inputs: configurable initial capital, strategy, fixed fee per trade, proportional
fee, spread and slippage. Outputs: historical trade count and turnover, gross and
net results, and comparable cost scenarios. Define whether exposure changes count
as one rebalance or multiple instrument trades before computing trade fees.

Distinguish a theoretical IBEX 35 index from executable ETFs, futures, CFDs or other
instruments. Instrument multipliers, contract rolls, financing, cash treatment,
minimum fees and execution assumptions must be explicit before estimating net
results. Future intermediary comparisons require dated, verified tariff sources.
No provider rankings or tariff assumptions are introduced in this sprint.
The original academic 10 bp Transaction Costs assumption and backtest are unchanged.

## Local checks and startup

```bash
python -B -m unittest discover -s tests -p 'test_dashboard_ui.py' -v
uvicorn main:app --reload
# In a second terminal, from backend:
streamlit run dashboard.py
```

Interface tests mock HTTP and never invoke updates or market downloads. Their
lightweight Spanish-string check covers dashboard literals and current product
documentation; historical sprint documents and data artifacts are retained.
The existing Update Market Data button remains a manual operational action.
No scheduling, deployment, downloads or training were performed for Sprint 4C.
