"""Point-in-time trailing valuation metrics and evidence features."""

import hashlib
from typing import Optional

import numpy as np
import pandas as pd

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

VALUATION_METRIC_COLUMNS = [
    "valuation_metric_id",
    "date",
    "ticker",
    "market_cap",
    "enterprise_value",
    "price",
    "shares_outstanding",
    "cash",
    "debt",
    "ttm_revenue",
    "ttm_gross_profit",
    "ttm_operating_income",
    "ttm_net_income",
    "ttm_free_cash_flow",
    "pe_ttm",
    "ev_sales_ttm",
    "ev_gross_profit_ttm",
    "ev_operating_income_ttm",
    "fcf_yield_ttm",
    "earnings_yield_ttm",
    "revenue_growth_yoy",
    "gross_profit_growth_yoy",
    "fcf_growth_yoy",
    "valuation_percentile_1y",
    "valuation_percentile_3y",
    "valuation_percentile_5y",
    "data_quality_flag",
    "source_fundamental_ids",
    "created_at",
    "ingested_at",
]

VALUATION_FEATURE_COLUMNS = [
    "date",
    "ticker",
    "feature_name",
    "feature_value",
    "feature_score",
    "direction",
    "confidence",
    "source_metric_ids",
    "data_quality_flag",
    "ingested_at",
]


def build_valuation_metrics(tickers: Optional[list[str]] = None) -> pd.DataFrame:
    """Build PIT trailing valuation metrics from prices and available fundamentals."""

    ticker_list = tickers or CORE_TICKERS
    initialize_database()
    with connect() as conn:
        prices = conn.execute(
            """
            SELECT date, ticker, close AS price
            FROM prices
            WHERE ticker IN (SELECT unnest(?))
              AND close IS NOT NULL
            ORDER BY ticker, date
            """,
            [ticker_list],
        ).fetchdf()
        fundamentals = conn.execute(
            """
            SELECT *
            FROM fundamentals_quarterly_normalized
            WHERE ticker IN (SELECT unnest(?))
              AND available_date IS NOT NULL
            ORDER BY ticker, available_date, period_end
            """,
            [ticker_list],
        ).fetchdf()

    if prices.empty:
        return pd.DataFrame(columns=VALUATION_METRIC_COLUMNS)

    prices["date"] = pd.to_datetime(prices["date"])
    if not fundamentals.empty:
        fundamentals["available_date"] = pd.to_datetime(fundamentals["available_date"])
        fundamentals["period_end"] = pd.to_datetime(fundamentals["period_end"])

    created_at = utc_now_naive()
    rows = []
    for ticker, ticker_prices in prices.groupby("ticker", dropna=False):
        ticker_fundamentals = fundamentals[fundamentals["ticker"] == ticker].copy()
        if ticker_fundamentals.empty:
            rows.extend(
                _missing_fundamental_rows(ticker, ticker_prices, created_at)
            )
            continue
        rows.extend(_ticker_valuation_rows(ticker, ticker_prices, ticker_fundamentals, created_at))

    metrics = pd.DataFrame(rows)
    if metrics.empty:
        return pd.DataFrame(columns=VALUATION_METRIC_COLUMNS)
    metrics = _add_valuation_percentiles(metrics)
    return metrics[VALUATION_METRIC_COLUMNS].sort_values(["ticker", "date"])


def store_valuation_metrics(metrics: pd.DataFrame) -> int:
    """Store valuation metrics as a full rebuild."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM valuation_metrics")
        if metrics.empty:
            return 0
        return upsert_dataframe(
            conn,
            metrics,
            "valuation_metrics",
            ["valuation_metric_id"],
        )


def build_valuation_features(tickers: Optional[list[str]] = None) -> pd.DataFrame:
    """Build latest valuation evidence features for each ticker."""

    ticker_list = tickers or CORE_TICKERS
    initialize_database()
    with connect() as conn:
        metrics = conn.execute(
            """
            SELECT *
            FROM valuation_metrics
            WHERE ticker IN (SELECT unnest(?))
            QUALIFY row_number() OVER (
                PARTITION BY ticker ORDER BY date DESC
            ) = 1
            ORDER BY ticker
            """,
            [ticker_list],
        ).fetchdf()
        snapshots = conn.execute(
            """
            SELECT *
            FROM valuation_snapshots
            WHERE ticker IN (SELECT unnest(?))
            QUALIFY row_number() OVER (
                PARTITION BY ticker ORDER BY snapshot_date DESC
            ) = 1
            ORDER BY ticker
            """,
            [ticker_list],
        ).fetchdf()

    ingested_at = utc_now_naive()
    rows = []
    metric_tickers: set[str] = set()
    if not metrics.empty:
        metrics["date"] = pd.to_datetime(metrics["date"]).dt.date
        for _, metric in metrics.iterrows():
            metric_rows = _valuation_feature_rows(metric, ingested_at)
            if metric_rows:
                metric_tickers.add(str(metric["ticker"]))
            rows.extend(metric_rows)

    missing_tickers = set(ticker_list) - metric_tickers
    if not snapshots.empty and missing_tickers:
        snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"]).dt.date
        for _, snapshot in snapshots.iterrows():
            if str(snapshot["ticker"]) in missing_tickers:
                rows.extend(_snapshot_feature_rows(snapshot, ingested_at))

    if not rows:
        return pd.DataFrame(columns=VALUATION_FEATURE_COLUMNS)
    return pd.DataFrame(rows)[VALUATION_FEATURE_COLUMNS].sort_values(
        ["ticker", "feature_name"]
    )


def store_valuation_features(features: pd.DataFrame) -> int:
    """Store valuation features as a full rebuild."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM valuation_features")
        if features.empty:
            return 0
        return upsert_dataframe(
            conn,
            features,
            "valuation_features",
            ["date", "ticker", "feature_name"],
        )


