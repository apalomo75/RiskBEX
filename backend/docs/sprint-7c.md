# Sprint 7C — Historical investment simulation engine

## Interface

`simulate_investment(comparison, *, initial_session, initial_capital, start_date,
end_date, strategy, basis='net')` lives in
`src/riskbex/backtesting/simulation.py`. Supply the validated output of
`performance_snapshot(data)` and the first signal session of that same snapshot.
It has no providers, training, inference or write operations.

`GET /investment-simulation` accepts `initial_capital` (EUR), `start_date`,
`end_date`, `strategy` (`benchmark`, `regime_based`, `ml_hard`, `ml_proba`) and
`basis` (`gross`, `net`; default net). Each request resolves one immutable
operational publication and reuses the existing complete-comparison validator.
Existing endpoints and artifacts are unchanged. Invalid inputs or unpublished
boundary dates return 422; unavailable/incomplete publications return 503.
Capital must be finite, positive and at most EUR 1 trillion. Responses contain
at most 10,000 return sessions plus one anchor; longer windows are rejected,
never truncated or sampled. No sessions are interpolated.

## Mathematical and execution assumptions

Investment begins **at the start-session close**. The return labelled with that
session is excluded. Every published session after start through end inclusive
contributes once. The earliest possible anchor is the first published signal
session, immediately before the first realised return. At start=end there is
one capital point and no returns.

For stored daily log returns `r`, capital is `C(t) = C(0) × exp(sum(r))`, rebased
from the chosen anchor. Stored returns already apply the prior-close exposure:
no additional shift or multiplication is performed. Both strategy and Buy & Hold
use identical sessions. Uninvested cash earns zero; index log returns are scaled
by exposure under the existing publication convention.

Net replay uses stored net returns **without deducting costs again**. It retains
the published path's 10 bp per absolute exposure change, including any cost on
the first included return. This is a hypothetical allocation following an
existing historical path, not a newly executed portfolio. Entry and final
liquidation are omitted. Gross replay deducts no costs. Buy & Hold has no
modelled trading costs. Turnover includes the published boundary change, not a
fresh cash-to-position trade. Cost totals are log-return deductions, not EUR
invoices. ETF fees, brokerage, spreads, slippage, financing and taxes are omitted.

Drawdown includes initial capital, unlike the original backtest's unanchored
running peaks. Consequently an initial loss is recognised and maximum drawdown
can differ from the published metric. Volatility uses sample standard deviation
of included daily returns times sqrt(252), with null below two returns. Daily
CVaR reuses the existing mean signed log return at/below the empirical fifth
percentile, with null without returns. The anchor is excluded from daily metrics.
No forecasts or future observations enter these calculations.

## Worked example from stored history

Existing test publication: `backend/runtime/main-wsl-test`, version
`729b9de228fd3e9100e95e93a81301590a17341f6033078db6e470a115e31335`,
model `riskbex-main-v1`. This is historical simulation, not live execution.

```text
GET /investment-simulation?initial_capital=10000&start_date=2021-01-04&end_date=2026-11-06&strategy=ml_hard&basis=net
```

The 1,496 included returns run from 2021-01-05 through 2026-11-06.
ML Hard finishes at EUR 17,452.46: EUR 7,452.46 profit, 74.5246% return,
-23.1704% maximum drawdown, 12.9772% annualized volatility and -1.9303%
daily CVaR. Buy & Hold finishes at EUR 23,915.32 (139.1532% return).
ML Hard turnover is 45.629934 exposure units and the retained cost deduction
sums to 0.045629934 log return. A later start would be independently rebased.

## Validation and Sprint 7D limits

18 distinct targeted tests passed: synthetic capital/cost/date/causality checks,
full-window comparisons for every strategy and basis, one-snapshot read-only
API checks, existing operational API tests, and frozen mapping/alignment integrity.
Two initial test expectations were corrected and only those tests repeated.
No full quantitative suite, training, downloads, Docker, deployment or commits.

Sprint 7D must add controls, date selection, EUR formatting, assumption disclosures
and visible publication freshness. This sprint returns provenance/freshness and
structured paths, metrics and differences but adds no Streamlit interface, fresh
entry cost model, contributions, withdrawals or forecasts. Historical simulations
are not investment advice and do not guarantee future outcomes.
