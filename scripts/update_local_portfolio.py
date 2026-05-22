"""Update the local/private AI framework portfolio tracker."""

import argparse
from datetime import date

from quant_learn.analytics.local_portfolio import DEFAULT_INITIAL_CAPITAL, update_local_portfolio


def main() -> None:
    parser = argparse.ArgumentParser(description="Update local AI framework portfolio snapshots.")
    parser.add_argument("--capital", type=float, default=DEFAULT_INITIAL_CAPITAL)
    parser.add_argument("--snapshot-date", default=None, help="YYYY-MM-DD; defaults to today.")
    parser.add_argument("--skip-price-ingest", action="store_true")
    parser.add_argument(
        "--force-reinitialize",
        action="store_true",
        help="Rebuild the initial lot file from current prices. This resets the cost basis.",
    )
    args = parser.parse_args()

    snapshot_date = date.fromisoformat(args.snapshot_date) if args.snapshot_date else None
    site_data = update_local_portfolio(
        initial_capital=args.capital,
        snapshot_date=snapshot_date,
        ingest_latest_prices=not args.skip_price_ingest,
        force_reinitialize=args.force_reinitialize,
    )
    summary = site_data["summary"]
    print(
        "Updated local portfolio: "
        f"{site_data['asOfDate']} value=${summary['total_value_usd']:.2f} "
        f"pnl=${summary['pnl_usd']:.2f} return={summary['return_pct']:.2f}%"
    )


if __name__ == "__main__":
    main()
