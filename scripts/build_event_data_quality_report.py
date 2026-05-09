import argparse

from quant_learn.analytics.data_quality import build_event_data_quality_report
from quant_learn.config import PROJECT_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Build event return data quality report.")
    parser.add_argument("--output", default="reports/event_data_quality_report.md")
    args = parser.parse_args()

    path = build_event_data_quality_report(PROJECT_ROOT / args.output)
    print(f"Wrote {path}.")


if __name__ == "__main__":
    main()
