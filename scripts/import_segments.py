import argparse
from pathlib import Path

from quant_learn.ingest.manual import import_segment_kpis


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manually verified segment KPIs from CSV.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    count = import_segment_kpis(args.path)
    print(f"Upserted {count} segment KPI rows.")


if __name__ == "__main__":
    main()
