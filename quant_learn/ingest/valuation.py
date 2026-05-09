"""Current valuation snapshot ingestion from yfinance.

These fields are useful for a first-pass valuation discipline check, but provider
normalization can be noisy for ADRs and non-US issuers. Treat the table as a
screening input, not a source-of-truth valuation model.
"""

from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def fetch_valuation_snapshot(tickers: Optional[list[str]] = None) -> pd.DataFrame:
    """Fetch current valuation fields for a ticker list."""

    ticker_list = tickers or CORE_TICKERS
    rows = []
    snapshot_date = date.today()
    ingested_at = utc_now_naive()

    for ticker in ticker_list:
        info = yf.Ticker(ticker).get_info()
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "ticker": ticker,
                "price": _number(info.get("currentPrice") or info.get("regularMarketPrice")),
                "market_cap": _number(info.get("marketCap")),
                "enterprise_value": _number(info.get("enterpriseValue")),
                "trailing_pe": _number(info.get("trailingPE")),
                "forward_pe": _number(info.get("forwardPE")),
                "price_to_sales": _number(info.get("priceToSalesTrailing12Months")),
                "price_to_book": _number(info.get("priceToBook")),
                "ev_to_ebitda": _number(info.get("enterpriseToEbitda")),
                "trailing_eps": _number(info.get("trailingEps")),
                "forward_eps": _number(info.get("forwardEps")),
                "dividend_yield": _number(info.get("dividendYield")),
                "beta": _number(info.get("beta")),
                "source": "yfinance",
                "ingested_at": ingested_at,
            }
        )

    return pd.DataFrame(rows)


def ingest_valuation_snapshot(tickers: Optional[list[str]] = None) -> int:
    """Fetch and store the current valuation snapshot."""

    snapshot = fetch_valuation_snapshot(tickers)
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(
            conn,
            snapshot,
            "valuation_snapshots",
            ["snapshot_date", "ticker", "source"],
        )


def _number(value) -> Optional[float]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
