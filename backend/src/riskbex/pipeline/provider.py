"""Existing Yahoo ^IBEX source, bounded request, explicit adjustment policy."""
import pandas as pd
from src.riskbex.ml.data import dated_frame, numeric_values


def validate_prices(frame, *, allow_empty=False):
    if allow_empty and frame.empty:
        return pd.DataFrame(columns=['date', 'ibex_close'])
    output = dated_frame(frame)[['date', 'ibex_close']].copy()
    numeric_values(output, ['ibex_close'])
    if not output.ibex_close.gt(0).all():
        raise ValueError('Prices must be positive.')
    return output


class YahooProvider:
    is_live = True
    source = 'yahoo-finance:^IBEX:1d:auto_adjust=True'

    def fetch(self, start, end):
        import yfinance as yf
        raw = yf.download('^IBEX', start=pd.Timestamp(start).date().isoformat(),
                          end=(pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat(),
                          interval='1d', auto_adjust=True, progress=False, threads=False, timeout=20)
        if raw.empty:
            raise RuntimeError('Yahoo returned no prices; provider failure or unavailable data.')
        close = raw['Close']
        if isinstance(close, pd.DataFrame):
            if list(close.columns) != ['^IBEX']:
                raise ValueError('Unexpected provider ticker schema.')
            close = close.iloc[:, 0]
        dates = pd.DatetimeIndex(close.index)
        if dates.tz is not None:
            dates = dates.tz_convert('Europe/Madrid').tz_localize(None)
        return validate_prices(pd.DataFrame({'date': dates, 'ibex_close': close.to_numpy()}))


def merge_new_sessions(history, fetched, calendar, eligible, overlap_start):
    history = validate_prices(history)
    fetched = validate_prices(fetched, allow_empty=True)
    last = history.date.iloc[-1]
    if last > eligible:
        raise ValueError('Stored history contains a session not eligible at generation time.')
    if not fetched.empty:
        if fetched.date.min() < overlap_start or fetched.date.max() > eligible:
            raise ValueError('Provider returned dates outside the closed-session request.')
        expected_dates = calendar.sessions(overlap_start, eligible)
        if not fetched.date.isin(expected_dates).all():
            raise ValueError('Provider returned a non-trading date.')
        overlap = fetched.merge(history, on='date', suffixes=('_provider', '_stored'))
        # No silent tolerance/rebasing: even small revisions require review.
        if not overlap.ibex_close_provider.eq(overlap.ibex_close_stored).all():
            raise ValueError('Historical provider revision detected; frozen history retained.')
    expected = calendar.sessions(overlap_start, eligible)
    if set(fetched.date) != set(expected):
        raise ValueError('Incomplete provider response or missing exchange sessions.')
    new = fetched.loc[fetched.date > last]
    return pd.concat([history, new], ignore_index=True), len(new)
