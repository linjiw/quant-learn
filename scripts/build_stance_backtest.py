import argparse
from pathlib import Path

from quant_learn.analytics.stance_backtest import (
    DEFAULT_HORIZONS,
    build_stance_backtest_observations,
    build_stance_backtest_report,
    build_stance_backtest_summary,
    store_stance_backtest_observations,
    store_stance_backtest_summary,
)
from quant_learn.config import EXPORT_DIR, ensure_directories


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build archive-based stance outcome tracking.",
    )
    parser.add_argument("--horizons", nargs="*", type=int, default=list(DEFAULT_HORIZONS))
    parser.add_argument("--model-name", default="three_factor_raw")
    parser.add_argument("--lookback-window", type=int, default=60)
    parser.add_argument("--report", default="reports/stance_backtest_report.md")
    args = parser.parse_args()

    ensure_directories()
    observations = build_stance_backtest_observations(
        horizons=tuple(args.horizons),
        model_name=args.model_name,
        lookback_window=args.lookback_window,
    )
    observation_count = store_stance_backtest_observations(observations)
    observation_export = EXPORT_DIR / "stance_backtest_observations.csv"
    observations.to_csv(observation_export, index=False)

    summary = build_stance_backtest_summary(observations)
    summary_count = store_stance_backtest_summary(summary)
    summary_export = EXPORT_DIR / "stance_backtest_summary.csv"
    summary.to_csv(summary_export, index=False)

    report_path = build_stance_backtest_report(Path(args.report))

    print(f"Upserted {observation_count} stance_backtest_observations rows.")
    print(f"Upserted {summary_count} stance_backtest_summary rows.")
    print(f"Exported {observation_export}.")
    print(f"Exported {summary_export}.")
    print(f"Wrote {report_path}.")


if __name__ == "__main__":
    main()
