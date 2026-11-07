"""Frozen prices -> MAIN inference -> realised strategies; creates a promotion receipt."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from scripts.check_main_engine import read_sprint2_fixture
from scripts.check_ml_equivalence import read_frozen_table, verify_reference
from src.riskbex.engine.package import load_main_package
from src.riskbex.pipeline.history import build_history
from src.riskbex.pipeline.service import pipeline_hashes
from src.riskbex.backtesting.ml_backtest import run_ml_backtest
from src.riskbex.backtesting.costs import summarize_returns
from src.riskbex.ml.config import FEATURE_COLUMNS
from src.riskbex.pipeline.store import write_json


def regression(package):
    reference = json.loads((BACKEND / 'tests/fixtures/tfm_ml/manifest.json').read_text())
    tables = build_history(package, read_sprint2_fixture('historical_prices'))
    def paired(actual, expected):
        expected = expected.copy()
        expected['date'] = pd.to_datetime(expected.date)
        result = actual.merge(expected, on='date', suffixes=('_new', '_ref'), validate='one_to_one')
        if len(result) != len(actual):
            raise AssertionError('Incomplete reference date coverage.')
        return result
    def errors(frame, columns, *, exact=True):
        result = {}
        for column in columns:
            a, b = frame[column + '_new'], frame[column + '_ref']
            result[column] = float(np.max(np.abs(a.to_numpy() - b.to_numpy())))
            if exact:
                np.testing.assert_allclose(a, b, atol=1e-12, rtol=1e-10, err_msg=column)
        return result
    master = read_frozen_table('historical_master', reference)
    feature_errors = errors(paired(tables['features'], master), ['ret_1d', *FEATURE_COLUMNS[1:]])
    predictions = read_sprint2_fixture('causal_main_predictions')
    prediction_errors = errors(paired(tables['signals'], predictions),
                               ['regime_pred', 'proba_0', 'proba_1', 'proba_2'])
    causal, causal_metrics, causal_turnover = run_ml_backtest(predictions, package.mapping, 'main')
    numeric = [c for c in causal if c != 'date' and c in tables['backtest'] and pd.api.types.is_numeric_dtype(causal[c])]
    causal_errors = errors(paired(tables['backtest'], causal), numeric)
    np.testing.assert_allclose(tables['metrics'].iloc[:len(causal_metrics)].select_dtypes('number'),
                               causal_metrics.select_dtypes('number'), atol=1e-12, rtol=1e-10)
    np.testing.assert_allclose(tables['turnover'].iloc[:len(causal_turnover)].select_dtypes('number'),
                               causal_turnover.select_dtypes('number'), atol=1e-12, rtol=1e-10)
    academic_regime = read_frozen_table('main_regime_backtest', reference)
    states = paired(tables['signals'].iloc[1:], academic_regime)
    np.testing.assert_array_equal(states.regime_new, states.regime_ref)
    markov_difference = errors(states, [f'p_regime_{k}' for k in range(3)], exact=False)
    if max(markov_difference.values()) > .002:
        raise AssertionError('Markov deviation exceeds approved Sprint 1D tolerance.')
    realised = paired(tables['backtest'], academic_regime.rename(columns={
        'strategy_exposure': 'strategy_exposure_regime_based', 'strategy_return': 'regime_based_return'}))
    regime_errors = errors(realised, ['strategy_exposure_regime_based', 'regime_based_return'])
    original_ml = read_frozen_table('main_ml_backtest', reference)
    original_predictions = read_frozen_table('main_predictions', reference)
    pc = paired(tables['signals'], original_predictions)
    class_differences = int((pc.regime_pred_new != pc.regime_pred_ref).sum())
    # Purging the single train/OOS boundary label was approved in Sprint 1C.
    if class_differences != 11:
        raise AssertionError('Unexplained change from approved causal-v1/academic classification differences.')
    comparison = paired(tables['backtest'], original_ml)
    impact = {}
    for key in ['ml_hard', 'ml_proba']:
        rows = {}
        for suffix, label in [('new', 'causal_v1'), ('ref', 'academic')]:
            rows[label] = summarize_returns(comparison[f'{key}_return_{suffix}'], comparison.date,
                                            sample='main', strategy=key)
        impact[key] = rows
    replay = verify_reference()  # Original frozen strategies/costs/turnover remain exactly reproducible.
    return {'status': 'passed', 'model_manifest_sha256': package.manifest_sha256,
            'implementation_sha256': pipeline_hashes(), 'feature_rows': len(tables['features']),
            'signal_rows': len(tables['signals']), 'realised_rows': len(tables['backtest']),
            'start_date': tables['backtest'].date.iloc[0].date().isoformat(),
            'end_date': tables['backtest'].date.iloc[-1].date().isoformat(),
            'feature_max_errors': feature_errors, 'causal_prediction_errors': prediction_errors,
            'causal_backtest_errors': causal_errors, 'regime_backtest_errors': regime_errors,
            'markov_probability_differences': markov_difference,
            'academic_classification_differences': class_differences,
            'causal_vs_academic_common_date_metrics': impact, 'academic_replay': replay,
            'approved_differences': ['MAIN Markov 500 converged vs academic default100 nonconverged; same labels',
                                     'XGBoost causal-v1 purged boundary vs original unpurged model'],
            'cost_rate': .001, 'shift_count': 1,
            'fixture_manifest_sha256': __import__('hashlib').sha256((BACKEND / 'tests/fixtures/sprint2/manifest.json').read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = regression(load_main_package(BACKEND / 'model_packages/main-v1'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(json.dumps({k: report[k] for k in ['status', 'signal_rows', 'realised_rows', 'start_date', 'end_date']}))


if __name__ == '__main__':
    main()
