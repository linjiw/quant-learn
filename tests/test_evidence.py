from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import evidence
from quant_learn.db import initialize_database
from quant_learn.time import utc_now_naive


def test_evidence_cards_have_source_lineage_and_core_types(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "evidence.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_full_evidence_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")

    assert {"GOOGL", "NVDA", "AMD", "TSM"}.issubset(set(cards["ticker"]))
    assert {
        "event_reaction",
        "segment_momentum",
        "cash_flow_quality",
        "factor_residual",
    }.issubset(set(cards["evidence_type"]))
    assert cards["source_table"].notna().all()
    assert cards["source_id"].astype(str).str.len().gt(0).all()
    assert cards["evidence_id"].is_unique


def test_research_stance_requires_minimum_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "limited_evidence.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_factor_only_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    amd = stance[stance["ticker"] == "AMD"].iloc[0]

    assert amd["stance"] == "neutral"
    assert amd["confidence"] <= 0.55
    assert "limited evidence coverage" in amd["data_quality_caveats"]


def test_strong_constructive_requires_segment_and_cash_flow_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stance_caps.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    cards = _direct_evidence_cards_without_segment_or_cash()

    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    nvda = stance[stance["ticker"] == "NVDA"].iloc[0]

    assert nvda["stance"] != "strong_constructive"
    assert nvda["confidence"] <= 0.55
    assert "missing segment evidence" in nvda["data_quality_caveats"]
    assert "missing cash-flow evidence" in nvda["data_quality_caveats"]


def test_decision_memo_contains_all_four_tickers_and_falsifiers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "memo.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_full_evidence_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    output_path = tmp_path / "decision_memo.md"

    evidence.build_decision_memo(output_path)
    memo = output_path.read_text(encoding="utf-8")

    for ticker in ("GOOGL", "NVDA", "AMD", "TSM"):
        assert f"## {ticker}" in memo
    assert "### Falsifiers" in memo
    assert "Stance is research output only" in memo


def _patch_evidence_db(monkeypatch, db_path: Path) -> None:
    initialize_database(db_path)
    monkeypatch.setattr(evidence, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(evidence, "initialize_database", lambda: initialize_database(db_path))


def _seed_full_evidence_fixture(db_path: Path) -> None:
    tickers = ["GOOGL", "NVDA", "AMD", "TSM"]
    created_at = utc_now_naive()
    with duckdb.connect(str(db_path)) as conn:
        event_reviews = pd.DataFrame(
            [
                {
                    "event_id": f"{ticker.lower()}_event",
                    "affected_ticker": ticker,
                    "reaction_date": pd.Timestamp("2026-01-20").date(),
                    "event_type": "earnings",
                    "summary": f"{ticker} event",
                    "raw_reaction_summary": "fixture raw reaction",
                    "benchmark_attribution_summary": "fixture benchmark attribution",
                    "metric_surprise_summary": "fixture metric surprise",
                    "linked_segment_features": "fixture_feature",
                    "linked_kpi_ids": f"{ticker.lower()}_kpi_1",
                    "fundamental_context_summary": "fixture context",
                    "interpretation": f"{ticker} showed company-specific event reaction.",
                    "thesis_impact": "supports thesis tag ai_compute",
                    "confidence": 0.72,
                    "data_quality_flag": "complete",
                    "analysis_status": "ready",
                    "created_at": created_at,
                    "ingested_at": created_at,
                }
                for ticker in tickers
            ]
        )
        _insert_df(conn, "event_reviews", event_reviews)

        event_returns = pd.DataFrame(
            [
                {
                    "event_id": f"{ticker.lower()}_event",
                    "event_date": pd.Timestamp("2026-01-19").date(),
                    "reaction_date": pd.Timestamp("2026-01-20").date(),
                    "affected_ticker": ticker,
                    "event_type": "earnings",
                    "return_window": "0_p5",
                    "raw_return": 0.08 if ticker in {"GOOGL", "AMD"} else -0.06,
                    "benchmark_type": "factor_model",
                    "benchmark_ticker": "QQQ_SOXX_TNX",
                    "benchmark_return": 0.02,
                    "abnormal_return": 0.06 if ticker in {"GOOGL", "AMD"} else -0.08,
                    "model_name": "three_factor_raw",
                    "data_quality_flag": "complete",
                    "missing_reason": None,
                    "analysis_status": "ready",
                    "ingested_at": created_at,
                }
                for ticker in tickers
            ]
        )
        _insert_df(conn, "event_returns", event_returns)

        segment_features = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-02-01").date(),
                    "ticker": ticker,
                    "feature_name": _segment_feature_name(ticker),
                    "feature_value": 0.25,
                    "feature_score": 82.0 if ticker != "TSM" else 28.0,
                    "direction": "positive" if ticker != "TSM" else "negative",
                    "confidence": 0.76,
                    "source_kpi_ids": f"{ticker.lower()}_segment_kpi_1",
                    "ingested_at": created_at,
                }
                for ticker in tickers
            ]
        )
        _insert_df(conn, "segment_features", segment_features)

        cash_flow_features = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-02-01").date(),
                    "ticker": ticker,
                    "feature_name": "fcf_margin",
                    "feature_value": 0.20,
                    "feature_score": 75.0 if ticker != "NVDA" else 25.0,
                    "direction": "positive" if ticker != "NVDA" else "negative",
                    "source_fundamental_ids": f"fundamental_{ticker.lower()}_2026_q4",
                    "confidence": 0.70,
                    "data_quality_flag": "complete",
                    "ingested_at": created_at,
                }
                for ticker in tickers
            ]
        )
        _insert_df(conn, "cash_flow_features", cash_flow_features)

        factor_exposures = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-02-10").date(),
                    "ticker": ticker,
                    "model_name": "three_factor_raw",
                    "lookback_window": 60,
                    "n_obs": 60,
                    "alpha_daily": 0.0,
                    "beta_qqq": 1.0,
                    "beta_soxx": 0.5,
                    "beta_tnx_bps": -0.0002,
                    "r2": 0.65,
                    "factor_corr_qqq_soxx": 0.70,
                    "data_quality_flag": "complete",
                    "ingested_at": created_at,
                }
                for ticker in tickers
            ]
        )
        _insert_df(conn, "factor_exposures", factor_exposures)

        factor_residuals = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2026-02-10").date(),
                    "ticker": ticker,
                    "model_name": "three_factor_raw",
                    "lookback_window": 60,
                    "stock_return_1d": 0.01,
                    "expected_return_1d": 0.0,
                    "residual_return_1d": 0.01,
                    "market_contribution_1d": 0.0,
                    "sector_contribution_1d": 0.0,
                    "rate_contribution_1d": 0.0,
                    "alpha_contribution_1d": 0.0,
                    "residual_return_5d": 0.04,
                    "residual_return_20d": 0.08 if ticker in {"GOOGL", "AMD"} else -0.08,
                    "residual_return_60d": 0.12 if ticker in {"GOOGL", "AMD"} else -0.12,
                    "data_quality_flag": "complete",
                    "ingested_at": created_at,
                }
                for ticker in tickers
            ]
        )
        _insert_df(conn, "factor_residuals", factor_residuals)


