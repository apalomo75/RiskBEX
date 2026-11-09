"""Deterministic presentation of stored performance; no strategy calculations."""
import math

STRATEGY_KEYS = {'Regime-Based': 'regime_based', 'ML Hard': 'ml_hard',
                 'ML Probability-Weighted': 'ml_proba'}
TURNOVER_LABELS = {'Regime-based': 'Regime-Based', 'ML Hard Classification': 'ML Hard',
                   'ML Probability-Weighted': 'ML Probability-Weighted'}
METRICS = ['Total Return', 'Annualized Volatility', 'Expected Shortfall (95%)', 'Maximum Drawdown']


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def metric_difference(label, value, reference):
    """Signed loss metrics increase towards zero when loss severity improves."""
    if not finite(value) or not finite(reference):
        return f'{label}: unavailable'
    delta = (value - reference) * 100
    if abs(delta) < .005:
        direction = 'unchanged at displayed precision'
    elif label == 'Total Return':
        direction = 'higher return' if delta > 0 else 'lower return'
    elif label == 'Annualized Volatility':
        direction = 'higher volatility' if delta > 0 else 'lower volatility'
    else:
        severity_delta = max(-value, 0) - max(-reference, 0)
        direction = ('less severe loss' if severity_delta < 0 else 'more severe loss') if severity_delta else 'no loss severity difference'
    return f'{label}: {delta:+.2f} percentage points ({direction})'


def comparison_stories(rows, selected, turnover):
    by_name = {row['Strategy']: row for row in rows}
    turns = {TURNOVER_LABELS.get(row.get('strategy')): row.get('total_turnover') for row in turnover}
    turns['Buy & Hold'] = 0.0
    stories = []
    for name in selected:
        references = ['Buy & Hold', 'Regime-Based'] if name.startswith('ML ') else ['Buy & Hold']
        if name == 'ML Probability-Weighted':
            references.append('ML Hard')
        for reference_name in references:
            if name == reference_name:
                continue
            row, ref = by_name.get(name), by_name.get(reference_name)
            if row is None or ref is None:
                stories.append(f'{name} versus {reference_name} — comparison unavailable.')
                continue
            parts = [metric_difference(metric, row.get(metric), ref.get(metric)) for metric in METRICS]
            a, b = turns.get(name), turns.get(reference_name)
            if finite(a) and finite(b):
                delta = a - b
                direction = 'higher turnover' if delta > .005 else 'lower turnover' if delta < -.005 else 'unchanged at displayed precision'
                parts.append(f'Total Turnover: {delta:+.2f} exposure units ({direction})')
            else:
                parts.append('Total Turnover: unavailable')
            a, b = row.get('Total Transaction Costs (Log Return)'), ref.get('Total Transaction Costs (Log Return)')
            if finite(a) and finite(b):
                delta = (a - b) * 100
                direction = 'higher costs' if delta > .005 else 'lower costs' if delta < -.005 else 'unchanged at displayed precision'
                parts.append(f'Transaction Costs: {delta:+.2f} log-return points ({direction})')
            else:
                parts.append('Transaction Costs: unavailable')
            stories.append(f'{name} versus {reference_name} — ' + '; '.join(parts) + '.')
    return stories


def participation_stories(records, selected, net):
    """Attribute selected-basis log-return differences on common up/down sessions.

    These disjoint session sums are not compounded period returns or drawdowns.
    Missing observations suppress a comparison rather than shortening its window.
    """
    stories = []
    for name in selected:
        key = STRATEGY_KEYS.get(name)
        if key is None:
            continue
        column = f'{key}_return' + ('_net' if net else '')
        exposure_column = f'strategy_exposure_{key}'
        if not records or any(not all(finite(row.get(c)) for c in
                                     ['benchmark_return', column, exposure_column]) for row in records):
            stories.append(f'{name}: market participation assessment unavailable; complete aligned observations are required.')
            continue
        parts = []
        for label, sign in [('down-market', -1), ('up-market', 1)]:
            sessions = [row for row in records if row['benchmark_return'] * sign > 0]
            if not sessions:
                parts.append(f'no {label} sessions to assess')
                continue
            delta = sum(row[column] - row['benchmark_return'] for row in sessions) * 100
            average_exposure = sum(row[exposure_column] for row in sessions) / len(sessions)
            if abs(delta) < .005:
                meaning = 'no difference at displayed precision'
            elif sign < 0:
                meaning = 'less loss than Buy & Hold' if delta > 0 else 'more loss than Buy & Hold'
            else:
                meaning = 'more gain than Buy & Hold' if delta > 0 else 'less gain than Buy & Hold'
            parts.append(f'{len(sessions):,} {label} sessions: average exposure {average_exposure:.1%}, '
                         f'{delta:+.2f} log-return points ({meaning})')
        stories.append(f'{name} — ' + '; '.join(parts) + '.')
    return stories
