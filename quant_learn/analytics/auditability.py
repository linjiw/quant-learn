"""Research auditability helpers: run tracking, freshness, and archival."""

import hashlib
import json
from collections.abc import Iterable
from typing import Optional

import duckdb
import pandas as pd

from quant_learn.db import connect, initialize_database
from quant_learn.time import utc_now_naive

FRESHNESS_TABLES = [
    "prices",
    "market_factor_inputs",
    "factor_residuals",
    "fundamentals_quarterly_normalized",
    "segment_features",
    "event_reviews",
    "valuation_features",
    "evidence_cards",
    "research_stance",
]

UPSTREAM_FRESHNESS_TABLES = {"prices", "market_factor_inputs"}

HISTORY_TABLES = {
    "evidence_cards": "evidence_cards_history",
    "research_stance": "research_stance_history",
    "stance_components": "stance_components_history",
    "stance_confidence_caps": "stance_confidence_caps_history",
    "stance_conflicts": "stance_conflicts_history",
}


def generate_run_id(prefix: str = "run") -> str:
    """Generate a compact run id."""

    now = utc_now_naive()
    stamp = now.strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(str(now.timestamp()).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{stamp}_{digest}"


def build_freshness_snapshot(tables: Iterable[str] = FRESHNESS_TABLES) -> list[dict]:
    """Summarize row counts and latest timestamps for core research tables."""

    initialize_database()
    now = utc_now_naive()
    rows = []
    with connect() as conn:
        for table in tables:
            rows.append(_table_freshness(conn, table, now))
    return rows


def data_snapshot_hash(freshness_snapshot: list[dict]) -> str:
    """Hash table-level freshness metadata for memo/run traceability.

    The hash reflects table row counts and max dates, not row-level content.
    In-place edits that do not change those table-level fields are not detected.
    """

    stable_snapshot = [
        {
            "table": row.get("table"),
            "row_count": row.get("row_count"),
            "max_date": row.get("max_date"),
            "max_available_date": row.get("max_available_date"),
        }
        for row in freshness_snapshot
    ]
    payload = json.dumps(stable_snapshot, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def archive_research_outputs(fallback_run_id: Optional[str] = None) -> None:
    """Archive current evidence/stance/audit tables before rebuilding them.

    History `run_id` values come from the source rows themselves. `fallback_run_id`
    is used only for legacy rows created before run_id was added to current tables.
    """

    initialize_database()
    archived_at = utc_now_naive()
    fallback = fallback_run_id or "legacy_untracked"
    with connect() as conn:
        for source_table, history_table in HISTORY_TABLES.items():
            row_count = conn.execute(f"SELECT COUNT(*) FROM {source_table}").fetchone()[0]
            if not row_count:
                continue
            columns = _table_columns(conn, source_table)
            source_columns = [column for column in columns if column != "run_id"]
            source_column_sql = ", ".join(source_columns)
            if "run_id" in columns:
                run_ids = [
                    row[0]
                    for row in conn.execute(
                        f"SELECT DISTINCT COALESCE(run_id, ?) FROM {source_table}",
                        [fallback],
                    ).fetchall()
                ]
                for source_run_id in run_ids:
                    conn.execute(
                        f"DELETE FROM {history_table} WHERE run_id = ?",
                        [source_run_id],
                    )
                run_id_sql = "COALESCE(run_id, ?)"
                params = [fallback, archived_at]
            else:
                conn.execute(f"DELETE FROM {history_table} WHERE run_id = ?", [fallback])
                run_id_sql = "?"
                params = [fallback, archived_at]
            conn.execute(
                f"""
                INSERT INTO {history_table} (
                    run_id,
                    archived_at,
                    {source_column_sql}
                )
                SELECT {run_id_sql}, ?, {source_column_sql}
                FROM {source_table}
                """,
                params,
            )


def record_pipeline_run(
    *,
    run_id: str,
    started_at,
    completed_at,
    mode: str,
    from_step: str,
    to_step: str,
    force_stale: bool,
    status: str,
    freshness_snapshot: list[dict],
    error_message: Optional[str] = None,
) -> str:
    """Upsert one pipeline run row and return its data snapshot hash."""

    initialize_database()
    snapshot_hash = data_snapshot_hash(freshness_snapshot)
    payload = json.dumps(freshness_snapshot, sort_keys=True, default=str)
    with connect() as conn:
        conn.execute("DELETE FROM pipeline_runs WHERE run_id = ?", [run_id])
        conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, started_at, completed_at, mode, from_step, to_step,
                force_stale, status, data_snapshot_hash, freshness_snapshot_json,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                started_at,
                completed_at,
                mode,
                from_step,
                to_step,
                force_stale,
                status,
                snapshot_hash,
                payload,
                error_message,
            ],
        )
    return snapshot_hash


def stale_tables(freshness_snapshot: list[dict], max_staleness_days: int) -> list[dict]:
    """Return tables whose ingest timestamp is missing or stale."""

    stale = []
    for row in freshness_snapshot:
        if row["row_count"] == 0:
            stale.append(row)
            continue
        staleness = row.get("staleness_days")
        if staleness is None or staleness > max_staleness_days:
            stale.append(row)
    return stale


def _table_freshness(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    now: pd.Timestamp,
) -> dict:
    columns = set(_table_columns(conn, table))
    row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    max_date = _max_column(conn, table, "date") if "date" in columns else None
    max_available = (
        _max_column(conn, table, "available_date") if "available_date" in columns else None
    )
    max_ingested = (
        _max_column(conn, table, "ingested_at") if "ingested_at" in columns else None
    )
    staleness_days = None
    if max_ingested is not None and pd.notna(max_ingested):
        staleness_days = max(0, (now - pd.to_datetime(max_ingested)).days)
    return {
        "table": table,
        "row_count": int(row_count),
        "max_date": _json_date(max_date),
        "max_available_date": _json_date(max_available),
        "max_ingested_at": _json_date(max_ingested),
        "staleness_days": staleness_days,
    }


def _table_columns(conn: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]


def _max_column(conn: duckdb.DuckDBPyConnection, table: str, column: str):
    return conn.execute(f"SELECT MAX({column}) FROM {table}").fetchone()[0]


def _json_date(value):
    if value is None or pd.isna(value):
        return None
    return str(value)
