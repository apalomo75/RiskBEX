import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.paths import (
    BASE_DIR,
    CHAPTER2_FIGURES_DIR,
    MASTER_DATASET_PATH,
    RAW_PRICES_PATH,
)


def print_path_status(name, path):
    print(f"{name}: {path} | exists={path.exists()}")


if __name__ == "__main__":
    print_path_status("BASE_DIR", BASE_DIR)
    print_path_status("MASTER_DATASET_PATH", MASTER_DATASET_PATH)
    print_path_status("RAW_PRICES_PATH", RAW_PRICES_PATH)
    print_path_status("CHAPTER2_FIGURES_DIR", CHAPTER2_FIGURES_DIR)
