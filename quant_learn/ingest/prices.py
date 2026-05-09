"""Price ingestion from Yahoo Finance via yfinance."""

from collections.abc import Iterable
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf

from quant_learn.analytics.price_features import update_price_return_columns
from quant_learn.config import DEFAULT_PRICE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

PRICE_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}


def normalize_prices(downloaded: pd.DataFrame, tickers: Iterable[str]) -> pd.DataFrame:
    """Normalize yfinance output into the project prices schema."""

    frames: list[pd.DataFrame] = []
    ticker_list = list(tickers)

    if downloaded.empty:
        return pd.DataFrame()

    if isinstance(downloaded.columns, pd.MultiIndex):
        first_level_values = set(downloaded.columns.get_level_values(0))
        for ticker in ticker_list:
            if ticker in first_level_values:
                ticker_frame = downloaded[ticker].copy()
            else:
                continue
            frames.append(_normalize_single_ticker(ticker_frame, ticker))
    else:
        if len(ticker_list) != 1:
            raise ValueError("Single-index yfinance frame received for multiple tickers.")
        frames.append(_normalize_single_ticker(downloaded.copy(), ticker_list[0]))

    if not frames:
        return pd.DataFrame()

    prices = pd.concat(frames, ignore_index=True)
    prices = prices.dropna(subset=["date", "ticker", "close"])
    prices["ingested_at"] = utc_now_naive()
    return prices[
        [
            "date",
            "ticker",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "source",
            "ingested_at",
        ]
    ]


def _normalize_single_ticker(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    frame = frame.reset_index()
    date_column = "Date" if "Date" in frame.columns else "Datetime"
    frame = frame.rename(columns={date_column: "date", **PRICE_COLUMNS})

    for column in PRICE_COLUMNS.values():
        if column not in frame.columns:
            frame[column] = pd.NA

    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["ticker"] = ticker
    frame["source"] = "yfinance"
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype("int64")
    return frame


def ingest_prices(
    tickers: Optional[Iterable[str]] = None,
    start: str = "2018-01-01",
    end: Optional[str] = None,
) -> int:
    """Download and store adjusted daily prices."""

    ticker_list = list(tickers or DEFAULT_PRICE_TICKERS)
    downloaded = yf.download(
        tickers=ticker_list,
        start=start,
        end=end,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    prices = normalize_prices(downloaded, ticker_list)
    initialize_database()
    with connect() as conn:
        count = upsert_dataframe(conn, prices, "prices", ["date", "ticker"])
    update_price_return_columns()
    return count


def latest_price_date() -> Optional[date]:
    """Return the latest stored price date."""

    initialize_database()
    with connect() as conn:
        result = conn.execute("SELECT max(date) FROM prices").fetchone()
        return result[0] if result else None
