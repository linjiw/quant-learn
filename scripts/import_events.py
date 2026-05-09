import argparse
from pathlib import Path

from quant_learn.ingest.manual import import_events


def main() -> None:
    parser = argparse.ArgumentParser(description="Import manually curated events from CSV.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    count = import_events(args.path)
    print(f"Upserted {count} event rows.")


if __name__ == "__main__":
    main()
