import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.data.loaders import load_regime_input_dataset
from src.riskbex.regimes.markov_switching import fit_markov_regression_with_attempts


ATTEMPTS = [
    {"maxiter": 500},
    {"maxiter": 1000},
    {"maxiter": 1000, "search_reps": 10},
    {"maxiter": 1500, "search_reps": 20},
]


def format_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def print_split_results(split_name, train_df):
    print(f"\n{split_name}")
    print(f"shape_train: {train_df.shape}")
    if "date" in train_df.columns and not train_df.empty:
        print(f"date_range_train: {train_df['date'].min()} to {train_df['date'].max()}")

    result_payload = fit_markov_regression_with_attempts(
        train_df["ret_1d"],
        k_regimes=3,
        attempts=ATTEMPTS,
    )

    print("attempt,config,AIC,BIC,log_likelihood,converged,warnings,error")
    for idx, attempt_summary in enumerate(result_payload["attempts"], start=1):
        print(
            "|".join(
                [
                    str(idx),
                    format_value(attempt_summary["config"]),
                    format_value(attempt_summary["aic"]),
                    format_value(attempt_summary["bic"]),
                    format_value(attempt_summary["log_likelihood"]),
                    format_value(attempt_summary["converged"]),
                    " ; ".join(attempt_summary["warnings"]),
                    format_value(attempt_summary["error"]),
                ]
            )
        )

    selected_summary = result_payload["selected_summary"]
    if selected_summary is None:
        print("selected_config: None")
        print("selected_converged: False")
        return

    print(f"selected_config: {selected_summary['config']}")
    print(f"selected_AIC: {selected_summary['aic']}")
    print(f"selected_BIC: {selected_summary['bic']}")
    print(f"selected_log_likelihood: {selected_summary['log_likelihood']}")
    print(f"selected_converged: {selected_summary['converged']}")


if __name__ == "__main__":
    df = load_regime_input_dataset()
    main_train_df = df[df["sample_split_main"] == "train"].reset_index(drop=True)
    robust_train_df = df[df["sample_split_robust"] == "train"].reset_index(drop=True)

    print_split_results("MAIN", main_train_df)
    print_split_results("ROBUST", robust_train_df)
