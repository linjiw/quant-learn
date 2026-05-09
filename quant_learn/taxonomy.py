"""Controlled vocabulary for curated research events."""

EVENT_TYPES = {
    "earnings",
    "guidance",
    "tsmc_monthly_revenue",
    "hyperscaler_capex",
    "product_launch",
    "export_control",
    "regulatory",
    "analyst_day",
    "major_customer_news",
    "macro_rate_event",
}

EXPECTED_DIRECTIONS = {"positive", "negative", "mixed", "neutral", "unknown"}

DATA_QUALITY_FLAGS = {"complete", "mapped_reaction_date", "incomplete"}

MISSING_REASONS = {
    "pending_future_window",
    "missing_ticker_price",
    "missing_benchmark_price",
    "missing_factor_input",
    "insufficient_factor_history",
    "insufficient_trading_days",
    "non_trading_reaction_date",
    "adr_calendar_gap",
    "unknown",
}

ANALYSIS_STATUSES = {"ready", "partial_pending", "data_issue", "excluded"}

SEGMENT_PERIOD_TYPES = {"quarter", "month", "year"}
SEGMENT_KPI_GROUPS = {
    "segment",
    "reportable_segment",
    "end_market",
    "platform",
    "technology",
    "cash_flow",
    "guidance",
    "monthly",
    "company",
}
