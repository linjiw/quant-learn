"""Weekly governance digest for stance auditability."""

from datetime import timedelta
from pathlib import Path

import pandas as pd

from quant_learn.analytics.auditability import (
    UPSTREAM_FRESHNESS_TABLES,
    build_freshness_snapshot,
)
from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database
from quant_learn.research_views import load_research_views
from quant_learn.time import utc_now_naive


def build_weekly_digest(output_path: Path) -> Path:
    """Write a compact governance digest for weekly research review."""

    initialize_database()
    with connect() as conn:
        stance = conn.execute("SELECT * FROM research_stance ORDER BY ticker").fetchdf()
        caps = conn.execute(
            "SELECT * FROM stance_confidence_caps ORDER BY ticker, cap_type"
        ).fetchdf()
        conflicts = conn.execute(
            "SELECT * FROM stance_conflicts ORDER BY ticker, severity, conflict_type"
        ).fetchdf()
        diagnostics = conn.execute(
            """
            SELECT *
            FROM residual_diagnostics
            QUALIFY row_number() OVER (
                PARTITION BY ticker, window_days ORDER BY as_of_date DESC
            ) = 1
            ORDER BY ticker, window_days
            """
        ).fetchdf()
        pipeline_runs = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5"
        ).fetchdf()
        backtest_summary = conn.execute(
            """
            SELECT *
            FROM stance_backtest_summary
            ORDER BY horizon, ticker, stance, stance_modifier, confidence_bucket
            """
        ).fetchdf()

    lines = ["# Weekly AI Compute Research Digest", ""]
    lines.extend(_pipeline_section(pipeline_runs))
    lines.extend(["", "## Upstream Data Freshness", ""])
    lines.extend(_freshness_section(build_freshness_snapshot()))
    lines.extend(["", "## Stance Summary", ""])
    lines.extend(_stance_table(stance))
    lines.extend(["", "## High-Severity Conflicts", ""])
    lines.extend(_conflict_bullets(conflicts))
    lines.extend(["", "## Confidence Caps", ""])
    lines.extend(_cap_bullets(caps))
    lines.extend(["", "## Residual Concentration Warnings", ""])
    lines.extend(_residual_bullets(diagnostics))
    lines.extend(["", "## Stance Backtest Hit Rate", ""])
    lines.extend(_backtest_bullets(backtest_summary))
    lines.extend(["", "## Missing Human Thesis Warnings", ""])
    lines.extend(_human_thesis_warnings(stance))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _pipeline_section(pipeline_runs: pd.DataFrame) -> list[str]:
    if pipeline_runs.empty:
        return ["## Latest Pipeline Runs", "", "- no pipeline runs recorded"]
    lines = ["## Latest Pipeline Runs", ""]
    for _, row in pipeline_runs.iterrows():
        lines.append(
            f"- {row['run_id']}: {row['status']} "
            f"({row.get('from_step')} -> {row.get('to_step')}), "
            f"snapshot {row.get('data_snapshot_hash')}"
            f"{', force-stale' if bool(row.get('force_stale')) else ''}"
        )
    return lines


def _freshness_section(freshness: list[dict]) -> list[str]:
    rows = [row for row in freshness if row.get("table") in UPSTREAM_FRESHNESS_TABLES]
    if not rows:
        return ["- no upstream freshness snapshot available"]
    lines = []
    for row in rows:
        staleness = row.get("staleness_days")
        staleness_text = "unknown" if staleness is None else str(staleness)
        lines.append(
            f"- {row['table']}: rows={row['row_count']}, "
            f"max_date={row.get('max_date') or 'n/a'}, "
            f"staleness_days={staleness_text}"
        )
    return lines


