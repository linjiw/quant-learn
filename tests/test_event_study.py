from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import event_reviews, event_study
from quant_learn.analytics.event_study import (
    EVENT_RETURN_WINDOWS,
    _event_window_return,
    event_return_invariants_pass,
    validate_event_return_invariants,
)
from quant_learn.db import initialize_database
from quant_learn.taxonomy import (
    ANALYSIS_STATUSES,
    EVENT_TYPES,
    EXPECTED_DIRECTIONS,
    MISSING_REASONS,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_import_events_ai_compute_csv_has_required_event_loop_fields() -> None:
    events = pd.read_csv(PROJECT_ROOT / "data/manual/events_ai_compute.csv")
    impacts = pd.read_csv(PROJECT_ROOT / "data/manual/event_impacts_ai_compute.csv")
    metrics = pd.read_csv(PROJECT_ROOT / "data/manual/event_metrics_ai_compute.csv")

    assert len(events) >= 25
    assert events["event_id"].notna().all()
    assert events["reaction_date"].notna().all()
    assert events["importance_score"].between(0, 1).all()
    assert set(events["event_id"]).issubset(set(impacts["event_id"]))
    assert set(events.loc[events["importance_score"] >= 0.8, "event_id"]).issubset(
        set(metrics["event_id"])
    )
    assert set(events["event_type"]).issubset(EVENT_TYPES)
    assert set(impacts["expected_direction"]).issubset(EXPECTED_DIRECTIONS)


def test_event_window_return_uses_inclusive_close_to_close_window() -> None:
    price = pd.DataFrame(
        {"TEST": [100.0, 102.0, 105.0, 110.0, 121.0]},
        index=pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
        ),
    )

    # Anchor is 2026-01-06. 0_p1 includes day 0 and day +1 returns, so it
    # starts from the close immediately before day 0: 121 / 105 - 1.
    result = _event_window_return(price, "TEST", anchor_index=3, start_offset=0, end_offset=1)

    assert result == 121.0 / 105.0 - 1.0


def test_build_event_returns_uses_reaction_date_and_long_benchmark_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "events.duckdb"
    initialize_database(db_path)
    ingested_at = pd.Timestamp("2026-01-10")
    price_rows = []
    for ticker, values in {
        "TEST": [100.0, 102.0, 105.0, 110.0, 121.0, 120.0, 132.0],
        "QQQ": [100.0, 100.0, 100.0, 105.0, 105.0, 105.0, 105.0],
    }.items():
        for date, price in zip(
            pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-05",
                    "2026-01-06",
                    "2026-01-07",
                    "2026-01-08",
                    "2026-01-09",
                ]
            ),
            values,
        ):
            price_rows.append(
                {
                    "date": date.date(),
                    "ticker": ticker,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "adj_close": price,
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
        prices = pd.DataFrame(price_rows)
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
        conn.execute(
            """
            INSERT INTO events (
                event_id, event_date, reaction_date, ticker, primary_ticker,
                event_type, event_name, event_description, source, source_url,
                after_market, importance_score, thesis_tag, expected_value,
                actual_value, surprise_pct, metadata_json, created_at, ingested_at
            )
            VALUES (
                'event_after_market', '2026-01-05', '2026-01-06', 'TEST', 'TEST',
                'earnings', 'fixture event', 'fixture', 'fixture', NULL,
                TRUE, 0.9, 'fixture', NULL, NULL, NULL, '{}', ?, ?
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
            VALUES ('event_after_market', 'TEST', 'positive', 'fixture', 'fixture', 0.9, ?)
            """,
            [ingested_at],
        )
        conn.execute(
            """
            INSERT INTO event_metrics (
                event_id, metric_name, actual_value, expected_value, surprise_value,
                surprise_pct, unit, source, confidence, metric_category,
                metric_polarity, surprise_direction, ingested_at
            )
            VALUES (
                'event_after_market', 'eps', 1.2, 1.0, 0.2, 0.2, 'usd_per_share',
                'fixture', 0.9, 'earnings', 'higher_is_better', 'positive', ?
            )
            """,
            [ingested_at],
        )

    monkeypatch.setattr(event_study, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(event_study, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(event_reviews, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        event_reviews,
        "initialize_database",
        lambda: initialize_database(db_path),
    )

    result = event_study.build_event_returns(
        event_type="earnings",
        benchmark_tickers=["QQQ", "SOXX"],
    )
    row = result[
        (result["return_window"] == "0_p1") & (result["benchmark_ticker"] == "QQQ")
    ].iloc[0]

    assert row["affected_ticker"] == "TEST"
    assert row["reaction_date"] == pd.Timestamp("2026-01-06").date()
    assert row["raw_return"] == 121.0 / 105.0 - 1.0
    assert row["benchmark_return"] == 105.0 / 100.0 - 1.0
    assert row["abnormal_return"] == row["raw_return"] - row["benchmark_return"]
    assert row["data_quality_flag"] == "complete"
    assert len(result) == len(EVENT_RETURN_WINDOWS) * 2

    invariants = validate_event_return_invariants(result)
    assert invariants["expected_rows"] == len(EVENT_RETURN_WINDOWS) * 2
    assert event_return_invariants_pass(result)

    missing_benchmark = result[
        (result["return_window"] == "0_p1") & (result["benchmark_ticker"] == "SOXX")
    ].iloc[0]
    assert missing_benchmark["data_quality_flag"] == "incomplete"
    assert missing_benchmark["missing_reason"] == "missing_benchmark_price"
    assert missing_benchmark["analysis_status"] == "data_issue"
    assert set(result["analysis_status"]).issubset(ANALYSIS_STATUSES)
    assert set(result["missing_reason"].dropna()).issubset(MISSING_REASONS)

    event_study.store_event_returns(result)
    reviews = event_reviews.build_event_reviews()
    review = reviews.iloc[0]

    assert len(reviews) == 1
    assert review["affected_ticker"] == "TEST"
    assert "Raw return" in review["raw_reaction_summary"]
    assert "Metric evidence" in review["metric_surprise_summary"]
    assert review["data_quality_flag"] == "incomplete"
    assert review["analysis_status"] == "data_issue"
