"""Event-study utilities."""

from typing import Optional

import pandas as pd

from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

EVENT_RETURN_WINDOWS = {
    "m1_p1": (-1, 1),
    "0_p1": (0, 1),
    "0_p5": (0, 5),
    "0_p20": (0, 20),
    "pre_20_m1": (-20, -1),
    "post_1_p20": (1, 20),
}

FACTOR_MODEL_NAME = "three_factor_raw"
FACTOR_MODEL_WINDOW = 60
FACTOR_MODEL_BENCHMARK = "QQQ_SOXX_TNX"


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
        factor_inputs = conn.execute(
            """
            SELECT date, qqq_return_1d, soxx_return_1d, delta_tnx_bps
            FROM market_factor_inputs
            ORDER BY date
            """
        ).fetchdf()
        factor_exposures = conn.execute(
            """
            SELECT *
            FROM factor_exposures
            WHERE model_name = ?
              AND lookback_window = ?
            ORDER BY date, ticker
            """,
            [FACTOR_MODEL_NAME, FACTOR_MODEL_WINDOW],
        ).fetchdf()

    if events.empty or prices.empty:
        return pd.DataFrame()

    events["event_date"] = pd.to_datetime(events["event_date"])
    events["reaction_date"] = pd.to_datetime(events["reaction_date"])
    prices["date"] = pd.to_datetime(prices["date"])
    prices["price"] = prices["adj_close"].fillna(prices["close"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    trading_dates = list(price.index)
    factor_frame = _factor_input_frame(factor_inputs)
    exposure_frame = _factor_exposure_frame(factor_exposures)
    ingested_at = utc_now_naive()

    rows = []
    for _, event in events.iterrows():
        ticker = event["affected_ticker"]
        anchor_index = _nearest_trading_index(trading_dates, event["reaction_date"])
        anchor_flag, anchor_reason = _reaction_date_quality(
            trading_dates,
            anchor_index,
            event["reaction_date"],
        )

        for window_name, (start_day, end_day) in EVENT_RETURN_WINDOWS.items():
            raw_return, raw_flag, raw_reason = _event_window_return_with_quality(
                price,
                ticker,
                anchor_index,
                start_day,
                end_day,
                missing_reason="missing_ticker_price",
            )
            for benchmark_ticker in benchmarks:
                benchmark_return, benchmark_flag, benchmark_reason = (
                    _event_window_return_with_quality(
                        price,
                        benchmark_ticker,
                        anchor_index,
                        start_day,
                        end_day,
                        missing_reason="missing_benchmark_price",
                    )
                )
                quality_flag, missing_reason = _combine_quality(
                    anchor_flag,
                    anchor_reason,
                    raw_flag,
                    raw_reason,
                    benchmark_flag,
                    benchmark_reason,
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
                        "data_quality_flag": quality_flag,
                        "missing_reason": missing_reason,
                        "analysis_status": _analysis_status(missing_reason, quality_flag),
                        "ingested_at": ingested_at,
                    }
                )
            if not factor_frame.empty and not exposure_frame.empty:
                factor_return, factor_flag, factor_reason = _event_factor_return_with_quality(
                    factor_frame,
                    exposure_frame,
                    trading_dates,
                    ticker,
                    anchor_index,
                    start_day,
                    end_day,
                )
                factor_quality_flag, factor_missing_reason = _combine_quality(
                    anchor_flag,
                    anchor_reason,
                    raw_flag,
                    raw_reason,
                    factor_flag,
                    factor_reason,
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
                        "benchmark_type": "factor_model",
                        "benchmark_ticker": FACTOR_MODEL_BENCHMARK,
                        "benchmark_return": factor_return,
                        "abnormal_return": _difference(raw_return, factor_return),
                        "model_name": FACTOR_MODEL_NAME,
                        "data_quality_flag": factor_quality_flag,
                        "missing_reason": factor_missing_reason,
                        "analysis_status": _analysis_status(
                            factor_missing_reason,
                            factor_quality_flag,
                        ),
                        "ingested_at": ingested_at,
                    }
                )

    return pd.DataFrame(rows)


def validate_event_return_invariants(event_returns: pd.DataFrame) -> dict[str, int]:
    """Return event-return count invariants for caller-side health checks."""

    if event_returns.empty:
        return {
            "impact_count": 0,
            "window_count": len(EVENT_RETURN_WINDOWS),
            "benchmark_count": 0,
            "expected_rows": 0,
            "actual_rows": 0,
        }

    impact_count = event_returns[["event_id", "affected_ticker"]].drop_duplicates().shape[0]
    window_count = event_returns["return_window"].nunique()
    benchmark_count = event_returns["benchmark_ticker"].nunique()
    expected_rows = impact_count * window_count * benchmark_count
    return {
        "impact_count": int(impact_count),
        "window_count": int(window_count),
        "benchmark_count": int(benchmark_count),
        "expected_rows": int(expected_rows),
        "actual_rows": int(len(event_returns)),
    }


def event_return_invariants_pass(event_returns: pd.DataFrame) -> bool:
    """Check the core long-format row-count invariant."""

    invariants = validate_event_return_invariants(event_returns)
    return invariants["expected_rows"] == invariants["actual_rows"]


