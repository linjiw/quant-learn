"""Official SEC filing segment KPI extraction heuristics."""

import re
from io import BytesIO
from typing import Optional

import pandas as pd
import requests

from quant_learn.db import connect, initialize_database
from quant_learn.ingest.sec import sec_headers
from quant_learn.time import utc_now_naive

SEC_ARCHIVE_DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/{document}"

TICKER_CIK_INT = {
    "GOOGL": 1652044,
    "NVDA": 1045810,
    "AMD": 2488,
}

MONTH_RE = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}"
)

GOOGL_PRODUCT_REVENUE_LABELS = {
    "Google Search & other": ("Google Search & other", "revenue"),
    "YouTube ads": ("YouTube ads", "revenue"),
    "Google Network": ("Google Network", "revenue"),
    "Google subscriptions, platforms, and devices": (
        "Google subscriptions platforms and devices",
        "revenue",
    ),
    "Google Services total": ("Google Services", "revenue"),
    "Google Cloud": ("Google Cloud", "revenue"),
    "Other Bets": ("Other Bets", "revenue"),
}

GOOGL_OPERATING_LABELS = {
    "Google Services": ("Google Services", "operating_income"),
    "Google Cloud": ("Google Cloud", "operating_income"),
    "Other Bets": ("Other Bets", "operating_income"),
}

NVDA_REVENUE_LABELS = {
    "Data Center": ("Data Center", "revenue"),
    "Gaming": ("Gaming", "revenue"),
    "Professional Visualization": ("Professional Visualization", "revenue"),
    "Automotive": ("Automotive", "revenue"),
    "OEM and Other": ("OEM and Other", "revenue"),
    "Compute & Networking": ("Compute & Networking", "revenue"),
    "Graphics": ("Graphics", "revenue"),
}

AMD_REVENUE_LABELS = {
    "Data Center": ("Data Center", "revenue"),
    "Client": ("Client", "revenue"),
    "Gaming": ("Gaming", "revenue"),
    "Total Client and Gaming": ("Client and Gaming", "revenue"),
    "Embedded": ("Embedded", "revenue"),
}

AMD_COST_LABELS = {
    "Data Center": ("Data Center", "cost_and_operating_expenses"),
    "Client and Gaming": ("Client and Gaming", "cost_and_operating_expenses"),
    "Embedded": ("Embedded", "cost_and_operating_expenses"),
}

AMD_OPERATING_LABELS = {
    "Data Center": ("Data Center", "operating_income"),
    "Client": ("Client", "operating_income"),
    "Gaming": ("Gaming", "operating_income"),
    "Client and Gaming": ("Client and Gaming", "operating_income"),
    "Embedded": ("Embedded", "operating_income"),
}


def build_sec_segment_kpis(
    tickers: Optional[list[str]] = None,
    max_filings: int = 16,
) -> pd.DataFrame:
    """Extract segment KPIs from official SEC filing HTML tables."""

    initialize_database()
    ticker_list = tickers or ["GOOGL", "NVDA", "AMD"]
    rows: list[dict] = []
    with connect() as conn:
        for ticker in ticker_list:
            filings = conn.execute(
                """
                SELECT ticker, form, filing_date, report_date, accession_number,
                       primary_document, source_url
                FROM sec_filings
                WHERE ticker = ?
                  AND form IN ('10-Q', '10-K')
                  AND primary_document IS NOT NULL
                ORDER BY filing_date DESC
                LIMIT ?
                """,
                [ticker, max_filings],
            ).fetchdf()
            for _, filing in filings.iterrows():
                rows.extend(_extract_filing_segment_kpis(filing))

    return pd.DataFrame(rows).drop_duplicates(subset=["segment_kpi_id"])


def _extract_filing_segment_kpis(filing: pd.Series) -> list[dict]:
    ticker = filing["ticker"]
    if ticker not in TICKER_CIK_INT:
        return []
    html = _fetch_filing_html(filing)
    if not html:
        return []

    try:
        tables = pd.read_html(BytesIO(html), flavor="lxml")
    except ValueError:
        return []

    rows: list[dict] = []
    for table in tables:
        period_columns = _period_columns(table)
        if not period_columns:
            continue
        period_end = _choose_period(period_columns, filing["report_date"])
        if period_end is None:
            continue
        columns = period_columns[period_end]
        if ticker == "GOOGL":
            rows.extend(_extract_googl_table(table, columns, period_end, filing))
        elif ticker == "NVDA":
            rows.extend(_extract_nvda_table(table, columns, period_end, filing))
        elif ticker == "AMD":
            rows.extend(_extract_amd_table(table, columns, period_end, filing))
    return rows


