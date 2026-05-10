from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from quant_learn.analytics import event_reviews, event_study, factor_model
from quant_learn.db import initialize_database


def test_tnx_unit_normalization_to_bps() -> None:
    yahoo_tnx = pd.Series([45.0, 45.1, 44.9])
    yield_percent = pd.Series([4.50, 4.51, 4.49])
    yield_decimal = pd.Series([0.0450, 0.0451, 0.0449])

    assert factor_model.normalize_10y_change_to_bps(yahoo_tnx, "YAHOO_TNX").iloc[1] == _approx(
        1.0
    )
    assert factor_model.normalize_10y_change_to_bps(
        yield_percent,
        "YIELD_PERCENT",
    ).iloc[1] == _approx(1.0)
    assert factor_model.normalize_10y_change_to_bps(
        yield_decimal,
        "YIELD_DECIMAL",
    ).iloc[1] == _approx(1.0)


def test_three_factor_regression_uses_prior_window_no_lookahead(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "factor_model.duckdb"
    _patch_factor_db(monkeypatch, db_path)
    dates, qqq, soxx, delta_bps, stock_returns = _synthetic_factor_returns()
    stock_returns[70] = 0.50
    _insert_factor_prices(db_path, dates, qqq, soxx, delta_bps, stock_returns)

    inputs = factor_model.build_market_factor_inputs()
    factor_model.store_market_factor_inputs(inputs)
    exposures = factor_model.build_factor_exposures(
        tickers=["GOOGL"],
        window=60,
        min_obs=50,
    )
    row = exposures[
        (pd.to_datetime(exposures["date"]) == dates[70])
        & (exposures["ticker"] == "GOOGL")
    ].iloc[0]

    assert row["data_quality_flag"] == "complete"
    assert row["n_obs"] == 60
    assert row["alpha_daily"] == _approx(0.001)
    assert row["beta_qqq"] == _approx(1.5)
    assert row["beta_soxx"] == _approx(0.5)
    assert row["beta_tnx_bps"] == _approx(-0.0002)

    factor_model.store_factor_exposures(exposures)
    residuals = factor_model.build_factor_residuals(tickers=["GOOGL"], window=60)
    residual_row = residuals[
        (pd.to_datetime(residuals["date"]) == dates[70])
        & (residuals["ticker"] == "GOOGL")
    ].iloc[0]

    expected = (
        0.001
        + 1.5 * qqq[70]
        + 0.5 * soxx[70]
        - 0.0002 * delta_bps[70]
    )
    assert residual_row["expected_return_1d"] == _approx(expected)
    assert residual_row["residual_return_1d"] == _approx(0.50 - expected)


def test_factor_model_handles_insufficient_observations(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insufficient_factor_model.duckdb"
    _patch_factor_db(monkeypatch, db_path)
    dates, qqq, soxx, delta_bps, stock_returns = _synthetic_factor_returns(periods=12)
    _insert_factor_prices(db_path, dates, qqq, soxx, delta_bps, stock_returns)

    factor_model.store_market_factor_inputs(factor_model.build_market_factor_inputs())
    exposures = factor_model.build_factor_exposures(tickers=["GOOGL"], window=60, min_obs=40)

    assert "insufficient_observations" in set(exposures["data_quality_flag"])
    assert exposures["beta_qqq"].isna().all()


def test_factor_residual_report_contains_all_four_tickers(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "factor_report.duckdb"
    _patch_factor_db(monkeypatch, db_path)
    dates, qqq, soxx, delta_bps, stock_returns = _synthetic_factor_returns()
    _insert_factor_prices(
        db_path,
        dates,
        qqq,
        soxx,
        delta_bps,
        stock_returns,
        stock_tickers=("GOOGL", "NVDA", "AMD", "TSM"),
    )

    factor_model.store_market_factor_inputs(factor_model.build_market_factor_inputs())
    factor_model.store_factor_exposures(
        factor_model.build_factor_exposures(window=60, min_obs=50)
    )
    factor_model.store_factor_residuals(factor_model.build_factor_residuals(window=60))
    output_path = tmp_path / "factor_residual_report.md"
    factor_model.build_factor_residual_report(output_path)
    report = output_path.read_text(encoding="utf-8")

    for ticker in ("GOOGL", "NVDA", "AMD", "TSM"):
        assert f"## {ticker}" in report


def test_residual_diagnostics_flags_concentrated_residuals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "residual_diagnostics.duckdb"
    _patch_factor_db(monkeypatch, db_path)
    ingested_at = pd.Timestamp("2026-05-01")
    dates = pd.bdate_range("2026-01-01", periods=70)
    rows = []
    for index, date in enumerate(dates):
        residual = 0.001
        if index in {64, 66, 68}:
            residual = 0.10
        rows.append(
            {
                "date": date.date(),
                "ticker": "AMD",
                "model_name": "three_factor_raw",
                "lookback_window": 60,
                "stock_return_1d": residual,
                "expected_return_1d": 0.0,
                "residual_return_1d": residual,
                "market_contribution_1d": 0.0,
                "sector_contribution_1d": 0.0,
                "rate_contribution_1d": 0.0,
                "alpha_contribution_1d": 0.0,
                "residual_return_5d": None,
                "residual_return_20d": None,
                "residual_return_60d": None,
                "data_quality_flag": "complete",
                "ingested_at": ingested_at,
            }
        )
    with duckdb.connect(str(db_path)) as conn:
        conn.register("rows", pd.DataFrame(rows))
        conn.execute("INSERT INTO factor_residuals SELECT * FROM rows")
        conn.unregister("rows")

    diagnostics = factor_model.build_residual_diagnostics(tickers=["AMD"])
    row = diagnostics[diagnostics["window_days"] == 60].iloc[0]

    assert row["ticker"] == "AMD"
    assert row["top_3_days_contribution_pct"] > 0.60
    assert row["data_quality_flag"] == "complete"


def test_event_factor_attribution_uses_pre_event_exposure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "event_factor.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(event_study, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(event_study, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(event_reviews, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        event_reviews,
        "initialize_database",
        lambda: initialize_database(db_path),
    )
    ingested_at = pd.Timestamp("2026-01-10")
    dates = pd.to_datetime(
        [
            "2026-01-01",
            "2026-01-02",
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
            "2026-01-09",
            "2026-01-12",
            "2026-01-13",
        ]
    )
    _insert_prices_from_levels(
        db_path,
        {
            "TEST": [100.0, 101.0, 102.0, 104.0, 108.0, 109.0, 110.0, 111.0, 112.0],
            "QQQ": [100.0, 101.0, 102.0, 103.02, 105.0804, 105.0804, 105.0804, 105.0804, 105.0804],
            "SOXX": [100.0, 100.5, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0],
        },
        dates,
    )
    with duckdb.connect(str(db_path)) as conn:
        factor_rows = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-01-05",
                        "2026-01-06",
                        "2026-01-07",
                        "2026-01-08",
                        "2026-01-09",
                        "2026-01-12",
                        "2026-01-13",
                    ]
                ).date,
                "qqq_return_1d": [0.009901, 0.01, 0.02, 0.0, 0.0, 0.0, 0.0],
                "soxx_return_1d": [0.004975, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "smh_return_1d": [None] * 7,
                "spy_return_1d": [None] * 7,
                "tnx_close": [45.0] * 7,
                "delta_tnx_bps": [0.0] * 7,
                "semi_specific_return_1d": [None] * 7,
                "data_quality_flag": ["complete"] * 7,
                "source": ["fixture"] * 7,
                "ingested_at": [ingested_at] * 7,
            }
        )
        conn.register("factor_rows", factor_rows)
        conn.execute(
            """
            INSERT INTO market_factor_inputs
            SELECT * FROM factor_rows
            """
        )
        conn.unregister("factor_rows")
        conn.execute(
            """
            INSERT INTO factor_exposures (
                date, ticker, model_name, lookback_window, n_obs, alpha_daily,
                beta_qqq, beta_soxx, beta_tnx_bps, r2, factor_corr_qqq_soxx,
                data_quality_flag, ingested_at
            )
            VALUES
                ('2026-01-05', 'TEST', 'three_factor_raw', 60, 60, 0.0,
                 1.0, 0.0, 0.0, 0.9, 0.2, 'complete', ?),
                ('2026-01-06', 'TEST', 'three_factor_raw', 60, 60, 0.0,
                 10.0, 0.0, 0.0, 0.9, 0.2, 'complete', ?)
            """,
            [ingested_at, ingested_at],
        )
        conn.execute(
            """
            INSERT INTO events (
                event_id, event_date, reaction_date, ticker, primary_ticker,
                event_type, event_name, event_description, source, source_url,
                after_market, importance_score, thesis_tag, expected_value,
                actual_value, surprise_pct, metadata_json, created_at, ingested_at
            )
            VALUES (
                'factor_event', '2026-01-05', '2026-01-06', 'TEST', 'TEST',
                'earnings', 'fixture', 'fixture', 'fixture', NULL, TRUE, 0.9,
                'fixture', NULL, NULL, NULL, '{}', ?, ?
            )
            """,
            [ingested_at, ingested_at],
        )
        conn.execute(
            """
            INSERT INTO event_impacts (
                event_id, affected_ticker, expected_direction, driver_tag,
                thesis_tag, impact_confidence, ingested_at
            )
            VALUES ('factor_event', 'TEST', 'positive', 'fixture', 'fixture', 0.9, ?)
            """,
            [ingested_at],
        )

    result = event_study.build_event_returns(event_type="earnings", benchmark_tickers=["QQQ"])
    factor_row = result[
        (result["return_window"] == "0_p1")
        & (result["benchmark_type"] == "factor_model")
    ].iloc[0]

    assert factor_row["benchmark_ticker"] == "QQQ_SOXX_TNX"
    assert factor_row["model_name"] == "three_factor_raw"
    assert factor_row["benchmark_return"] == _approx((1.01 * 1.02) - 1.0)
    assert factor_row["data_quality_flag"] == "complete"

    event_study.store_event_returns(result)
    reviews = event_reviews.build_event_reviews()
    review = reviews.iloc[0]
    assert "QQQ_SOXX_TNX:three_factor_raw" in review["benchmark_attribution_summary"]
    assert "pre-event factor model" in review["interpretation"]


