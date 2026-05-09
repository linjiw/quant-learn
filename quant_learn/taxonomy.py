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
