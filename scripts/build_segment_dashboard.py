import argparse

from quant_learn.analytics.segments import build_segment_dashboard
from quant_learn.config import PROJECT_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the segment dashboard markdown report.")
    parser.add_argument("--output", default="reports/segment_dashboard.md")
    args = parser.parse_args()

    output_path = PROJECT_ROOT / args.output
    path = build_segment_dashboard(output_path)
    print(f"Wrote {path}.")


if __name__ == "__main__":
    main()
