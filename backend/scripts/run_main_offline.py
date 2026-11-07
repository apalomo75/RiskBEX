"""Historical prices through an explicit cutoff -> MAIN JSON signal, stdout only."""

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from src.riskbex.engine.package import load_main_package
from src.riskbex.engine.service import infer_main_signals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=BACKEND / "model_packages/main-v1")
    parser.add_argument("--prices", type=Path, required=True, help="Local CSV: date, ibex_close; no download.")
    parser.add_argument("--as-of", required=True, help="Information cutoff YYYY-MM-DD, not a future target date.")
    args = parser.parse_args()
    package = load_main_package(args.package)
    prices = pd.read_csv(args.prices, float_precision="round_trip")
    print(json.dumps(infer_main_signals(package, prices, as_of=args.as_of), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
