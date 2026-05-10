from pathlib import Path

import duckdb
import pandas as pd
import pytest

from quant_learn.analytics import evidence, valuation
from quant_learn.config import CORE_TICKERS
from quant_learn.db import initialize_database
from quant_learn.time import utc_now_naive


def test_valuation_uses_only_available_fundamentals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "valuation_pit.duckdb"
    _patch_valuation_db(monkeypatch, db_path)
    _seed_price_rows(db_path, ["GOOGL"], ["2026-04-15", "2026-05-15"], [20.0, 30.0])
    _seed_fundamental_rows(db_path, "GOOGL")

    metrics = valuation.build_valuation_metrics(["GOOGL"])
    by_date = metrics.set_index(pd.to_datetime(metrics["date"]).dt.date)
    before_future = by_date.loc[pd.Timestamp("2026-04-15").date()]
    after_future = by_date.loc[pd.Timestamp("2026-05-15").date()]

    assert "googl_2026_q1" not in before_future["source_fundamental_ids"]
    assert "googl_2026_q1" in after_future["source_fundamental_ids"]
    assert before_future["ttm_revenue"] == 460.0
    assert after_future["ttm_revenue"] == 1360.0
    assert before_future["market_cap"] == 20.0 * 10.0
    assert after_future["market_cap"] == 30.0 * 100.0


