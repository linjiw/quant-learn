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
        return_1d DOUBLE,
        return_5d DOUBLE,
        return_20d DOUBLE,
        return_60d DOUBLE,
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
        reaction_date DATE,
        ticker TEXT NOT NULL,
        primary_ticker TEXT,
        event_type TEXT NOT NULL,
        event_name TEXT,
        event_description TEXT,
        source TEXT,
        source_url TEXT,
        after_market BOOLEAN,
        importance_score DOUBLE,
        thesis_tag TEXT,
        expected_value DOUBLE,
        actual_value DOUBLE,
        surprise_pct DOUBLE,
        metadata_json TEXT,
        created_at TIMESTAMP,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (event_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_impacts (
        event_id TEXT NOT NULL,
        affected_ticker TEXT NOT NULL,
        expected_direction TEXT,
        driver_tag TEXT,
        thesis_tag TEXT,
        impact_confidence DOUBLE,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (event_id, affected_ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_metrics (
        event_id TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        actual_value DOUBLE,
        expected_value DOUBLE,
        prior_value DOUBLE,
        surprise_value DOUBLE,
        surprise_pct DOUBLE,
        unit TEXT,
        source TEXT,
        confidence DOUBLE,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (event_id, metric_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_returns (
        event_id TEXT NOT NULL,
        event_date DATE NOT NULL,
        reaction_date DATE NOT NULL,
        affected_ticker TEXT NOT NULL,
        event_type TEXT NOT NULL,
        return_window TEXT NOT NULL,
        raw_return DOUBLE,
        benchmark_type TEXT NOT NULL,
        benchmark_ticker TEXT NOT NULL,
        benchmark_return DOUBLE,
        abnormal_return DOUBLE,
        model_name TEXT NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (
            event_id,
            affected_ticker,
            return_window,
            benchmark_type,
            benchmark_ticker,
            model_name
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fundamentals_quarterly (
        ticker TEXT NOT NULL,
        fiscal_year INTEGER NOT NULL,
        fiscal_quarter TEXT NOT NULL,
        period_end DATE NOT NULL,
        revenue DOUBLE,
        gross_profit DOUBLE,
        gross_margin DOUBLE,
        operating_income DOUBLE,
        operating_margin DOUBLE,
        net_income DOUBLE,
        eps DOUBLE,
        operating_cash_flow DOUBLE,
        capex DOUBLE,
        free_cash_flow DOUBLE,
        cash DOUBLE,
        debt DOUBLE,
        shares_outstanding DOUBLE,
        buyback DOUBLE,
        dividend DOUBLE,
        source_accession_number TEXT,
        source_filed_date DATE,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (ticker, fiscal_year, fiscal_quarter, period_end)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        relative_strength_score DOUBLE,
        fundamental_momentum_score DOUBLE,
        valuation_score DOUBLE,
        event_score DOUBLE,
        cash_flow_score DOUBLE,
        risk_score DOUBLE,
        final_score DOUBLE,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS valuation_snapshots (
        snapshot_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        price DOUBLE,
        market_cap DOUBLE,
        enterprise_value DOUBLE,
        trailing_pe DOUBLE,
        forward_pe DOUBLE,
        price_to_sales DOUBLE,
        price_to_book DOUBLE,
        ev_to_ebitda DOUBLE,
        trailing_eps DOUBLE,
        forward_eps DOUBLE,
        dividend_yield DOUBLE,
        beta DOUBLE,
        source TEXT NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (snapshot_date, ticker, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forward_price_estimates (
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        horizon_days INTEGER NOT NULL,
        current_price DOUBLE,
        expected_return DOUBLE,
        expected_price DOUBLE,
        p10_price DOUBLE,
        p25_price DOUBLE,
        p50_price DOUBLE,
        p75_price DOUBLE,
        p90_price DOUBLE,
        probability_gain DOUBLE,
        annualized_mu DOUBLE,
        annualized_vol DOUBLE,
        method TEXT NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (as_of_date, ticker, horizon_days, method)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS investment_scorecard (
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        decision_label TEXT,
        investability_score DOUBLE,
        momentum_score DOUBLE,
        alpha_score DOUBLE,
        quality_score DOUBLE,
        valuation_score DOUBLE,
        risk_score DOUBLE,
        event_score DOUBLE,
        data_quality_score DOUBLE,
        model_confidence DOUBLE,
        confidence_cap_reason TEXT,
        key_flags TEXT,
        notes TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (as_of_date, ticker)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forward_model_validation (
        validation_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        horizon_days INTEGER NOT NULL,
        sample_size INTEGER,
        p10_p90_coverage DOUBLE,
        p25_p75_coverage DOUBLE,
        median_direction_accuracy DOUBLE,
        mean_realized_return DOUBLE,
        mean_expected_return DOUBLE,
        method TEXT NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (validation_date, ticker, horizon_days, method)
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

MIGRATION_SQL = [
    "ALTER TABLE prices ADD COLUMN IF NOT EXISTS return_1d DOUBLE",
    "ALTER TABLE prices ADD COLUMN IF NOT EXISTS return_5d DOUBLE",
    "ALTER TABLE prices ADD COLUMN IF NOT EXISTS return_20d DOUBLE",
    "ALTER TABLE prices ADD COLUMN IF NOT EXISTS return_60d DOUBLE",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS event_name TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS source TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS importance_score DOUBLE",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS reaction_date DATE",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS primary_ticker TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS after_market BOOLEAN",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS thesis_tag TEXT",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS created_at TIMESTAMP",
    "ALTER TABLE investment_scorecard ADD COLUMN IF NOT EXISTS data_quality_score DOUBLE",
    "ALTER TABLE investment_scorecard ADD COLUMN IF NOT EXISTS model_confidence DOUBLE",
    "ALTER TABLE investment_scorecard ADD COLUMN IF NOT EXISTS confidence_cap_reason TEXT",
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
        for statement in MIGRATION_SQL:
            conn.execute(statement)
        _ensure_event_returns_long_schema(conn)


def _ensure_event_returns_long_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Ensure event_returns uses the V0.8 long attribution schema.

    The earlier V0.7 table was a wide, single-ticker table. It is safe to migrate
    automatically only while the legacy table is empty; otherwise callers should
    export legacy rows and migrate them intentionally.
    """

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info('event_returns')").fetchall()
    }
    if "affected_ticker" in columns and "return_window" in columns:
        return

    row_count = conn.execute("SELECT COUNT(*) FROM event_returns").fetchone()[0]
    if row_count:
        raise RuntimeError(
            "event_returns still uses the legacy wide schema and contains rows. "
            "Export or migrate those rows before initializing the V0.8 schema."
        )

    conn.execute("DROP TABLE event_returns")
    conn.execute(
        """
        CREATE TABLE event_returns (
            event_id TEXT NOT NULL,
            event_date DATE NOT NULL,
            reaction_date DATE NOT NULL,
            affected_ticker TEXT NOT NULL,
            event_type TEXT NOT NULL,
            return_window TEXT NOT NULL,
            raw_return DOUBLE,
            benchmark_type TEXT NOT NULL,
            benchmark_ticker TEXT NOT NULL,
            benchmark_return DOUBLE,
            abnormal_return DOUBLE,
            model_name TEXT NOT NULL,
            ingested_at TIMESTAMP NOT NULL,
            PRIMARY KEY (
                event_id,
                affected_ticker,
                return_window,
                benchmark_type,
                benchmark_ticker,
                model_name
            )
        )
        """
    )


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
    columns = list(df.columns)
    column_sql = ", ".join(columns)
    incoming_column_sql = ", ".join([f"{incoming_name}.{column}" for column in columns])
    insert_sql = (
        f"INSERT INTO {table} ({column_sql}) "
        f"SELECT {incoming_column_sql} FROM {incoming_name}"
    )
    conn.execute(insert_sql)
    conn.unregister(incoming_name)
    return len(df)


def fetch_dataframe(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    params: Iterable[object] = (),
) -> pd.DataFrame:
    """Run a query and return a DataFrame."""

    return conn.execute(query, list(params)).fetchdf()
