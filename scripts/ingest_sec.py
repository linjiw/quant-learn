import argparse

from quant_learn.config import SEC_CIKS
from quant_learn.ingest.sec import ingest_sec


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC filings and selected company facts.")
    parser.add_argument("--tickers", nargs="*", default=list(SEC_CIKS.keys()))
    args = parser.parse_args()

    counts = ingest_sec(args.tickers)
    print(f"Upserted {counts['sec_filings']} SEC filing rows.")
    print(f"Upserted {counts['sec_facts']} SEC fact rows.")


if __name__ == "__main__":
    main()
