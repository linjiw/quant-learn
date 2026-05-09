import argparse

from quant_learn.analytics.factor_dashboard import build_factor_dashboard, store_factor_dashboard
from quant_learn.config import CORE_TICKERS, EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and store factor dashboard metrics.")
    parser.add_argument("--tickers", nargs="*", default=CORE_TICKERS)
    parser.add_argument("--export", default="factor_dashboard.csv")
    args = parser.parse_args()

    ensure_directories()
    dashboard = build_factor_dashboard(args.tickers)
    count = store_factor_dashboard(dashboard)
    export_path = EXPORT_DIR / args.export
    dashboard.to_csv(export_path, index=False)
    print(f"Upserted {count} factor dashboard rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