def _ticker_valuation_rows(
    ticker: str,
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame,
    created_at,
) -> list[dict]:
    rows = []
    fundamentals = fundamentals.sort_values(["available_date", "period_end"])
    for _, price_row in prices.iterrows():
        price_date = price_row["date"]
        available = fundamentals[fundamentals["available_date"] <= price_date]
        if available.empty:
            rows.extend(_missing_fundamental_rows(ticker, pd.DataFrame([price_row]), created_at))
            continue
        available = (
            available.sort_values(["period_end", "available_date"])
            .groupby("period_end", dropna=False)
            .tail(1)
            .sort_values("period_end")
        )
        latest = available.iloc[-1]
        ttm = available.tail(4)
        prior = available.iloc[-5] if len(available) >= 5 else pd.Series(dtype=object)
        rows.append(_valuation_row(ticker, price_row, latest, ttm, prior, created_at))
    return rows


def _valuation_row(
    ticker: str,
    price_row: pd.Series,
    latest: pd.Series,
    ttm: pd.DataFrame,
    prior: pd.Series,
    created_at,
) -> dict:
    price = _safe_number(price_row.get("price"))
    shares = _safe_number(latest.get("shares_outstanding"))
    cash = _safe_number(latest.get("cash"), default=0.0)
    debt = _safe_number(latest.get("debt"), default=0.0)
    market_cap = price * shares if _positive(price) and _positive(shares) else np.nan
    enterprise_value = market_cap + debt - cash if pd.notna(market_cap) else np.nan

    ttm_revenue = _sum(ttm, "revenue")
    ttm_gross_profit = _sum(ttm, "gross_profit")
    ttm_operating_income = _sum(ttm, "operating_income")
    ttm_net_income = _sum(ttm, "net_income")
    ttm_free_cash_flow = _sum(ttm, "free_cash_flow_quarterly")
    source_ids = ",".join(ttm["fundamental_id"].dropna().astype(str).tolist())

    data_quality = _valuation_quality_flag(ttm, market_cap, ttm_revenue, source_ids)
    date_value = pd.to_datetime(price_row["date"]).date()
    row = {
        "valuation_metric_id": _valuation_metric_id(ticker, date_value),
        "date": date_value,
        "ticker": ticker,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "price": price,
        "shares_outstanding": shares,
        "cash": cash,
        "debt": debt,
        "ttm_revenue": ttm_revenue,
        "ttm_gross_profit": ttm_gross_profit,
        "ttm_operating_income": ttm_operating_income,
        "ttm_net_income": ttm_net_income,
        "ttm_free_cash_flow": ttm_free_cash_flow,
        "pe_ttm": _ratio(market_cap, ttm_net_income),
        "ev_sales_ttm": _ratio(enterprise_value, ttm_revenue),
        "ev_gross_profit_ttm": _ratio(enterprise_value, ttm_gross_profit),
        "ev_operating_income_ttm": _ratio(enterprise_value, ttm_operating_income),
        "fcf_yield_ttm": _ratio(ttm_free_cash_flow, market_cap),
        "earnings_yield_ttm": _ratio(ttm_net_income, market_cap),
        "revenue_growth_yoy": _growth(latest, prior, "revenue"),
        "gross_profit_growth_yoy": _growth(latest, prior, "gross_profit"),
        "fcf_growth_yoy": _growth(latest, prior, "free_cash_flow_quarterly"),
        "valuation_percentile_1y": np.nan,
        "valuation_percentile_3y": np.nan,
        "valuation_percentile_5y": np.nan,
        "data_quality_flag": data_quality,
        "source_fundamental_ids": source_ids,
        "created_at": created_at,
        "ingested_at": created_at,
    }
    return row


