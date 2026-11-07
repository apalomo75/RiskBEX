# Sprint 5D — Decision Explorer

Open **Explore → Decision Explorer**. The selector contains only the 1,497 signal
sessions in the configured operational publication, defaulting to its final
session. It is independent of the existing observation-period selector.

The view displays the information close, next eligible session, optional IBEX
close, filtered Markov state and probabilities, predicted next-session XGBoost
state and probabilities, three target exposures, verified CVaR mapping and model
package/publication identifiers. Probability-weighted targets are explained using
the actual predictive probabilities and mapping values. No feature-importance or
causal explanation is inferred.

Previous targets refer to the previous available signal session. Differences are
percentage points; the first session displays N/A. Differences below 1e-10
percentage points are treated as numerical zero. Targets are hypothetical model
allocations, not executed orders. The view is labelled **Historical Backtest —
Not Live Trading Records.** Stale publications remain inspectable with a warning.

One interactive chart displays target exposure for the selected strategy, diamonds
at filtered Markov regime transitions and a blue circle at the selected signal
close. Tooltips distinguish signal dates from target sessions. Pan and zoom inspect
history without implying execution.

`GET /decision-explorer` returns one snapshot containing all sessions, previous
comparisons, mapping and publication metadata. Optional `?session=YYYY-MM-DD`
adds the selected published row; unavailable or invalid dates return HTTP 404.
Missing, incomplete or mismatched publications/model mappings return HTTP 503.
Existing endpoint contracts are unchanged. Streamlit caches this complete response
for 30 seconds; selection changes use the same response rather than fetching
separate versions for history and mapping.

The existing `model_packages/main-v1` manifest hash must match the publication;
the mapping hash must match both manifests. Only those small package files are
read; models are not loaded. Earlier next-session labels use the next observed
feature date in the same validated publication. The final target is verified with
the embedded publication calendar. The 2026 calendar is not extrapolated backwards.
Closing prices are optional and display N/A when absent. A different unavailable
model package fails closed rather than borrowing another mapping.

Targeted checks in `tests/test_decision_explorer.py` cover session selection, state
labels, probability-weighted reconstruction, previous changes, first-session N/A,
optional closes, missing/incomplete data, mapping/version mismatch, invalid dates,
API compatibility, stale presentation and interactive chart controls. English
presentation uses the existing lightweight literal check. No inference, training,
downloads, academic changes, deployment, scheduling or commits are involved.
