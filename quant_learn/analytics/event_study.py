"""Event-study utilities."""

from typing import Optional

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def run_event_study(
    event_type: str,
    window_before: int = 5,
    window_after: int = 20,
    benchmark: str = "QQQ",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """Compute event-window raw and abnormal returns for stored events."""

    initialize_database()
    with connect() as conn:
        events_query = """
            SELECT *
            FROM events
            WHERE event_type = ?
        """
        params = [event_type]
        if start_date:
            events_query += " AND event_date >= ?"
            params.append(start_date)
        if end_date:
            events_query += " AND event_date <= ?"
            params.append(end_date)
        events_query += " ORDER BY event_date, ticker"
        events = conn.execute(events_query, params).fetchdf()

        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            WHERE ticker IN (
                SELECT DISTINCT ticker FROM events WHERE event_type = ?
            )
            OR ticker = ?
            ORDER BY date, ticker
            """,
            [event_type, benchmark],
        ).fetchdf()

    if events.empty or prices.empty:
        return pd.DataFrame()

    events["event_date"] = pd.to_datetime(events["event_date"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices["price"] = prices["adj_close"].fillna(prices["close"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    returns = price.pct_change()

    rows = []
    trading_dates = list(price.index)
    for _, event in events.iterrows():
        ticker = event["ticker"]
        if ticker not in price.columns or benchmark not in price.columns:
            continue
        anchor_index = _nearest_trading_index(trading_dates, event["event_date"])
        if anchor_index is None:
            continue
        start_index = max(0, anchor_index - window_before)
        end_index = min(len(trading_dates) - 1, anchor_index + window_after)
        window_dates = trading_dates[start_index : end_index + 1]

        cumulative_stock = 1.0
        cumulative_benchmark = 1.0
        for trading_date in window_dates:
            rel_day = trading_dates.index(trading_date) - anchor_index
            stock_return = returns.loc[trading_date, ticker]
            benchmark_return = returns.loc[trading_date, benchmark]
            if pd.notna(stock_return):
                cumulative_stock *= 1.0 + stock_return
            if pd.notna(benchmark_return):
                cumulative_benchmark *= 1.0 + benchmark_return
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_date": event["event_date"].date(),
                    "ticker": ticker,
                    "event_type": event["event_type"],
                    "event_description": event["event_description"],
                    "trading_date": trading_date.date(),
                    "relative_day": rel_day,
                    "stock_return": stock_return,
                    "benchmark": benchmark,
                    "benchmark_return": benchmark_return,
                    "abnormal_return": stock_return - benchmark_return,
                    "cumulative_stock_return": cumulative_stock - 1.0,
                    "cumulative_benchmark_return": cumulative_benchmark - 1.0,
                    "cumulative_abnormal_return": cumulative_stock - cumulative_benchmark,
                    "surprise_pct": event["surprise_pct"],
                }
            )

    return pd.DataFrame(rows)


def build_event_returns(
    event_type: Optional[str] = None,
    benchmark: str = "QQQ",
    sector_benchmark: str = "SOXX",
    benchmark_tickers: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Build long-format event CAR windows for research attribution."""

    initialize_database()
    benchmarks = _dedupe_benchmarks(benchmark_tickers or [benchmark, sector_benchmark, "SMH"])
    with connect() as conn:
        events_query = """
            SELECT
                e.event_id,
                e.event_date,
                COALESCE(e.reaction_date, e.event_date) AS reaction_date,
                e.event_type,
                COALESCE(i.affected_ticker, e.primary_ticker, e.ticker) AS affected_ticker
            FROM events e
            LEFT JOIN event_impacts i
                ON e.event_id = i.event_id
        """
        params = []
        if event_type:
            events_query += " WHERE e.event_type = ?"
            params.append(event_type)
        events_query += " ORDER BY e.event_date, e.event_id, affected_ticker"
        events = conn.execute(events_query, params).fetchdf()

        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            ORDER BY date, ticker
            """
        ).fetchdf()

    if events.empty or prices.empty:
        return pd.DataFrame()

    events["event_date"] = pd.to_datetime(events["event_date"])
    events["reaction_date"] = pd.to_datetime(events["reaction_date"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices["price"] = prices["adj_close"].fillna(prices["close"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    trading_dates = list(price.index)
    ingested_at = utc_now_naive()
    window_specs = {
        "m1_p1": (-1, 1),
        "0_p1": (0, 1),
        "0_p5": (0, 5),
        "0_p20": (0, 20),
        "pre_20_m1": (-20, -1),
        "post_1_p20": (1, 20),
    }

    rows = []
    for _, event in events.iterrows():
        ticker = event["affected_ticker"]
        if ticker not in price.columns:
            continue
        anchor_index = _nearest_trading_index(trading_dates, event["reaction_date"])
        if anchor_index is None:
            continue

        for window_name, (start_day, end_day) in window_specs.items():
            raw_return = _event_window_return(price, ticker, anchor_index, start_day, end_day)
            for benchmark_ticker in benchmarks:
                if benchmark_ticker not in price.columns:
                    continue
                benchmark_return = _event_window_return(
                    price,
                    benchmark_ticker,
                    anchor_index,
                    start_day,
                    end_day,
                )
                rows.append(
                    {
                        "event_id": event["event_id"],
                        "event_date": event["event_date"].date(),
                        "reaction_date": event["reaction_date"].date(),
                        "affected_ticker": ticker,
                        "event_type": event["event_type"],
                        "return_window": window_name,
                        "raw_return": raw_return,
                        "benchmark_type": _benchmark_type(benchmark_ticker),
                        "benchmark_ticker": benchmark_ticker,
                        "benchmark_return": benchmark_return,
                        "abnormal_return": _difference(raw_return, benchmark_return),
                        "model_name": "raw_vs_benchmark",
                        "ingested_at": ingested_at,
                    }
                )

    return pd.DataFrame(rows)


def store_event_returns(event_returns: pd.DataFrame) -> int:
    """Store event_returns rows."""

    if event_returns.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(
            conn,
            event_returns,
            "event_returns",
            [
                "event_id",
                "affected_ticker",
                "return_window",
                "benchmark_type",
                "benchmark_ticker",
                "model_name",
            ],
        )


def _nearest_trading_index(trading_dates, event_date: pd.Timestamp) -> Optional[int]:
    for index, trading_date in enumerate(trading_dates):
        if trading_date >= event_date:
            return index
    return None


def _window_return(
    price: pd.DataFrame,
    ticker: str,
    anchor_index: int,
    start_offset: int,
    end_offset: int,
) -> Optional[float]:
    return _event_window_return(price, ticker, anchor_index, start_offset, end_offset)


def _event_window_return(
    price: pd.DataFrame,
    ticker: str,
    anchor_index: int,
    start_offset: int,
    end_offset: int,
) -> Optional[float]:
    """Return inclusive close-to-close event window return.

    A window of 0_p1 includes the reaction-day close-to-close return and the
    next trading day's close-to-close return, so its start price is the close
    immediately before day 0.
    """

    if ticker not in price.columns:
        return None

    start_index = anchor_index + start_offset - 1
    end_index = anchor_index + end_offset
    if start_index < 0 or end_index >= len(price.index):
        return None

    start_price = price.iloc[start_index][ticker]
    end_price = price.iloc[end_index][ticker]
    if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
        return None
    return float(end_price / start_price - 1.0)


def _difference(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None
    return left - right


def _dedupe_benchmarks(benchmarks: list[str]) -> list[str]:
    deduped = []
    for ticker in benchmarks:
        if ticker and ticker not in deduped:
            deduped.append(ticker)
    return deduped


def _benchmark_type(ticker: str) -> str:
    if ticker in {"QQQ", "SPY"}:
        return "market"
    if ticker in {"SOXX", "SMH"}:
        return "sector"
    return "benchmark"
