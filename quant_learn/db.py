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
        metric_category TEXT,
        metric_polarity TEXT,
        surprise_direction TEXT,
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
        data_quality_flag TEXT,
        missing_reason TEXT,
        analysis_status TEXT,
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
    CREATE TABLE IF NOT EXISTS event_reviews (
        event_id TEXT NOT NULL,
        affected_ticker TEXT NOT NULL,
        reaction_date DATE NOT NULL,
        event_type TEXT NOT NULL,
        summary TEXT,
        raw_reaction_summary TEXT,
        benchmark_attribution_summary TEXT,
        metric_surprise_summary TEXT,
        linked_segment_features TEXT,
        linked_kpi_ids TEXT,
        fundamental_context_summary TEXT,
        interpretation TEXT,
        thesis_impact TEXT,
        confidence DOUBLE,
        data_quality_flag TEXT,
        analysis_status TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (event_id, affected_ticker)
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
    CREATE TABLE IF NOT EXISTS fundamentals_quarterly_normalized (
        fundamental_id TEXT NOT NULL,
        ticker TEXT NOT NULL,
        fiscal_year INTEGER NOT NULL,
        fiscal_quarter TEXT NOT NULL,
        period_start DATE,
        period_end DATE NOT NULL,
        available_date DATE,
        source_accession_number TEXT,
        source_form TEXT,
        filed_date DATE,
        source_url TEXT,
        revenue DOUBLE,
        gross_profit DOUBLE,
        gross_margin DOUBLE,
        operating_income DOUBLE,
        operating_margin DOUBLE,
        net_income DOUBLE,
        eps_diluted DOUBLE,
        operating_cash_flow_ytd DOUBLE,
        capex_ytd DOUBLE,
        free_cash_flow_ytd DOUBLE,
        operating_cash_flow_quarterly DOUBLE,
        capex_quarterly DOUBLE,
        free_cash_flow_quarterly DOUBLE,
        cash DOUBLE,
        debt DOUBLE,
        shares_outstanding DOUBLE,
        is_ytd_source BOOLEAN,
        is_quarterly_derived BOOLEAN,
        derivation_method TEXT,
        source_xbrl_tags TEXT,
        source_fact_keys TEXT,
        data_quality_flag TEXT,
        confidence DOUBLE,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (fundamental_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cash_flow_features (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        feature_name TEXT NOT NULL,
        feature_value DOUBLE,
        feature_score DOUBLE,
        direction TEXT,
        source_fundamental_ids TEXT,
        confidence DOUBLE,
        data_quality_flag TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker, feature_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_cards (
        evidence_id TEXT NOT NULL,
        run_id TEXT,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        source_table TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_date DATE,
        available_date DATE,
        direction TEXT NOT NULL,
        strength TEXT NOT NULL,
        confidence DOUBLE,
        materiality DOUBLE,
        summary TEXT,
        metric_name TEXT,
        metric_value DOUBLE,
        comparison_value DOUBLE,
        interpretation TEXT,
        thesis_tag TEXT,
        risk_tag TEXT,
        data_quality_flag TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (evidence_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_stance (
        stance_id TEXT NOT NULL,
        run_id TEXT,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        stance TEXT NOT NULL,
        stance_modifier TEXT,
        confidence DOUBLE,
        thesis_summary TEXT,
        positive_evidence_ids TEXT,
        negative_evidence_ids TEXT,
        mixed_evidence_ids TEXT,
        risk_flags TEXT,
        falsifiers TEXT,
        next_catalysts TEXT,
        data_quality_caveats TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (stance_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_components (
        run_id TEXT,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        direction TEXT NOT NULL,
        weighted_score DOUBLE,
        raw_strength DOUBLE,
        avg_confidence DOUBLE,
        evidence_count INTEGER,
        top_evidence_ids TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (as_of_date, ticker, evidence_type, direction)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_confidence_caps (
        run_id TEXT,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        cap_type TEXT NOT NULL,
        cap_value DOUBLE,
        reason TEXT,
        applied BOOLEAN,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (as_of_date, ticker, cap_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_conflicts (
        run_id TEXT,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        conflict_type TEXT NOT NULL,
        positive_evidence_ids TEXT,
        negative_evidence_ids TEXT,
        severity TEXT,
        summary TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (as_of_date, ticker, conflict_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_cards_history (
        run_id TEXT NOT NULL,
        archived_at TIMESTAMP NOT NULL,
        evidence_id TEXT NOT NULL,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        source_table TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_date DATE,
        available_date DATE,
        direction TEXT NOT NULL,
        strength TEXT NOT NULL,
        confidence DOUBLE,
        materiality DOUBLE,
        summary TEXT,
        metric_name TEXT,
        metric_value DOUBLE,
        comparison_value DOUBLE,
        interpretation TEXT,
        thesis_tag TEXT,
        risk_tag TEXT,
        data_quality_flag TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (run_id, evidence_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_stance_history (
        run_id TEXT NOT NULL,
        archived_at TIMESTAMP NOT NULL,
        stance_id TEXT NOT NULL,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        stance TEXT NOT NULL,
        stance_modifier TEXT,
        confidence DOUBLE,
        thesis_summary TEXT,
        positive_evidence_ids TEXT,
        negative_evidence_ids TEXT,
        mixed_evidence_ids TEXT,
        risk_flags TEXT,
        falsifiers TEXT,
        next_catalysts TEXT,
        data_quality_caveats TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (run_id, stance_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_components_history (
        run_id TEXT NOT NULL,
        archived_at TIMESTAMP NOT NULL,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        evidence_type TEXT NOT NULL,
        direction TEXT NOT NULL,
        weighted_score DOUBLE,
        raw_strength DOUBLE,
        avg_confidence DOUBLE,
        evidence_count INTEGER,
        top_evidence_ids TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (run_id, as_of_date, ticker, evidence_type, direction)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_confidence_caps_history (
        run_id TEXT NOT NULL,
        archived_at TIMESTAMP NOT NULL,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        cap_type TEXT NOT NULL,
        cap_value DOUBLE,
        reason TEXT,
        applied BOOLEAN,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (run_id, as_of_date, ticker, cap_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_conflicts_history (
        run_id TEXT NOT NULL,
        archived_at TIMESTAMP NOT NULL,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        conflict_type TEXT NOT NULL,
        positive_evidence_ids TEXT,
        negative_evidence_ids TEXT,
        severity TEXT,
        summary TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (run_id, as_of_date, ticker, conflict_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_runs (
        run_id TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        mode TEXT,
        from_step TEXT,
        to_step TEXT,
        force_stale BOOLEAN,
        status TEXT NOT NULL,
        data_snapshot_hash TEXT,
        freshness_snapshot_json TEXT,
        error_message TEXT,
        PRIMARY KEY (run_id)
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
    CREATE TABLE IF NOT EXISTS valuation_metrics (
        valuation_metric_id TEXT NOT NULL,
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        market_cap DOUBLE,
        enterprise_value DOUBLE,
        price DOUBLE,
        shares_outstanding DOUBLE,
        cash DOUBLE,
        debt DOUBLE,
        ttm_revenue DOUBLE,
        ttm_gross_profit DOUBLE,
        ttm_operating_income DOUBLE,
        ttm_net_income DOUBLE,
        ttm_free_cash_flow DOUBLE,
        pe_ttm DOUBLE,
        ev_sales_ttm DOUBLE,
        ev_gross_profit_ttm DOUBLE,
        ev_operating_income_ttm DOUBLE,
        fcf_yield_ttm DOUBLE,
        earnings_yield_ttm DOUBLE,
        revenue_growth_yoy DOUBLE,
        gross_profit_growth_yoy DOUBLE,
        fcf_growth_yoy DOUBLE,
        valuation_percentile_1y DOUBLE,
        valuation_percentile_3y DOUBLE,
        valuation_percentile_5y DOUBLE,
        data_quality_flag TEXT,
        source_fundamental_ids TEXT,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (valuation_metric_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS valuation_features (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        feature_name TEXT NOT NULL,
        feature_value DOUBLE,
        feature_score DOUBLE,
        direction TEXT,
        confidence DOUBLE,
        source_metric_ids TEXT,
        data_quality_flag TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker, feature_name)
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
        segment_kpi_id TEXT NOT NULL,
        period_end DATE NOT NULL,
        fiscal_year INTEGER,
        fiscal_quarter TEXT,
        period_type TEXT NOT NULL,
        ticker TEXT NOT NULL,
        kpi_group TEXT NOT NULL,
        segment_name TEXT,
        kpi_name TEXT NOT NULL,
        kpi_value DOUBLE,
        unit TEXT,
        currency TEXT,
        source_type TEXT,
        source_url TEXT,
        source_accession_number TEXT,
        filed_date DATE,
        is_reported BOOLEAN,
        is_derived BOOLEAN,
        derivation_method TEXT,
        confidence TEXT,
        notes TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (segment_kpi_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS segment_features (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        feature_name TEXT NOT NULL,
        feature_value DOUBLE,
        feature_score DOUBLE,
        direction TEXT,
        confidence DOUBLE,
        source_kpi_ids TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker, feature_name)
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
    """
    CREATE TABLE IF NOT EXISTS market_factor_inputs (
        date DATE NOT NULL,
        qqq_return_1d DOUBLE,
        soxx_return_1d DOUBLE,
        smh_return_1d DOUBLE,
        spy_return_1d DOUBLE,
        tnx_close DOUBLE,
        delta_tnx_bps DOUBLE,
        semi_specific_return_1d DOUBLE,
        data_quality_flag TEXT,
        source TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS factor_exposures (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        model_name TEXT NOT NULL,
        lookback_window INTEGER NOT NULL,
        n_obs INTEGER,
        alpha_daily DOUBLE,
        beta_qqq DOUBLE,
        beta_soxx DOUBLE,
        beta_tnx_bps DOUBLE,
        r2 DOUBLE,
        factor_corr_qqq_soxx DOUBLE,
        data_quality_flag TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker, model_name, lookback_window)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS factor_residuals (
        date DATE NOT NULL,
        ticker TEXT NOT NULL,
        model_name TEXT NOT NULL,
        lookback_window INTEGER NOT NULL,
        stock_return_1d DOUBLE,
        expected_return_1d DOUBLE,
        residual_return_1d DOUBLE,
        market_contribution_1d DOUBLE,
        sector_contribution_1d DOUBLE,
        rate_contribution_1d DOUBLE,
        alpha_contribution_1d DOUBLE,
        residual_return_5d DOUBLE,
        residual_return_20d DOUBLE,
        residual_return_60d DOUBLE,
        data_quality_flag TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (date, ticker, model_name, lookback_window)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS residual_diagnostics (
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        model_name TEXT NOT NULL,
        lookback_window INTEGER NOT NULL,
        window_days INTEGER NOT NULL,
        residual_return DOUBLE,
        top_1_day_contribution_pct DOUBLE,
        top_3_days_contribution_pct DOUBLE,
        positive_residual_days INTEGER,
        negative_residual_days INTEGER,
        residual_hit_rate DOUBLE,
        max_positive_residual_day DATE,
        max_negative_residual_day DATE,
        data_quality_flag TEXT,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (as_of_date, ticker, model_name, lookback_window, window_days)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_backtest_observations (
        run_id TEXT NOT NULL,
        as_of_date DATE NOT NULL,
        ticker TEXT NOT NULL,
        stance TEXT NOT NULL,
        stance_modifier TEXT,
        confidence DOUBLE,
        confidence_bucket TEXT,
        data_snapshot_hash TEXT,
        horizon INTEGER NOT NULL,
        entry_date DATE,
        maturity_date DATE,
        is_mature BOOLEAN,
        forward_raw_return DOUBLE,
        forward_factor_expected_return DOUBLE,
        forward_residual_return DOUBLE,
        forward_max_drawdown DOUBLE,
        data_quality_flag TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (run_id, ticker, horizon)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stance_backtest_summary (
        as_of_date DATE NOT NULL,
        horizon INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        stance TEXT NOT NULL,
        stance_modifier TEXT NOT NULL,
        confidence_bucket TEXT NOT NULL,
        observation_count INTEGER,
        mature_count INTEGER,
        hit_rate DOUBLE,
        mean_forward_residual_return DOUBLE,
        median_forward_residual_return DOUBLE,
        p25_forward_residual_return DOUBLE,
        p75_forward_residual_return DOUBLE,
        mean_forward_raw_return DOUBLE,
        mean_forward_max_drawdown DOUBLE,
        created_at TIMESTAMP NOT NULL,
        ingested_at TIMESTAMP NOT NULL,
        PRIMARY KEY (
            as_of_date,
            horizon,
            ticker,
            stance,
            stance_modifier,
            confidence_bucket
        )
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
    "ALTER TABLE event_metrics ADD COLUMN IF NOT EXISTS metric_category TEXT",
    "ALTER TABLE event_metrics ADD COLUMN IF NOT EXISTS metric_polarity TEXT",
    "ALTER TABLE event_metrics ADD COLUMN IF NOT EXISTS surprise_direction TEXT",
    "ALTER TABLE event_returns ADD COLUMN IF NOT EXISTS data_quality_flag TEXT",
    "ALTER TABLE event_returns ADD COLUMN IF NOT EXISTS missing_reason TEXT",
    "ALTER TABLE event_returns ADD COLUMN IF NOT EXISTS analysis_status TEXT",
    "ALTER TABLE event_reviews ADD COLUMN IF NOT EXISTS analysis_status TEXT",
    "ALTER TABLE event_reviews ADD COLUMN IF NOT EXISTS linked_segment_features TEXT",
    "ALTER TABLE event_reviews ADD COLUMN IF NOT EXISTS linked_kpi_ids TEXT",
    "ALTER TABLE event_reviews ADD COLUMN IF NOT EXISTS fundamental_context_summary TEXT",
    "ALTER TABLE investment_scorecard ADD COLUMN IF NOT EXISTS data_quality_score DOUBLE",
    "ALTER TABLE investment_scorecard ADD COLUMN IF NOT EXISTS model_confidence DOUBLE",
    "ALTER TABLE investment_scorecard ADD COLUMN IF NOT EXISTS confidence_cap_reason TEXT",
    "ALTER TABLE evidence_cards ADD COLUMN IF NOT EXISTS run_id TEXT",
    "ALTER TABLE research_stance ADD COLUMN IF NOT EXISTS run_id TEXT",
    "ALTER TABLE stance_components ADD COLUMN IF NOT EXISTS run_id TEXT",
    "ALTER TABLE stance_confidence_caps ADD COLUMN IF NOT EXISTS run_id TEXT",
    "ALTER TABLE stance_conflicts ADD COLUMN IF NOT EXISTS run_id TEXT",
    "ALTER TABLE research_stance ADD COLUMN IF NOT EXISTS stance_modifier TEXT",
    """
    UPDATE evidence_cards
    SET run_id = COALESCE(
        run_id,
        (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1),
        'legacy_untracked'
    )
    WHERE run_id IS NULL
    """,
    """
    UPDATE research_stance
    SET run_id = COALESCE(
        run_id,
        (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1),
        'legacy_untracked'
    )
    WHERE run_id IS NULL
    """,
    """
    UPDATE stance_components
    SET run_id = COALESCE(
        run_id,
        (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1),
        'legacy_untracked'
    )
    WHERE run_id IS NULL
    """,
    """
    UPDATE stance_confidence_caps
    SET run_id = COALESCE(
        run_id,
        (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1),
        'legacy_untracked'
    )
    WHERE run_id IS NULL
    """,
    """
    UPDATE stance_conflicts
    SET run_id = COALESCE(
        run_id,
        (SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1),
        'legacy_untracked'
    )
    WHERE run_id IS NULL
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
        for statement in MIGRATION_SQL:
            conn.execute(statement)
        _ensure_event_returns_long_schema(conn)
        _ensure_segment_kpis_v09_schema(conn)
        _create_segment_views(conn)


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
            data_quality_flag TEXT,
            missing_reason TEXT,
            analysis_status TEXT,
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


def _ensure_segment_kpis_v09_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Ensure segment_kpis uses the V0.9 flexible KPI schema."""

    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info('segment_kpis')").fetchall()
    }
    if "segment_kpi_id" in columns and "kpi_name" in columns:
        return

    row_count = conn.execute("SELECT COUNT(*) FROM segment_kpis").fetchone()[0]
    if row_count:
        raise RuntimeError(
            "segment_kpis still uses the legacy schema and contains rows. "
            "Export or migrate those rows before initializing the V0.9 schema."
        )

    conn.execute("DROP TABLE segment_kpis")
    conn.execute(
        """
        CREATE TABLE segment_kpis (
            segment_kpi_id TEXT NOT NULL,
            period_end DATE NOT NULL,
            fiscal_year INTEGER,
            fiscal_quarter TEXT,
            period_type TEXT NOT NULL,
            ticker TEXT NOT NULL,
            kpi_group TEXT NOT NULL,
            segment_name TEXT,
            kpi_name TEXT NOT NULL,
            kpi_value DOUBLE,
            unit TEXT,
            currency TEXT,
            source_type TEXT,
            source_url TEXT,
            source_accession_number TEXT,
            filed_date DATE,
            is_reported BOOLEAN,
            is_derived BOOLEAN,
            derivation_method TEXT,
            confidence TEXT,
            notes TEXT,
            ingested_at TIMESTAMP NOT NULL,
            PRIMARY KEY (segment_kpi_id)
        )
        """
    )


def _create_segment_views(conn: duckdb.DuckDBPyConnection) -> None:
    """Create normalized segment KPI views."""

    conn.execute(
        """
        CREATE OR REPLACE VIEW segments_view AS
        WITH segment_rows AS (
            SELECT
                segment_kpi_id,
                period_end,
                fiscal_year,
                fiscal_quarter,
                period_type,
                ticker,
                segment_name,
                kpi_name,
                kpi_value,
                source_url,
                source_accession_number,
                filed_date,
                confidence
            FROM segment_kpis
            WHERE kpi_group IN ('segment', 'reportable_segment', 'end_market', 'platform')
              AND segment_name IS NOT NULL
        ),
        pivoted AS (
            SELECT
                period_end,
                fiscal_year,
                fiscal_quarter,
                period_type,
                ticker,
                segment_name,
                MAX(CASE WHEN kpi_name = 'revenue' THEN kpi_value END) AS segment_revenue,
                MAX(CASE WHEN kpi_name = 'operating_income' THEN kpi_value END)
                    AS segment_operating_income,
                MAX(CASE WHEN kpi_name = 'margin' THEN kpi_value END) AS reported_margin,
                STRING_AGG(
                    CASE WHEN kpi_name = 'revenue' THEN segment_kpi_id END,
                    ','
                ) AS segment_revenue_source_kpi_ids,
                STRING_AGG(
                    CASE WHEN kpi_name = 'operating_income' THEN segment_kpi_id END,
                    ','
                ) AS segment_operating_income_source_kpi_ids,
                STRING_AGG(
                    CASE WHEN kpi_name = 'margin' THEN segment_kpi_id END,
                    ','
                ) AS reported_margin_source_kpi_ids,
                MAX(source_url) AS source_url,
                MAX(source_accession_number) AS source_accession_number,
                MAX(filed_date) AS available_date,
                MAX(confidence) AS confidence,
                STRING_AGG(segment_kpi_id, ',') AS source_kpi_ids
            FROM segment_rows
            GROUP BY period_end, fiscal_year, fiscal_quarter, period_type, ticker, segment_name
        )
        SELECT
            period_end,
            fiscal_year,
            fiscal_quarter,
            period_type,
            ticker,
            segment_name,
            segment_revenue,
            segment_operating_income,
            COALESCE(
                reported_margin,
                segment_operating_income / NULLIF(segment_revenue, 0)
            ) AS segment_margin,
            segment_revenue_source_kpi_ids,
            LAG(segment_revenue_source_kpi_ids, 4)
                OVER (PARTITION BY ticker, segment_name ORDER BY period_end)
                AS prior_year_segment_revenue_source_kpi_ids,
            CASE
                WHEN reported_margin IS NOT NULL THEN reported_margin_source_kpi_ids
                WHEN segment_operating_income_source_kpi_ids IS NULL
                    THEN segment_revenue_source_kpi_ids
                WHEN segment_revenue_source_kpi_ids IS NULL
                    THEN segment_operating_income_source_kpi_ids
                ELSE
                    segment_operating_income_source_kpi_ids
                    || ','
                    || segment_revenue_source_kpi_ids
            END AS segment_margin_source_kpi_ids,
            segment_revenue
                / NULLIF(
                    LAG(segment_revenue, 4)
                    OVER (PARTITION BY ticker, segment_name ORDER BY period_end),
                    0
                )
                - 1 AS segment_revenue_growth_yoy,
            source_url,
            source_accession_number,
            available_date,
            confidence,
            source_kpi_ids
        FROM pivoted
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
