import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.tail_risk.tail_analysis import (  # noqa: E402
    TAIL_ANALYSIS_MAIN_PATH,
    TAIL_ANALYSIS_ROBUST_PATH,
    TAIL_METRICS_PATH,
    TAIL_THRESHOLDS_PATH,
    save_tail_outputs,
)


def print_analysis_summary(name, df):
    print(f"created {name} shape {df.shape}")
    if "date" in df.columns:
        print(f"date min: {df['date'].min()}")
        print(f"date max: {df['date'].max()}")
    if "stress_tail_event" in df.columns:
        print(f"tail event counts: {df['stress_tail_event'].value_counts().to_dict()}")


def main():
    main_df, robust_df, metrics_df, thresholds_df = save_tail_outputs()

    print_analysis_summary("tail_analysis_main.csv", main_df)
    print(f"saved_to: {TAIL_ANALYSIS_MAIN_PATH}")
    print_analysis_summary("tail_analysis_robust.csv", robust_df)
    print(f"saved_to: {TAIL_ANALYSIS_ROBUST_PATH}")

    print(f"created tail_thresholds.csv shape {thresholds_df.shape}")
    print(thresholds_df.to_string(index=False))
    print(f"saved_to: {TAIL_THRESHOLDS_PATH}")

    print(f"created tail_metrics.csv shape {metrics_df.shape}")
    print(metrics_df.to_string(index=False))
    print(f"saved_to: {TAIL_METRICS_PATH}")


if __name__ == "__main__":
    main()
