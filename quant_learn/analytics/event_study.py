"""Event-study utilities."""

from typing import Optional

import pandas as pd

from quant_learn.db import connect, initialize_database


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


def _nearest_trading_index(trading_dates, event_date: pd.Timestamp) -> Optional[int]:
    for index, trading_date in enumerate(trading_dates):
        if trading_date >= event_date:
            return index
    return None
