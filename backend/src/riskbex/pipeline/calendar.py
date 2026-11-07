"""Explicit exchange calendar, with a conservative provider-availability cutoff."""
import hashlib
import json
from pathlib import Path
import pandas as pd


class SessionCalendar:
    def __init__(self, config):
        self.config = config
        self.years = set(config['years'])
        self.holidays = set(config['holidays'])
        self.digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def sessions(self, start, end):
        start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
        if any(year not in self.years for year in range(start.year, end.year + 1)):
            raise ValueError('Calendar coverage expired or unavailable; supply a reviewed calendar.')
        return pd.DatetimeIndex([d for d in pd.date_range(start, end) if d.weekday() < 5
                                 and d.date().isoformat() not in self.holidays])

    def eligible(self, now):
        now = pd.Timestamp(now)
        if now.tz is None:
            raise ValueError('Generation time must have an explicit timezone.')
        local = now.tz_convert(self.config['timezone'])
        today = local.normalize().tz_localize(None)
        # This is an operational delay policy, not the exchange close time or a guarantee of delivery.
        hour, minute = map(int, self.config['available_after_local'].split(':'))
        cutoff = local.normalize() + pd.Timedelta(hours=hour, minutes=minute)
        candidate = today if local >= cutoff else today - pd.Timedelta(days=1)
        for offset in range(15):
            day = candidate - pd.Timedelta(days=offset)
            if len(self.sessions(day, day)):
                return day
        raise ValueError('No eligible closed session in calendar window.')

    def next_session(self, day):
        day = pd.Timestamp(day)
        for offset in range(1, 15):
            candidate = day + pd.Timedelta(days=offset)
            if len(self.sessions(candidate, candidate)):
                return candidate
        raise ValueError('Next exchange session unavailable.')
