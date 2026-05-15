import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.paths import REGIME_DATASET_PATH, REGIME_SUMMARY_PATH
from src.riskbex.regimes.interpretation import build_regime_summary


if __name__ == "__main__":
    regime_dataset_df = pd.read_csv(REGIME_DATASET_PATH, parse_dates=["date"])
    regime_summary_df = build_regime_summary(regime_dataset_df)
    regime_summary_df = regime_summary_df.sort_values(["split", "risk_order"]).reset_index(drop=True)
    regime_summary_df.to_csv(REGIME_SUMMARY_PATH, index=False)
    print(regime_summary_df.to_string(index=False))
    print(f"saved_to: {REGIME_SUMMARY_PATH}")
