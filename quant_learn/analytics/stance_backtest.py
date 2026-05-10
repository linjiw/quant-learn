"""Archive-based stance outcome tracking.

This module evaluates outcomes for stance rows that the system actually emitted.
It does not replay historical evidence or simulate trading PnL.
"""

from pathlib import Path
from typing import Optional

import pandas as pd

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

DEFAULT_HORIZONS = (21, 63, 126)
DEFAULT_MODEL_NAME = "three_factor_raw"
DEFAULT_LOOKBACK_WINDOW = 60

OBSERVATION_COLUMNS = [
    "run_id",
    "as_of_date",
    "ticker",
    "stance",
    "stance_modifier",
    "confidence",
    "confidence_bucket",
    "data_snapshot_hash",
    "horizon",
    "entry_date",
    "maturity_date",
    "is_mature",
    "forward_raw_return",
    "forward_factor_expected_return",
    "forward_residual_return",
    "forward_max_drawdown",
    "data_quality_flag",
    "created_at",
    "ingested_at",
]

SUMMARY_COLUMNS = [
    "as_of_date",
    "horizon",
    "ticker",
    "stance",
    "stance_modifier",
    "confidence_bucket",
    "observation_count",
    "mature_count",
    "hit_rate",
    "mean_forward_residual_return",
    "median_forward_residual_return",
    "p25_forward_residual_return",
    "p75_forward_residual_return",
    "mean_forward_raw_return",
    "mean_forward_max_drawdown",
    "created_at",
    "ingested_at",
]


