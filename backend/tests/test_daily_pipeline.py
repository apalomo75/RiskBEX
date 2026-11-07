"""Offline MAIN acceptance with fake providers and real frozen models."""
import importlib.util
import json
from pathlib import Path
import platform
import tempfile
import unittest
from unittest.mock import patch, Mock
import numpy as np
import pandas as pd
from scripts.check_main_engine import read_sprint2_fixture
from src.riskbex.engine.package import load_main_package
from src.riskbex.pipeline.calendar import SessionCalendar
from src.riskbex.pipeline.provider import YahooProvider, validate_prices, merge_new_sessions
from src.riskbex.pipeline.service import update_main, pipeline_hashes
from src.riskbex.pipeline.store import VersionStore, write_json
from src.riskbex.pipeline.loaders import load_operational_results
BACKEND=Path(__file__).resolve().parents[1]
NATIVE=importlib.util.find_spec('xgboost') is not None and platform.python_version()=='3.11.14'

def calendar():
    return SessionCalendar.load(BACKEND/'config/bme-2026.json')

class Provider:
    source='simulated-frozen-historical-prices'
    def __init__(self, prices):
        self.prices=prices
        self.calls=0
    def fetch(self,start,end):
        self.calls+=1
        return self.prices.loc[self.prices.date.between(start,end),['date','ibex_close']].copy()

class CalendarAndProviderTests(unittest.TestCase):
    def test_weekend(self):
        self.assertEqual(str(calendar().eligible('2026-04-26T22:00Z').date()),'2026-04-24')
    def test_holiday(self):
        self.assertEqual(str(calendar().eligible('2026-04-06T22:00Z').date()),'2026-04-02')
    def test_delay_after_close(self):
        self.assertEqual(str(calendar().eligible('2026-04-23T16:00Z').date()),'2026-04-22')
        self.assertEqual(str(calendar().eligible('2026-04-23T18:00Z').date()),'2026-04-23')
    def test_unknown_calendar(self):
        with self.assertRaisesRegex(ValueError,'coverage'):
            calendar().eligible('2027-02-01T22:00Z')
    def test_timezone_required(self):
        with self.assertRaises(ValueError): calendar().eligible('2026-04-23')
    def test_next_session(self):
        self.assertEqual(str(calendar().next_session('2026-04-30').date()),'2026-05-04')
        self.assertEqual(str(calendar().next_session('2026-12-18').date()),'2026-12-21')
        self.assertEqual(str(calendar().eligible('2026-01-02T22:00Z').date()),'2026-01-02')
    def test_price_validation(self):
        for dates,values in [(['2026-04-23']*2,[1,2]),(['2026-04-23','2026-04-22'],[1,2]),
                             (['2026-04-23'],[np.nan]),(['2026-04-23'],[-1])]:
            with self.subTest(), self.assertRaises(ValueError):
                validate_prices(pd.DataFrame({'date':dates,'ibex_close':values}))
    def test_yahoo_schema(self):
        import sys
        from types import SimpleNamespace
        raw=pd.DataFrame({('Close','^IBEX'):[18000.]},index=pd.to_datetime(['2026-04-23']))
        download=Mock(return_value=raw)
        with patch.dict(sys.modules,{'yfinance':SimpleNamespace(download=download)}):
            result=YahooProvider().fetch('2026-04-23','2026-04-23')
        self.assertEqual(result.ibex_close.iloc[0],18000.)
        self.assertTrue(download.call_args.kwargs['auto_adjust'])
        self.assertEqual(download.call_args.kwargs['end'],'2026-04-24')
    def test_empty_yahoo(self):
        import sys
        from types import SimpleNamespace
        with patch.dict(sys.modules,{'yfinance':SimpleNamespace(download=lambda *a,**k:pd.DataFrame())}):
            with self.assertRaises(RuntimeError): YahooProvider().fetch('2026-04-23','2026-04-23')
    def test_missing_or_revised_sessions(self):
        history=pd.DataFrame({'date':pd.to_datetime(['2026-04-21','2026-04-22']),'ibex_close':[10.,11.]})
        for response in [history, pd.DataFrame({'date':pd.to_datetime(['2026-04-21','2026-04-22','2026-04-23']),
                                               'ibex_close':[9.,11.,12.]})]:
            with self.subTest(), self.assertRaises(ValueError):
                merge_new_sessions(history,response,calendar(),pd.Timestamp('2026-04-23'),pd.Timestamp('2026-04-21'))
    def test_concurrency(self):
        with tempfile.TemporaryDirectory() as root:
            with VersionStore(root).lock():
                with self.assertRaisesRegex(RuntimeError,'Another'):
                    with VersionStore(root).lock(): pass
    def test_empty_store(self):
        with tempfile.TemporaryDirectory() as root: self.assertIsNone(VersionStore(root).current())

