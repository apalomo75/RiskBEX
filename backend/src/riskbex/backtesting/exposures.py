import numpy as np
import pandas as pd


REQUIRED_MAPPING_COLUMNS = [
    "regime",
    "economic_label",
    "risk_order",
    "target_exposure",
]


def build_cvar_exposure_mapping(
    regime_summary: pd.DataFrame, defensive_alpha: float = 1.0
) -> pd.DataFrame:
    """TFM notebook 03: ratio of mean rolling CVaR, computed on train only.

    The caller must supply a single sample's training summary. Regime identifiers
    are model outputs, not hardcoded economic labels.
    """
    required = ["regime", "economic_label", "risk_order", "mean_cvar_95_60d"]
    missing = [column for column in required if column not in regime_summary]
    if missing:
        raise ValueError(f"Missing CVaR exposure mapping columns: {missing}")
    if not np.isfinite(defensive_alpha) or defensive_alpha <= 0:
        raise ValueError("defensive_alpha must be finite and positive.")
    mapping = regime_summary[required].copy()
    mapping["economic_label"] = (
        mapping["economic_label"].astype(str).str.strip().str.lower().str.replace(" ", "_", regex=False)
    )
    if len(mapping) != 3 or mapping["regime"].duplicated().any():
        raise ValueError("CVaR mapping requires three distinct regimes.")
    ordered = mapping.sort_values("risk_order").reset_index(drop=True)
    if ordered["risk_order"].tolist() != [1, 2, 3] or ordered["economic_label"].tolist() != ["low_risk", "medium_risk", "high_risk"]:
        raise ValueError("CVaR mapping requires ordered low, medium and high risk labels.")
    mapping = ordered
    mapping["cvar_severity_abs"] = mapping["mean_cvar_95_60d"].abs()
    severity = mapping["cvar_severity_abs"].to_numpy(dtype=float)
    if not np.isfinite(severity).all() or (severity <= 0).any():
        raise ValueError("Training CVaR severity must be finite and strictly positive.")
    mapping["cvar_low_abs"] = float(mapping.loc[0, "cvar_severity_abs"])
    mapping["defensive_alpha"] = defensive_alpha
    mapping["target_exposure"] = (
        mapping["cvar_low_abs"] / mapping["cvar_severity_abs"]
    ).pow(defensive_alpha).clip(lower=0.0, upper=1.0)
    low, medium, high = mapping["target_exposure"]
    if not high < medium < low:
        raise ValueError("Expected high_risk exposure < medium_risk < low_risk.")
    mapping["methodology"] = "CVaR_train_abs_ratio"
    return mapping[[
        *REQUIRED_MAPPING_COLUMNS, "mean_cvar_95_60d", "cvar_severity_abs",
        "cvar_low_abs", "defensive_alpha", "methodology",
    ]]


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

