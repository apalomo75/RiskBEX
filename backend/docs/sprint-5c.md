# Sprint 5C — Unified strategy performance

Results reads `/backtesting/comparison`, which resolves one validated publication
pointer and returns stored backtest series, metrics, turnover and provenance from
that immutable version. Signals from the same snapshot verify prior-close target
alignment. No inference, training, downloads or publication regeneration occurs
when viewing Results. Existing backtesting API response contracts are unchanged.

The current `runtime/main-wsl-test` publication supports Buy & Hold, Regime-Based,
ML Hard and ML Probability-Weighted on the same 1,496 realised market sessions:
January 5, 2021 through November 6, 2026. The January 4 signal supplies the first
applied exposure. MAIN frozen Markov parameters, MAIN causal-v1 XGBoost and the
training-only CVaR mapping supply all adaptive strategies. Exposure levels are
1.0, approximately 0.590556 and 0.355552; probability-weighted exposure combines
these levels using XGBoost probabilities. Legacy fixed exposures are confined to
the academic reference view.

## Presentation and conventions

Results allows selecting any of the four strategies and gross or net performance.
It displays growth, drawdown, applied exposure, total return, annualized volatility,
daily 95% Expected Shortfall, maximum drawdown, transaction-cost deductions and
turnover. The version, engine, evaluation dates and current publication freshness
are visible. Stale historical performance remains usable with a warning. Missing,
incomplete or invalid comparisons show an unavailable message without substituting
academic values. API connection failures remain visible.

Stored returns use exposure multiplied by index log returns. Targets formed at
close t apply exactly once to the next realised session. Growth is exp(cumulative
log returns). Net results subtract 0.001 times absolute changes in applied exposure
from daily log returns. Small changes incur costs even below the one-percentage-
point effective-change reporting threshold. Total turnover is the sum of absolute
exposure changes; annualized turnover is daily mean turnover multiplied by 252.
Total transaction costs shown are summed log-return deductions.

Volatility is sample daily standard deviation multiplied by square root of 252.
Expected Shortfall averages daily log returns at or below the empirical fifth
percentile. Maximum drawdown uses observed running peaks. Net drawdown is derived
from the stored net growth curve; all metrics are the stored metrics, not model
recomputations.

Methodological limitations remain explicit: no initial entry or final liquidation
cost; no trading costs for Buy & Hold; zero cash yield; no financing, slippage or
taxes. Exposure-scaled log returns are the existing research convention rather
than exact self-financing portfolio arithmetic. Drawdown excludes an initial
capital anchor. These conventions are retained consistently; no historical files
are overwritten and no missing results are fabricated.

## Academic preservation

Research retains all six original figures and the original MAIN/ROBUST backtest
view under **Academic Reference — Original TFM Methodology**. Explicit read-only
`/backtesting/academic/results`, `/metrics` and `/latest` routes load the existing
academic files. The operational comparison never uses those loaders. Existing
MAIN/ROBUST model comparisons and Tail Risk remain accessible.

## Validation

`tests/test_strategy_performance.py` checks the existing publication's CVaR mapping,
model metadata hash and OOS cutoff, benchmark/strategy dates, exactly one exposure
lag, return and cost arithmetic, stored metrics, API compatibility, academic route
access, missing/incomplete data, stale presentation and Streamlit strategy/basis
selection. Additional lightweight checks cover English presentation and future
label/return independence using the existing strategy tests. No full quantitative
suite is required. Startup configuration remains in `docs/sprint-5b.md`.