def _fetch_filing_html(filing: pd.Series) -> bytes:
    cik = TICKER_CIK_INT[filing["ticker"]]
    url = SEC_ARCHIVE_DOC.format(
        cik=cik,
        accession_no_dash=filing["accession_number"].replace("-", ""),
        document=filing["primary_document"],
    )
    response = requests.get(url, headers={**sec_headers(), "Host": "www.sec.gov"}, timeout=30)
    response.raise_for_status()
    return response.content


def _period_columns(table: pd.DataFrame) -> dict[pd.Timestamp, list[int]]:
    periods: dict[pd.Timestamp, list[int]] = {}
    header_rows = table.head(6).astype(str)
    for column_index, column in enumerate(table.columns):
        text = " ".join(str(value) for value in header_rows.iloc[:, column_index].tolist())
        match = re.search(MONTH_RE, text)
        if not match:
            continue
        period = pd.to_datetime(match.group(0).replace(",", ""), errors="coerce")
        if pd.isna(period):
            continue
        periods.setdefault(period.normalize(), []).append(column)
    return periods


def _choose_period(
    period_columns: dict[pd.Timestamp, list[int]],
    report_date: object,
) -> Optional[pd.Timestamp]:
    report = pd.to_datetime(report_date, errors="coerce")
    if pd.notna(report):
        for period in period_columns:
            if period.date() == report.date():
                return period
    return max(period_columns)


def _extract_googl_table(
    table: pd.DataFrame,
    columns: list[int],
    period_end: pd.Timestamp,
    filing: pd.Series,
) -> list[dict]:
    text = _table_text(table)
    rows: list[dict] = []
    if "Google Search & other" in text and "Total revenues" in text:
        for label, (segment_name, kpi_name) in GOOGL_PRODUCT_REVENUE_LABELS.items():
            value = _value_for_label(table, columns, label)
            if value is not None:
                rows.append(_kpi_row(filing, period_end, "segment", segment_name, kpi_name, value))

    if "Operating income (loss)" in text:
        marker_row = _first_label_index(table, "Operating income (loss)")
        for label, (segment_name, kpi_name) in GOOGL_OPERATING_LABELS.items():
            value = _value_for_label(table, columns, label, start_row=marker_row)
            if value is not None:
                rows.append(_kpi_row(filing, period_end, "segment", segment_name, kpi_name, value))
    return rows


def _extract_nvda_table(
    table: pd.DataFrame,
    columns: list[int],
    period_end: pd.Timestamp,
    filing: pd.Series,
) -> list[dict]:
    text = _table_text(table)
    if not any(label in text for label in NVDA_REVENUE_LABELS):
        return []

    rows = []
    for label, (segment_name, kpi_name) in NVDA_REVENUE_LABELS.items():
        value = _value_for_label(table, columns, label)
        if value is None:
            continue
        kpi_group = (
            "product_category"
            if label in {"Compute & Networking", "Graphics"}
            else "end_market"
        )
        rows.append(_kpi_row(filing, period_end, kpi_group, segment_name, kpi_name, value))
    return rows


