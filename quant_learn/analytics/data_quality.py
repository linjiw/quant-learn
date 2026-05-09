"""Research data quality reports."""

from pathlib import Path

import pandas as pd

from quant_learn.db import connect, initialize_database


def build_event_data_quality_report(output_path: Path) -> Path:
    """Write a compact event return data quality report."""

    initialize_database()
    with connect() as conn:
        event_returns = conn.execute("SELECT * FROM event_returns").fetchdf()

    lines = ["# Event Data Quality Report", ""]
    if event_returns.empty:
        lines.append("No event return rows are available yet.")
    else:
        lines.append(f"Total event return rows: {len(event_returns)}")
        lines.append("")
        lines.extend(_section("Analysis status", event_returns, "analysis_status"))
        lines.extend(_section("Missing reason", event_returns, "missing_reason"))
        lines.extend(_section("By affected ticker", event_returns, "affected_ticker"))
        lines.extend(_section("By benchmark", event_returns, "benchmark_ticker"))

        data_issues = event_returns[event_returns["analysis_status"] == "data_issue"]
        if data_issues.empty:
            lines.extend(["## Data Issues", "", "No data_issue rows are currently present.", ""])
        else:
            lines.extend(["## Data Issues", ""])
            issue_summary = (
                data_issues.groupby(["affected_ticker", "benchmark_ticker", "missing_reason"])
                .size()
                .reset_index(name="rows")
                .sort_values(["rows", "affected_ticker"], ascending=[False, True])
            )
            lines.extend(_markdown_table(issue_summary))
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _section(title: str, frame: pd.DataFrame, column: str) -> list[str]:
    values = (
        frame[column]
        .fillna("none")
        .value_counts()
        .rename_axis(column)
        .reset_index(name="rows")
    )
    return [f"## {title}", "", *_markdown_table(values), ""]


def _markdown_table(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return ["No rows."]
    return frame.to_markdown(index=False).splitlines()
