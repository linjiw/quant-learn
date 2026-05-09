import argparse

from quant_learn.config import CORE_TICKERS
from quant_learn.ingest.valuation import ingest_valuation_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest current valuation snapshots.")
    parser.add_argument("--tickers", nargs="*", default=CORE_TICKERS)
    args = parser.parse_args()

    count = ingest_valuation_snapshot(args.tickers)
    print(f"Upserted {count} valuation snapshot rows.")


if __name__ == "__main__":
    main()
