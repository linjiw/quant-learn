import argparse

from quant_learn.config import DEFAULT_PRICE_TICKERS
from quant_learn.ingest.prices import ingest_prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest daily Yahoo Finance prices.")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_PRICE_TICKERS)
    args = parser.parse_args()

    count = ingest_prices(tickers=args.tickers, start=args.start, end=args.end)
    print(f"Upserted {count} price rows.")


if __name__ == "__main__":
    main()