def _stance_table(stance: pd.DataFrame) -> list[str]:
    lines = [
        "| Ticker | Stance | Modifier | Confidence | Caveat |",
        "|---|---|---|---:|---|",
    ]
    if stance.empty:
        lines.append("| none | n/a | n/a | 0.00 | no stance rows |")
        return lines
    for _, row in stance.iterrows():
        caveat = str(row.get("data_quality_caveats") or "none").split("; ", 1)[0]
        lines.append(
            f"| {row['ticker']} | {row['stance']} | {row.get('stance_modifier', 'n/a')} | "
            f"{float(row['confidence']):.2f} | {caveat} |"
        )
    return lines


def _conflict_bullets(conflicts: pd.DataFrame) -> list[str]:
    if conflicts.empty:
        return ["- none"]
    high = conflicts[conflicts["severity"] == "high"]
    if high.empty:
        return ["- none"]
    return [f"- {row['ticker']}: {row['summary']}" for _, row in high.iterrows()]


def _cap_bullets(caps: pd.DataFrame) -> list[str]:
    if caps.empty:
        return ["- none"]
    lines = []
    for _, row in caps.iterrows():
        lines.append(f"- {row['ticker']}: {row['cap_type']} ({row['reason']})")
    return lines


def _residual_bullets(diagnostics: pd.DataFrame) -> list[str]:
    if diagnostics.empty:
        return ["- no residual diagnostics available"]
    warnings = diagnostics[
        (diagnostics["window_days"] == 60)
        & (diagnostics["top_3_days_contribution_pct"] > 0.60)
        & (diagnostics["residual_return"] > 0)
    ]
    if warnings.empty:
        return ["- none"]
    return [
        (
            f"- {row['ticker']}: top 3 days explain "
            f"{float(row['top_3_days_contribution_pct']) * 100:.1f}% of 60d "
            "absolute residual movement"
        )
        for _, row in warnings.iterrows()
    ]


def _backtest_bullets(summary: pd.DataFrame) -> list[str]:
    if summary.empty:
        return ["- no stance backtest summary available"]
    mature = summary[summary["mature_count"].fillna(0) > 0]
    if mature.empty:
        return ["- no mature stance outcome observations yet"]
    latest_horizon = min(mature["horizon"].astype(int))
    horizon_rows = mature[mature["horizon"].astype(int) == latest_horizon]
    lines = []
    for _, row in horizon_rows.iterrows():
        lines.append(
            f"- {row['ticker']} {int(row['horizon'])}d {row['stance']} "
            f"({row['confidence_bucket']}): hit_rate={_fmt_pct(row['hit_rate'])}, "
            f"mean_residual={_fmt_pct(row['mean_forward_residual_return'])}, "
            f"n={int(row['mature_count'])}"
        )
    return lines


def _human_thesis_warnings(stance: pd.DataFrame) -> list[str]:
    views = load_research_views()
    warnings = []
    missing_views = [ticker for ticker in CORE_TICKERS if ticker not in views]
    if missing_views:
        warnings.extend(f"- missing manual research view for {ticker}" for ticker in missing_views)
    stale_cutoff = utc_now_naive().date() - timedelta(days=30)
    for ticker in CORE_TICKERS:
        view = views.get(ticker)
        if view is None or not view.updated_at:
            continue
        updated_at = pd.to_datetime(view.updated_at, errors="coerce")
        if pd.isna(updated_at):
            warnings.append(f"- {ticker} manual research view has invalid updated_at")
            continue
        if updated_at.date() < stale_cutoff:
            warnings.append(
                f"- {ticker} manual research view last updated {view.updated_at} (>30d)"
            )
    if stance.empty:
        warnings.append("- no stance rows available")
        return warnings or ["- none"]
    missing = [
        ticker
        for ticker in CORE_TICKERS
        if ticker not in set(stance["ticker"]) or stance[stance["ticker"] == ticker].empty
    ]
    if missing:
        warnings.extend(f"- missing stance/research view for {ticker}" for ticker in missing)
    return warnings or ["- none"]


def _fmt_pct(value) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"