def _missing_fundamental_rows(ticker: str, prices: pd.DataFrame, created_at) -> list[dict]:
    rows = []
    for _, price_row in prices.iterrows():
        price_date = pd.to_datetime(price_row["date"]).date()
        price = _safe_number(price_row.get("price"))
        rows.append(
            {
                "valuation_metric_id": _valuation_metric_id(ticker, price_date),
                "date": price_date,
                "ticker": ticker,
                "market_cap": np.nan,
                "enterprise_value": np.nan,
                "price": price,
                "shares_outstanding": np.nan,
                "cash": np.nan,
                "debt": np.nan,
                "ttm_revenue": np.nan,
                "ttm_gross_profit": np.nan,
                "ttm_operating_income": np.nan,
                "ttm_net_income": np.nan,
                "ttm_free_cash_flow": np.nan,
                "pe_ttm": np.nan,
                "ev_sales_ttm": np.nan,
                "ev_gross_profit_ttm": np.nan,
                "ev_operating_income_ttm": np.nan,
                "fcf_yield_ttm": np.nan,
                "earnings_yield_ttm": np.nan,
                "revenue_growth_yoy": np.nan,
                "gross_profit_growth_yoy": np.nan,
                "fcf_growth_yoy": np.nan,
                "valuation_percentile_1y": np.nan,
                "valuation_percentile_3y": np.nan,
                "valuation_percentile_5y": np.nan,
                "data_quality_flag": "missing_fundamentals",
                "source_fundamental_ids": "",
                "created_at": created_at,
                "ingested_at": created_at,
            }
        )
    return rows


