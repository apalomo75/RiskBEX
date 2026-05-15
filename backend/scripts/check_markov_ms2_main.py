import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.data.loaders import load_regime_train_dataset
from src.riskbex.regimes.markov_switching import (
    fit_markov_regression,
    summarize_markov_result,
)


if __name__ == "__main__":
    train_df = load_regime_train_dataset()
    endog_train = train_df["ret_1d"]

    print(f"shape_train: {train_df.shape}")
    if "date" in train_df.columns and not train_df.empty:
        print(f"date_range_train: {train_df['date'].min()} to {train_df['date'].max()}")

    try:
        result = fit_markov_regression(endog_train, k_regimes=2)
    except Exception as exc:
        print(f"fit_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise

    summary = summarize_markov_result(result)
    if summary["converged"] is False:
        print("warning: MarkovRegression fit did not converge", file=sys.stderr)

    print(f"k_regimes: {summary['k_regimes']}")
    print(f"AIC: {summary['aic']}")
    print(f"BIC: {summary['bic']}")
    print(f"log_likelihood: {summary['log_likelihood']}")
    print(f"converged: {summary['converged']}")
