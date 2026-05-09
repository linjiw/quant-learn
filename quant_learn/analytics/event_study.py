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
) -> pd.DataFrame:
    """Build event-level CAR windows for research attribution."""

    initialize_database()
    with connect() as conn:
        events_query = "SELECT * FROM events"
        params = []
        if event_type:
            events_query += " WHERE event_type = ?"
            params.append(event_type)
        events_query += " ORDER BY event_date, ticker"
        events = conn.execute(events_query, params).fetchdf()

        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            WHERE ticker IN (
                SELECT DISTINCT ticker FROM events
            )
            OR ticker IN (?, ?)
            ORDER BY date, ticker
            """,
            [benchmark, sector_benchmark],
        ).fetchdf()

    if events.empty or prices.empty:
        return pd.DataFrame()

    events["event_date"] = pd.to_datetime(events["event_date"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices["price"] = prices["adj_close"].fillna(prices["close"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    trading_dates = list(price.index)
    ingested_at = utc_now_naive()

    rows = []
    for _, event in events.iterrows():
        ticker = event["ticker"]
        if ticker not in price.columns:
            continue
        anchor_index = _nearest_trading_index(trading_dates, event["event_date"])
        if anchor_index is None:
            continue

        return_0_p5 = _window_return(price, ticker, anchor_index, 0, 5)
        benchmark_return_0_p5 = _window_return(price, benchmark, anchor_index, 0, 5)
        sector_return_0_p5 = _window_return(price, sector_benchmark, anchor_index, 0, 5)

        rows.append(
            {
                "event_id": event["event_id"],
                "event_date": event["event_date"].date(),
                "ticker": ticker,
                "event_type": event["event_type"],
                "benchmark": benchmark,
                "sector_benchmark": sector_benchmark,
                "return_m1_p1": _window_return(price, ticker, anchor_index, -1, 1),
                "return_0_p1": _window_return(price, ticker, anchor_index, 0, 1),
                "return_0_p5": return_0_p5,
                "return_0_p20": _window_return(price, ticker, anchor_index, 0, 20),
                "benchmark_return_0_p5": benchmark_return_0_p5,
                "sector_return_0_p5": sector_return_0_p5,
                "abnormal_return_0_p5": _difference(return_0_p5, benchmark_return_0_p5),
                "sector_abnormal_return_0_p5": _difference(return_0_p5, sector_return_0_p5),
                "pre_event_runup_20d": _window_return(price, ticker, anchor_index, -20, 0),
                "post_event_drift_20d": _window_return(price, ticker, anchor_index, 1, 20),
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
            ["event_id", "benchmark", "sector_benchmark"],
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
    if ticker not in price.columns:
        return None

    start_index = anchor_index + start_offset
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
