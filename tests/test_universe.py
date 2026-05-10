from quant_learn.config import CORE_TICKERS
from quant_learn.research_views import load_research_views, validate_research_views
from quant_learn.universe import UNIVERSE, validate_universe


def test_universe_config_covers_core_tickers_and_weights_sum_to_one() -> None:
    validate_universe()

    assert set(UNIVERSE) == set(CORE_TICKERS)
    for ticker in CORE_TICKERS:
        config = UNIVERSE[ticker]
        assert config["role"]
        assert config["required_kpis"]
        assert config["driver_features"]
        assert sum(config["evidence_weights"].values()) == 1.0


def test_research_views_cover_core_tickers_outside_code_config() -> None:
    validate_research_views()
    views = load_research_views()

    assert set(views) == set(CORE_TICKERS)
    for view in views.values():
        assert view.thesis_text
        assert view.falsifiers
        assert view.next_catalysts
