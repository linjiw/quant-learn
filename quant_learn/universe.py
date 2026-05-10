"""Structural universe configuration for the AI compute research system."""

from quant_learn.config import CORE_TICKERS

UNIVERSE = {
    "GOOGL": {
        "role": "hyperscaler_demand_and_cash_flow",
        "evidence_weights": {
            "segment_momentum": 0.25,
            "cash_flow_quality": 0.25,
            "valuation": 0.20,
            "event_reaction": 0.10,
            "factor_residual": 0.10,
            "risk": 0.10,
        },
        "required_kpis": [
            "google_cloud_revenue",
            "google_cloud_operating_income",
            "google_search_other_revenue",
            "capex",
            "operating_cash_flow",
            "free_cash_flow",
        ],
        "driver_features": [
            "cloud_growth_score",
            "cloud_margin_score",
            "search_resilience_score",
            "capex_pressure_score",
            "fcf_quality_score",
        ],
        "structural_risk_tags": ["capex_pressure", "regulatory_risk", "search_disruption"],
    },
    "NVDA": {
        "role": "ai_accelerator_platform_leader",
        "evidence_weights": {
            "segment_momentum": 0.30,
            "valuation": 0.20,
            "event_reaction": 0.15,
            "factor_residual": 0.15,
            "risk": 0.12,
            "cash_flow_quality": 0.08,
        },
        "required_kpis": [
            "data_center_revenue",
            "gross_margin",
            "operating_margin",
            "inventory",
            "revenue_guidance_midpoint",
        ],
        "driver_features": [
            "data_center_momentum_score",
            "gross_margin_quality_score",
            "guidance_strength_score",
            "inventory_risk_score",
            "platform_premium_score",
        ],
        "structural_risk_tags": ["valuation_risk", "export_control", "competition"],
    },
    "AMD": {
        "role": "ai_second_source_and_server_cpu_challenger",
        "evidence_weights": {
            "segment_momentum": 0.25,
            "factor_residual": 0.20,
            "valuation": 0.20,
            "event_reaction": 0.15,
            "risk": 0.10,
            "cash_flow_quality": 0.10,
        },
        "required_kpis": [
            "data_center_revenue",
            "data_center_operating_income",
            "gross_margin",
            "client_revenue",
            "gaming_revenue",
            "embedded_revenue",
        ],
        "driver_features": [
            "data_center_momentum_score",
            "ai_accelerator_traction_score",
            "gross_margin_improvement_score",
            "client_cycle_score",
            "second_source_thesis_score",
        ],
        "structural_risk_tags": ["factor_led_risk", "nvda_dominance", "margin_pressure"],
    },
    "TSM": {
        "role": "foundry_and_advanced_packaging_bottleneck",
        "evidence_weights": {
            "segment_momentum": 0.30,
            "cash_flow_quality": 0.15,
            "factor_residual": 0.15,
            "valuation": 0.20,
            "risk": 0.10,
            "event_reaction": 0.10,
        },
        "required_kpis": [
            "monthly_revenue_yoy",
            "gross_margin",
            "operating_margin",
            "hpc_revenue_share",
            "advanced_technology_revenue_share",
        ],
        "driver_features": [
            "monthly_revenue_momentum_score",
            "hpc_mix_score",
            "advanced_node_mix_score",
            "gross_margin_quality_score",
            "capex_cycle_score",
        ],
        "structural_risk_tags": ["geopolitical_risk", "fx_model_gap", "overseas_fab_cost"],
    },
}


def evidence_weights_by_ticker() -> dict[str, dict[str, float]]:
    """Return ticker-specific evidence weights."""

    return {
        ticker: dict(config["evidence_weights"])
        for ticker, config in UNIVERSE.items()
    }


def validate_universe() -> None:
    """Validate structural universe configuration."""

    missing = set(CORE_TICKERS) - set(UNIVERSE)
    if missing:
        raise ValueError(f"Missing universe config for: {sorted(missing)}")

    for ticker in CORE_TICKERS:
        config = UNIVERSE[ticker]
        for key in ("role", "evidence_weights", "required_kpis", "driver_features"):
            if not config.get(key):
                raise ValueError(f"{ticker} missing universe field {key}")
        weight_sum = sum(config["evidence_weights"].values())
        if abs(weight_sum - 1.0) > 1e-6:
            raise ValueError(f"{ticker} evidence weights sum to {weight_sum:.4f}")
