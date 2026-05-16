import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.paths import (
    BASE_DIR,
    DATA_DIR,
    MASTER_DATASET_PATH,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    REGIME_DATASET_PATH,
    REGIME_DURATION_SUMMARY_PATH,
)


def print_path(name, path):
    print(f"{name}: {path}")


if __name__ == "__main__":
    print_path("BASE_DIR", BASE_DIR)
    print_path("DATA_DIR", DATA_DIR)
    print_path("RAW_DATA_DIR", RAW_DATA_DIR)
    print_path("PROCESSED_DATA_DIR", PROCESSED_DATA_DIR)
    print_path("MASTER_DATASET_PATH", MASTER_DATASET_PATH)
    print_path("REGIME_DATASET_PATH", REGIME_DATASET_PATH)
    print_path("REGIME_DURATION_SUMMARY_PATH", REGIME_DURATION_SUMMARY_PATH)
