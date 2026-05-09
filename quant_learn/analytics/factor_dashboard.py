"""Factor dashboard calculations."""

from collections.abc import Iterable
from typing import Optional

import numpy as np
import pandas as pd

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive


def build_factor_dashboard(tickers: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """Build daily factor dashboard metrics from stored prices."""

    ticker_list = list(tickers or CORE_TICKERS)
    initialize_database()
    with connect() as conn:
        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close, volume
            FROM prices
            WHERE ticker IN (
                SELECT unnest(?)
            )
            OR ticker IN ('QQQ', 'SOXX')
            ORDER BY date, ticker
            """,
            [ticker_list],
        ).fetchdf()

    if prices.empty:
        return pd.DataFrame()

    prices["date"] = pd.to_datetime(prices["date"])
    prices["price"] = prices["adj_close"].fillna(prices["close"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    volume = prices.pivot(index="date", columns="ticker", values="volume").sort_index()
    returns = price.pct_change()

    rows: list[pd.DataFrame] = []
    ingested_at = utc_now_naive()
    for ticker in ticker_list:
        if ticker not in price.columns:
            continue
        frame = pd.DataFrame(index=price.index)
        frame["date"] = frame.index.date
        frame["ticker"] = ticker
        frame["return_20d"] = price[ticker].pct_change(20)
        frame["return_60d"] = price[ticker].pct_change(60)
        frame["return_120d"] = price[ticker].pct_change(120)
        frame["rel_qqq_60d"] = frame["return_60d"] - price["QQQ"].pct_change(60)
        frame["rel_soxx_60d"] = frame["return_60d"] - price["SOXX"].pct_change(60)
        frame["realized_vol_20d"] = returns[ticker].rolling(20).std() * np.sqrt(252)
        frame["realized_vol_60d"] = returns[ticker].rolling(60).std() * np.sqrt(252)
        frame["max_drawdown_120d"] = _rolling_max_drawdown(price[ticker], 120)
        frame["beta_qqq_60d"] = _rolling_beta(returns[ticker], returns["QQQ"], 60)
        frame["beta_soxx_60d"] = _rolling_beta(returns[ticker], returns["SOXX"], 60)
        frame["residual_return_60d"] = _rolling_two_factor_residual_return(
            returns[ticker], returns[["QQQ", "SOXX"]], 60
        )
        frame["volume_z_60d"] = _rolling_zscore(volume[ticker], 60)
        frame["ingested_at"] = ingested_at
        rows.append(frame)

    if not rows:
        return pd.DataFrame()

    dashboard = pd.concat(rows, ignore_index=True)
    dashboard = dashboard.dropna(subset=["date", "ticker"])
    return dashboard[
        [
            "date",
            "ticker",
            "return_20d",
            "return_60d",
            "return_120d",
            "rel_qqq_60d",
            "rel_soxx_60d",
            "realized_vol_20d",
            "realized_vol_60d",
            "max_drawdown_120d",
            "beta_qqq_60d",
            "beta_soxx_60d",
            "residual_return_60d",
            "volume_z_60d",
            "ingested_at",
        ]
    ]


def store_factor_dashboard(dashboard: pd.DataFrame) -> int:
    """Store factor dashboard rows."""

    if dashboard.empty:
        return 0
    initialize_database()
    with connect() as conn:
        return upsert_dataframe(conn, dashboard, "factor_dashboard", ["date", "ticker"])


def _rolling_beta(asset_returns: pd.Series, benchmark_returns: pd.Series, window: int) -> pd.Series:
    covariance = asset_returns.rolling(window).cov(benchmark_returns)
    variance = benchmark_returns.rolling(window).var()
    return covariance / variance


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std()
    return (series - mean) / std


def _rolling_max_drawdown(price: pd.Series, window: int) -> pd.Series:
    def max_drawdown(values: np.ndarray) -> float:
        running_peak = np.maximum.accumulate(values)
        drawdowns = values / running_peak - 1.0
        return float(np.nanmin(drawdowns))

    return price.rolling(window).apply(max_drawdown, raw=True)


def _rolling_two_factor_residual_return(
    asset_returns: pd.Series,
    factor_returns: pd.DataFrame,
    window: int,
) -> pd.Series:
    residuals = pd.Series(index=asset_returns.index, dtype="float64")
    combined = pd.concat([asset_returns.rename("asset"), factor_returns], axis=1)

    for index in range(window - 1, len(combined)):
        sample = combined.iloc[index - window + 1 : index + 1].dropna()
        if len(sample) < max(30, window // 2):
            continue
        y = sample["asset"].to_numpy()
        x = sample[factor_returns.columns].to_numpy()
        x = np.column_stack([np.ones(len(x)), x])
        coefficients, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
        fitted = x @ coefficients
        residual_daily = y - fitted
        residuals.iloc[index] = float(np.prod(1.0 + residual_daily) - 1.0)

    return residuals
