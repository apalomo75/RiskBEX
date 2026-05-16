import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm


def fit_markov_regression(
    endog,
    k_regimes,
    maxiter=100,
    search_reps=0,
    em_iter=5,
    method="bfgs",
    disp=False,
):
    endog_series = pd.Series(endog).astype(float).dropna()
    model = sm.tsa.MarkovRegression(
        endog_series,
        k_regimes=k_regimes,
        trend="c",
        switching_variance=True,
    )
    return model.fit(
        disp=disp,
        maxiter=maxiter,
        search_reps=search_reps,
        em_iter=em_iter,
        method=method,
    )


def summarize_markov_result(result):
    return {
        "k_regimes": result.model.k_regimes,
        "aic": result.aic,
        "bic": result.bic,
        "log_likelihood": result.llf,
        "converged": result.mle_retvals.get("converged")
        if hasattr(result, "mle_retvals")
        else None,
    }


def extract_transition_matrix(result):
    raw_matrix = np.asarray(result.regime_transition, dtype=float).squeeze()
    if raw_matrix.ndim != 2 or raw_matrix.shape[0] != raw_matrix.shape[1]:
        raise ValueError(
            "Expected a square transition matrix from MarkovRegression, "
            f"got shape {raw_matrix.shape}."
        )

    # statsmodels stores regime_transition[to_regime, from_regime, t], so columns
    # sum to one. RISKBEX persists transitions as rows=from_regime, cols=to_regime.
    transition_matrix = raw_matrix.T
    row_sums = transition_matrix.sum(axis=1)
    if not np.allclose(row_sums, 1.0, atol=1e-6):
        raise ValueError(
            "Extracted transition matrix rows do not sum to one: "
            f"{row_sums.tolist()}"
        )
    return transition_matrix


def compare_markov_models(train_df, k_values, fit_kwargs=None):
    fit_kwargs = fit_kwargs or {}
    endog = train_df["ret_1d"]
    comparisons = []
    for k_regimes in k_values:
        try:
            result = fit_markov_regression(
                endog,
                k_regimes=k_regimes,
                **fit_kwargs,
            )
            summary = summarize_markov_result(result)
            summary["error"] = None
            comparisons.append(summary)
        except Exception as exc:
            comparisons.append(
                {
                    "k_regimes": k_regimes,
                    "aic": None,
                    "bic": None,
                    "log_likelihood": None,
                    "converged": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return comparisons


def fit_markov_regression_with_attempts(endog, k_regimes, attempts):
    attempt_summaries = []
    successful_results = []

    for attempt in attempts:
        fit_kwargs = dict(attempt)
        try:
            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                result = fit_markov_regression(
                    endog,
                    k_regimes=k_regimes,
                    **fit_kwargs,
                )
            summary = summarize_markov_result(result)
            summary["config"] = fit_kwargs
            summary["warnings"] = [str(warning.message) for warning in caught_warnings]
            summary["error"] = None
            attempt_summaries.append(summary)
            successful_results.append((result, summary))

            if summary["converged"] is True:
                return {
                    "result": result,
                    "selected_summary": summary,
                    "attempts": attempt_summaries,
                }
        except Exception as exc:
            attempt_summaries.append(
                {
                    "k_regimes": k_regimes,
                    "aic": None,
                    "bic": None,
                    "log_likelihood": None,
                    "converged": False,
                    "config": fit_kwargs,
                    "warnings": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    if successful_results:
        result, summary = min(
            successful_results,
            key=lambda item: (
                float("inf") if item[1]["bic"] is None else item[1]["bic"],
                float("inf") if item[1]["aic"] is None else item[1]["aic"],
            ),
        )
        return {
            "result": result,
            "selected_summary": summary,
            "attempts": attempt_summaries,
        }

    return {
        "result": None,
        "selected_summary": None,
        "attempts": attempt_summaries,
    }


def apply_markov_model_to_full_dataset(df, fitted_result, k_regimes):
    endog_full = pd.Series(df["ret_1d"]).astype(float)
    full_model = sm.tsa.MarkovRegression(
        endog_full,
        k_regimes=k_regimes,
        trend="c",
        switching_variance=True,
    )
    filtered_result = full_model.filter(fitted_result.params)
    probabilities = pd.DataFrame(filtered_result.filtered_marginal_probabilities)
    probabilities = probabilities.reset_index(drop=True)
    probabilities.columns = [f"p_regime_{idx}" for idx in range(k_regimes)]
    probabilities["regime"] = np.argmax(probabilities.to_numpy(), axis=1)
    return probabilities
