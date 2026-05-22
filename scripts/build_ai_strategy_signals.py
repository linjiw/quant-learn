import argparse
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.analytics.ai_strategy_signals import REPORT_PATH, run_ai_strategy_signals


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 1 AI strategy review signals.")
    parser.add_argument("--as-of-date", type=str, default=None)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    as_of_date: Optional[date] = None
    if args.as_of_date:
        as_of_date = pd.to_datetime(args.as_of_date).date()

    signals, report_path = run_ai_strategy_signals(
        as_of_date=as_of_date,
        output_path=args.output,
    )
    print(f"Generated {len(signals)} AI strategy signal rows.")
    print(f"Exported {report_path}.")


if __name__ == "__main__":
    main()
