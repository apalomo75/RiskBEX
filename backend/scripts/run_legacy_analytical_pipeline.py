import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_regime_datasets import main as prepare_regime_datasets  # noqa: E402
from scripts.run_adaptive_backtest import main as run_adaptive_backtest  # noqa: E402
from scripts.run_tail_analysis import main as run_tail_analysis  # noqa: E402


def run_step(index: int, total: int, message: str, step):
    print(f"[{index}/{total}] {message}")
    step()
    print("OK\n")


def main():
    run_step(1, 3, "Preparing clean regime datasets...", prepare_regime_datasets)
    run_step(2, 3, "Running adaptive regime backtest...", run_adaptive_backtest)
    run_step(3, 3, "Running tail risk analysis...", run_tail_analysis)
    print("Full RISKBEX analytical pipeline completed successfully.")


if __name__ == "__main__":
    main()
