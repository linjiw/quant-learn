"""SEC EDGAR ingestion."""

import os
from collections.abc import Iterable
from typing import Optional

import pandas as pd
import requests

from quant_learn.config import SEC_CIKS, SELECTED_SEC_CONCEPTS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"


def sec_headers() -> dict[str, str]:
    """Return SEC-compliant headers."""

    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        user_agent = "quant-learn/0.1 research contact@example.com"
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers=sec_headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def flatten_company_facts(
    ticker: str,
    cik: str,
    payload: dict,
    selected_concepts: Optional[dict[str, set[str]]] = None,
) -> pd.DataFrame:
    """Flatten SEC companyfacts JSON into one row per reported fact."""

    rows: list[dict] = []
    facts = payload.get("facts", {})
    selected = selected_concepts or SELECTED_SEC_CONCEPTS
    ingested_at = utc_now_naive()
    source_url = SEC_COMPANY_FACTS_URL.format(cik=cik)

    for taxonomy, concepts in facts.items():
        allowed = selected.get(taxonomy)
        for concept, concept_payload in concepts.items():
            if allowed is not None and concept not in allowed:
                continue
            units = concept_payload.get("units", {})
            for unit, observations in units.items():
                for observation in observations:
                    rows.append(
                        {
                            "ticker": ticker,
                            "cik": cik,
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "unit": unit,
                            "fiscal_year": observation.get("fy"),
                            "fiscal_period": observation.get("fp"),
                            "form": observation.get("form"),
                            "filed_date": observation.get("filed"),
                            "start_date": observation.get("start"),
                            "end_date": observation.get("end"),
                            "frame": observation.get("frame"),
                            "accession_number": observation.get("accn"),
                            "value": observation.get("val"),
                            "source_url": source_url,
                            "ingested_at": ingested_at,
                        }
                    )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for column in ("filed_date", "start_date", "end_date"):
        df[column] = pd.to_datetime(df[column], errors="coerce").dt.date
    df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def flatten_submissions(ticker: str, cik: str, payload: dict) -> pd.DataFrame:
    """Flatten the recent filings section of SEC submissions JSON."""

    recent = payload.get("filings", {}).get("recent", {})
    if not recent:
        return pd.DataFrame()

    rows: list[dict] = []
    ingested_at = utc_now_naive()
    accession_numbers = recent.get("accessionNumber", [])
    for index, accession_number in enumerate(accession_numbers):
        no_dash = accession_number.replace("-", "")
        source_url = f"{SEC_ARCHIVE_BASE}/{int(cik)}/{no_dash}/{accession_number}-index.html"
        rows.append(
            {
                "ticker": ticker,
                "cik": cik,
                "accession_number": accession_number,
                "form": _list_get(recent.get("form", []), index),
                "filing_date": _list_get(recent.get("filingDate", []), index),
                "report_date": _list_get(recent.get("reportDate", []), index),
                "primary_document": _list_get(recent.get("primaryDocument", []), index),
                "primary_doc_description": _list_get(
                    recent.get("primaryDocDescription", []), index
                ),
                "source_url": source_url,
                "ingested_at": ingested_at,
            }
        )

    df = pd.DataFrame(rows)
    for column in ("filing_date", "report_date"):
        df[column] = pd.to_datetime(df[column], errors="coerce").dt.date
    return df


def _list_get(values: list, index: int):
    return values[index] if index < len(values) else None


def ingest_sec(tickers: Optional[Iterable[str]] = None) -> dict[str, int]:
    """Fetch SEC filings and selected company facts for the configured universe."""

    initialize_database()
    counts = {"sec_filings": 0, "sec_facts": 0}
    ticker_list = list(tickers or SEC_CIKS.keys())

    with connect() as conn:
        for ticker in ticker_list:
            cik = SEC_CIKS[ticker]
            submissions = flatten_submissions(
                ticker, cik, fetch_json(SEC_SUBMISSIONS_URL.format(cik=cik))
            )
            counts["sec_filings"] += upsert_dataframe(
                conn, submissions, "sec_filings", ["ticker", "accession_number"]
            )

            facts = flatten_company_facts(
                ticker, cik, fetch_json(SEC_COMPANY_FACTS_URL.format(cik=cik))
            )
            counts["sec_facts"] += upsert_dataframe(
                conn,
                facts,
                "sec_facts",
                [
                    "ticker",
                    "taxonomy",
                    "concept",
                    "unit",
                    "fiscal_year",
                    "fiscal_period",
                    "form",
                    "filed_date",
                    "start_date",
                    "end_date",
                    "accession_number",
                    "value",
                ],
            )
    return counts
