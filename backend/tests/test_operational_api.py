"""Targeted HTTP checks without inference, training or downloads."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
import pandas as pd
from main import app
from src.riskbex.pipeline.store import VersionStore, digest, write_json
from src.riskbex.api.schemas import LatestRiskResponse, RegimeLatestResponse, AdaptiveBacktestLatestResponse

BACKEND=Path(__file__).resolve().parents[1]


class OperationalApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        env=patch.dict(os.environ,{'RISKBEX_OPERATIONAL_DIR':str(self.root)})
        env.start();self.addCleanup(env.stop)
        clock=patch('src.riskbex.api.operational.utc_now',return_value=pd.Timestamp('2026-04-23T21:00Z'))
        clock.start();self.addCleanup(clock.stop)

    def publish(self,version='a'*64,mode='live'):
        dates=['2026-04-22','2026-04-23']
        signals=pd.DataFrame({'date':dates,'regime':[2,2],'economic_label':['medium_risk']*2,
          'p_regime_0':[.1]*2,'p_regime_1':[.1]*2,'p_regime_2':[.8]*2,'target_exposure_regime_based':[.59]*2})
        features=pd.DataFrame({'date':dates,**{c:[.01]*2 for c in ['vol_20d','vol_60d','var_95_60d','cvar_95_60d','drawdown','skew_60d']}})
        bt=pd.DataFrame({'date':dates[1:],'ret_1d':[.01],'benchmark_return':[.01],
                         'benchmark_cum':[1.01],'benchmark_drawdown':[0.]})
        for key in ['regime_based','ml_hard','ml_proba']:
            bt['strategy_exposure_'+key]=.59
            if key!='regime_based':bt['target_exposure_'+key]=.59
            for suffix,value in [('return',.0059),('cum',1.0059),('drawdown',0.)]:bt[key+'_'+suffix]=value
        latest={'last_valid_session':dates[-1],'package_id':'main-v1','generated_at':'2026-04-23T20:00Z',
          'target_session_date':'2026-04-24','freshness':{},'provenance':{'manifest_sha256':'model-hash',
          'source_mode':mode,'live_market_freshness_verified':mode=='live'},'xgboost':{'probabilities':{'0':.1,'1':.1,'2':.8}}}
        manifest={'status':'validated','engine':'MAIN','version':version,'data_date':dates[-1],
                  'package_id':'main-v1','model_manifest_sha256':'model-hash'}
        metrics=pd.DataFrame([dict(sample='MAIN',strategy='Regime-based gross',total_return=.0059,
          mean_daily_return=.0059,daily_volatility=.01,annualized_volatility=.15,VaR_95=-.01,CVaR_95=-.02,
          max_drawdown=-.03,n_observations=1,start_date=dates[-1],end_date=dates[-1])])
        store=VersionStore(self.root)
        with store.lock():
            return store.publish({'prices':pd.DataFrame({'date':dates,'ibex_close':[100.,101.]}),
              'features':features,'signals':signals,'backtest':bt,'metrics':metrics,
              'turnover':pd.DataFrame({'strategy':['regime_based'],'total_turnover':[0.]})},latest,manifest,version)

    def request(self,path,method='GET'):
        async def inline(func,*args,**kwargs):
            return func(*args,**kwargs)
        async def call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                return await client.request(method,path)
        # This sandbox cannot wake the ASGI worker pool; retain real HTTP routing/serialization.
        with patch('fastapi.routing.run_in_threadpool',new=inline):
            return asyncio.run(call())

    def test_routes_contracts_and_dates(self):
        self.publish()
        for path,model in [('/latest-risk',LatestRiskResponse),('/regimes/latest',RegimeLatestResponse),('/backtesting/latest',AdaptiveBacktestLatestResponse)]:
            with self.subTest(path=path):
                response=self.request(path);self.assertEqual(response.status_code,200,response.text)
                body=response.json();model.model_validate(body)
                self.assertEqual(body['date'],'2026-04-23');self.assertTrue(body['publication']['is_current'])
                self.assertIn('xgboost',body['signal'])
        for path in ['/historical-risk?limit=1','/regimes/history?limit=1','/backtesting/results','/backtesting/metrics',
                     '/backtesting/latest?strategy=ml_hard','/backtesting/latest?strategy=ml_proba']:
            with self.subTest(path=path):
                response=self.request(path);self.assertEqual(response.status_code,200,response.text)

    def test_missing_and_corrupt_publications(self):
        for path in ['/latest-risk','/historical-risk','/regimes/latest','/regimes/history','/backtesting/latest','/backtesting/results','/backtesting/metrics']:
            with self.subTest(path=path):self.assertEqual(self.request(path).status_code,503)
        directory=self.publish();(directory/'latest.json').write_text('{}')
        self.assertEqual(self.request('/latest-risk').status_code,503)

    def test_simulation_and_stale_are_not_current(self):
        self.publish(mode='offline_simulation')
        body=self.request('/latest-risk').json();self.assertFalse(body['publication']['is_current'])
        self.assertEqual(body['publication']['freshness'],'simulated')
        self.publish(version='b'*64)
        with patch('src.riskbex.api.operational.utc_now',return_value=pd.Timestamp('2026-04-24T21:00Z')):
            body=self.request('/regimes/latest').json()
        self.assertEqual(body['date'],'2026-04-23');self.assertEqual(body['publication']['freshness'],'stale')
        self.assertFalse(body['publication']['is_current'])

    def test_one_version_per_request(self):
        first=self.publish();self.publish(version='b'*64)
        pointer=(self.root/'current.json').read_bytes()
        write_json(self.root/'current.json',{'version':first.name,'manifest_sha256':digest(first/'manifest.json')})
        original=VersionStore.current
        def switch(store):
            result=original(store);(self.root/'current.json').write_bytes(pointer);return result
        with patch.object(VersionStore,'current',switch) as current:
            body=self.request('/latest-risk').json()
        self.assertEqual(body['publication']['version'],'a'*64)
        self.assertEqual(self.request('/latest-risk').json()['publication']['version'],'b'*64)

    def test_ml_methodology_and_robust_strategy_guard(self):
        self.publish()
        body=self.request('/backtesting/latest?strategy=ml_hard').json()
        self.assertIn('XGBoost',body['methodology'])
        for path in ['/backtesting/latest?sample=robust&strategy=ml_hard',
                     '/backtesting/results?sample=robust&strategy=ml_proba']:
            self.assertEqual(self.request(path).status_code,400)

    def test_update_disabled_without_subprocess(self):
        with patch('subprocess.run',side_effect=AssertionError('must not execute')) as run:
            response=self.request('/run-update','POST')
        self.assertEqual(response.status_code,403);run.assert_not_called()
        self.assertEqual(response.json()['status'],'disabled')


if __name__=='__main__':unittest.main()
