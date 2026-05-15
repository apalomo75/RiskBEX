import pandas as pd


ECONOMIC_LABELS = ["Low Risk", "Medium Risk", "High Risk"]


def summarize_regimes(df, regime_column, split_name):
    grouped = df.groupby(regime_column, sort=True)
    summary_df = grouped.agg(
        n_obs=("ret_1d", "size"),
        mean_ret_1d=("ret_1d", "mean"),
        mean_ewma_vol=("ewma_vol", "mean"),
        mean_cvar_95_60d=("cvar_95_60d", "mean"),
        median_ewma_vol=("ewma_vol", "median"),
        median_cvar_95_60d=("cvar_95_60d", "median"),
    ).reset_index()
    summary_df = summary_df.rename(columns={regime_column: "regime"})
    summary_df.insert(0, "split", split_name)
    summary_df["frequency_pct"] = summary_df["n_obs"] / len(df)
    return summary_df[
        [
            "split",
            "regime",
            "n_obs",
            "frequency_pct",
            "mean_ret_1d",
            "mean_ewma_vol",
            "mean_cvar_95_60d",
            "median_ewma_vol",
            "median_cvar_95_60d",
        ]
    ]


def build_regime_label_mapping(summary_df):
    working_df = summary_df.copy()
    working_df["vol_rank"] = working_df["mean_ewma_vol"].rank(method="first")
    working_df["cvar_rank"] = working_df["mean_cvar_95_60d"].abs().rank(method="first")
    working_df["risk_severity"] = working_df["vol_rank"] + working_df["cvar_rank"]
    working_df = working_df.sort_values(["risk_severity", "regime"]).reset_index(drop=True)
    working_df["economic_label"] = ECONOMIC_LABELS[: len(working_df)]
    working_df["risk_order"] = range(1, len(working_df) + 1)
    return working_df[["regime", "economic_label", "risk_order", "risk_severity"]]


def build_regime_summary(regime_dataset_df):
    summaries = []
    for split_name, regime_column in [
        ("MAIN", "main_regime"),
        ("ROBUST", "robust_regime"),
    ]:
        summary_df = summarize_regimes(regime_dataset_df, regime_column, split_name)
        mapping_df = build_regime_label_mapping(summary_df)
        summaries.append(summary_df.merge(mapping_df, on="regime", how="left"))
    return pd.concat(summaries, ignore_index=True)
