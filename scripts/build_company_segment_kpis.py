import argparse

from quant_learn.analytics.segments import build_company_segment_kpis, store_segment_kpis
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge company fundamentals into segment KPIs.")
    parser.add_argument("--tickers", nargs="*", default=["GOOGL", "NVDA", "AMD"])
    parser.add_argument("--quarters", type=int, default=8)
    parser.add_argument("--export", default="company_segment_kpis.csv")
    args = parser.parse_args()

    ensure_directories()
    segment_kpis = build_company_segment_kpis(tickers=args.tickers, quarters=args.quarters)
    count = store_segment_kpis(segment_kpis)
    export_path = EXPORT_DIR / args.export
    segment_kpis.to_csv(export_path, index=False)
    print(f"Upserted {count} company-level segment KPI rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
