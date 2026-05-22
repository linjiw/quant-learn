"""Build the static AI framework site artifact for GitHub Pages."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from quant_learn.config import MANUAL_DIR, PROJECT_ROOT

SITE_SOURCE_DIR = PROJECT_ROOT / "site" / "ai-framework"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "public"
REPORTS_TO_COPY = (
    PROJECT_ROOT / "reports" / "ai_execution_tracker.md",
    PROJECT_ROOT / "reports" / "ai_strategy_system.md",
)
LOCAL_ONLY_SITE_NAMES = {"local-portfolio-data.json", "local-portfolio"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the AI framework GitHub Pages artifact.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--site-source-dir", type=Path, default=SITE_SOURCE_DIR)
    parser.add_argument("--data-date", default=None)
    parser.add_argument("--review-date", default=None)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    site_source_dir = args.site_source_dir.resolve()
    data_date = args.data_date or _latest_manual_data_date()
    review_date = args.review_date or _today_los_angeles()

    if not site_source_dir.exists():
        raise SystemExit(f"Site source directory not found: {site_source_dir}")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(site_source_dir, output_dir, ignore=_ignore_local_only_site_files)

    _stamp_research_data(output_dir / "research-data.js", data_date, review_date)
    _copy_reports(output_dir)
    _write_refresh_manifest(output_dir, data_date, review_date)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Built AI framework Pages artifact: {output_dir}")
    print(f"Data date: {data_date}")
    print(f"Review date: {review_date}")


def _today_los_angeles() -> str:
    return datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()


def _latest_manual_data_date() -> str:
    candidates = []
    for filename in (
        "ai_framework_holdings.csv",
        "ai_framework_indicators.csv",
        "ai_framework_predictions.csv",
        "ai_framework_scenarios.csv",
    ):
        path = MANUAL_DIR / filename
        if not path.exists():
            continue
        df = pd.read_csv(path, usecols=["as_of_date"])
        if not df.empty:
            candidates.append(pd.to_datetime(df["as_of_date"]).dt.date.max())
    if not candidates:
        return _today_los_angeles()
    return max(candidates).isoformat()


def _stamp_research_data(path: Path, data_date: str, review_date: str) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "asOf": review_date,
        "dataDate": data_date,
        "reviewDate": review_date,
    }
    for field, value in replacements.items():
        text = re.sub(
            rf'{field}: "\d{{4}}-\d{{2}}-\d{{2}}"',
            f'{field}: "{value}"',
            text,
            count=1,
        )
    path.write_text(text, encoding="utf-8")


def _copy_reports(output_dir: Path) -> None:
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for report_path in REPORTS_TO_COPY:
        if report_path.exists():
            shutil.copy2(report_path, reports_dir / report_path.name)


def _ignore_local_only_site_files(_directory: str, names: list[str]) -> set[str]:
    """Prevent private local portfolio data from entering GitHub Pages artifacts."""

    return {name for name in names if name in LOCAL_ONLY_SITE_NAMES}


def _write_refresh_manifest(output_dir: Path, data_date: str, review_date: str) -> None:
    manifest = {
        "built_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "data_date": data_date,
        "review_date": review_date,
        "site_source": str(SITE_SOURCE_DIR.relative_to(PROJECT_ROOT)),
        "reports": [path.name for path in REPORTS_TO_COPY if path.exists()],
    }
    (output_dir / "refresh.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