def test_valuation_formulas_market_cap_ev_and_fcf_yield(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "valuation_formula.duckdb"
    _patch_valuation_db(monkeypatch, db_path)
    _seed_price_rows(db_path, ["GOOGL"], ["2026-04-15"], [20.0])
    _seed_fundamental_rows(db_path, "GOOGL")

    row = valuation.build_valuation_metrics(["GOOGL"]).iloc[0]

    assert row["market_cap"] == pytest.approx(200.0)
    assert row["enterprise_value"] == pytest.approx(200.0 + 20.0 - 5.0)
    assert row["fcf_yield_ttm"] == pytest.approx((10.0 + 11.0 + 12.0 + 13.0) / 200.0)
    assert row["ev_sales_ttm"] == pytest.approx(215.0 / 460.0)


def test_valuation_metrics_and_features_cover_all_four_tickers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "valuation_coverage.duckdb"
    _patch_valuation_db(monkeypatch, db_path)
    for ticker in CORE_TICKERS:
        _seed_price_rows(db_path, [ticker], ["2026-04-15"], [20.0])
        _seed_fundamental_rows(db_path, ticker)

    metrics = valuation.build_valuation_metrics(CORE_TICKERS)
    valuation.store_valuation_metrics(metrics)
    features = valuation.build_valuation_features(CORE_TICKERS)

    assert set(metrics["ticker"]) == set(CORE_TICKERS)
    assert set(features["ticker"]) == set(CORE_TICKERS)
    assert {"valuation_percentile_score", "fcf_yield_score", "ev_sales_score"}.issubset(
        set(features["feature_name"])
    )
    assert features["source_metric_ids"].astype(str).str.startswith("valuation_").all()


def test_valuation_evidence_generated_for_all_four_tickers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "valuation_evidence.duckdb"
    _patch_valuation_db(monkeypatch, db_path)
    monkeypatch.setattr(evidence, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(evidence, "initialize_database", lambda: initialize_database(db_path))
    for ticker in CORE_TICKERS:
        _seed_price_rows(db_path, [ticker], ["2026-04-15"], [20.0])
        _seed_fundamental_rows(db_path, ticker)

    valuation.store_valuation_metrics(valuation.build_valuation_metrics(CORE_TICKERS))
    valuation.store_valuation_features(valuation.build_valuation_features(CORE_TICKERS))
    cards = evidence.build_evidence_cards(as_of_date="2026-04-15", run_id="fixture_run")
    valuation_cards = cards[cards["evidence_type"] == "valuation"]

    assert set(valuation_cards["ticker"]) == set(CORE_TICKERS)
    assert set(valuation_cards["source_table"]) == {"valuation_features"}
    assert valuation_cards["source_id"].astype(str).str.startswith("valuation_").all()


def test_valuation_features_use_snapshot_fallback_when_pit_metrics_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "valuation_snapshot_fallback.duckdb"
    _patch_valuation_db(monkeypatch, db_path)
    _seed_price_rows(db_path, ["TSM"], ["2026-05-08"], [410.0])
    _seed_valuation_snapshot(db_path, "TSM")

    valuation.store_valuation_metrics(valuation.build_valuation_metrics(["TSM"]))
    features = valuation.build_valuation_features(["TSM"])

    assert set(features["ticker"]) == {"TSM"}
    assert "snapshot_pe_score" in set(features["feature_name"])
    assert set(features["data_quality_flag"]) == {"snapshot_fallback"}
    assert features["source_metric_ids"].astype(str).str.startswith(
        "valuation_snapshot|TSM|"
    ).all()


def _patch_valuation_db(monkeypatch, db_path: Path) -> None:
    initialize_database(db_path)
    monkeypatch.setattr(valuation, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(valuation, "initialize_database", lambda: initialize_database(db_path))


def _seed_price_rows(
    db_path: Path,
    tickers: list[str],
    dates: list[str],
    prices: list[float],
) -> None:
    ingested_at = utc_now_naive()
    rows = []
    for ticker in tickers:
        for date_value, price in zip(dates, prices):
            rows.append(
                {
                    "date": pd.Timestamp(date_value).date(),
                    "ticker": ticker,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                    "return_1d": None,
                    "return_5d": None,
                    "return_20d": None,
                    "return_60d": None,
                    "source": "fixture",
                    "ingested_at": ingested_at,
                }
            )
    _insert_df(db_path, "prices", pd.DataFrame(rows))


def _seed_fundamental_rows(db_path: Path, ticker: str) -> None:
    ticker_lower = ticker.lower()
    ingested_at = utc_now_naive()
    quarters = [
        ("2025_q1", 2025, "Q1", "2025-03-31", "2025-04-30", 100.0, 50.0, 25.0, 20.0, 10.0, 10.0),
        ("2025_q2", 2025, "Q2", "2025-06-30", "2025-07-30", 110.0, 55.0, 27.5, 22.0, 11.0, 10.0),
        ("2025_q3", 2025, "Q3", "2025-09-30", "2025-10-30", 120.0, 60.0, 30.0, 24.0, 12.0, 10.0),
        ("2025_q4", 2025, "Q4", "2025-12-31", "2026-02-15", 130.0, 65.0, 32.5, 26.0, 13.0, 10.0),
        (
            "2026_q1",
            2026,
            "Q1",
            "2026-03-31",
            "2026-05-01",
            1000.0,
            500.0,
            250.0,
            200.0,
            100.0,
            100.0,
        ),
    ]
    rows = []
    for (
        suffix,
        year,
        quarter,
        period_end,
        available_date,
        revenue,
        gp,
        opinc,
        ni,
        fcf,
        shares,
    ) in quarters:
        fundamental_id = f"{ticker_lower}_{suffix}"
        rows.append(
            {
                "fundamental_id": fundamental_id,
                "ticker": ticker,
                "fiscal_year": year,
                "fiscal_quarter": quarter,
                "period_start": None,
                "period_end": pd.Timestamp(period_end).date(),
                "available_date": pd.Timestamp(available_date).date(),
                "source_accession_number": f"acc_{fundamental_id}",
                "source_form": "10-Q" if quarter != "Q4" else "10-K",
                "filed_date": pd.Timestamp(available_date).date(),
                "source_url": "fixture",
                "revenue": revenue,
                "gross_profit": gp,
                "gross_margin": gp / revenue,
                "operating_income": opinc,
                "operating_margin": opinc / revenue,
                "net_income": ni,
                "eps_diluted": None,
                "operating_cash_flow_ytd": None,
                "capex_ytd": None,
                "free_cash_flow_ytd": None,
                "operating_cash_flow_quarterly": None,
                "capex_quarterly": None,
                "free_cash_flow_quarterly": fcf,
                "cash": 5.0,
                "debt": 20.0,
                "shares_outstanding": shares,
                "is_ytd_source": False,
                "is_quarterly_derived": False,
                "derivation_method": "fixture",
                "source_xbrl_tags": "fixture",
                "source_fact_keys": "fixture",
                "data_quality_flag": "complete",
                "confidence": 0.95,
                "ingested_at": ingested_at,
            }
        )
    _insert_df(db_path, "fundamentals_quarterly_normalized", pd.DataFrame(rows))


def _seed_valuation_snapshot(db_path: Path, ticker: str) -> None:
    _insert_df(
        db_path,
        "valuation_snapshots",
        pd.DataFrame(
            [
                {
                    "snapshot_date": pd.Timestamp("2026-05-09").date(),
                    "ticker": ticker,
                    "price": 411.68,
                    "market_cap": 2_100_000.0,
                    "enterprise_value": 2_050_000.0,
                    "trailing_pe": 36.0,
                    "forward_pe": 22.0,
                    "price_to_sales": None,
                    "price_to_book": None,
                    "ev_to_ebitda": None,
                    "trailing_eps": 11.69,
                    "forward_eps": 19.29,
                    "dividend_yield": 0.85,
                    "beta": 1.26,
                    "source": "fixture_snapshot",
                    "ingested_at": utc_now_naive(),
                }
            ]
        ),
    )


def _insert_df(db_path: Path, table: str, frame: pd.DataFrame) -> None:
    with duckdb.connect(str(db_path)) as conn:
        conn.register("frame", frame)
        conn.execute(f"INSERT INTO {table} SELECT * FROM frame")
        conn.unregister("frame")
