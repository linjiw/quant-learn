from pathlib import Path
from typing import Optional

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
    assert features["source_kpi_ids"].str.startswith("segment_kpi_").all()
    growth_feature = features[
        features["feature_name"] == "google_cloud_revenue_growth_yoy"
    ].iloc[0]
    cloud_revenue = kpis[
        (kpis["ticker"] == "GOOGL")
        & (kpis["segment_name"] == "Google Cloud")
        & (kpis["kpi_name"] == "revenue")
    ].copy()
    cloud_revenue["period_end"] = pd.to_datetime(cloud_revenue["period_end"])
    expected_source_ids = set(
        cloud_revenue[
            cloud_revenue["period_end"].isin(
                [pd.Timestamp("2025-03-31"), pd.Timestamp("2026-03-31")]
            )
        ]["segment_kpi_id"]
    )
    assert expected_source_ids.issubset(set(growth_feature["source_kpi_ids"].split(",")))


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


def test_segment_features_cover_all_four_tickers_and_driver_scores(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "full_segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(manual, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(manual, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    csv_path = tmp_path / "segment_kpis_full.csv"
    _write_feature_fixture(csv_path)
    manual.import_segment_kpis(csv_path)

    features = segments.build_segment_features()
    assert set(features["ticker"]) == {"AMD", "GOOGL", "NVDA", "TSM"}
    feature_names = set(features["feature_name"])
    assert "cloud_growth_score" in feature_names
    assert "data_center_momentum_score" in feature_names
    assert "second_source_thesis_score" in feature_names
    assert "monthly_revenue_yoy_trend_score" in feature_names
    assert features["source_kpi_ids"].notna().all()
    assert features["source_kpi_ids"].str.contains("segment_kpi_").all()


def test_required_kpi_taxonomy_covers_all_four_tickers() -> None:
    required = segments.REQUIRED_KPIS_BY_TICKER

    assert set(required) == {"GOOGL", "NVDA", "AMD", "TSM"}
    for ticker, feature_specs in required.items():
        assert feature_specs, ticker
        for feature_name, kpi_keys in feature_specs.items():
            assert feature_name.endswith("_score")
            assert kpi_keys
            assert all(":" in key for key in kpi_keys)


def test_segment_dashboard_contains_all_four_tickers(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "dashboard_segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(manual, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(manual, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    csv_path = tmp_path / "segment_kpis_full.csv"
    _write_feature_fixture(csv_path)
    manual.import_segment_kpis(csv_path)
    segment_features = segments.build_segment_features()
    segments.store_segment_features(segment_features)

    output_path = tmp_path / "segment_dashboard.md"
    segments.build_segment_dashboard(output_path)
    dashboard = output_path.read_text(encoding="utf-8")

    for ticker in ("GOOGL", "NVDA", "AMD", "TSM"):
        assert f"## {ticker}" in dashboard


def test_segment_features_do_not_generate_without_required_kpis(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "gated_segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(manual, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(manual, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    rows = []
    for index, period_end in enumerate(pd.date_range("2025-03-31", periods=5, freq="QE")):
        rows.append(
            _segment_row(
                period_end.date().isoformat(),
                "GOOGL",
                "segment",
                "Google Cloud",
                "revenue",
                100.0 + index * 10.0,
            )
        )
    csv_path = tmp_path / "segment_kpis_missing_margin.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    manual.import_segment_kpis(csv_path)

    features = segments.build_segment_features()
    feature_names = set(features["feature_name"])
    assert "google_cloud_revenue_growth_yoy" in feature_names
    assert "google_cloud_margin" not in feature_names
    assert "cloud_margin_score" not in feature_names


def test_driver_features_require_taxonomy_inputs(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "reported_margin_segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(manual, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(manual, "initialize_database", lambda: initialize_database(db_path))
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    rows = []
    for index, period_end in enumerate(pd.date_range("2025-03-31", periods=5, freq="QE")):
        date_text = period_end.date().isoformat()
        rows.append(
            _segment_row(
                date_text,
                "GOOGL",
                "segment",
                "Google Cloud",
                "revenue",
                100.0 + index * 10.0,
            )
        )
        rows.append(
            _segment_row(
                date_text,
                "GOOGL",
                "segment",
                "Google Cloud",
                "margin",
                0.2,
                unit="ratio",
                currency=None,
            )
        )
    csv_path = tmp_path / "segment_kpis_reported_margin_only.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    manual.import_segment_kpis(csv_path)

    features = segments.build_segment_features()
    feature_names = set(features["feature_name"])
    assert "google_cloud_margin" in feature_names
    assert "cloud_margin_score" not in feature_names


def test_company_segment_kpis_generate_capex_and_margin_features(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "company_segments.duckdb"
    initialize_database(db_path)
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))

    ingested_at = pd.Timestamp("2026-05-09")
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO fundamentals_quarterly (
                ticker, fiscal_year, fiscal_quarter, period_end, revenue,
                gross_profit, gross_margin, operating_income, operating_margin,
                net_income, eps, operating_cash_flow, capex, free_cash_flow,
                cash, debt, shares_outstanding, buyback, dividend,
                source_accession_number, source_filed_date, ingested_at
            )
            VALUES
                ('GOOGL', 2026, 'Q1', DATE '2026-03-31', 1000.0,
                 NULL, NULL, 300.0, 0.30, NULL, NULL, 400.0, 200.0, 200.0,
                 NULL, NULL, NULL, NULL, NULL, 'fixture', DATE '2026-04-30', ?),
                ('NVDA', 2026, 'Q1', DATE '2026-04-26', 1000.0,
                 700.0, 0.70, 600.0, 0.60, NULL, NULL, NULL, NULL, NULL,
                 NULL, NULL, NULL, NULL, NULL, 'fixture', DATE '2026-05-20', ?)
            """,
            [ingested_at, ingested_at],
        )

    company_kpis = segments.build_company_segment_kpis(tickers=["GOOGL", "NVDA"], quarters=1)
    assert {"capex_to_ocf", "fcf_margin", "gross_margin", "operating_margin"}.issubset(
        set(company_kpis["kpi_name"])
    )
    segments.store_segment_kpis(company_kpis)
    features = segments.build_segment_features()
    feature_names = set(features["feature_name"])
    assert "capex_pressure_score" in feature_names
    assert "fcf_quality_score" in feature_names
    assert "gross_margin_quality_score" in feature_names
    assert features["source_kpi_ids"].str.contains("segment_kpi_").all()


def _write_feature_fixture(path: Path) -> None:
    rows = []
    quarter_dates = pd.date_range("2025-03-31", periods=5, freq="QE")
    for index, period_end in enumerate(quarter_dates):
        date_text = period_end.date().isoformat()
        rows.extend(
            [
                _segment_row(
                    date_text,
                    "GOOGL",
                    "segment",
                    "Google Cloud",
                    "revenue",
                    100 + index * 30,
                ),
                _segment_row(
                    date_text,
                    "GOOGL",
                    "segment",
                    "Google Cloud",
                    "operating_income",
                    10 + index * 8,
                ),
                _segment_row(
                    date_text,
                    "GOOGL",
                    "segment",
                    "Google Search & other",
                    "revenue",
                    500 + index * 25,
                ),
                _segment_row(
                    date_text,
                    "GOOGL",
                    "segment",
                    "Google Services",
                    "revenue",
                    700 + index * 35,
                ),
                _segment_row(
                    date_text,
                    "GOOGL",
                    "segment",
                    "Google Services",
                    "operating_income",
                    250 + index * 20,
                ),
                _segment_row(
                    date_text,
                    "GOOGL",
                    "segment",
                    "YouTube ads",
                    "revenue",
                    80 + index * 8,
                ),
                _segment_row(
                    date_text,
                    "NVDA",
                    "end_market",
                    "Data Center",
                    "revenue",
                    300 + index * 90,
                ),
                _segment_row(
                    date_text,
                    "NVDA",
                    "end_market",
                    "Gaming",
                    "revenue",
                    100 + index * 12,
                ),
                _segment_row(
                    date_text,
                    "NVDA",
                    "end_market",
                    "Automotive",
                    "revenue",
                    20 + index * 4,
                ),
                _segment_row(
                    date_text,
                    "NVDA",
                    "end_market",
                    "Professional Visualization",
                    "revenue",
                    30 + index * 5,
                ),
                _segment_row(
                    date_text,
                    "AMD",
                    "reportable_segment",
                    "Data Center",
                    "revenue",
                    120 + index * 35,
                ),
                _segment_row(
                    date_text,
                    "AMD",
                    "reportable_segment",
                    "Data Center",
                    "operating_income",
                    20 + index * 10,
                ),
                _segment_row(
                    date_text,
                    "AMD",
                    "reportable_segment",
                    "Client",
                    "revenue",
                    90 + index * 15,
                ),
                _segment_row(
                    date_text,
                    "AMD",
                    "reportable_segment",
                    "Embedded",
                    "revenue",
                    70 + index * 2,
                ),
                _segment_row(
                    date_text,
                    "AMD",
                    "reportable_segment",
                    "Embedded",
                    "operating_income",
                    30 + index,
                ),
            ]
        )

    for index, period_end in enumerate(pd.date_range("2026-01-01", periods=4, freq="MS")):
        rows.append(
            _segment_row(
                period_end.date().isoformat(),
                "TSM",
                "monthly",
                "total",
                "monthly_revenue_yoy",
                20 + index * 5,
                period_type="month",
                unit="percent",
                currency=None,
            )
        )

    pd.DataFrame(rows).to_csv(path, index=False)


def _segment_row(
    period_end: str,
    ticker: str,
    kpi_group: str,
    segment_name: str,
    kpi_name: str,
    kpi_value: float,
    period_type: str = "quarter",
    unit: str = "USD_mn",
    currency: Optional[str] = "USD",
) -> dict:
    return {
        "period_end": period_end,
        "fiscal_year": int(period_end[:4]),
        "fiscal_quarter": "Q1",
        "period_type": period_type,
        "ticker": ticker,
        "kpi_group": kpi_group,
        "segment_name": segment_name,
        "kpi_name": kpi_name,
        "kpi_value": kpi_value,
        "unit": unit,
        "currency": currency,
        "source_type": "fixture",
        "source_url": "https://example.com",
        "is_reported": True,
        "is_derived": False,
        "confidence": "high",
    }
