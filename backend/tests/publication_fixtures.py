"""Offline inputs derived from a verified release approval."""
import pandas as pd

from src.riskbex.actions_update import approved_bundle
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.store import VersionStore


class ApprovedPublication:
    def __init__(self, root):
        self.approval = approved_bundle(root)
        self.session = pd.Timestamp(self.approval['data_date'])
        self.calendar = SessionCalendar.load(root / 'backend/config/bme-2026.json')
        self.store = VersionStore(root / 'cloud/publication/store')

    def clock(self, session, *, before_cutoff=False):
        hour, minute = map(int, self.calendar.config['available_after_local'].split(':'))
        cutoff = session.tz_localize(self.calendar.config['timezone']) + pd.Timedelta(hours=hour, minutes=minute)
        return cutoff + pd.Timedelta(minutes=-1 if before_cutoff else 1)

    def history(self):
        return pd.read_csv(self.store.current() / 'prices.csv', float_precision='round_trip')

    def extension(self, history, sessions):
        return pd.DataFrame({
            'date': [session.date().isoformat() for session in sessions],
            'ibex_close': [float(history.ibex_close.iloc[-1]) + i for i in range(1, len(sessions) + 1)],
        })
