"""Compatibility entrypoint to the single versioned MAIN pipeline.

Legacy academic CSV generation remains available explicitly in
run_legacy_analytical_pipeline.py; it is never invoked by daily updates.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from scripts.run_daily_update import main

if __name__ == '__main__':
    main()
