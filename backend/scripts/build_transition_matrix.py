import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.data.loaders import load_regime_input_dataset
from src.riskbex.paths import REGIME_SUMMARY_PATH, REGIME_TRANSITION_MATRIX_PATH
from src.riskbex.regimes.transitions import build_all_transition_matrices


if __name__ == "__main__":
    regime_input_df = load_regime_input_dataset()
    regime_summary_df = pd.read_csv(REGIME_SUMMARY_PATH)
    transition_df = build_all_transition_matrices(regime_input_df, regime_summary_df)
    transition_df.to_csv(REGIME_TRANSITION_MATRIX_PATH, index=False)
    print(transition_df.to_string(index=False))
    print(f"saved_to: {REGIME_TRANSITION_MATRIX_PATH}")
