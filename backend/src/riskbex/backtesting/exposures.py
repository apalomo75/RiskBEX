import pandas as pd


REQUIRED_MAPPING_COLUMNS = [
    "regime",
    "economic_label",
    "risk_order",
    "target_exposure",
]


def validate_exposure_mapping(mapping_df: pd.DataFrame) -> None:
    missing_columns = [
        column for column in REQUIRED_MAPPING_COLUMNS if column not in mapping_df.columns
    ]
    if missing_columns:
        raise ValueError(f"Missing required exposure mapping columns: {missing_columns}")
    if mapping_df["regime"].duplicated().any():
        duplicated = mapping_df.loc[mapping_df["regime"].duplicated(), "regime"].tolist()
        raise ValueError(f"Exposure mapping has duplicated regimes: {duplicated}")
    if mapping_df["target_exposure"].isna().any():
        raise ValueError("Exposure mapping has null target_exposure values.")


def apply_target_exposure(
    df: pd.DataFrame,
    mapping_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_exposure_mapping(mapping_df)
    output_df = df.copy()
    exposure_by_regime = mapping_df.set_index("regime")["target_exposure"]
    output_df["target_exposure"] = output_df["regime"].map(exposure_by_regime)

    if output_df["target_exposure"].isna().any():
        missing_regimes = sorted(
            output_df.loc[output_df["target_exposure"].isna(), "regime"]
            .dropna()
            .unique()
            .tolist()
        )
        raise ValueError(
            "Some out-of-sample regimes do not have target_exposure: "
            f"{missing_regimes}"
        )
    return output_df


def apply_shifted_exposure(df: pd.DataFrame) -> pd.DataFrame:
    output_df = df.copy()
    output_df["strategy_exposure"] = output_df["target_exposure"].shift(1)

    expected_nulls = int(output_df["strategy_exposure"].isna().sum())
    if expected_nulls != 1:
        raise ValueError(
            "strategy_exposure must contain exactly one null before dropna, "
            f"found {expected_nulls}."
        )

    output_df = output_df.dropna(subset=["strategy_exposure"]).reset_index(drop=True)
    if output_df["strategy_exposure"].isna().any():
        raise ValueError("strategy_exposure still contains null values after dropna.")
    return output_df

