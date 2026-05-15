import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.data.loaders import load_regime_input_dataset
from src.riskbex.paths import REGIME_DATASET_PATH
from src.riskbex.regimes.outputs import build_regime_dataset


if __name__ == "__main__":
    regime_input_df = load_regime_input_dataset()
    regime_dataset_df = build_regime_dataset(regime_input_df)
    regime_dataset_df.to_csv(REGIME_DATASET_PATH, index=False)

    print(f"shape: {regime_dataset_df.shape}")
    print(f"date_range: {regime_dataset_df['date'].min()} to {regime_dataset_df['date'].max()}")
    print("main_regime_distribution:")
    print(regime_dataset_df["main_regime"].value_counts().sort_index().to_string())
    print("robust_regime_distribution:")
    print(regime_dataset_df["robust_regime"].value_counts().sort_index().to_string())
    print(f"saved_to: {REGIME_DATASET_PATH}")
