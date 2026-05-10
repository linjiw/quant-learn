from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import auditability
from quant_learn.db import initialize_database
from quant_learn.time import utc_now_naive


def test_archive_research_outputs_preserves_prior_stance(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "archive.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(auditability, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        auditability,
        "initialize_database",
        lambda: initialize_database(db_path),
    )
    now = utc_now_naive()
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO research_stance (
                run_id, stance_id, as_of_date, ticker, stance, stance_modifier, confidence,
                thesis_summary, positive_evidence_ids, negative_evidence_ids,
                mixed_evidence_ids, risk_flags, falsifiers, next_catalysts,
                data_quality_caveats, created_at, ingested_at
            )
            VALUES (
                'source_run', 'stance_test', '2026-05-01', 'AMD', 'constructive', 'factor_led',
                0.7, 'fixture', '', '', '', '', '', '', '', ?, ?
            )
            """,
            [now, now],
        )

    auditability.archive_research_outputs("run_fixture")
    auditability.archive_research_outputs("run_fixture")

    with duckdb.connect(str(db_path)) as conn:
        archived = conn.execute(
            "SELECT run_id, stance_id, ticker FROM research_stance_history"
        ).fetchdf()

    assert archived.to_dict("records") == [
        {"run_id": "source_run", "stance_id": "stance_test", "ticker": "AMD"}
    ]


def test_freshness_snapshot_hash_and_stale_tables(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "freshness.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(auditability, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(
        auditability,
        "initialize_database",
        lambda: initialize_database(db_path),
    )
    now = utc_now_naive()
    prices = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-05-01").date(),
                "ticker": "AMD",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "adj_close": 1.0,
                "volume": 1,
                "return_1d": None,
                "return_5d": None,
                "return_20d": None,
                "return_60d": None,
                "source": "fixture",
                "ingested_at": now,
            }
        ]
    )
    with duckdb.connect(str(db_path)) as conn:
        conn.register("frame", prices)
        conn.execute("INSERT INTO prices SELECT * FROM frame")
        conn.unregister("frame")

    snapshot = auditability.build_freshness_snapshot(["prices", "research_stance"])
    snapshot_hash = auditability.data_snapshot_hash(snapshot)
    volatile_snapshot = [
        {
            **row,
            "max_ingested_at": "2026-05-09 12:00:00",
            "staleness_days": 999,
        }
        for row in snapshot
    ]
    stale = auditability.stale_tables(snapshot, max_staleness_days=0)

    assert len(snapshot_hash) == 16
    assert auditability.data_snapshot_hash(volatile_snapshot) == snapshot_hash
    assert snapshot[0]["table"] == "prices"
    assert snapshot[0]["row_count"] == 1
    assert any(row["table"] == "research_stance" for row in stale)