def _add_valuation_percentiles(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    metrics["date"] = pd.to_datetime(metrics["date"])
    for window_name, _days in (
        ("valuation_percentile_1y", 365),
        ("valuation_percentile_3y", 365 * 3),
        ("valuation_percentile_5y", 365 * 5),
    ):
        metrics[window_name] = np.nan

    for _ticker, group in metrics.groupby("ticker", dropna=False):
        group = group.sort_values("date")
        for idx, row in group.iterrows():
            current = row["ev_sales_ttm"]
            if pd.isna(current):
                continue
            for column, days in (
                ("valuation_percentile_1y", 365),
                ("valuation_percentile_3y", 365 * 3),
                ("valuation_percentile_5y", 365 * 5),
            ):
                start = row["date"] - pd.Timedelta(days=days)
                window = group[(group["date"] >= start) & (group["date"] <= row["date"])]
                values = window["ev_sales_ttm"].dropna()
                if values.empty:
                    continue
                metrics.loc[idx, column] = (values <= current).mean()

    metrics["date"] = metrics["date"].dt.date
    return metrics


def _valuation_feature_rows(metric: pd.Series, ingested_at) -> list[dict]:
    metric_id = str(metric["valuation_metric_id"])
    ticker = str(metric["ticker"])
    data_quality = str(metric.get("data_quality_flag") or "complete")
    confidence = 0.75 if data_quality == "complete" else 0.55
    rows = []

    percentile = _first_number(
        metric.get("valuation_percentile_3y"),
        metric.get("valuation_percentile_5y"),
        metric.get("valuation_percentile_1y"),
    )
    rows.append(
        _feature_row(
            metric,
            "valuation_percentile_score",
            percentile,
            100.0 - 100.0 * percentile if pd.notna(percentile) else np.nan,
            confidence,
            metric_id,
            data_quality,
            ingested_at,
        )
    )
    rows.append(
        _feature_row(
            metric,
            "fcf_yield_score",
            metric.get("fcf_yield_ttm"),
            _range_score(metric.get("fcf_yield_ttm"), -0.02, 0.08),
            confidence,
            metric_id,
            data_quality,
            ingested_at,
        )
    )
    rows.append(
        _feature_row(
            metric,
            "ev_sales_score",
            metric.get("ev_sales_ttm"),
            100.0 - _range_score(metric.get("ev_sales_ttm"), 3.0, 30.0),
            confidence,
            metric_id,
            data_quality,
            ingested_at,
        )
    )
    rows.append(
        _feature_row(
            metric,
            "gross_profit_multiple_score",
            metric.get("ev_gross_profit_ttm"),
            100.0 - _range_score(metric.get("ev_gross_profit_ttm"), 8.0, 60.0),
            confidence,
            metric_id,
            data_quality,
            ingested_at,
        )
    )
    growth = _safe_number(metric.get("revenue_growth_yoy"))
    growth_adjusted_score = (
        np.clip(50.0 + 100.0 * growth - 70.0 * (percentile - 0.50), 0.0, 100.0)
        if pd.notna(growth) and pd.notna(percentile)
        else np.nan
    )
    rows.append(
        _feature_row(
            metric,
            "growth_adjusted_valuation_score",
            growth,
            growth_adjusted_score,
            confidence,
            metric_id,
            data_quality,
            ingested_at,
        )
    )

    if ticker == "GOOGL":
        rows.append(
            _feature_row(
                metric,
                "capex_adjusted_fcf_score",
                metric.get("fcf_yield_ttm"),
                _range_score(metric.get("fcf_yield_ttm"), -0.01, 0.07),
                confidence,
                metric_id,
                data_quality,
                ingested_at,
            )
        )

    return [row for row in rows if pd.notna(row["feature_score"])]


def _snapshot_feature_rows(snapshot: pd.Series, ingested_at) -> list[dict]:
    """Build low-confidence valuation features from current screening snapshots.

    This is a fallback for tickers such as TSM where normalized PIT financials are
    incomplete. Snapshot features are not treated as historical PIT metrics.
    """

    source_id = f"valuation_snapshot|{snapshot['ticker']}|{snapshot['snapshot_date']}"
    confidence = 0.45
    data_quality = "snapshot_fallback"
    rows = [
        _snapshot_feature_row(
            snapshot,
            "snapshot_pe_score",
            snapshot.get("trailing_pe"),
            100.0 - _range_score(snapshot.get("trailing_pe"), 10.0, 45.0),
            confidence,
            source_id,
            data_quality,
            ingested_at,
        ),
        _snapshot_feature_row(
            snapshot,
            "snapshot_forward_pe_score",
            snapshot.get("forward_pe"),
            100.0 - _range_score(snapshot.get("forward_pe"), 10.0, 35.0),
            confidence,
            source_id,
            data_quality,
            ingested_at,
        ),
    ]
    return [row for row in rows if pd.notna(row["feature_score"])]


def _feature_row(
    metric: pd.Series,
    feature_name: str,
    feature_value: float,
    feature_score: float,
    confidence: float,
    metric_id: str,
    data_quality: str,
    ingested_at,
) -> dict:
    return {
        "date": metric["date"],
        "ticker": metric["ticker"],
        "feature_name": feature_name,
        "feature_value": feature_value,
        "feature_score": float(np.clip(feature_score, 0.0, 100.0)),
        "direction": _direction_from_score(feature_score),
        "confidence": confidence,
        "source_metric_ids": metric_id,
        "data_quality_flag": data_quality,
        "ingested_at": ingested_at,
    }


def _snapshot_feature_row(
    snapshot: pd.Series,
    feature_name: str,
    feature_value: float,
    feature_score: float,
    confidence: float,
    source_id: str,
    data_quality: str,
    ingested_at,
) -> dict:
    return {
        "date": snapshot["snapshot_date"],
        "ticker": snapshot["ticker"],
        "feature_name": feature_name,
        "feature_value": feature_value,
        "feature_score": float(np.clip(feature_score, 0.0, 100.0)),
        "direction": _direction_from_score(feature_score),
        "confidence": confidence,
        "source_metric_ids": source_id,
        "data_quality_flag": data_quality,
        "ingested_at": ingested_at,
    }


def _valuation_quality_flag(
    ttm: pd.DataFrame,
    market_cap: float,
    ttm_revenue: float,
    source_ids: str,
) -> str:
    if not source_ids:
        return "missing_fundamentals"
    if len(ttm) < 4:
        return "partial_ttm"
    if pd.isna(market_cap):
        return "missing_market_cap"
    if pd.isna(ttm_revenue) or ttm_revenue <= 0:
        return "missing_revenue"
    return "complete"


def _valuation_metric_id(ticker: str, date_value) -> str:
    key = f"{ticker}|{date_value}"
    return "valuation_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:14]


def _sum(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(values.sum()) if not values.empty else np.nan


def _growth(latest: pd.Series, prior: pd.Series, column: str) -> float:
    current = _safe_number(latest.get(column))
    previous = _safe_number(prior.get(column)) if not prior.empty else np.nan
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return np.nan
    return current / abs(previous) - 1.0


def _ratio(numerator: float, denominator: float) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or denominator <= 0:
        return np.nan
    return float(numerator) / float(denominator)


def _positive(value: float) -> bool:
    return pd.notna(value) and value > 0


def _safe_number(value, default=np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_number(*values) -> float:
    for value in values:
        numeric = _safe_number(value)
        if pd.notna(numeric):
            return numeric
    return np.nan


def _range_score(value, low: float, high: float) -> float:
    numeric = _safe_number(value)
    if pd.isna(numeric):
        return np.nan
    return float(np.clip(100.0 * (numeric - low) / (high - low), 0.0, 100.0))


def _direction_from_score(score: float) -> str:
    if pd.isna(score):
        return "mixed"
    if score >= 70:
        return "positive"
    if score <= 30:
        return "negative"
    return "neutral"
