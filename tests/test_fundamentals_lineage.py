from pathlib import Path

import duckdb
import pandas as pd

from quant_learn.analytics import fundamentals, segments
from quant_learn.db import initialize_database


def test_cash_flow_ytd_to_quarterly_and_lineage(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "fundamentals.duckdb"
    _patch_fundamentals_db(monkeypatch, db_path)
    _load_sec_fact_fixture(db_path)

    normalized = fundamentals.build_fundamentals_quarterly_normalized()

    rows = _by_quarter(normalized)
    q2 = rows["Q2"]
    q3 = rows["Q3"]
    q4 = rows["Q4"]

    assert q2["operating_cash_flow_quarterly"] == 150.0
    assert q2["capex_ytd"] == 70.0
    assert q2["capex_quarterly"] == 50.0
    assert q2["free_cash_flow_quarterly"] == 100.0
    assert q2["is_quarterly_derived"] is True
    assert "ytd_difference" in q2["derivation_method"]

    assert q3["operating_cash_flow_quarterly"] == 200.0
    assert q3["capex_quarterly"] == 60.0
    assert q3["free_cash_flow_quarterly"] == 140.0

    assert q4["revenue"] == 1300.0
    assert q4["operating_cash_flow_quarterly"] == 250.0
    assert q4["capex_quarterly"] == 90.0
    assert q4["free_cash_flow_quarterly"] == 160.0
    assert q4["available_date"] == pd.Timestamp("2027-02-01").date()
    assert q4["filed_date"] == pd.Timestamp("2027-02-01").date()
    assert q4["source_accession_number"] == "acc-fy"
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in q4["source_xbrl_tags"]
    assert q4["source_fact_keys"]


def test_quarterly_values_not_fabricated_without_prior_ytd(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "fundamentals_missing_prior.duckdb"
    _patch_fundamentals_db(monkeypatch, db_path)
    _insert_filing(db_path, "acc-fy", "10-K", "2027-02-01", "2026-12-31", "FY")
    _insert_fact(
        db_path,
        "acc-fy",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        4600.0,
        "2026-01-01",
        "2026-12-31",
        "FY",
    )
    _insert_fact(
        db_path,
        "acc-fy",
        "NetCashProvidedByUsedInOperatingActivities",
        700.0,
        "2026-01-01",
        "2026-12-31",
        "FY",
    )
    _insert_fact(
        db_path,
        "acc-fy",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        -220.0,
        "2026-01-01",
        "2026-12-31",
        "FY",
    )

    normalized = fundamentals.build_fundamentals_quarterly_normalized()
    q4 = _by_quarter(normalized)["Q4"]

    assert pd.isna(q4["revenue"])
    assert pd.isna(q4["operating_cash_flow_quarterly"])
    assert pd.isna(q4["capex_quarterly"])
    assert pd.isna(q4["free_cash_flow_quarterly"])
    assert "revenue_q4_missing_prior_quarters" in q4["derivation_method"]
    assert "operating_cash_flow_quarterly_missing_prior_ytd" in q4["derivation_method"]


def test_cash_flow_features_have_source_fundamental_ids(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cash_flow_features.duckdb"
    _patch_fundamentals_db(monkeypatch, db_path)
    _load_sec_fact_fixture(db_path)

    normalized = fundamentals.build_fundamentals_quarterly_normalized()
    fundamentals.store_fundamentals_quarterly_normalized(normalized)
    features = fundamentals.build_cash_flow_features()

    assert {"capex_to_ocf", "fcf_margin"}.issubset(set(features["feature_name"]))
    assert features["source_fundamental_ids"].str.startswith("fundamental_").all()
    latest = features[features["feature_name"] == "capex_to_ocf"].iloc[0]
    assert latest["feature_value"] == 90.0 / 250.0
    assert latest["direction"] == "neutral"


def test_company_segment_kpis_prefer_normalized_pit_fundamentals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "company_bridge.duckdb"
    _patch_fundamentals_db(monkeypatch, db_path)
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))
    _load_sec_fact_fixture(db_path)

    normalized = fundamentals.build_fundamentals_quarterly_normalized()
    fundamentals.store_fundamentals_quarterly_normalized(normalized)
    company_kpis = segments.build_company_segment_kpis(tickers=["AMD"], quarters=1)

    assert set(company_kpis["source_type"]) == {"fundamentals_quarterly_normalized"}
    assert set(company_kpis["confidence"]).issubset({"medium", "high"})
    assert "capex_to_ocf" in set(company_kpis["kpi_name"])
    capex_to_ocf = company_kpis[company_kpis["kpi_name"] == "capex_to_ocf"].iloc[0]
    assert pd.to_datetime(capex_to_ocf["filed_date"]).date() == pd.Timestamp(
        "2027-02-01"
    ).date()
    assert capex_to_ocf["kpi_value"] == 90.0 / 250.0


def test_segment_features_do_not_fabricate_inventory_or_guidance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "no_fake_inventory.duckdb"
    _patch_fundamentals_db(monkeypatch, db_path)
    monkeypatch.setattr(segments, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(segments, "initialize_database", lambda: initialize_database(db_path))
    _load_sec_fact_fixture(db_path)

    normalized = fundamentals.build_fundamentals_quarterly_normalized()
    fundamentals.store_fundamentals_quarterly_normalized(normalized)
    segments.store_segment_kpis(segments.build_company_segment_kpis(tickers=["AMD"], quarters=4))
    feature_names = set(segments.build_segment_features()["feature_name"])

    assert "inventory_risk_score" not in feature_names
    assert "guidance_strength_score" not in feature_names


def _patch_fundamentals_db(monkeypatch, db_path: Path) -> None:
    initialize_database(db_path)
    monkeypatch.setattr(fundamentals, "connect", lambda: duckdb.connect(str(db_path)))
    monkeypatch.setattr(fundamentals, "initialize_database", lambda: initialize_database(db_path))


def _load_sec_fact_fixture(db_path: Path) -> None:
    for accession, form_type, filing_date, report_date, fiscal_period in (
        ("acc-q1", "10-Q", "2026-05-01", "2026-03-31", "Q1"),
        ("acc-q2", "10-Q", "2026-08-01", "2026-06-30", "Q2"),
        ("acc-q3", "10-Q", "2026-11-01", "2026-09-30", "Q3"),
        ("acc-fy", "10-K", "2027-02-01", "2026-12-31", "FY"),
    ):
        _insert_filing(db_path, accession, form_type, filing_date, report_date, fiscal_period)

    income_rows = (
        ("acc-q1", "Q1", "2026-01-01", "2026-03-31", 1000.0, 500.0, 250.0),
        ("acc-q2", "Q2", "2026-04-01", "2026-06-30", 1100.0, 550.0, 275.0),
        ("acc-q3", "Q3", "2026-07-01", "2026-09-30", 1200.0, 600.0, 300.0),
        ("acc-fy", "FY", "2026-01-01", "2026-12-31", 4600.0, 2300.0, 1150.0),
    )
    for (
        accession,
        fiscal_period,
        period_start,
        period_end,
        revenue,
        gross_profit,
        operating_income,
    ) in income_rows:
        _insert_fact(
            db_path,
            accession,
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            revenue,
            period_start,
            period_end,
            fiscal_period,
        )
        _insert_fact(
            db_path,
            accession,
            "GrossProfit",
            gross_profit,
            period_start,
            period_end,
            fiscal_period,
        )
        _insert_fact(
            db_path,
            accession,
            "OperatingIncomeLoss",
            operating_income,
            period_start,
            period_end,
            fiscal_period,
        )

    for accession, fiscal_period, period_end, ocf_ytd, capex_ytd in (
        ("acc-q1", "Q1", "2026-03-31", 100.0, -20.0),
        ("acc-q2", "Q2", "2026-06-30", 250.0, -70.0),
        ("acc-q3", "Q3", "2026-09-30", 450.0, -130.0),
        ("acc-fy", "FY", "2026-12-31", 700.0, -220.0),
    ):
        _insert_fact(
            db_path,
            accession,
            "NetCashProvidedByUsedInOperatingActivities",
            ocf_ytd,
            "2026-01-01",
            period_end,
            fiscal_period,
        )
        _insert_fact(
            db_path,
            accession,
            "PaymentsToAcquirePropertyPlantAndEquipment",
            capex_ytd,
            "2026-01-01",
            period_end,
            fiscal_period,
        )


def _insert_filing(
    db_path: Path,
    accession: str,
    form_type: str,
    filing_date: str,
    report_date: str,
    fiscal_period: str,
) -> None:
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO sec_filings (
                ticker, cik, accession_number, form, filing_date, report_date,
                primary_document, primary_doc_description, source_url, ingested_at
            )
            VALUES ('AMD', '0000002488', ?, ?, ?, ?, 'fixture.htm', ?, ?, ?)
            """,
            [
                accession,
                form_type,
                filing_date,
                report_date,
                fiscal_period,
                f"https://example.com/{accession}",
                pd.Timestamp("2027-02-01"),
            ],
        )


def _insert_fact(
    db_path: Path,
    accession: str,
    concept: str,
    value: float,
    start_date: str,
    end_date: str,
    fiscal_period: str,
) -> None:
    with duckdb.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO sec_facts (
                ticker, cik, taxonomy, concept, unit, fiscal_year, fiscal_period,
                form, filed_date, start_date, end_date, frame, accession_number,
                value, source_url, ingested_at
            )
            VALUES (
                'AMD', '0000002488', 'us-gaap', ?, 'USD', 2026, ?, ?,
                ?, ?, ?, NULL, ?, ?, ?, ?
            )
            """,
            [
                concept,
                fiscal_period,
                "10-K" if fiscal_period == "FY" else "10-Q",
                _filed_date_for_accession(accession),
                start_date,
                end_date,
                accession,
                value,
                f"https://example.com/{accession}",
                pd.Timestamp("2027-02-01"),
            ],
        )


def _filed_date_for_accession(accession: str) -> str:
    return {
        "acc-q1": "2026-05-01",
        "acc-q2": "2026-08-01",
        "acc-q3": "2026-11-01",
        "acc-fy": "2027-02-01",
    }[accession]


def _by_quarter(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        row["fiscal_quarter"]: row
        for _, row in df.sort_values("fiscal_quarter").iterrows()
    }