@unittest.skipUnless(NATIVE,'Requires native frozen-model runtime')
class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package=load_main_package(BACKEND/'model_packages/main-v1')
        cls.prices=read_sprint2_fixture('historical_prices')[['date','ibex_close']]
        cls.prices.date=pd.to_datetime(cls.prices.date)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=VersionStore(Path(self.temp.name)/'store')
        self.receipt=Path(self.temp.name)/'receipt.json'
        write_json(self.receipt,{'status':'passed','model_manifest_sha256':self.package.manifest_sha256,
                                 'implementation_sha256':pipeline_hashes()})
        self.seed=self.prices.loc[self.prices.date<'2026-04-23'].copy()
        self.provider=Provider(self.prices)
    def run_update(self,now='2026-04-23T20:00Z'):
        return update_main(self.package,self.seed,self.provider,calendar(),self.store,
                           now=now,regression_receipt=self.receipt)
    def extend_provider(self):
        frame=read_sprint2_fixture('extended_prices'); frame.date=pd.to_datetime(frame.date)
        self.provider=Provider(frame)
    def test_success_idempotence_continuity_no_fit(self):
        import statsmodels.api as sm
        import xgboost
        with patch.object(sm.tsa.MarkovRegression,'fit',side_effect=AssertionError('fit forbidden')), patch.object(xgboost.XGBClassifier,'fit',side_effect=AssertionError('fit forbidden')):
            first=self.run_update(); pointer=(self.store.root/'current.json').read_bytes()
            second=self.run_update()
        self.assertEqual(first['new_sessions'],1); self.assertEqual(second['status'],'unchanged')
        self.assertEqual(pointer,(self.store.root/'current.json').read_bytes())
        self.assertEqual(len(list((self.store.root/'versions').iterdir())),1)
        current=self.store.current(); signals=pd.read_csv(current/'signals.csv'); bt=pd.read_csv(current/'backtest.csv')
        for key in ['regime_based','ml_hard','ml_proba']:
            np.testing.assert_allclose(bt['strategy_exposure_'+key],signals['target_exposure_'+key].iloc[:-1])
            np.testing.assert_allclose(bt[key+'_return'],bt['strategy_exposure_'+key]*bt.ret_1d)
        latest=json.loads((current/'latest.json').read_text())
        self.assertEqual(latest['target_session_date'],'2026-04-24')
        self.assertFalse(latest['provenance']['live_market_freshness_verified'])
        self.assertEqual(latest['provenance']['source_mode'],'offline_simulation')
        loaded=load_operational_results(self.store.root,calendar=calendar(),now='2026-04-24T21:00Z')
        self.assertEqual(loaded['latest']['freshness']['status'],'stale')
    def test_provider_failure_retains_current(self):
        self.run_update(); old=self.store.current()
        with patch.object(self.provider,'fetch',side_effect=RuntimeError('provider down')):
            with self.assertRaisesRegex(RuntimeError,'provider down'): self.run_update()
        self.assertEqual(self.store.current(),old)
        self.assertEqual(json.loads((self.store.root/'status.json').read_text())['status'],'failed')
    def test_inference_failure(self):
        with patch('src.riskbex.pipeline.service.build_history',side_effect=RuntimeError('inference')):
            with self.assertRaisesRegex(RuntimeError,'inference'): self.run_update()
        self.assertIsNone(self.store.current())
    def test_write_failure_retains_current(self):
        self.run_update(); old=self.store.current(); self.extend_provider()
        with patch('src.riskbex.pipeline.store.pd.DataFrame.to_csv',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'): self.run_update('2026-04-24T20:00Z')
        self.assertEqual(self.store.current(),old); self.assertFalse(list(self.store.root.glob('.stage-*')))
    def test_pointer_failure_retains_current(self):
        import os
        self.run_update(); old=self.store.current(); self.extend_provider(); original=os.replace
        def fail(src,dst):
            if Path(dst).name=='current.json': raise OSError('promotion interrupted')
            return original(src,dst)
        with patch('src.riskbex.pipeline.store.os.replace',side_effect=fail):
            with self.assertRaisesRegex(OSError,'promotion'): self.run_update('2026-04-24T20:00Z')
        self.assertEqual(self.store.current(),old)
        recovered=self.run_update('2026-04-24T20:00Z')
        self.assertEqual(recovered['status'],'published')
        self.assertNotEqual(self.store.current(),old)
    def test_training_revision_before_download(self):
        self.seed.loc[self.seed.date=='2020-12-30','ibex_close']+=1
        with self.assertRaisesRegex(ValueError,'Training price prefix'): self.run_update()
        self.assertEqual(self.provider.calls,0)
    def test_future_observation_rejected(self):
        with self.assertRaisesRegex(ValueError,'not eligible'): self.run_update('2026-04-22T16:00Z')
    def test_incomplete_response(self):
        self.provider=Provider(self.seed)
        with self.assertRaisesRegex(ValueError,'Incomplete'): self.run_update()
        self.assertIsNone(self.store.current())
    def test_stale_gate_before_download(self):
        write_json(self.receipt,{'status':'failed'})
        with self.assertRaisesRegex(ValueError,'regression'): self.run_update()
        self.assertEqual(self.provider.calls,0)
    def test_integral_frozen_regression(self):
        from scripts.check_daily_regression import regression
        report=regression(self.package)
        self.assertEqual(report['status'],'passed')
        self.assertEqual(report['realised_rows'],1356)
        self.assertEqual(report['academic_classification_differences'],11)
    def test_future_extension_does_not_change_past_signals(self):
        from src.riskbex.pipeline.history import build_history
        historical=build_history(self.package,self.prices)['signals']
        extended=build_history(self.package,read_sprint2_fixture('extended_prices'))['signals']
        common=extended.loc[extended.date<=historical.date.iloc[-1]].reset_index(drop=True)
        pd.testing.assert_frame_equal(historical,common,check_exact=True)
    def test_corrupt_publication(self):
        self.run_update(); (self.store.current()/'latest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'integrity'): self.store.current()

if __name__=='__main__': unittest.main()
