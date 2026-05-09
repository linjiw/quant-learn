"""Derived price-return features stored back onto the prices table."""

import pandas as pd

from quant_learn.db import connect, initialize_database


def update_price_return_columns() -> int:
    """Compute return_1d/5d/20d/60d for every stored ticker."""

    initialize_database()
    with connect() as conn:
        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            ORDER BY ticker, date
            """
        ).fetchdf()

        if prices.empty:
            return 0

        prices["date"] = pd.to_datetime(prices["date"]).dt.date
        prices["price"] = prices["adj_close"].fillna(prices["close"])
        prices = prices.sort_values(["ticker", "date"])
        grouped = prices.groupby("ticker")["price"]
        returns = prices[["date", "ticker"]].copy()
        returns["return_1d"] = grouped.pct_change(1)
        returns["return_5d"] = grouped.pct_change(5)
        returns["return_20d"] = grouped.pct_change(20)
        returns["return_60d"] = grouped.pct_change(60)

        conn.register("_price_returns", returns)
        conn.execute(
            """
            UPDATE prices
            SET
                return_1d = _price_returns.return_1d,
                return_5d = _price_returns.return_5d,
                return_20d = _price_returns.return_20d,
                return_60d = _price_returns.return_60d
            FROM _price_returns
            WHERE prices.date = _price_returns.date
              AND prices.ticker = _price_returns.ticker
            """
        )
        conn.unregister("_price_returns")
        return len(returns)
