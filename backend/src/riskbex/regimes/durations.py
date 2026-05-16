import pandas as pd

from src.riskbex.config import REGIME_TRAIN_LABEL


TRAIN_FILTERED = "TRAIN_FILTERED"
FULL_FILTERED = "FULL_FILTERED"


def _build_label_mapping(regime_summary_df, split_name):
    split_summary = regime_summary_df[regime_summary_df["split"] == split_name].copy()
    if split_summary.empty:
        raise ValueError(f"No regime summary rows found for split {split_name}.")

    required_columns = ["regime", "economic_label", "risk_order"]
    missing_columns = [
        column for column in required_columns if column not in split_summary.columns
    ]
    if missing_columns:
        raise ValueError(f"Missing regime summary columns: {missing_columns}")

    split_summary["regime"] = split_summary["regime"].astype(int)
    return split_summary[required_columns]


def _apply_scope(regime_df, split_column, scope):
    if scope == TRAIN_FILTERED:
        return regime_df[regime_df[split_column] == REGIME_TRAIN_LABEL].copy()
    if scope == FULL_FILTERED:
        return regime_df.copy()
    raise ValueError(f"Unsupported duration scope: {scope}")


def build_duration_summary_for_scope(
    regime_df,
    regime_column,
    split_column,
    split_name,
    scope,
    regime_summary_df,
):
    scoped_df = _apply_scope(regime_df, split_column, scope)
    if scoped_df.empty:
        raise ValueError(f"No rows found for {split_name} {scope}.")

    scoped_df = scoped_df.sort_values("date").reset_index(drop=True)
    scoped_df[regime_column] = scoped_df[regime_column].astype(int)
    regime_changed = scoped_df[regime_column] != scoped_df[regime_column].shift(1)
    scoped_df["block_id"] = regime_changed.cumsum()

    block_df = (
        scoped_df.groupby(["block_id", regime_column], sort=True)
        .size()
        .reset_index(name="duration_trading_days")
        .rename(columns={regime_column: "regime"})
    )

    summary_df = (
        block_df.groupby("regime", sort=True)
        .agg(
            n_blocks=("duration_trading_days", "size"),
            mean_duration_trading_days=("duration_trading_days", "mean"),
            median_duration_trading_days=("duration_trading_days", "median"),
            max_duration_trading_days=("duration_trading_days", "max"),
            min_duration_trading_days=("duration_trading_days", "min"),
            total_obs=("duration_trading_days", "sum"),
        )
        .reset_index()
    )
    summary_df.insert(0, "scope", scope)
    summary_df.insert(0, "split", split_name)
    summary_df["frequency_pct"] = summary_df["total_obs"] / len(scoped_df)

    label_mapping = _build_label_mapping(regime_summary_df, split_name)
    summary_df = summary_df.merge(label_mapping, on="regime", how="left")
    if summary_df[["economic_label", "risk_order"]].isna().any().any():
        missing_regimes = summary_df[summary_df["economic_label"].isna()][
            "regime"
        ].tolist()
        raise ValueError(
            f"Missing label mapping for regimes {missing_regimes} in {split_name}."
        )

    summary_df["risk_order"] = summary_df["risk_order"].astype(int)
    summary_df = summary_df.sort_values(["split", "scope", "risk_order"]).reset_index(
        drop=True
    )
    return summary_df[
        [
            "split",
            "scope",
            "regime",
            "economic_label",
            "risk_order",
            "n_blocks",
            "mean_duration_trading_days",
            "median_duration_trading_days",
            "max_duration_trading_days",
            "min_duration_trading_days",
            "total_obs",
            "frequency_pct",
        ]
    ]


def build_all_duration_summaries(regime_df, regime_summary_df):
    duration_frames = []
    for split_name, regime_column, split_column in [
        ("MAIN", "main_regime", "sample_split_main"),
        ("ROBUST", "robust_regime", "sample_split_robust"),
    ]:
        for scope in [TRAIN_FILTERED, FULL_FILTERED]:
            duration_frames.append(
                build_duration_summary_for_scope(
                    regime_df=regime_df,
                    regime_column=regime_column,
                    split_column=split_column,
                    split_name=split_name,
                    scope=scope,
                    regime_summary_df=regime_summary_df,
                )
            )

    return pd.concat(duration_frames, ignore_index=True)
