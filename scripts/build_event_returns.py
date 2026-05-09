import argparse

from quant_learn.analytics.event_study import (
    build_event_returns,
    store_event_returns,
    validate_event_return_invariants,
)
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(description="Build event-level return windows.")
    parser.add_argument("--event-type", default=None)
    parser.add_argument("--benchmark", default="QQQ")
    parser.add_argument("--sector-benchmark", default="SOXX")
    parser.add_argument(
        "--benchmarks",
        nargs="*",
        default=None,
        help="Optional benchmark list. Defaults to QQQ SOXX SMH.",
    )
    parser.add_argument("--export", default="event_returns.csv")
    args = parser.parse_args()

    ensure_directories()
    event_returns = build_event_returns(
        event_type=args.event_type,
        benchmark=args.benchmark,
        sector_benchmark=args.sector_benchmark,
        benchmark_tickers=args.benchmarks,
    )
    count = store_event_returns(event_returns)
    invariants = validate_event_return_invariants(event_returns)
    export_path = EXPORT_DIR / args.export
    event_returns.to_csv(export_path, index=False)
    print(f"Upserted {count} event return rows.")
    print(
        "Invariant: "
        f"{invariants['actual_rows']} actual rows / {invariants['expected_rows']} expected rows."
    )
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
