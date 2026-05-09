import argparse

from quant_learn.analytics.sec_segments import build_sec_segment_kpis
from quant_learn.analytics.segments import store_segment_kpis
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract segment KPIs from official SEC filings.")
    parser.add_argument("--tickers", nargs="*", default=["GOOGL", "NVDA", "AMD"])
    parser.add_argument("--max-filings", type=int, default=12)
    parser.add_argument("--export", default="sec_segment_kpis.csv")
    args = parser.parse_args()

    ensure_directories()
    segment_kpis = build_sec_segment_kpis(tickers=args.tickers, max_filings=args.max_filings)
    count = store_segment_kpis(segment_kpis)
    export_path = EXPORT_DIR / args.export
    segment_kpis.to_csv(export_path, index=False)
    print(f"Upserted {count} SEC-derived segment KPI rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
