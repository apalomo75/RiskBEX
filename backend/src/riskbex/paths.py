from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

FIGURES_DIR = BASE_DIR / "figures"
CHAPTER2_FIGURES_DIR = FIGURES_DIR / "chapter2"

RAW_PRICES_PATH = RAW_DATA_DIR / "ibex_prices.csv"
MASTER_DATASET_PATH = PROCESSED_DATA_DIR / "dataset_cap3_master.csv"
CAP4_INPUT_PATH = PROCESSED_DATA_DIR / "dataset_cap4_input.csv"
CAP4_STANDARDIZED_PATH = PROCESSED_DATA_DIR / "dataset_cap4_input_standardized.csv"