def _seed_factor_only_fixture(db_path: Path) -> None:
    created_at = utc_now_naive()
    with duckdb.connect(str(db_path)) as conn:
        _insert_df(
            conn,
            "factor_exposures",
            pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-02-10").date(),
                        "ticker": "AMD",
                        "model_name": "three_factor_raw",
                        "lookback_window": 60,
                        "n_obs": 60,
                        "alpha_daily": 0.0,
                        "beta_qqq": 1.0,
                        "beta_soxx": 0.5,
                        "beta_tnx_bps": -0.0002,
                        "r2": 0.70,
                        "factor_corr_qqq_soxx": 0.65,
                        "data_quality_flag": "complete",
                        "ingested_at": created_at,
                    }
                ]
            ),
        )
        _insert_df(
            conn,
            "factor_residuals",
            pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp("2026-02-10").date(),
                        "ticker": "AMD",
                        "model_name": "three_factor_raw",
                        "lookback_window": 60,
                        "stock_return_1d": 0.01,
                        "expected_return_1d": 0.0,
                        "residual_return_1d": 0.01,
                        "market_contribution_1d": 0.0,
                        "sector_contribution_1d": 0.0,
                        "rate_contribution_1d": 0.0,
                        "alpha_contribution_1d": 0.0,
                        "residual_return_5d": 0.04,
                        "residual_return_20d": 0.08,
                        "residual_return_60d": 0.12,
                        "data_quality_flag": "complete",
                        "ingested_at": created_at,
                    }
                ]
            ),
        )


def _direct_evidence_cards_without_segment_or_cash() -> pd.DataFrame:
    created_at = utc_now_naive()
    rows = []
    for index in range(6):
        evidence_type = "event_reaction" if index < 3 else "factor_residual"
        rows.append(
            {
                "evidence_id": f"evidence_nvda_{index}",
                "as_of_date": pd.Timestamp("2026-02-10").date(),
                "ticker": "NVDA",
                "evidence_type": evidence_type,
                "source_table": "fixture",
                "source_id": f"source_{index}",
                "source_date": pd.Timestamp("2026-02-01").date(),
                "available_date": pd.Timestamp("2026-02-01").date(),
                "direction": "positive",
                "strength": "very_high",
                "confidence": 0.9,
                "materiality": 0.20,
                "summary": "NVDA fixture positive evidence.",
                "metric_name": f"metric_{index}",
                "metric_value": 0.20,
                "comparison_value": 0.0,
                "interpretation": "fixture",
                "thesis_tag": "fixture",
                "risk_tag": None,
                "data_quality_flag": "complete",
                "created_at": created_at,
                "ingested_at": created_at,
            }
        )
    return pd.DataFrame(rows)[evidence.EVIDENCE_COLUMNS]


def _segment_feature_name(ticker: str) -> str:
    return {
        "GOOGL": "cloud_growth_score",
        "NVDA": "data_center_momentum_score",
        "AMD": "data_center_momentum_score",
        "TSM": "monthly_revenue_momentum_score",
    }[ticker]


def _insert_df(conn: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    conn.register("frame", frame)
    conn.execute(f"INSERT INTO {table} SELECT * FROM frame")
    conn.unregister("frame")
