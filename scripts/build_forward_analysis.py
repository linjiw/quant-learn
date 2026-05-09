import argparse

from quant_learn.analytics.forward_analysis import (
    export_forward_analysis_report,
    run_forward_analysis,
)
from quant_learn.config import CORE_TICKERS


def main() -> None:
    parser = argparse.ArgumentParser(description="Build forward estimates and decision scorecard.")
    parser.add_argument("--tickers", nargs="*", default=CORE_TICKERS)
    args = parser.parse_args()

    estimates, scorecard = run_forward_analysis(args.tickers)
    report_path = export_forward_analysis_report(estimates, scorecard)
    print(f"Generated {len(estimates)} forward price estimate rows.")
    print(f"Generated {len(scorecard)} investment scorecard rows.")
    print(f"Exported {report_path}.")


if __name__ == "__main__":
    main()
