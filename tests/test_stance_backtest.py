from pathlib import Path

import duckdb
import pandas as pd
import pytest

from quant_learn.analytics import stance_backtest
from quant_learn.db import initialize_database
from quant_learn.time import utc_now_naive


def test_stance_backtest_observation_calculates_forward_residual(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stance_backtest.duckdb"
    _patch_backtest_db(monkeypatch, db_path)
    _seed_backtest_fixture(db_path)

    observations = stance_backtest.build_stance_backtest_observations(horizons=(2,))

    assert len(observations) == 1
    row = observations.iloc[0]
    expected_return = (1.03 * 1.02) - 1
    assert row["data_quality_flag"] == "complete"
    assert bool(row["is_mature"]) is True
    assert row["entry_date"] == pd.Timestamp("2026-01-02").date()
    assert row["maturity_date"] == pd.Timestamp("2026-01-06").date()
    assert row["forward_raw_return"] == pytest.approx(0.21)
    assert row["forward_factor_expected_return"] == pytest.approx(expected_return)
    assert row["forward_residual_return"] == pytest.approx(0.21 - expected_return)
    assert row["forward_max_drawdown"] == pytest.approx(0.0)


def test_stance_backtest_pending_horizon_stays_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stance_backtest_pending.duckdb"
    _patch_backtest_db(monkeypatch, db_path)
    _seed_backtest_fixture(db_path)

    observations = stance_backtest.build_stance_backtest_observations(horizons=(5,))

    assert len(observations) == 1
    row = observations.iloc[0]
    assert bool(row["is_mature"]) is False
    assert row["data_quality_flag"] == "pending"
    assert pd.isna(row["forward_residual_return"])


def test_stance_backtest_excludes_failed_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stance_backtest_failed.duckdb"
    _patch_backtest_db(monkeypatch, db_path)
    _seed_backtest_fixture(db_path, status="failed")

    observations = stance_backtest.build_stance_backtest_observations(horizons=(2,))

    assert observations.empty


def test_stance_backtest_summary_uses_mature_complete_observations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stance_backtest_summary.duckdb"
    _patch_backtest_db(monkeypatch, db_path)
    _seed_backtest_fixture(db_path)
    observations = stance_backtest.build_stance_backtest_observations(horizons=(2, 5))

    summary = stance_backtest.build_stance_backtest_summary(observations)

    mature = summary[summary["mature_count"] == 1]
    pending = summary[summary["horizon"] == 5]
    assert len(mature) == 1
    assert mature.iloc[0]["hit_rate"] == pytest.approx(1.0)
    assert mature.iloc[0]["mean_forward_residual_return"] > 0
    assert pending.iloc[0]["mature_count"] == 0
    assert pd.isna(pending.iloc[0]["hit_rate"])


def _patch_backtest_db(monkeypatch, db_path: Path) -> None:
    initialize_database(db_path)
    monkeypatch.setattr(
        stance_backtest,
        "connect",
        lambda: duckdb.connect(str(db_path)),
    )
    monkeypatch.setattr(
        stance_backtest,
        "initialize_database",
        lambda: initialize_database(db_path),
    )


def _seed_backtest_fixture(db_path: Path, status: str = "success") -> None:
    now = utc_now_naive()
    prices = pd.DataFrame(
        [
            _price_row("2026-01-02", "AMD", 100.0, now),
            _price_row("2026-01-05", "AMD", 110.0, now),
            _price_row("2026-01-06", "AMD", 121.0, now),
        ]
    )
    residuals = pd.DataFrame(
        [
            _residual_row("2026-01-05", "AMD", 0.03, now),
            _residual_row("2026-01-06", "AMD", 0.02, now),
        ]
    )
    with duckdb.connect(str(db_path)) as conn:
        conn.register("prices_frame", prices)
        conn.execute("INSERT INTO prices SELECT * FROM prices_frame")
        conn.unregister("prices_frame")
        conn.register("residuals_frame", residuals)
        conn.execute("INSERT INTO factor_residuals SELECT * FROM residuals_frame")
        conn.unregister("residuals_frame")
        conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, started_at, completed_at, mode, from_step, to_step,
                force_stale, status, data_snapshot_hash, freshness_snapshot_json,
                error_message
            )
            VALUES (
                'run_fixture', ?, ?, 'full', 'fundamentals', 'weekly_digest',
                FALSE, ?, 'snapshot_fixture', '[]', NULL
            )
            """,
            [now, now, status],
        )
        conn.execute(
            """
            INSERT INTO research_stance_history (
                run_id, archived_at, stance_id, as_of_date, ticker, stance,
                stance_modifier, confidence, thesis_summary, positive_evidence_ids,
                negative_evidence_ids, mixed_evidence_ids, risk_flags, falsifiers,
                next_catalysts, data_quality_caveats, created_at, ingested_at
            )
            VALUES (
                'run_fixture', ?, 'stance_fixture', '2026-01-02', 'AMD',
                'constructive', 'factor_led', 0.8, 'fixture thesis', 'e1',
                '', '', '', '', '', '', ?, ?
            )
            """,
            [now, now, now],
        )


def _price_row(date: str, ticker: str, price: float, now) -> dict:
    return {
        "date": pd.Timestamp(date).date(),
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
        "ingested_at": now,
    }


def _residual_row(date: str, ticker: str, expected_return: float, now) -> dict:
    return {
        "date": pd.Timestamp(date).date(),
        "ticker": ticker,
        "model_name": "three_factor_raw",
        "lookback_window": 60,
        "stock_return_1d": None,
        "expected_return_1d": expected_return,
        "residual_return_1d": None,
        "market_contribution_1d": None,
        "sector_contribution_1d": None,
        "rate_contribution_1d": None,
        "alpha_contribution_1d": None,
        "residual_return_5d": None,
        "residual_return_20d": None,
        "residual_return_60d": None,
        "data_quality_flag": "complete",
        "ingested_at": now,
    }
