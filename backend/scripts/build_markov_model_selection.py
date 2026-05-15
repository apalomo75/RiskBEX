import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.data.loaders import load_regime_input_dataset
from src.riskbex.paths import REGIME_MODEL_SELECTION_PATH
from src.riskbex.regimes.model_selection import build_model_selection_table


if __name__ == "__main__":
    regime_input_df = load_regime_input_dataset()
    model_selection_df = build_model_selection_table(regime_input_df)
    model_selection_df.to_csv(REGIME_MODEL_SELECTION_PATH, index=False)
    print(model_selection_df.to_string(index=False))
    print(f"saved_to: {REGIME_MODEL_SELECTION_PATH}")
