import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.config import REGIME_CANDIDATE_K
from src.riskbex.data.loaders import load_regime_input_dataset
from src.riskbex.regimes.markov_switching import compare_markov_models


def format_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def print_results(split_name, results):
    print(f"\n{split_name}")
    print("split,k_regimes,AIC,BIC,log_likelihood,converged,error")
    for row in results:
        print(
            ",".join(
                [
                    split_name,
                    format_value(row["k_regimes"]),
                    format_value(row["aic"]),
                    format_value(row["bic"]),
                    format_value(row["log_likelihood"]),
                    format_value(row["converged"]),
                    format_value(row["error"]),
                ]
            )
        )


if __name__ == "__main__":
    df = load_regime_input_dataset()

    main_train_df = df[df["sample_split_main"] == "train"].reset_index(drop=True)
    robust_train_df = df[df["sample_split_robust"] == "train"].reset_index(drop=True)

    print(f"shape_main_train: {main_train_df.shape}")
    print(f"shape_robust_train: {robust_train_df.shape}")

    main_results = compare_markov_models(main_train_df, REGIME_CANDIDATE_K)
    robust_results = compare_markov_models(robust_train_df, REGIME_CANDIDATE_K)

    print_results("MAIN", main_results)
    print_results("ROBUST", robust_results)
