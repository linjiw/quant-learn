"""TSMC monthly revenue ingestion from the official investor relations page."""

from collections.abc import Iterable
from io import StringIO
from typing import Optional

import pandas as pd
import requests

from quant_learn.config import TSMC_MONTHLY_REVENUE_URL
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

MONTH_MAP = {
    "Jan.": 1,
    "Feb.": 2,
    "Mar.": 3,
    "Apr.": 4,
    "May": 5,
    "Jun.": 6,
    "Jul.": 7,
    "Aug.": 8,
    "Sep.": 9,
    "Sept.": 9,
    "Oct.": 10,
    "Nov.": 11,
    "Dec.": 12,
}


def fetch_tsmc_monthly_revenue(year: int) -> pd.DataFrame:
    """Fetch one year of TSMC monthly revenue from the official page."""

    source_url = TSMC_MONTHLY_REVENUE_URL.format(year=year)
    response = requests.get(source_url, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    parsed_tables = [_parse_revenue_table(table, year, source_url) for table in tables]
    parsed_tables = [table for table in parsed_tables if not table.empty]
    if not parsed_tables:
        return pd.DataFrame()

    result = pd.concat(parsed_tables, ignore_index=True).drop_duplicates(subset=["period"])
    result["ingested_at"] = utc_now_naive()
    return result[
        [
            "period",
            "year",
            "month",
            "revenue_ntd_million",
            "mom_pct",
            "yoy_pct",
            "source_url",
            "ingested_at",
        ]
    ]


def _parse_revenue_table(table: pd.DataFrame, year: int, source_url: str) -> pd.DataFrame:
    columns = [_flatten_column(column) for column in table.columns]
    normalized = table.copy()
    normalized.columns = columns

    month_column = _find_column(columns, ["Month"])
    revenue_column = _find_column(columns, ["Net Revenue", "NetRevenue", "Revenue"])
    mom_column = _find_column(columns, ["M-o-M", "MoM"])
    yoy_column = _find_column(columns, ["Y-o-Y", "YoY"])

    if not month_column or not revenue_column:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, row in normalized.iterrows():
        month_raw = str(row.get(month_column, "")).strip()
        month = MONTH_MAP.get(month_raw)
        if month is None:
            continue
        rows.append(
            {
                "period": pd.Timestamp(year=year, month=month, day=1).date(),
                "year": year,
                "month": month,
                "revenue_ntd_million": _to_number(row.get(revenue_column)),
                "mom_pct": _to_number(row.get(mom_column)) if mom_column else None,
                "yoy_pct": _to_number(row.get(yoy_column)) if yoy_column else None,
                "source_url": source_url,
            }
        )
    parsed = pd.DataFrame(rows)
    if parsed.empty:
        return parsed
    return parsed.dropna(subset=["revenue_ntd_million"])


def _flatten_column(column) -> str:
    if isinstance(column, tuple):
        return " ".join([str(part).strip() for part in column if str(part) != "nan"]).strip()
    return str(column).strip()


def _find_column(columns: list[str], candidates: list[str]) -> Optional[str]:
    for column in columns:
        clean = column.lower().replace(" ", "").replace("-", "")
        for candidate in candidates:
            if candidate.lower().replace(" ", "").replace("-", "") in clean:
                return column
    return None


def _to_number(value) -> Optional[float]:
    if pd.isna(value):
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text or text == "-":
        return None
    return float(text)


def ingest_tsmc_monthly_revenue(years: Iterable[int]) -> int:
    """Fetch and store TSMC monthly revenue for one or more years."""

    frames = [fetch_tsmc_monthly_revenue(year) for year in years]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return 0

    revenue = pd.concat(frames, ignore_index=True)
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, revenue, "tsmc_monthly_revenue", ["period"])
