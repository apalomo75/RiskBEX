import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.config import REGIME_FEATURES, REGIME_SPLIT_COLUMN
from src.riskbex.data.loaders import load_regime_input_dataset, load_regime_train_dataset


def print_date_range(label, df):
    if "date" not in df.columns or df.empty:
        print(f"{label}: N/A")
        return
    print(f"{label}: {df['date'].min()} to {df['date'].max()}")


if __name__ == "__main__":
    regime_input_df = load_regime_input_dataset()
    regime_train_df = load_regime_train_dataset()

    print(f"shape_total: {regime_input_df.shape}")
    print(f"shape_train: {regime_train_df.shape}")
    print_date_range("date_range_total", regime_input_df)
    print_date_range("date_range_train", regime_train_df)
    print(f"feature_columns: {REGIME_FEATURES}")
    print("na_by_feature:")
    for feature in REGIME_FEATURES:
        print(f"  {feature}: {int(regime_input_df[feature].isna().sum())}")
    print(f"{REGIME_SPLIT_COLUMN}_counts:")
    for label, count in regime_input_df[REGIME_SPLIT_COLUMN].value_counts().to_dict().items():
        print(f"  {label}: {count}")