def _patch_factor_db(monkeypatch, db_path: Path) -> None:
    initialize_database(db_path)
    monkeypatch.setattr(factor_model, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(factor_model, "initialize_database", lambda: initialize_database(db_path))


def _synthetic_factor_returns(periods: int = 100):
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2026-01-01", periods=periods)
    qqq = rng.normal(0.0005, 0.01, periods)
    soxx = rng.normal(0.0007, 0.012, periods)
    delta_bps = rng.normal(0.0, 3.0, periods)
    stock = 0.001 + 1.5 * qqq + 0.5 * soxx - 0.0002 * delta_bps
    qqq[0] = np.nan
    soxx[0] = np.nan
    delta_bps[0] = np.nan
    stock[0] = np.nan
    return dates, qqq, soxx, delta_bps, stock


def _insert_factor_prices(
    db_path: Path,
    dates: pd.DatetimeIndex,
    qqq: np.ndarray,
    soxx: np.ndarray,
    delta_bps: np.ndarray,
    stock_returns: np.ndarray,
    stock_tickers: tuple[str, ...] = ("GOOGL",),
) -> None:
    tnx = 45.0 + np.nancumsum(np.nan_to_num(delta_bps, nan=0.0) / 10.0)
    levels = {
        "QQQ": _price_from_returns(qqq),
        "SOXX": _price_from_returns(soxx),
        "SMH": _price_from_returns(soxx * 0.95),
        "SPY": _price_from_returns(qqq * 0.6),
        "^TNX": tnx,
    }
    for ticker in stock_tickers:
        levels[ticker] = _price_from_returns(stock_returns)
    _insert_prices_from_levels(db_path, levels, dates)


def _insert_prices_from_levels(
    db_path: Path,
    levels: dict[str, list[float] | np.ndarray],
    dates: pd.DatetimeIndex,
) -> None:
    rows = []
    ingested_at = pd.Timestamp("2026-05-09")
    for ticker, values in levels.items():
        for date, price in zip(dates, values):
            rows.append(
                {
                    "date": date.date(),
                    "ticker": ticker,
                    "open": float(price),
                    "high": float(price),
                    "low": float(price),
                    "close": float(price),
                    "adj_close": float(price),
                    "volume": 1,
                    "return_1d": None,
                    "return_5d": None,
                    "return_20d": None,
                    "return_60d": None,
                    "source": "fixture",
                    "ingested_at": ingested_at,
                }
            )
    with duckdb.connect(str(db_path)) as conn:
        prices = pd.DataFrame(rows)
        conn.register("fixture_prices", prices)
        conn.execute(
            """
            INSERT INTO prices (
                date, ticker, open, high, low, close, adj_close, volume,
                return_1d, return_5d, return_20d, return_60d, source, ingested_at
            )
            SELECT
                date, ticker, open, high, low, close, adj_close, volume,
                return_1d, return_5d, return_20d, return_60d, source, ingested_at
            FROM fixture_prices
            """
        )
        conn.unregister("fixture_prices")


def _price_from_returns(returns: np.ndarray) -> np.ndarray:
    result = [100.0]
    for value in returns[1:]:
        result.append(result[-1] * (1.0 + float(value)))
    return np.array(result)


def _approx(value: float):
    return pytest.approx(value, rel=1e-6, abs=1e-6)
