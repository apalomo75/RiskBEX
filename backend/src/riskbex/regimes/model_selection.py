import pandas as pd

from src.riskbex.config import REGIME_CANDIDATE_K
from src.riskbex.regimes.markov_switching import compare_markov_models


SPLIT_DEFINITIONS = [
    ("MAIN", "sample_split_main"),
    ("ROBUST", "sample_split_robust"),
]


def _build_split_rows(df, split_name, split_column):
    train_df = df[df[split_column] == "train"].reset_index(drop=True)
    model_results = compare_markov_models(
        train_df,
        REGIME_CANDIDATE_K,
        fit_kwargs={"maxiter": 500},
    )
    rows = []
    for result in model_results:
        rows.append(
            {
                "split": split_name,
                "split_column": split_column,
                "train_start": train_df["date"].min(),
                "train_end": train_df["date"].max(),
                "n_obs_train": len(train_df),
                "k_regimes": result["k_regimes"],
                "aic": result["aic"],
                "bic": result["bic"],
                "log_likelihood": result["log_likelihood"],
                "converged": result["converged"],
                "selected": result["k_regimes"] == 3 and result["converged"] is True,
            }
        )
    return rows


def build_model_selection_table(df):
    rows = []
    for split_name, split_column in SPLIT_DEFINITIONS:
        rows.extend(_build_split_rows(df, split_name, split_column))
    return pd.DataFrame(
        rows,
        columns=[
            "split",
            "split_column",
            "train_start",
            "train_end",
            "n_obs_train",
            "k_regimes",
            "aic",
            "bic",
            "log_likelihood",
            "converged",
            "selected",
        ],
    )
