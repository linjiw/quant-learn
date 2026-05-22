"""Daily refresh workflow for the AI trusted-execution dashboard."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from quant_learn.config import PROJECT_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh core data, rebuild AI framework outputs, and build the Pages site."
    )
    parser.add_argument("--price-start", default="2018-01-01")
    parser.add_argument("--tsmc-years", nargs="*", type=int, default=None)
    parser.add_argument("--skip-market-data", action="store_true")
    parser.add_argument("--include-sec", action="store_true")
    parser.add_argument("--skip-link-audit", action="store_true")
    parser.add_argument("--pages-output", type=Path, default=PROJECT_ROOT / "public")
    args = parser.parse_args()

    print("== initialize database ==")
    _run_python_module("scripts.init_db")

    if not args.skip_market_data:
        print("== ingest prices ==")
        _run_python_module("scripts.ingest_prices", "--start", args.price_start)

        print("== ingest TSMC monthly revenue ==")
        years = args.tsmc_years or _default_tsmc_years()
        _run_python_module("scripts.ingest_tsmc_revenue", "--years", *[str(year) for year in years])

        if args.include_sec:
            if os.environ.get("SEC_USER_AGENT"):
                print("== ingest SEC facts ==")
                _run_python_module("scripts.ingest_sec")
            else:
                print("Skipping SEC ingest because SEC_USER_AGENT is not set.")

    print("== import AI framework manual snapshots ==")
    _run_python_module("scripts.import_ai_framework")

    print("== build AI framework tracker ==")
    _run_python_module("scripts.build_ai_framework_tracker")

    print("== build AI strategy signals ==")
    _run_python_module("scripts.build_ai_strategy_signals")

    print("== validate source site data ==")
    _run_node("scripts/validate_ai_framework_site.mjs")

    print("== build Pages artifact ==")
    _run_python_module("scripts.build_ai_framework_pages", "--output-dir", str(args.pages_output))

    print("== validate Pages artifact ==")
    _run_node("scripts/validate_ai_framework_site.mjs", "--site-dir", str(args.pages_output))

    if not args.skip_link_audit:
        print("== audit source links ==")
        _run_node("scripts/check_ai_framework_sources.mjs", "--site-dir", str(args.pages_output))

    print(f"Daily AI framework refresh complete: {args.pages_output.resolve()}")


def _default_tsmc_years() -> list[int]:
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    return sorted({today.year - 1, today.year})


def _run_python_module(module: str, *args: str) -> None:
    subprocess.run([sys.executable, "-m", module, *args], cwd=PROJECT_ROOT, check=True)


def _run_node(script: str, *args: str) -> None:
    subprocess.run(["node", script, *args], cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    main()
