import argparse
from pathlib import Path

from quant_learn.analytics.weekly_digest import build_weekly_digest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the weekly governance digest.")
    parser.add_argument("--output", default="reports/weekly_digest.md")
    args = parser.parse_args()

    path = build_weekly_digest(Path(args.output))
    print(f"Wrote {path}.")


if __name__ == "__main__":
    main()