def _reaction_date_quality(
    trading_dates: list[pd.Timestamp],
    anchor_index: Optional[int],
    reaction_date: pd.Timestamp,
) -> tuple[str, Optional[str]]:
    if anchor_index is None:
        latest_trading_date = max(trading_dates) if trading_dates else None
        if latest_trading_date is not None and reaction_date > latest_trading_date:
            return "incomplete", "pending_future_window"
        return "incomplete", "non_trading_reaction_date"
    if trading_dates[anchor_index].date() != reaction_date.date():
        return "mapped_reaction_date", "reaction_date_mapped_to_next_trading_day"
    return "complete", None


def _event_window_return_with_quality(
    price: pd.DataFrame,
    ticker: str,
    anchor_index: Optional[int],
    start_offset: int,
    end_offset: int,
    missing_reason: str,
) -> tuple[Optional[float], str, Optional[str]]:
    if anchor_index is None:
        return None, "incomplete", "non_trading_reaction_date"
    if ticker not in price.columns:
        return None, "incomplete", missing_reason

    start_index = anchor_index + start_offset - 1
    end_index = anchor_index + end_offset
    if start_index < 0 or end_index >= len(price.index):
        if end_index >= len(price.index):
            return None, "incomplete", "pending_future_window"
        return None, "incomplete", "insufficient_trading_days"

    start_price = price.iloc[start_index][ticker]
    end_price = price.iloc[end_index][ticker]
    if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
        if ticker == "TSM":
            return None, "incomplete", "adr_calendar_gap"
        return None, "incomplete", missing_reason

    return float(end_price / start_price - 1.0), "complete", None


def _combine_quality(
    anchor_flag: str,
    anchor_reason: Optional[str],
    raw_flag: str,
    raw_reason: Optional[str],
    benchmark_flag: str,
    benchmark_reason: Optional[str],
) -> tuple[str, Optional[str]]:
    if raw_flag == "incomplete":
        return "incomplete", raw_reason
    if benchmark_flag == "incomplete":
        return "incomplete", benchmark_reason
    if anchor_flag == "mapped_reaction_date":
        return anchor_flag, anchor_reason
    return "complete", None


def _analysis_status(missing_reason: Optional[str], data_quality_flag: str) -> str:
    if data_quality_flag in {"complete", "mapped_reaction_date"}:
        return "ready"
    if missing_reason == "pending_future_window":
        return "partial_pending"
    if missing_reason in {
        "missing_ticker_price",
        "missing_benchmark_price",
        "missing_factor_input",
        "insufficient_factor_history",
        "insufficient_trading_days",
        "non_trading_reaction_date",
        "adr_calendar_gap",
    }:
        return "data_issue"
    return "excluded"


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


def _factor_input_frame(factor_inputs: pd.DataFrame) -> pd.DataFrame:
    if factor_inputs.empty:
        return pd.DataFrame()
    frame = factor_inputs.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def _factor_exposure_frame(factor_exposures: pd.DataFrame) -> pd.DataFrame:
    if factor_exposures.empty:
        return pd.DataFrame()
    frame = factor_exposures.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index(["date", "ticker"]).sort_index()


def _event_factor_return_with_quality(
    factor_frame: pd.DataFrame,
    exposure_frame: pd.DataFrame,
    trading_dates: list[pd.Timestamp],
    ticker: str,
    anchor_index: Optional[int],
    start_offset: int,
    end_offset: int,
) -> tuple[Optional[float], str, Optional[str]]:
    if anchor_index is None:
        return None, "incomplete", "non_trading_reaction_date"
    exposure_index = anchor_index - 1
    if exposure_index < 0:
        return None, "incomplete", "insufficient_factor_history"

    exposure_date = trading_dates[exposure_index]
    if (exposure_date, ticker) not in exposure_frame.index:
        return None, "incomplete", "insufficient_factor_history"
    exposure = exposure_frame.loc[(exposure_date, ticker)]
    if exposure["data_quality_flag"] == "insufficient_observations":
        return None, "incomplete", "insufficient_factor_history"

    start_index = anchor_index + start_offset
    end_index = anchor_index + end_offset
    if start_index < 0 or end_index >= len(trading_dates):
        if end_index >= len(trading_dates):
            return None, "incomplete", "pending_future_window"
        return None, "incomplete", "insufficient_trading_days"

    expected_daily = []
    for trading_date in trading_dates[start_index : end_index + 1]:
        if trading_date not in factor_frame.index:
            return None, "incomplete", "missing_factor_input"
        factors = factor_frame.loc[trading_date]
        if factors[["qqq_return_1d", "soxx_return_1d", "delta_tnx_bps"]].isna().any():
            return None, "incomplete", "missing_factor_input"
        expected_daily.append(
            float(exposure["alpha_daily"])
            + float(exposure["beta_qqq"]) * float(factors["qqq_return_1d"])
            + float(exposure["beta_soxx"]) * float(factors["soxx_return_1d"])
            + float(exposure["beta_tnx_bps"]) * float(factors["delta_tnx_bps"])
        )

    return float(pd.Series(expected_daily).add(1.0).prod() - 1.0), "complete", None
