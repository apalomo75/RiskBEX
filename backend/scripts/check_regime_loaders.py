import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.data.loaders import (
    load_duration_summary,
    load_model_selection,
    load_regime_dataset,
    load_regime_summary,
    load_transition_matrix,
)


def print_dataset_status(name, df):
    print(f"{name}")
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    if "date" in df.columns:
        print(f"date_min: {df['date'].min()}")
        print(f"date_max: {df['date'].max()}")
    print()


if __name__ == "__main__":
    datasets = [
        ("model_selection", load_model_selection()),
        ("regime_dataset", load_regime_dataset()),
        ("regime_summary", load_regime_summary()),
        ("transition_matrix", load_transition_matrix()),
        ("duration_summary", load_duration_summary()),
    ]

    for name, df in datasets:
        print_dataset_status(name, df)
