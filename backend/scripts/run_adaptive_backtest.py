import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.riskbex.backtesting.regime_backtest import (  # noqa: E402
    BACKTEST_MAIN_PATH,
    BACKTEST_METRICS_PATH,
    BACKTEST_ROBUST_PATH,
    save_backtest_outputs,
)


def print_backtest_summary(name, df):
    print(f"created {name} shape {df.shape}")
    if "date" in df.columns:
        dates = df["date"]
        print(f"date min: {dates.min()}")
        print(f"date max: {dates.max()}")
    if "strategy_exposure" in df.columns:
        print(
            "strategy_exposure unique: "
            f"{sorted(df['strategy_exposure'].dropna().unique().tolist())}"
        )
    if "target_exposure" in df.columns:
        print(
            "target_exposure unique: "
            f"{sorted(df['target_exposure'].dropna().unique().tolist())}"
        )


if __name__ == "__main__":
    main_df, robust_df, metrics_df = save_backtest_outputs()

    print_backtest_summary("adaptive_backtest_main.csv", main_df)
    print(f"saved_to: {BACKTEST_MAIN_PATH}")
    print_backtest_summary("adaptive_backtest_robust.csv", robust_df)
    print(f"saved_to: {BACKTEST_ROBUST_PATH}")
    print(f"created adaptive_backtest_metrics.csv shape {metrics_df.shape}")
    print(metrics_df.to_string(index=False))
    print(f"saved_to: {BACKTEST_METRICS_PATH}")
