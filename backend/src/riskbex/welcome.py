"""Read-only Welcome presentation guards; no inference or signal alignment."""
import math
from datetime import date

import pandas as pd

RISK_LABELS = {'low_risk': 'Low Risk', 'medium_risk': 'Medium Risk', 'high_risk': 'High Risk'}


def welcome_history(frame, latest):
    """Use same-publication, same-session filtered labels and observed closes only."""
    publication = (latest or {}).get('publication') or {}
    required = {'date', 'ibex_close', 'regime_label', 'publication'}
    if frame.empty or not required.issubset(frame) or not publication.get('version'):
        return pd.DataFrame()
    try:
        cutoff = pd.Timestamp(date.fromisoformat(publication['data_date']))
        result = frame.copy()
        result['date'] = pd.to_datetime(result.date, errors='coerce')
        result['ibex_close'] = pd.to_numeric(result.ibex_close, errors='coerce')
        matching = result.publication.map(lambda p: isinstance(p, dict) and
                                         p.get('version') == publication['version'])
        valid = (matching & result.date.le(cutoff) & result.ibex_close.gt(0)
                 & result.ibex_close.map(lambda p: math.isfinite(p))
                 & result.regime_label.isin(RISK_LABELS))
        result = result.loc[valid].sort_values('date')
        if result.date.duplicated().any():
            return pd.DataFrame()
        return result.tail(252).copy()
    except (KeyError, TypeError, ValueError):
        return pd.DataFrame()


def welcome_assessment(latest):
    """Read current Markov label and published next-session strategy target separately."""
    latest = latest or {}
    publication = latest.get('publication') or {}
    signal = latest.get('signal') or {}
    try:
        session = date.fromisoformat(publication['data_date'])
        if signal.get('last_valid_session') != session.isoformat():
            return 'Unavailable', None
    except (KeyError, TypeError, ValueError):
        return 'Unavailable', None
    label = RISK_LABELS.get((signal.get('markov') or {}).get('economic_label'), 'Unavailable')
    target = (signal.get('target_exposures') or {}).get('regime_based')
    if (label == 'Unavailable' or isinstance(target, bool) or not isinstance(target, (int, float))
            or not math.isfinite(target) or not 0 <= target <= 1):
        target = None
    return label, target
