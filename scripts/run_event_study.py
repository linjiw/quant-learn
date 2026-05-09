import argparse

from quant_learn.analytics.event_study import run_event_study
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an event study from stored events and prices."
    )
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--window-before", type=int, default=5)
    parser.add_argument("--window-after", type=int, default=20)
    parser.add_argument("--benchmark", default="QQQ")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--export", default=None)
    args = parser.parse_args()

    ensure_directories()
    result = run_event_study(
        event_type=args.event_type,
        window_before=args.window_before,
        window_after=args.window_after,
        benchmark=args.benchmark,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    export_name = args.export or f"event_study_{args.event_type}.csv"
    export_path = EXPORT_DIR / export_name
    result.to_csv(export_path, index=False)
    print(f"Generated {len(result)} event-study rows.")
    print(f"Exported {export_path}.")


if __name__ == "__main__":
    main()
