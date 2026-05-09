from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import segments
from quant_learn.db import initialize_database
from quant_learn.ingest import manual
from quant_learn.taxonomy import SEGMENT_KPI_GROUPS, SEGMENT_PERIOD_TYPES


def test_segment_kpis_import_view_and_features(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(manual, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(manual, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    csv_path = tmp_path / "segment_kpis.csv"
    rows = []
    for period_end, revenue, operating_income in (
        ("2025-03-31", 100.0, 10.0),
        ("2025-06-30", 120.0, 18.0),
        ("2025-09-30", 140.0, 21.0),
        ("2025-12-31", 160.0, 32.0),
        ("2026-03-31", 200.0, 40.0),
    ):
        for kpi_name, value in (("revenue", revenue), ("operating_income", operating_income)):
            rows.append(
                {
                    "period_end": period_end,
                    "fiscal_year": int(period_end[:4]),
                    "fiscal_quarter": "Q1",
                    "period_type": "quarter",
                    "ticker": "GOOGL",
                    "kpi_group": "segment",
                    "segment_name": "Google Cloud",
                    "kpi_name": kpi_name,
                    "kpi_value": value,
                    "unit": "USD_mn",
                    "currency": "USD",
                    "source_type": "fixture",
                    "source_url": "https://example.com",
                    "is_reported": True,
                    "is_derived": False,
                    "confidence": "high",
                }
            )
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    imported = manual.import_segment_kpis(csv_path)
    assert imported == 10

    with duckdb.connect(str(db_path)) as conn:
        kpis = conn.execute("SELECT * FROM segment_kpis").fetchdf()
        view = conn.execute(
            """
            SELECT *
            FROM segments_view
            WHERE ticker = 'GOOGL' AND segment_name = 'Google Cloud'
            ORDER BY period_end DESC
            LIMIT 1
            """
        ).fetchdf()

    assert set(kpis["period_type"]).issubset(SEGMENT_PERIOD_TYPES)
    assert set(kpis["kpi_group"]).issubset(SEGMENT_KPI_GROUPS)
    assert view.iloc[0]["segment_margin"] == 0.2
    assert view.iloc[0]["segment_revenue_growth_yoy"] == 1.0

    features = segments.build_segment_features()
    feature_names = set(features["feature_name"])
    assert "google_cloud_revenue_growth_yoy" in feature_names
    assert "google_cloud_margin" in feature_names


def test_tsmc_monthly_revenue_integrates_with_segment_features(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "tsm_segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    ingested_at = pd.Timestamp("2026-05-09")
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO tsmc_monthly_revenue (
                period, year, month, revenue_ntd_million, mom_pct, yoy_pct,
                source_url, ingested_at
            )
            VALUES
                ('2026-03-01', 2026, 3, 415191, 30.7, 45.2, 'fixture', ?),
                ('2026-04-01', 2026, 4, 410726, -1.1, 17.5, 'fixture', ?)
            """,
            [ingested_at, ingested_at],
        )

    kpis = segments.build_tsmc_monthly_segment_kpis(months=2)
    assert len(kpis) == 6
    segments.store_segment_kpis(kpis)
    features = segments.build_segment_features()

    assert set(features["ticker"]) == {"TSM"}
    assert "monthly_revenue_momentum_score" in set(features["feature_name"])