def _extract_amd_table(
    table: pd.DataFrame,
    columns: list[int],
    period_end: pd.Timestamp,
    filing: pd.Series,
) -> list[dict]:
    text = _table_text(table)
    if "Net revenue:" not in text:
        return []
    if "Cost of sales and operating expenses:" not in text and "Operating income" not in text:
        return []

    rows = []
    revenue_marker = _first_label_index(table, "Net revenue:")
    cost_marker = _first_label_index(table, "Cost of sales and operating expenses:")
    operating_marker = _first_label_index(table, "Operating income")
    revenue_end = cost_marker if cost_marker is not None else operating_marker
    revenue_by_segment: dict[str, float] = {}
    cost_by_segment: dict[str, float] = {}

    for label, (segment_name, kpi_name) in AMD_REVENUE_LABELS.items():
        value = _value_for_label(
            table,
            columns,
            label,
            start_row=revenue_marker,
            end_row=revenue_end,
        )
        if value is None:
            continue
        revenue_by_segment[segment_name] = value
        rows.append(
            _kpi_row(filing, period_end, "reportable_segment", segment_name, kpi_name, value)
        )

    if cost_marker is not None:
        for label, (segment_name, kpi_name) in AMD_COST_LABELS.items():
            value = _value_for_label(table, columns, label, start_row=cost_marker)
            if value is None:
                continue
            cost_by_segment[segment_name] = value
            rows.append(
                _kpi_row(filing, period_end, "reportable_segment", segment_name, kpi_name, value)
            )

        for segment_name, revenue in revenue_by_segment.items():
            if segment_name not in cost_by_segment:
                continue
            rows.append(
                _kpi_row(
                    filing,
                    period_end,
                    "reportable_segment",
                    segment_name,
                    "operating_income",
                    revenue - cost_by_segment[segment_name],
                    is_reported=False,
                    is_derived=True,
                    derivation_method="revenue_minus_cost_and_operating_expenses",
                )
            )

    if operating_marker is not None:
        for label, (segment_name, kpi_name) in AMD_OPERATING_LABELS.items():
            value = _value_for_label(table, columns, label, start_row=operating_marker)
            if value is None:
                continue
            rows.append(
                _kpi_row(filing, period_end, "reportable_segment", segment_name, kpi_name, value)
            )
    return rows


def _kpi_row(
    filing: pd.Series,
    period_end: pd.Timestamp,
    kpi_group: str,
    segment_name: str,
    kpi_name: str,
    value: float,
    is_reported: bool = True,
    is_derived: bool = False,
    derivation_method: Optional[str] = None,
) -> dict:
    row = {
        "period_end": period_end.date(),
        "fiscal_year": int(period_end.year),
        "fiscal_quarter": _quarter_from_month(period_end.month),
        "period_type": "year" if filing["form"] == "10-K" else "quarter",
        "ticker": filing["ticker"],
        "kpi_group": kpi_group,
        "segment_name": segment_name,
        "kpi_name": kpi_name,
        "kpi_value": float(value),
        "unit": "USD_mn",
        "currency": "USD",
        "source_type": filing["form"],
        "source_url": filing["source_url"],
        "source_accession_number": filing["accession_number"],
        "filed_date": filing["filing_date"],
        "is_reported": is_reported,
        "is_derived": is_derived,
        "derivation_method": derivation_method,
        "confidence": "medium" if is_derived else "high",
        "notes": "Extracted from official SEC filing table.",
        "ingested_at": utc_now_naive(),
    }
    row["segment_kpi_id"] = _segment_kpi_id(row)
    return row


def _value_for_label(
    table: pd.DataFrame,
    columns: list[int],
    label: str,
    start_row: Optional[int] = None,
    end_row: Optional[int] = None,
) -> Optional[float]:
    start = 0 if start_row is None else start_row + 1
    end = len(table) if end_row is None else end_row
    for row_index in range(start, end):
        row = table.iloc[row_index]
        row_label = _clean_label(row.iloc[0])
        if row_label != label:
            continue
        for column in columns:
            value = _parse_number(row[column])
            if value is not None:
                return value
    return None


def _first_label_index(table: pd.DataFrame, label: str) -> Optional[int]:
    for index, row in table.iterrows():
        row_text = " ".join(_clean_label(value) for value in row.tolist())
        if label in row_text:
            return int(index)
    return None


def _table_text(table: pd.DataFrame) -> str:
    return " ".join(str(value) for value in table.astype(str).values.flatten())


def _clean_label(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _parse_number(value: object) -> Optional[float]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"$", "—", "-", "nan", "%"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )
    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    value_float = float(cleaned)
    return -value_float if negative else value_float


def _segment_kpi_id(row: dict) -> str:
    key = "|".join(
        str(row.get(column, ""))
        for column in (
            "ticker",
            "period_end",
            "period_type",
            "kpi_group",
            "segment_name",
            "kpi_name",
        )
    )
    import hashlib

    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"segment_kpi_{digest}"


def _quarter_from_month(month: int) -> str:
    return f"Q{((month - 1) // 3) + 1}"
