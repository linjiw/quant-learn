from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import data_quality, event_reviews
from quant_learn.db import initialize_database


def test_event_reviews_link_segment_features_when_available(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "event_reviews.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(event_reviews, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(event_reviews, "initialize_database", lambda: initialize_database(db_path))

    ingested_at = pd.Timestamp("2026-05-09")
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO events (
                event_id, event_date, reaction_date, ticker, primary_ticker, event_type,
                event_name, event_description, source, source_url, after_market,
                importance_score, thesis_tag, expected_value, actual_value, surprise_pct,
                metadata_json, created_at, ingested_at
            )
            VALUES (
                'nvda_test_event', DATE '2026-03-01', DATE '2026-03-02', 'NVDA', 'NVDA',
                'earnings', 'NVDA test earnings', 'fixture', 'fixture', 'https://example.com',
                false, 4.0, 'ai_platform', NULL, NULL, NULL, NULL, ?, ?
            )
            """,
            [ingested_at, ingested_at],
        )
        conn.execute(
            """
            INSERT INTO event_impacts (
                event_id, affected_ticker, expected_direction, driver_tag, thesis_tag,
                impact_confidence, ingested_at
            )
            VALUES ('nvda_test_event', 'NVDA', 'positive', 'ai_demand', 'ai_platform', 0.8, ?)
            """,
            [ingested_at],
        )
        conn.execute(
            """
            INSERT INTO event_returns (
                event_id, event_date, reaction_date, affected_ticker, event_type,
                return_window, raw_return, benchmark_type, benchmark_ticker,
                benchmark_return, abnormal_return, model_name, data_quality_flag,
                missing_reason, analysis_status, ingested_at
            )
            VALUES
                ('nvda_test_event', DATE '2026-03-01', DATE '2026-03-02', 'NVDA',
                 'earnings', '0_p1', 0.04, 'sector', 'SOXX', 0.01, 0.03,
                 'fixture', 'complete', NULL, 'ready', ?),
                ('nvda_test_event', DATE '2026-03-01', DATE '2026-03-02', 'NVDA',
                 'earnings', '0_p5', 0.08, 'sector', 'SOXX', 0.02, 0.06,
                 'fixture', 'complete', NULL, 'ready', ?)
            """,
            [ingested_at, ingested_at],
        )
        conn.execute(
            """
            INSERT INTO segment_features (
                date, ticker, feature_name, feature_value, feature_score, direction,
                confidence, source_kpi_ids, ingested_at
            )
            VALUES
                (
                    DATE '2026-01-15', 'NVDA', 'data_center_momentum_score', 0.2,
                    70.0, 'positive', 0.8, 'segment_kpi_old', ?
                ),
                (
                    DATE '2026-02-20', 'NVDA', 'gross_margin_quality_score', 0.7,
                    70.0, 'positive', 0.9, 'segment_kpi_margin', ?
                ),
                (
                    DATE '2026-02-25', 'NVDA', 'data_center_momentum_score', 0.5,
                    100.0, 'positive', 0.9, 'segment_kpi_fixture', ?
                )
            """,
            [ingested_at, ingested_at, ingested_at],
        )

    reviews = event_reviews.build_event_reviews()
    row = reviews.iloc[0]
    assert row["linked_segment_features"] == (
        "data_center_momentum_score,gross_margin_quality_score"
    )
    assert row["linked_kpi_ids"] == "segment_kpi_fixture,segment_kpi_margin"
    assert "segment_kpi_old" not in row["linked_kpi_ids"]
    assert "segment context" in row["fundamental_context_summary"]


def test_event_data_quality_report_groups_missing_reasons(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "event_quality.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(data_quality, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(data_quality, "initialize_database", lambda: initialize_database(db_path))

    ingested_at = pd.Timestamp("2026-05-09")
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO event_returns (
                event_id, event_date, reaction_date, affected_ticker, event_type,
                return_window, raw_return, benchmark_type, benchmark_ticker,
                benchmark_return, abnormal_return, model_name, data_quality_flag,
                missing_reason, analysis_status, ingested_at
            )
            VALUES
                ('event_a', DATE '2026-01-01', DATE '2026-01-02', 'TSM',
                 'earnings', '0_p20', NULL, 'sector', 'SOXX', NULL, NULL,
                 'fixture', 'incomplete', 'pending_future_window', 'partial_pending', ?),
                ('event_b', DATE '2026-01-01', DATE '2026-01-02', 'TSM',
                 'earnings', '0_p5', NULL, 'sector', 'SOXX', NULL, NULL,
                 'fixture', 'incomplete', 'adr_calendar_gap', 'data_issue', ?)
            """,
            [ingested_at, ingested_at],
        )

    output_path = tmp_path / "event_quality.md"
    data_quality.build_event_data_quality_report(output_path)
    report = output_path.read_text(encoding="utf-8")
    assert "pending_future_window" in report
    assert "adr_calendar_gap" in report
    assert "data_issue" in report
