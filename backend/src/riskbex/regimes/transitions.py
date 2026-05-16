import pandas as pd

from src.riskbex.config import REGIME_TRAIN_LABEL
from src.riskbex.regimes.markov_switching import (
    extract_transition_matrix,
    fit_markov_regression,
)


K_REGIMES = 3
FIT_KWARGS = {"maxiter": 500}


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
    return split_summary.set_index("regime")[["economic_label", "risk_order"]]


def build_transition_matrix_for_split(df, split_name, split_column, regime_summary_df):
    train_df = df[df[split_column] == REGIME_TRAIN_LABEL].reset_index(drop=True)
    if train_df.empty:
        raise ValueError(f"No training rows found for split column {split_column}.")

    fitted_result = fit_markov_regression(
        train_df["ret_1d"],
        k_regimes=K_REGIMES,
        **FIT_KWARGS,
    )
    transition_matrix = extract_transition_matrix(fitted_result)
    label_mapping = _build_label_mapping(regime_summary_df, split_name)

    rows = []
    for from_regime in range(K_REGIMES):
        for to_regime in range(K_REGIMES):
            if from_regime not in label_mapping.index:
                raise ValueError(
                    f"Missing label mapping for regime {from_regime} in {split_name}."
                )
            if to_regime not in label_mapping.index:
                raise ValueError(
                    f"Missing label mapping for regime {to_regime} in {split_name}."
                )

            from_row = label_mapping.loc[from_regime]
            to_row = label_mapping.loc[to_regime]
            rows.append(
                {
                    "split": split_name,
                    "from_regime": from_regime,
                    "from_label": from_row["economic_label"],
                    "from_risk_order": int(from_row["risk_order"]),
                    "to_regime": to_regime,
                    "to_label": to_row["economic_label"],
                    "to_risk_order": int(to_row["risk_order"]),
                    "transition_probability": float(
                        transition_matrix[from_regime, to_regime]
                    ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "split",
            "from_regime",
            "from_label",
            "from_risk_order",
            "to_regime",
            "to_label",
            "to_risk_order",
            "transition_probability",
        ],
    )


def build_all_transition_matrices(df, regime_summary_df):
    transition_frames = [
        build_transition_matrix_for_split(
            df,
            split_name="MAIN",
            split_column="sample_split_main",
            regime_summary_df=regime_summary_df,
        ),
        build_transition_matrix_for_split(
            df,
            split_name="ROBUST",
            split_column="sample_split_robust",
            regime_summary_df=regime_summary_df,
        ),
    ]
    return pd.concat(transition_frames, ignore_index=True)
