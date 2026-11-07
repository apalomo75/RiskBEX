import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.paths import PROCESSED_DATA_DIR, REGIME_DATASET_PATH, REGIME_SUMMARY_PATH
from src.riskbex.backtesting.exposures import build_cvar_exposure_mapping
from src.riskbex.regimes.interpretation import build_regime_summary


MAIN_OUTPUT_PATH = PROCESSED_DATA_DIR / "regime_dataset_main.csv"
ROBUST_OUTPUT_PATH = PROCESSED_DATA_DIR / "regime_dataset_robust.csv"
MAIN_MAPPING_PATH = PROCESSED_DATA_DIR / "regime_exposure_mapping.csv"
ROBUST_MAPPING_PATH = PROCESSED_DATA_DIR / "regime_exposure_mapping_robust.csv"

REGIME_DATASET_REQUIRED_COLUMNS = [
    "date",
    "ret_1d",
    "sample_split_main",
    "sample_split_robust",
    "main_regime",
    "main_p_regime_0",
    "main_p_regime_1",
    "main_p_regime_2",
    "robust_regime",
    "robust_p_regime_0",
    "robust_p_regime_1",
    "robust_p_regime_2",
]
OPTIONAL_MARKET_COLUMNS = ["ewma_vol", "cvar_95_60d"]
REGIME_SUMMARY_REQUIRED_COLUMNS = ["split", "regime", "economic_label", "risk_order"]

def validate_columns(df, required_columns, dataset_name):
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required {dataset_name} columns: {missing_columns}")


def normalize_label(label):
    return str(label).strip().lower().replace(" ", "_")


def build_label_mapping(regime_summary_df, split):
    split_summary = regime_summary_df[regime_summary_df["split"] == split].copy()
    if split_summary.empty:
        raise ValueError(f"No regime summary rows found for split {split}.")
    split_summary["regime"] = split_summary["regime"].astype(int)
    split_summary["risk_order"] = split_summary["risk_order"].astype(int)
    return split_summary.set_index("regime")[["economic_label", "risk_order"]]


def validate_probabilities(df, dataset_name, tolerance=1e-6):
    probability_columns = ["p_regime_0", "p_regime_1", "p_regime_2"]
    probability_sums = df[probability_columns].sum(axis=1)
    invalid_sums = ~np.isclose(probability_sums, 1.0, atol=tolerance)
    if invalid_sums.any():
        raise ValueError(
            f"{dataset_name} has {int(invalid_sums.sum())} rows with probabilities "
            f"not summing to 1 within tolerance {tolerance}."
        )

    dominant_regimes = np.argmax(df[probability_columns].to_numpy(), axis=1)
    mismatches = df["regime"].to_numpy() != dominant_regimes
    if mismatches.any():
        raise ValueError(
            f"{dataset_name} has {int(mismatches.sum())} rows where regime does not "
            "match argmax(p_regime_0, p_regime_1, p_regime_2)."
        )


def build_clean_regime_dataset(regime_df, regime_summary_df, split, split_column, regime_prefix):
    label_mapping = build_label_mapping(regime_summary_df, split)
    output_df = pd.DataFrame(
        {
            "date": regime_df["date"],
            "ret_1d": regime_df["ret_1d"],
            "ewma_vol": regime_df["ewma_vol"],
            "cvar_95_60d": regime_df["cvar_95_60d"],
            split_column: regime_df[split_column],
            "regime": regime_df[f"{regime_prefix}_regime"].astype(int),
            "p_regime_0": regime_df[f"{regime_prefix}_p_regime_0"],
            "p_regime_1": regime_df[f"{regime_prefix}_p_regime_1"],
            "p_regime_2": regime_df[f"{regime_prefix}_p_regime_2"],
        }
    )
    output_df = output_df.merge(
        label_mapping,
        left_on="regime",
        right_index=True,
        how="left",
    )
    output_df = output_df.rename(columns={"economic_label": "regime_label"})
    output_df = output_df[
        [
            "date",
            "ret_1d",
            "ewma_vol",
            "cvar_95_60d",
            split_column,
            "regime",
            "regime_label",
            "risk_order",
            "p_regime_0",
            "p_regime_1",
            "p_regime_2",
        ]
    ]
    if output_df["regime_label"].isna().any():
        raise ValueError(f"{split} clean dataset has null regime_label values.")
    validate_probabilities(output_df, f"{split} clean dataset")
    return output_df


def build_exposure_mapping(regime_summary_df, split):
    split_summary = regime_summary_df.loc[regime_summary_df["split"] == split]
    return build_cvar_exposure_mapping(split_summary)


def print_dataset_summary(name, df, split_column):
    dates = pd.to_datetime(df["date"], errors="coerce")
    print(f"created {name} shape {df.shape}")
    print(f"date min: {dates.min()}")
    print(f"date max: {dates.max()}")
    print(f"regime counts: {df['regime'].value_counts().sort_index().to_dict()}")
    print(f"regime_label counts: {df['regime_label'].value_counts().to_dict()}")
    print(f"{split_column}: {df[split_column].value_counts().to_dict()}")


def main():
    regime_df = pd.read_csv(REGIME_DATASET_PATH)
    validate_columns(regime_df, REGIME_DATASET_REQUIRED_COLUMNS, "regime dataset")
    validate_columns(regime_df, OPTIONAL_MARKET_COLUMNS, "regime dataset")
    # Never reuse an old full-sample summary to determine historical exposures.
    regime_summary_df = build_regime_summary(regime_df)
    validate_columns(regime_summary_df, REGIME_SUMMARY_REQUIRED_COLUMNS, "regime summary")

    main_df = build_clean_regime_dataset(
        regime_df,
        regime_summary_df,
        split="MAIN",
        split_column="sample_split_main",
        regime_prefix="main",
    )
    robust_df = build_clean_regime_dataset(
        regime_df,
        regime_summary_df,
        split="ROBUST",
        split_column="sample_split_robust",
        regime_prefix="robust",
    )

    main_mapping_df = build_exposure_mapping(regime_summary_df, "MAIN")
    robust_mapping_df = build_exposure_mapping(regime_summary_df, "ROBUST")
    regime_summary_df.to_csv(REGIME_SUMMARY_PATH, index=False)
    main_df.to_csv(MAIN_OUTPUT_PATH, index=False)
    robust_df.to_csv(ROBUST_OUTPUT_PATH, index=False)
    main_mapping_df.to_csv(MAIN_MAPPING_PATH, index=False)
    robust_mapping_df.to_csv(ROBUST_MAPPING_PATH, index=False)

    print_dataset_summary("regime_dataset_main.csv", main_df, "sample_split_main")
    print_dataset_summary("regime_dataset_robust.csv", robust_df, "sample_split_robust")
    print(f"created regime_exposure_mapping.csv shape {main_mapping_df.shape}")
    print(main_mapping_df.to_string(index=False))
    print(f"created regime_exposure_mapping_robust.csv shape {robust_mapping_df.shape}")
    print(robust_mapping_df.to_string(index=False))


if __name__ == "__main__":
    main()
