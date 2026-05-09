from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import event_study
from quant_learn.analytics.event_study import _event_window_return
from quant_learn.db import initialize_database

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

    monkeypatch.setattr(event_study, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(event_study, "initialize_database", lambda: initialize_database(db_path))

    result = event_study.build_event_returns(
        event_type="earnings",
        benchmark_tickers=["QQQ"],
    )
    row = result[
        (result["return_window"] == "0_p1") & (result["benchmark_ticker"] == "QQQ")
    ].iloc[0]

    assert row["affected_ticker"] == "TEST"
    assert row["reaction_date"] == pd.Timestamp("2026-01-06").date()
    assert row["raw_return"] == 121.0 / 105.0 - 1.0
    assert row["benchmark_return"] == 105.0 / 100.0 - 1.0
    assert row["abnormal_return"] == row["raw_return"] - row["benchmark_return"]
