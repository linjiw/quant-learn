import argparse

from quant_learn.ingest.tsmc import ingest_tsmc_monthly_revenue


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TSMC monthly revenue.")
    parser.add_argument("--years", nargs="+", type=int, required=True)
    args = parser.parse_args()

    count = ingest_tsmc_monthly_revenue(args.years)
    print(f"Upserted {count} TSMC monthly revenue rows.")


if __name__ == "__main__":
    main()
