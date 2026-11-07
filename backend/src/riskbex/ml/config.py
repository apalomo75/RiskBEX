"""Explicit notebook 05 parameters; library defaults are not recovered parameters."""

from src.riskbex.config import MAIN_TEST_START, ROBUST_TEST_START


FEATURE_COLUMNS = (
    "ret_1d", "ret_20d", "ret_60d", "ewma_vol", "vol_20d", "vol_60d",
    "downside_vol_20d", "downside_vol_60d", "cvar_95_60d", "drawdown", "skew_60d",
)
XGBOOST_PARAMETERS = {
    "n_estimators": 300, "max_depth": 3, "learning_rate": 0.05,
    "subsample": 0.8, "colsample_bytree": 0.8, "objective": "multi:softprob",
    "eval_metric": "mlogloss", "random_state": 42, "n_jobs": -1,
}
SAMPLES = {
    "main": {"split_column": "sample_split_main", "test_start": MAIN_TEST_START},
    "robust": {"split_column": "sample_split_robust", "test_start": ROBUST_TEST_START},
}


def normalize_sample(sample):
    name = str(sample).lower()
    if name not in SAMPLES:
        raise ValueError("sample must be main or robust")
    return name
