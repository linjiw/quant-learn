from pathlib import Path

import duckdb
import pandas as pd
import pytest

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


def test_stance_components_sum_to_net_score(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "components.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_full_evidence_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    components, caps, conflicts = evidence.build_stance_audit_tables(
        as_of_date="2026-02-10",
    )

    amd_cards = cards[cards["ticker"] == "AMD"].copy()
    amd_cards["source_date"] = pd.to_datetime(amd_cards["source_date"], errors="coerce")
    scored = evidence._score_evidence_for_ticker(  # noqa: SLF001
        "AMD",
        amd_cards,
        pd.Timestamp("2026-02-10").date(),
    )
    component_sum = components[components["ticker"] == "AMD"]["weighted_score"].sum()

    assert component_sum == _approx(scored["weighted_score"].sum())
    assert not caps.empty
    assert not conflicts.empty


def test_confidence_caps_are_recorded_when_applied(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cap_audit.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_factor_only_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    evidence.store_research_stance(evidence.build_research_stance(as_of_date="2026-02-10"))
    _, caps, _ = evidence.build_stance_audit_tables(as_of_date="2026-02-10")
    amd_caps = set(caps[caps["ticker"] == "AMD"]["cap_type"])

    assert "limited_evidence" in amd_caps
    assert "missing_segment_evidence" in amd_caps
    assert "missing_cash_flow_evidence" in amd_caps
    assert "missing_valuation_evidence" in amd_caps
    assert "factor_dominated_positive_evidence" in amd_caps


def test_tsm_constructive_confidence_capped_by_fx_gap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "tsm_fx_cap.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_full_evidence_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    _, caps, _ = evidence.build_stance_audit_tables(as_of_date="2026-02-10")
    tsm = stance[stance["ticker"] == "TSM"].iloc[0]

    assert tsm["confidence"] <= 0.65
    assert "tsm_fx_model_gap" in set(caps[caps["ticker"] == "TSM"]["cap_type"])


def test_positive_stance_with_negative_factor_residual_sets_conflict_flag(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "conflict.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    cards = _direct_conflicted_constructive_evidence()

    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    _, _, conflicts = evidence.build_stance_audit_tables(as_of_date="2026-02-10")
    nvda = stance[stance["ticker"] == "NVDA"].iloc[0]

    assert nvda["stance"] in {"constructive", "strong_constructive"}
    assert "factor_conflicted" in nvda["stance_modifier"]
    assert "positive_stance_negative_factor_residual" in set(conflicts["conflict_type"])
    assert "positive_segment_negative_factor" in set(conflicts["conflict_type"])


def test_factor_dominated_positive_stance_capped_below_strong_constructive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "factor_dominated_cap.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    cards = _direct_factor_dominated_evidence()

    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    _, caps, conflicts = evidence.build_stance_audit_tables(as_of_date="2026-02-10")
    amd = stance[stance["ticker"] == "AMD"].iloc[0]
    amd_caps = set(caps[caps["ticker"] == "AMD"]["cap_type"])

    assert amd["stance"] == "neutral"
    assert "factor_led" in amd["stance_modifier"]
    assert "factor_dominated_positive_evidence" in amd_caps
    assert "factor_led_insufficient_confirmation" in amd_caps
    assert "insufficient_non_factor_positive_confirmation" in amd_caps
    assert "factor_dominated_positive_stance" in set(conflicts["conflict_type"])


def test_decision_memo_summary_includes_modifiers_and_caveats(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "memo_modifiers.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_full_evidence_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    output_path = tmp_path / "decision_memo.md"

    evidence.build_decision_memo(output_path)
    memo = output_path.read_text(encoding="utf-8")

    assert "| Ticker | Stance | Modifier | Confidence | Main caveat | One-line thesis |" in memo
    assert "/ factor_conflicted" in memo or "/ data_quality_capped" in memo


def test_stance_audit_report_contains_all_four_tickers(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "audit_report.duckdb"
    _patch_evidence_db(monkeypatch, db_path)
    _seed_full_evidence_fixture(db_path)

    cards = evidence.build_evidence_cards(as_of_date="2026-02-10")
    evidence.store_evidence_cards(cards)
    stance = evidence.build_research_stance(as_of_date="2026-02-10")
    evidence.store_research_stance(stance)
    evidence.store_stance_audit_tables(
        *evidence.build_stance_audit_tables(as_of_date="2026-02-10")
    )
    output_path = tmp_path / "stance_audit_report.md"

    evidence.build_stance_audit_report(output_path)
    report = output_path.read_text(encoding="utf-8")

    for ticker in ("GOOGL", "NVDA", "AMD", "TSM"):
        assert f"## {ticker}" in report
    assert "### Score Contribution By Type" in report
    assert "### Confidence Caps Applied" in report


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


def _direct_conflicted_constructive_evidence() -> pd.DataFrame:
    created_at = utc_now_naive()
    rows = [
        _evidence_fixture_row(
            "nvda_segment_positive",
            "NVDA",
            "segment_momentum",
            "positive",
            "very_high",
            0.90,
            "NVDA segment momentum is strongly positive.",
            "data_center_momentum_score",
        ),
        _evidence_fixture_row(
            "nvda_event_positive",
            "NVDA",
            "event_reaction",
            "positive",
            "very_high",
            0.90,
            "NVDA event reaction is strongly positive.",
            "factor_model_abnormal_0_p5",
        ),
        _evidence_fixture_row(
            "nvda_cash_positive",
            "NVDA",
            "cash_flow_quality",
            "positive",
            "high",
            0.85,
            "NVDA cash-flow evidence is positive.",
            "fcf_margin",
        ),
        _evidence_fixture_row(
            "nvda_factor_negative",
            "NVDA",
            "factor_residual",
            "negative",
            "high",
            0.80,
            "NVDA factor residual evidence is negative.",
            "residual_return_60d",
            risk_tag="factor_residual_pressure",
        ),
    ]
    frame = pd.DataFrame(rows)
    frame["created_at"] = created_at
    frame["ingested_at"] = created_at
    return frame[evidence.EVIDENCE_COLUMNS]


def _direct_factor_dominated_evidence() -> pd.DataFrame:
    created_at = utc_now_naive()
    rows = [
        _evidence_fixture_row(
            "amd_factor_positive",
            "AMD",
            "factor_residual",
            "positive",
            "very_high",
            0.95,
            "AMD factor residual evidence is very positive.",
            "residual_return_60d",
        ),
        _evidence_fixture_row(
            "amd_event_positive",
            "AMD",
            "event_reaction",
            "positive",
            "very_high",
            0.95,
            "AMD event evidence is positive.",
            "factor_model_abnormal_0_p5",
        ),
        _evidence_fixture_row(
            "amd_cash_negative",
            "AMD",
            "cash_flow_quality",
            "negative",
            "low",
            0.60,
            "AMD cash-flow evidence is weak.",
            "fcf_margin",
            risk_tag="cash_flow_pressure",
        ),
        _evidence_fixture_row(
            "amd_cash_negative_2",
            "AMD",
            "cash_flow_quality",
            "negative",
            "low",
            0.60,
            "AMD second cash-flow evidence is weak.",
            "capex_to_ocf",
            risk_tag="cash_flow_pressure",
        ),
    ]
    frame = pd.DataFrame(rows)
    frame["created_at"] = created_at
    frame["ingested_at"] = created_at
    return frame[evidence.EVIDENCE_COLUMNS]


def _evidence_fixture_row(
    evidence_id: str,
    ticker: str,
    evidence_type: str,
    direction: str,
    strength: str,
    confidence: float,
    summary: str,
    metric_name: str,
    risk_tag: str | None = None,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "as_of_date": pd.Timestamp("2026-02-10").date(),
        "ticker": ticker,
        "evidence_type": evidence_type,
        "source_table": "fixture",
        "source_id": evidence_id,
        "source_date": pd.Timestamp("2026-02-01").date(),
        "available_date": pd.Timestamp("2026-02-01").date(),
        "direction": direction,
        "strength": strength,
        "confidence": confidence,
        "materiality": 0.20,
        "summary": summary,
        "metric_name": metric_name,
        "metric_value": 0.20,
        "comparison_value": 0.0,
        "interpretation": "fixture",
        "thesis_tag": "fixture",
        "risk_tag": risk_tag,
        "data_quality_flag": "complete",
    }


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


def _approx(value: float):
    return pytest.approx(value, abs=1e-9)