def build_stance_backtest_observations(
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    model_name: str = DEFAULT_MODEL_NAME,
    lookback_window: int = DEFAULT_LOOKBACK_WINDOW,
) -> pd.DataFrame:
    """Build forward outcome observations for successful archived/current stances."""

    initialize_database()
    with connect() as conn:
        stances = _fetch_successful_stances(conn)
        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            ORDER BY ticker, date
            """
        ).fetchdf()
        residuals = conn.execute(
            """
            SELECT date, ticker, expected_return_1d, residual_return_1d
            FROM factor_residuals
            WHERE model_name = ? AND lookback_window = ?
            ORDER BY ticker, date
            """,
            [model_name, lookback_window],
        ).fetchdf()

    if stances.empty:
        return pd.DataFrame(columns=OBSERVATION_COLUMNS)

    now = utc_now_naive()
    price_by_ticker = _prepare_prices(prices)
    residual_by_ticker = _prepare_residuals(residuals)
    rows = []
    for _, stance in stances.iterrows():
        for horizon in horizons:
            rows.append(
                _observation_row(
                    stance=stance,
                    horizon=int(horizon),
                    prices=price_by_ticker.get(str(stance["ticker"])),
                    residuals=residual_by_ticker.get(str(stance["ticker"])),
                    now=now,
                )
            )
    return pd.DataFrame(rows, columns=OBSERVATION_COLUMNS)


def store_stance_backtest_observations(observations: pd.DataFrame) -> int:
    """Upsert stance outcome observations by emitted run, ticker, and horizon."""

    initialize_database()
    if observations.empty:
        return 0
    with connect() as conn:
        return upsert_dataframe(
            conn,
            observations,
            "stance_backtest_observations",
            ["run_id", "ticker", "horizon"],
        )


def build_stance_backtest_summary(
    observations: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Summarize mature outcome observations by stance, modifier, ticker, and horizon."""

    initialize_database()
    if observations is None:
        with connect() as conn:
            observations = conn.execute(
                "SELECT * FROM stance_backtest_observations"
            ).fetchdf()
    if observations.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    now = utc_now_naive()
    as_of_date = now.date()
    prepared = observations.copy()
    prepared["stance_modifier"] = prepared["stance_modifier"].fillna("none")
    prepared["confidence_bucket"] = prepared["confidence_bucket"].fillna("unknown")
    group_columns = [
        "horizon",
        "ticker",
        "stance",
        "stance_modifier",
        "confidence_bucket",
    ]
    rows = []
    for keys, group in prepared.groupby(group_columns, dropna=False):
        mature = group[
            (group["is_mature"] == True)  # noqa: E712
            & (group["data_quality_flag"] == "complete")
            & group["forward_residual_return"].notna()
        ]
        residual = mature["forward_residual_return"].astype(float)
        raw = mature["forward_raw_return"].astype(float)
        drawdown = mature["forward_max_drawdown"].astype(float)
        rows.append(
            {
                "as_of_date": as_of_date,
                "horizon": int(keys[0]),
                "ticker": keys[1],
                "stance": keys[2],
                "stance_modifier": keys[3],
                "confidence_bucket": keys[4],
                "observation_count": int(len(group)),
                "mature_count": int(len(mature)),
                "hit_rate": _mean_or_none((residual > 0).astype(float)),
                "mean_forward_residual_return": _mean_or_none(residual),
                "median_forward_residual_return": _median_or_none(residual),
                "p25_forward_residual_return": _quantile_or_none(residual, 0.25),
                "p75_forward_residual_return": _quantile_or_none(residual, 0.75),
                "mean_forward_raw_return": _mean_or_none(raw),
                "mean_forward_max_drawdown": _mean_or_none(drawdown),
                "created_at": now,
                "ingested_at": now,
            }
        )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def store_stance_backtest_summary(summary: pd.DataFrame) -> int:
    """Replace the current stance backtest summary with the latest aggregate view."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM stance_backtest_summary")
        if summary.empty:
            return 0
        return upsert_dataframe(
            conn,
            summary,
            "stance_backtest_summary",
            [
                "as_of_date",
                "horizon",
                "ticker",
                "stance",
                "stance_modifier",
                "confidence_bucket",
            ],
        )


def build_stance_backtest_report(output_path: Path) -> Path:
    """Write a concise report describing archive-based stance outcomes."""

    initialize_database()
    with connect() as conn:
        observations = conn.execute(
            "SELECT * FROM stance_backtest_observations ORDER BY horizon, ticker, run_id"
        ).fetchdf()
        summary = conn.execute(
            """
            SELECT *
            FROM stance_backtest_summary
            ORDER BY horizon, ticker, stance, stance_modifier, confidence_bucket
            """
        ).fetchdf()

    lines = [
        "# Stance Backtest Report",
        "",
        "Scope: archive-based outcome tracking for stance rows the system actually emitted.",
        "This is not a trading PnL simulation and does not replay historical evidence.",
        "Forward residual return compounds daily factor residuals from factor_residuals.",
        "",
        "## Coverage",
        "",
    ]
    lines.extend(_coverage_lines(observations))
    lines.extend(["", "## Mature Outcome Summary", ""])
    lines.extend(_summary_lines(summary))
    lines.extend(["", "## Pending Horizons", ""])
    lines.extend(_pending_lines(observations))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _fetch_successful_stances(conn) -> pd.DataFrame:
    current = conn.execute(
        """
        SELECT
            run_id,
            stance_id,
            as_of_date,
            ticker,
            stance,
            stance_modifier,
            confidence,
            created_at,
            ingested_at,
            'current' AS source_kind
        FROM research_stance
        """
    ).fetchdf()
    history = conn.execute(
        """
        SELECT
            run_id,
            stance_id,
            as_of_date,
            ticker,
            stance,
            stance_modifier,
            confidence,
            created_at,
            ingested_at,
            'history' AS source_kind
        FROM research_stance_history
        """
    ).fetchdf()
    runs = conn.execute(
        "SELECT run_id, status, data_snapshot_hash FROM pipeline_runs"
    ).fetchdf()
    if runs.empty:
        return pd.DataFrame()
    stances = pd.concat([current, history], ignore_index=True)
    if stances.empty:
        return stances
    stances = stances[stances["run_id"].notna()].copy()
    successful_runs = runs[runs["status"] == "success"][
        ["run_id", "data_snapshot_hash"]
    ]
    stances = stances.merge(successful_runs, on="run_id", how="inner")
    if stances.empty:
        return stances
    stances["source_rank"] = stances["source_kind"].map({"current": 0, "history": 1})
    stances = stances.sort_values(["run_id", "ticker", "as_of_date", "source_rank"])
    return stances.drop_duplicates(["run_id", "ticker", "as_of_date"], keep="first")


def _prepare_prices(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if prices.empty:
        return {}
    frame = prices.copy()
    frame = frame[frame["ticker"].isin(CORE_TICKERS)]
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = frame["adj_close"].where(frame["adj_close"].notna(), frame["close"])
    return {
        ticker: group.sort_values("date").reset_index(drop=True)
        for ticker, group in frame.groupby("ticker")
    }


def _prepare_residuals(residuals: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if residuals.empty:
        return {}
    frame = residuals.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    return {
        ticker: group.sort_values("date").reset_index(drop=True)
        for ticker, group in frame.groupby("ticker")
    }


def _observation_row(
    *,
    stance: pd.Series,
    horizon: int,
    prices: Optional[pd.DataFrame],
    residuals: Optional[pd.DataFrame],
    now,
) -> dict:
    base = {
        "run_id": stance["run_id"],
        "as_of_date": pd.to_datetime(stance["as_of_date"]).date(),
        "ticker": stance["ticker"],
        "stance": stance["stance"],
        "stance_modifier": stance.get("stance_modifier"),
        "confidence": stance.get("confidence"),
        "confidence_bucket": _confidence_bucket(stance.get("confidence")),
        "data_snapshot_hash": stance.get("data_snapshot_hash"),
        "horizon": horizon,
        "entry_date": None,
        "maturity_date": None,
        "is_mature": False,
        "forward_raw_return": None,
        "forward_factor_expected_return": None,
        "forward_residual_return": None,
        "forward_max_drawdown": None,
        "data_quality_flag": "missing_price",
        "created_at": now,
        "ingested_at": now,
    }
    if prices is None or prices.empty:
        return base

    as_of = pd.to_datetime(stance["as_of_date"]).normalize()
    entry_candidates = prices[prices["date"] <= as_of]
    if entry_candidates.empty:
        return base
    entry_pos = int(entry_candidates.index[-1])
    entry_price = prices.loc[entry_pos, "price"]
    base["entry_date"] = prices.loc[entry_pos, "date"].date()
    if pd.isna(entry_price) or float(entry_price) <= 0:
        return base

    target_pos = entry_pos + horizon
    if target_pos >= len(prices):
        base["data_quality_flag"] = "pending"
        return base

    maturity_date = prices.loc[target_pos, "date"]
    maturity_price = prices.loc[target_pos, "price"]
    base["maturity_date"] = maturity_date.date()
    base["is_mature"] = True
    if pd.isna(maturity_price) or float(maturity_price) <= 0:
        base["data_quality_flag"] = "missing_price"
        return base

    window_prices = prices.iloc[entry_pos : target_pos + 1]["price"].astype(float)
    raw_return = float(maturity_price) / float(entry_price) - 1
    max_drawdown = _max_drawdown(window_prices)
    factor_returns = _forward_factor_returns(
        residuals=residuals,
        entry_date=prices.loc[entry_pos, "date"],
        maturity_date=maturity_date,
        horizon=horizon,
    )
    base["forward_raw_return"] = raw_return
    base["forward_max_drawdown"] = max_drawdown
    if factor_returns is None:
        base["data_quality_flag"] = "missing_factor_residuals"
        return base
    expected_return, residual_return = factor_returns
    base["forward_factor_expected_return"] = expected_return
    base["forward_residual_return"] = residual_return
    base["data_quality_flag"] = "complete"
    return base


def _forward_factor_returns(
    *,
    residuals: Optional[pd.DataFrame],
    entry_date,
    maturity_date,
    horizon: int,
) -> Optional[tuple[float, float]]:
    if residuals is None or residuals.empty:
        return None
    window = residuals[
        (residuals["date"] > entry_date) & (residuals["date"] <= maturity_date)
    ]
    required_columns = ["expected_return_1d", "residual_return_1d"]
    if len(window) < horizon or window[required_columns].isna().any().any():
        return None
    expected_return = float((1 + window["expected_return_1d"].astype(float)).prod() - 1)
    residual_return = float((1 + window["residual_return_1d"].astype(float)).prod() - 1)
    return expected_return, residual_return


def _max_drawdown(prices: pd.Series) -> Optional[float]:
    if prices.empty:
        return None
    peaks = prices.cummax()
    drawdowns = prices / peaks - 1
    return float(drawdowns.min())


def _confidence_bucket(confidence) -> str:
    if pd.isna(confidence):
        return "unknown"
    value = float(confidence)
    if value < 0.55:
        return "low"
    if value < 0.75:
        return "medium"
    return "high"


def _mean_or_none(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    return float(series.mean())


def _median_or_none(series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    return float(series.median())


def _quantile_or_none(series: pd.Series, quantile: float) -> Optional[float]:
    if series.empty:
        return None
    return float(series.quantile(quantile))


def _coverage_lines(observations: pd.DataFrame) -> list[str]:
    if observations.empty:
        return ["- no stance outcome observations available"]
    lines = [
        "| Horizon | Observations | Mature | Complete | Pending |",
        "|---:|---:|---:|---:|---:|",
    ]
    for horizon, group in observations.groupby("horizon"):
        complete = group[group["data_quality_flag"] == "complete"]
        pending = group[group["data_quality_flag"] == "pending"]
        mature = group[group["is_mature"] == True]  # noqa: E712
        lines.append(
            f"| {int(horizon)} | {len(group)} | {len(mature)} | "
            f"{len(complete)} | {len(pending)} |"
        )
    return lines


def _summary_lines(summary: pd.DataFrame) -> list[str]:
    if summary.empty or not summary["mature_count"].fillna(0).gt(0).any():
        return ["- no mature complete observations yet"]
    lines = [
        "| Horizon | Ticker | Stance | Modifier | Bucket | N | Hit Rate | Mean Residual |",
        "|---:|---|---|---|---|---:|---:|---:|",
    ]
    mature = summary[summary["mature_count"].fillna(0) > 0]
    for _, row in mature.iterrows():
        lines.append(
            f"| {int(row['horizon'])} | {row['ticker']} | {row['stance']} | "
            f"{row['stance_modifier']} | {row['confidence_bucket']} | "
            f"{int(row['mature_count'])} | {_fmt_pct(row['hit_rate'])} | "
            f"{_fmt_pct(row['mean_forward_residual_return'])} |"
        )
    return lines


def _pending_lines(observations: pd.DataFrame) -> list[str]:
    if observations.empty:
        return ["- none"]
    pending = observations[observations["data_quality_flag"] == "pending"]
    if pending.empty:
        return ["- none"]
    counts = (
        pending.groupby(["ticker", "horizon"]).size().reset_index(name="count")
    )
    return [
        f"- {row['ticker']} {int(row['horizon'])}d: {int(row['count'])} pending"
        for _, row in counts.iterrows()
    ]


def _fmt_pct(value) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"
