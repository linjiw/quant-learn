import argparse
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.analytics.ai_framework_tracker import REPORT_PATH, run_ai_framework_tracker


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AI trusted-execution tracker report.")
    parser.add_argument("--as-of-date", type=str, default=None)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    as_of_date: Optional[date] = None
    if args.as_of_date:
        as_of_date = pd.to_datetime(args.as_of_date).date()

    decisions, report_path = run_ai_framework_tracker(
        as_of_date=as_of_date,
        output_path=args.output,
    )
    print(f"Generated {len(decisions)} AI framework decision rows.")
    print(f"Exported {report_path}.")


if __name__ == "__main__":
    main()
