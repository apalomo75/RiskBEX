import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.paths import (
    REGIME_DATASET_PATH,
    REGIME_DURATION_SUMMARY_PATH,
    REGIME_SUMMARY_PATH,
)
from src.riskbex.regimes.durations import build_all_duration_summaries


if __name__ == "__main__":
    regime_df = pd.read_csv(REGIME_DATASET_PATH, parse_dates=["date"])
    regime_summary_df = pd.read_csv(REGIME_SUMMARY_PATH)
    duration_df = build_all_duration_summaries(regime_df, regime_summary_df)
    duration_df.to_csv(REGIME_DURATION_SUMMARY_PATH, index=False)
    print(duration_df.to_string(index=False))
    print(f"saved_to: {REGIME_DURATION_SUMMARY_PATH}")
