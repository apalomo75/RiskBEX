import pandas as pd

from src.riskbex.regimes.markov_switching import (
    apply_markov_model_to_full_dataset,
    fit_markov_regression,
)


K_REGIMES = 3
FIT_KWARGS = {"maxiter": 500}


def _fit_and_apply(df, split_column):
    train_df = df[df[split_column] == "train"].reset_index(drop=True)
    fitted_result = fit_markov_regression(
        train_df["ret_1d"],
        k_regimes=K_REGIMES,
        **FIT_KWARGS,
    )
    return apply_markov_model_to_full_dataset(df, fitted_result, K_REGIMES)


def _prefixed_regime_columns(probability_df, prefix):
    output_df = probability_df.rename(
        columns={
            "regime": f"{prefix}_regime",
            "p_regime_0": f"{prefix}_p_regime_0",
            "p_regime_1": f"{prefix}_p_regime_1",
            "p_regime_2": f"{prefix}_p_regime_2",
        }
    )
    return output_df[
        [
            f"{prefix}_regime",
            f"{prefix}_p_regime_0",
            f"{prefix}_p_regime_1",
            f"{prefix}_p_regime_2",
        ]
    ]


def build_regime_dataset(df):
    base_columns = [
        "date",
        "ret_1d",
        "ewma_vol",
        "cvar_95_60d",
        "sample_split_main",
        "sample_split_robust",
    ]
    base_df = df[base_columns].copy().reset_index(drop=True)

    main_probabilities = _fit_and_apply(df, "sample_split_main")
    robust_probabilities = _fit_and_apply(df, "sample_split_robust")

    return pd.concat(
        [
            base_df,
            _prefixed_regime_columns(main_probabilities, "main"),
            _prefixed_regime_columns(robust_probabilities, "robust"),
        ],
        axis=1,
    )
