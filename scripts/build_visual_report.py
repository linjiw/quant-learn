import argparse
from pathlib import Path

from quant_learn.analytics.visual_report import build_visual_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the four-stock visual quant report.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--report-name", default="ai_compute_quant_report.md")
    args = parser.parse_args()

    report_path = build_visual_report(args.output_dir, args.report_name)
    print(f"Generated {report_path}.")


if __name__ == "__main__":
    main()
