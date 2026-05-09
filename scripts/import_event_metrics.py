import argparse
from pathlib import Path

from quant_learn.ingest.manual import import_event_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manually curated event metrics from CSV.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    count = import_event_metrics(args.path)
    print(f"Upserted {count} event metric rows.")


if __name__ == "__main__":
    main()
