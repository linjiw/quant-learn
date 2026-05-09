from collections.abc import Iterable, Sequence
from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.config import DEFAULT_DB_PATH, ensure_directories

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS prices (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        open DOUBLE,
        high DOUBLE,
        low DOUBLE,
        close DOUBLE,
        adj_close DOUBLE,
        volume BIGINT,
        source TEXT NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sec_filings (
        ticker TEXT NOT NULL,
        cik TEXT NOT NULL,
        accession_number TEXT NOT NULL,
        form TEXT,
        filing_date DATE,
        report_date DATE,
        primary_document TEXT,
        primary_doc_description TEXT,
        source_url TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (ticker, accession_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sec_facts (
        ticker TEXT NOT NULL,
        cik TEXT NOT NULL,
        taxonomy TEXT NOT NULL,
        concept TEXT NOT NULL,
        unit TEXT NOT NULL,
        fiscal_year INTEGER,
        fiscal_period TEXT,
        form TEXT,
        filed_date DATE,
        start_date DATE,
        end_date DATE,
        frame TEXT,
        accession_number TEXT,
        value DOUBLE,
        source_url TEXT,
        ingested_at TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tsmc_monthly_revenue (
        period DATE NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        revenue_ntd_million DOUBLE,
        mom_pct DOUBLE,
        yoy_pct DOUBLE,
        source_url TEXT NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (period)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT NOT NULL,
        event_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_description TEXT,
        source_url TEXT,
        expected_value DOUBLE,
        actual_value DOUBLE,
        surprise_pct DOUBLE,
        metadata_json TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS segment_kpis (
        ticker TEXT NOT NULL,
        fiscal_period TEXT NOT NULL,
        fiscal_year INTEGER,
        period_end DATE,
        segment_name TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        value DOUBLE,
        unit TEXT,
        source_url TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (ticker, fiscal_period, segment_name, metric_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS factor_dashboard (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        return_20d DOUBLE,
        return_60d DOUBLE,
        return_120d DOUBLE,
        rel_qqq_60d DOUBLE,
        rel_soxx_60d DOUBLE,
        realized_vol_20d DOUBLE,
        realized_vol_60d DOUBLE,
        max_drawdown_120d DOUBLE,
        beta_qqq_60d DOUBLE,
        beta_soxx_60d DOUBLE,
        residual_return_60d DOUBLE,
        volume_z_60d DOUBLE,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker)
    )
    """,
]


def connect(db_path: Path = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    """Connect to the project DuckDB database."""

    ensure_directories()
    return duckdb.connect(str(db_path))


def initialize_database(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create all required database tables."""

    with connect(db_path) as conn:
        for statement in SCHEMA_SQL:
            conn.execute(statement)


def upsert_dataframe(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    table: str,
    key_columns: Sequence[str],
) -> int:
    """Upsert a DataFrame into a table by deleting matching keys and inserting incoming rows."""

    if df.empty:
        return 0

    incoming_name = "_incoming"
    conn.register(incoming_name, df)
    key_match_parts = [
        f"{table}.{column} IS NOT DISTINCT FROM {incoming_name}.{column}"
        for column in key_columns
    ]
    key_match = " AND ".join(key_match_parts)
    delete_sql = (
        f"DELETE FROM {table} "
        f"WHERE EXISTS (SELECT 1 FROM {incoming_name} WHERE {key_match})"
    )
    conn.execute(delete_sql)
    conn.execute(f"INSERT INTO {table} SELECT * FROM {incoming_name}")
    conn.unregister(incoming_name)
    return len(df)


def fetch_dataframe(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: Iterable[object] = (),
) -> pd.DataFrame:
    """Run a query and return a DataFrame."""

    return conn.execute(query, list(params)).fetchdf()
