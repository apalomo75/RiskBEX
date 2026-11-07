"""Read-only historical replay. Prints JSON; never fits models or writes outputs."""

import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.backtesting.ml_backtest import compare_on_common_dates, run_ml_backtest
from src.riskbex.ml.evaluation import classification_metrics

FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "tfm_ml"


def read_frozen_table(key, manifest, root=FIXTURE_ROOT):
    source = manifest["sources"][key]
    if "fixture" in source:
        raw = gzip.decompress((root / source["fixture"]).read_bytes())
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Frozen reference SHA-256 mismatch: {key}")
        return pd.read_csv(BytesIO(raw))
    frame = pd.DataFrame(manifest["tables"][key])
    for column in frame.columns:
        # Only convert wholly numeric columns; retain strategy/sample labels.
        try:
            frame[column] = pd.to_numeric(frame[column])
        except (ValueError, TypeError):
            pass
    return frame


def verify_reference(root=FIXTURE_ROOT):
    manifest = json.loads((root / "manifest.json").read_text())
    report = {"reference_status": manifest["status"], "model_recovered": False, "samples": {}}
    for sample in ["main", "robust"]:
        read = lambda kind: read_frozen_table(f"{sample}_{kind}", manifest, root)
        predictions, mapping = read("predictions"), read("mapping")
        expected = read("ml_backtest")
        actual, metrics, turnover = run_ml_backtest(predictions, mapping, sample)
        if not actual["date"].equals(pd.to_datetime(expected["date"])):
            raise AssertionError(f"{sample}: historical dates disagree.")
        errors = {}
        for column in expected.columns:
            if column == "date":
                continue
            if pd.api.types.is_numeric_dtype(expected[column]):
                error = float(np.max(np.abs(actual[column].to_numpy() - expected[column].to_numpy())))
                errors[column] = error
                np.testing.assert_allclose(actual[column], expected[column], atol=1e-12, rtol=1e-10,
                                           err_msg=f"{sample}: daily {column}")
            else:
                if actual[column].tolist() != expected[column].tolist():
                    raise AssertionError(f"{sample}: {column} disagrees.")
        metric_error = 0.
        for _, row in read("cost_metrics").iterrows():
            calculated = metrics.loc[metrics["strategy"] == row["strategy"]].iloc[0]
            for column in row.index.drop("strategy"):
                metric_error = max(metric_error, abs(float(calculated[column]) - float(row[column])))
                np.testing.assert_allclose(calculated[column], row[column], atol=1e-12, rtol=1e-10,
                                           err_msg=f"{sample}: {row['strategy']} {column}")
        turnover_error = 0.
        for _, row in read("turnover").iterrows():
            calculated = turnover.loc[turnover["strategy"] == row["strategy"]].iloc[0]
            for column in row.index.drop(["sample", "strategy"]):
                turnover_error = max(turnover_error, abs(float(calculated[column]) - float(row[column])))
                np.testing.assert_allclose(calculated[column], row[column], atol=1e-12, rtol=1e-10,
                                           err_msg=f"{sample}: turnover {column}")
        stress = mapping.loc[mapping["economic_label"] == "high_risk", "regime"].iloc[0]
        classification = classification_metrics(predictions, stress_regime=stress)
        for column, value in manifest["classification_exact"][sample].items():
            np.testing.assert_allclose(classification[column], value, atol=1e-12, rtol=0)
        rounded = read("classification_rounded")
        xgb = rounded.loc[rounded["Model"] == "XGBoost"].iloc[0]
        for metric, column in [("accuracy", "Accuracy"), ("balanced_accuracy", "Balanced Accuracy"),
                               ("stress_recall", "Stress Recall")]:
            if abs(classification[metric] - xgb[column]) > .0005:
                raise AssertionError(f"{sample}: rounded classification metric {column}")
        common, excluded = compare_on_common_dates(actual, read("regime_backtest"), sample)
        common_error = 0.
        rename = {
            "Buy & Hold": "Buy & Hold", "Regime-based": "Regime-based",
            "ML hard classification": "ML Hard", "ML probability-weighted": "ML Probability-weighted",
        }
        columns = {"Total Return": "total_return", "Daily Volatility": "daily_volatility",
                   "VaR 95%": "VaR_95", "CVaR 95%": "CVaR_95",
                   "Max Drawdown": "max_drawdown", "Sharpe": "sharpe_ratio"}
        for _, row in read("common_metrics").iterrows():
            calculated = common.loc[common["strategy"] == rename[row["Strategy"]]].iloc[0]
            for source, destination in columns.items():
                common_error = max(common_error, abs(calculated[destination] - row[source]))
                np.testing.assert_allclose(calculated[destination], row[source], atol=1e-12, rtol=1e-10,
                                           err_msg=f"{sample}: common {source}")
        report["samples"][sample] = {
            "prediction_rows": len(predictions), "backtest_rows": len(actual),
            "start_date": actual["date"].min().date().isoformat(),
            "end_date": actual["date"].max().date().isoformat(),
            "max_daily_error": max(errors.values()), "daily_errors": errors,
            "max_cost_metrics_error": metric_error, "max_turnover_error": turnover_error,
            "max_common_metrics_error": common_error, "excluded_dates": excluded,
            "classification": classification,
        }
    return report


if __name__ == "__main__":
    print(json.dumps(verify_reference(), indent=2, allow_nan=False))
