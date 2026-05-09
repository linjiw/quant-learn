import argparse

from quant_learn.analytics.segments import build_tsmc_monthly_segment_kpis, store_segment_kpis
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge TSMC monthly revenue into segment KPIs.")
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--export", default="tsmc_segment_kpis.csv")
    args = parser.parse_args()

    ensure_directories()
    segment_kpis = build_tsmc_monthly_segment_kpis(months=args.months)
    count = store_segment_kpis(segment_kpis)
    export_path = EXPORT_DIR / args.export
    segment_kpis.to_csv(export_path, index=False)
    print(f"Upserted {count} TSMC segment KPI rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
