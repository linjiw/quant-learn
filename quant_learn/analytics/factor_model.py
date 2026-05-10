"""Three-factor residual model with point-in-time rolling exposures."""

from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from quant_learn.config import CORE_TICKERS
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

MODEL_NAME = "three_factor_raw"
DEFAULT_WINDOW = 60
DEFAULT_MIN_OBS = 40
DIAGNOSTIC_WINDOWS = (20, 60)
FACTOR_COLUMNS = ["qqq_return_1d", "soxx_return_1d", "delta_tnx_bps"]
FACTOR_TICKERS = ["QQQ", "SOXX", "SMH", "SPY", "^TNX"]


def normalize_10y_change_to_bps(series: pd.Series, source: str) -> pd.Series:
    """Normalize a 10Y yield series change into basis points."""

    normalized_source = source.strip().upper()
    if normalized_source == "YAHOO_TNX":
        return series.diff() * 10.0
    if normalized_source == "YIELD_PERCENT":
        return series.diff() * 100.0
    if normalized_source == "YIELD_DECIMAL":
        return series.diff() * 10000.0
    raise ValueError(f"Unknown 10Y source: {source}")


def build_market_factor_inputs(tnx_source: str = "YAHOO_TNX") -> pd.DataFrame:
    """Build daily QQQ/SOXX/10Y factor inputs from stored prices."""

    initialize_database()
    with connect() as conn:
        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            WHERE ticker IN (SELECT unnest(?))
            ORDER BY date, ticker
            """,
            [FACTOR_TICKERS],
        ).fetchdf()

    if prices.empty:
        return pd.DataFrame(columns=_market_factor_columns())

    price = _price_pivot(prices)
    returns = price.pct_change()
    ingested_at = utc_now_naive()
    frame = pd.DataFrame(index=price.index)
    frame["date"] = frame.index.date
    frame["qqq_return_1d"] = returns.get("QQQ")
    frame["soxx_return_1d"] = returns.get("SOXX")
    frame["smh_return_1d"] = returns.get("SMH")
    frame["spy_return_1d"] = returns.get("SPY")
    frame["tnx_close"] = price.get("^TNX")
    frame["delta_tnx_bps"] = normalize_10y_change_to_bps(frame["tnx_close"], tnx_source)
    frame["semi_specific_return_1d"] = _semi_specific_return(frame)
    frame["data_quality_flag"] = np.where(
        frame[FACTOR_COLUMNS].notna().all(axis=1),
        "complete",
        "incomplete",
    )
    frame["source"] = tnx_source
    frame["ingested_at"] = ingested_at
    return frame[_market_factor_columns()].reset_index(drop=True)


def store_market_factor_inputs(inputs: pd.DataFrame) -> int:
    """Store market factor inputs as a full rebuild."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM market_factor_inputs")
        if inputs.empty:
            return 0
        return upsert_dataframe(conn, inputs, "market_factor_inputs", ["date"])


def build_factor_exposures(
    tickers: Optional[Iterable[str]] = None,
    window: int = DEFAULT_WINDOW,
    min_obs: int = DEFAULT_MIN_OBS,
    model_name: str = MODEL_NAME,
) -> pd.DataFrame:
    """Estimate rolling factor exposures using only prior observations."""

    ticker_list = list(tickers or CORE_TICKERS)
    returns = _load_stock_returns(ticker_list)
    inputs = _load_market_factor_inputs()
    if returns.empty or inputs.empty:
        return pd.DataFrame(columns=_factor_exposure_columns())

    factors = inputs.set_index("date")[FACTOR_COLUMNS]
    dates = sorted(set(returns.index).intersection(set(factors.index)))
    ingested_at = utc_now_naive()
    rows = []
    for ticker in ticker_list:
        if ticker not in returns.columns:
            continue
        combined = pd.concat([returns[ticker].rename("stock_return"), factors], axis=1)
        combined = combined.loc[dates]
        for index, date in enumerate(combined.index):
            sample = combined.iloc[max(0, index - window) : index].dropna()
            row = {
                "date": date.date(),
                "ticker": ticker,
                "model_name": model_name,
                "lookback_window": window,
                "n_obs": int(len(sample)),
                "alpha_daily": np.nan,
                "beta_qqq": np.nan,
                "beta_soxx": np.nan,
                "beta_tnx_bps": np.nan,
                "r2": np.nan,
                "factor_corr_qqq_soxx": _factor_corr(sample),
                "data_quality_flag": "insufficient_observations",
                "ingested_at": ingested_at,
            }
            if len(sample) >= min_obs:
                coefficients, r2 = _ols(sample["stock_return"], sample[FACTOR_COLUMNS])
                row.update(
                    {
                        "alpha_daily": coefficients[0],
                        "beta_qqq": coefficients[1],
                        "beta_soxx": coefficients[2],
                        "beta_tnx_bps": coefficients[3],
                        "r2": r2,
                        "data_quality_flag": _exposure_quality(row["factor_corr_qqq_soxx"]),
                    }
                )
            rows.append(row)

    return pd.DataFrame(rows, columns=_factor_exposure_columns())


def store_factor_exposures(exposures: pd.DataFrame, model_name: str = MODEL_NAME) -> int:
    """Store factor exposures as a full rebuild for one model."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM factor_exposures WHERE model_name = ?", [model_name])
        if exposures.empty:
            return 0
        return upsert_dataframe(
            conn,
            exposures,
            "factor_exposures",
            ["date", "ticker", "model_name", "lookback_window"],
        )


def build_factor_residuals(
    tickers: Optional[Iterable[str]] = None,
    window: int = DEFAULT_WINDOW,
    model_name: str = MODEL_NAME,
) -> pd.DataFrame:
    """Build daily expected and residual returns from PIT exposures."""

    ticker_list = list(tickers or CORE_TICKERS)
    returns = _load_stock_returns(ticker_list)
    inputs = _load_market_factor_inputs()
    exposures = _load_factor_exposures(model_name, window)
    if returns.empty or inputs.empty or exposures.empty:
        return pd.DataFrame(columns=_factor_residual_columns())

    factor_frame = inputs.set_index("date")[FACTOR_COLUMNS]
    exposure_frame = exposures.set_index(["date", "ticker"])
    ingested_at = utc_now_naive()
    rows = []
    for ticker in ticker_list:
        if ticker not in returns.columns:
            continue
        for date, stock_return in returns[ticker].dropna().items():
            row = _factor_residual_row(
                date,
                ticker,
                stock_return,
                factor_frame,
                exposure_frame,
                model_name,
                window,
                ingested_at,
            )
            rows.append(row)

    residuals = pd.DataFrame(rows, columns=_factor_residual_columns())
    if residuals.empty:
        return residuals
    residuals = _add_cumulative_residuals(residuals)
    return residuals[_factor_residual_columns()]


def store_factor_residuals(residuals: pd.DataFrame, model_name: str = MODEL_NAME) -> int:
    """Store factor residuals as a full rebuild for one model."""

    initialize_database()
    with connect() as conn:
        conn.execute("DELETE FROM factor_residuals WHERE model_name = ?", [model_name])
        if residuals.empty:
            return 0
        return upsert_dataframe(
            conn,
            residuals,
            "factor_residuals",
            ["date", "ticker", "model_name", "lookback_window"],
        )


def build_residual_diagnostics(
    tickers: Optional[Iterable[str]] = None,
    model_name: str = MODEL_NAME,
    lookback_window: int = DEFAULT_WINDOW,
    windows: Iterable[int] = DIAGNOSTIC_WINDOWS,
) -> pd.DataFrame:
    """Build residual concentration diagnostics from daily residuals."""

    ticker_list = list(tickers or CORE_TICKERS)
    initialize_database()
    with connect() as conn:
        residuals = conn.execute(
            """
            SELECT *
            FROM factor_residuals
            WHERE ticker IN (SELECT unnest(?))
              AND model_name = ?
              AND lookback_window = ?
            ORDER BY ticker, date
            """,
            [ticker_list, model_name, lookback_window],
        ).fetchdf()
    if residuals.empty:
        return pd.DataFrame(columns=_residual_diagnostic_columns())

    residuals["date"] = pd.to_datetime(residuals["date"])
    ingested_at = utc_now_naive()
    rows = []
    for ticker, group in residuals.groupby("ticker", dropna=False):
        clean = group.dropna(subset=["residual_return_1d"]).sort_values("date")
        if clean.empty:
            continue
        as_of_date = clean["date"].max().date()
        for window_days in windows:
            rows.append(
                _residual_diagnostic_row(
                    ticker=str(ticker),
                    clean=clean,
                    as_of_date=as_of_date,
                    model_name=model_name,
                    lookback_window=lookback_window,
                    window_days=int(window_days),
                    ingested_at=ingested_at,
                )
            )
    return pd.DataFrame(rows, columns=_residual_diagnostic_columns())


def store_residual_diagnostics(
    diagnostics: pd.DataFrame,
    model_name: str = MODEL_NAME,
    lookback_window: int = DEFAULT_WINDOW,
) -> int:
    """Store residual concentration diagnostics as a full rebuild for one model."""

    initialize_database()
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM residual_diagnostics
            WHERE model_name = ?
              AND lookback_window = ?
            """,
            [model_name, lookback_window],
        )
        if diagnostics.empty:
            return 0
        return upsert_dataframe(
            conn,
            diagnostics,
            "residual_diagnostics",
            ["as_of_date", "ticker", "model_name", "lookback_window", "window_days"],
        )


def build_factor_residual_report(output_path: Path) -> Path:
    """Write a concise factor residual markdown report."""

    initialize_database()
    with connect() as conn:
        latest = conn.execute(
            """
            SELECT *
            FROM factor_residuals r
            JOIN factor_exposures e
              ON r.date = e.date
             AND r.ticker = e.ticker
             AND r.model_name = e.model_name
             AND r.lookback_window = e.lookback_window
            QUALIFY ROW_NUMBER() OVER (PARTITION BY r.ticker ORDER BY r.date DESC) = 1
            ORDER BY r.ticker
            """
        ).fetchdf()

    lines = ["# Factor Residual Report", ""]
    if latest.empty:
        lines.append("No factor residuals are available yet.")
    else:
        for _, row in latest.iterrows():
            lines.extend(
                [
                    f"## {row['ticker']}",
                    "",
                    f"- beta_qqq_60d: {_fmt(row['beta_qqq'])}",
                    f"- beta_soxx_60d: {_fmt(row['beta_soxx'])}",
                    f"- beta_tnx_bps_60d: {_fmt(row['beta_tnx_bps'])}",
                    f"- r2_60d: {_fmt(row['r2'])}",
                    f"- factor_corr_qqq_soxx: {_fmt(row['factor_corr_qqq_soxx'])}",
                    f"- residual_return_20d: {_fmt_pct(row['residual_return_20d'])}",
                    f"- residual_return_60d: {_fmt_pct(row['residual_return_60d'])}",
                    f"- data_quality_flag: {row['data_quality_flag']}",
                    "",
                ]
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _load_stock_returns(tickers: list[str]) -> pd.DataFrame:
    initialize_database()
    with connect() as conn:
        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close
            FROM prices
            WHERE ticker IN (SELECT unnest(?))
            ORDER BY date, ticker
            """,
            [tickers],
        ).fetchdf()
    if prices.empty:
        return pd.DataFrame()
    price = _price_pivot(prices)
    return price.pct_change()


def _load_market_factor_inputs() -> pd.DataFrame:
    initialize_database()
    with connect() as conn:
        inputs = conn.execute(
            """
            SELECT date, qqq_return_1d, soxx_return_1d, delta_tnx_bps
            FROM market_factor_inputs
            ORDER BY date
            """
        ).fetchdf()
    if inputs.empty:
        return pd.DataFrame()
    inputs["date"] = pd.to_datetime(inputs["date"])
    return inputs


def _load_factor_exposures(model_name: str, lookback_window: int) -> pd.DataFrame:
    initialize_database()
    with connect() as conn:
        exposures = conn.execute(
            """
            SELECT *
            FROM factor_exposures
            WHERE model_name = ?
              AND lookback_window = ?
            ORDER BY date, ticker
            """,
            [model_name, lookback_window],
        ).fetchdf()
    if exposures.empty:
        return pd.DataFrame()
    exposures["date"] = pd.to_datetime(exposures["date"])
    return exposures


def _price_pivot(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["price"] = frame["adj_close"].fillna(frame["close"])
    return frame.pivot(index="date", columns="ticker", values="price").sort_index()


def _semi_specific_return(frame: pd.DataFrame, lookback_window: int = DEFAULT_WINDOW) -> pd.Series:
    residual = pd.Series(index=frame.index, dtype="float64")
    qqq = frame["qqq_return_1d"]
    soxx = frame["soxx_return_1d"]
    for index in range(lookback_window, len(frame)):
        sample = pd.concat(
            [soxx.rename("soxx"), qqq.rename("qqq")],
            axis=1,
        ).iloc[index - lookback_window : index].dropna()
        if len(sample) < DEFAULT_MIN_OBS or pd.isna(soxx.iloc[index]) or pd.isna(qqq.iloc[index]):
            continue
        coefficients, _ = _ols(sample["soxx"], sample[["qqq"]])
        residual.iloc[index] = soxx.iloc[index] - (
            coefficients[0] + coefficients[1] * qqq.iloc[index]
        )
    return residual


def _ols(y: pd.Series, x: pd.DataFrame) -> tuple[np.ndarray, float]:
    y_array = y.to_numpy(dtype="float64")
    x_array = x.to_numpy(dtype="float64")
    x_array = np.column_stack([np.ones(len(x_array)), x_array])
    coefficients, _, _, _ = np.linalg.lstsq(x_array, y_array, rcond=None)
    fitted = x_array @ coefficients
    residual = y_array - fitted
    total = y_array - y_array.mean()
    rss = float(np.sum(residual**2))
    tss = float(np.sum(total**2))
    r2 = np.nan if tss == 0 else 1.0 - rss / tss
    return coefficients, r2


def _factor_corr(sample: pd.DataFrame) -> float:
    if len(sample) < 2:
        return float("nan")
    return float(sample["qqq_return_1d"].corr(sample["soxx_return_1d"]))


def _exposure_quality(factor_corr_qqq_soxx: float) -> str:
    if pd.notna(factor_corr_qqq_soxx) and abs(factor_corr_qqq_soxx) >= 0.9:
        return "high_collinearity"
    return "complete"


def _factor_residual_row(
    date: pd.Timestamp,
    ticker: str,
    stock_return: float,
    factor_frame: pd.DataFrame,
    exposure_frame: pd.DataFrame,
    model_name: str,
    lookback_window: int,
    ingested_at,
) -> dict:
    base = {
        "date": date.date(),
        "ticker": ticker,
        "model_name": model_name,
        "lookback_window": lookback_window,
        "stock_return_1d": stock_return,
        "expected_return_1d": np.nan,
        "residual_return_1d": np.nan,
        "market_contribution_1d": np.nan,
        "sector_contribution_1d": np.nan,
        "rate_contribution_1d": np.nan,
        "alpha_contribution_1d": np.nan,
        "residual_return_5d": np.nan,
        "residual_return_20d": np.nan,
        "residual_return_60d": np.nan,
        "data_quality_flag": "missing_factor_input",
        "ingested_at": ingested_at,
    }
    if date not in factor_frame.index or (date, ticker) not in exposure_frame.index:
        return base
    factors = factor_frame.loc[date]
    exposure = exposure_frame.loc[(date, ticker)]
    if exposure["data_quality_flag"] == "insufficient_observations":
        base["data_quality_flag"] = "insufficient_observations"
        return base
    if factors.isna().any():
        return base

    alpha = float(exposure["alpha_daily"])
    market = float(exposure["beta_qqq"]) * float(factors["qqq_return_1d"])
    sector = float(exposure["beta_soxx"]) * float(factors["soxx_return_1d"])
    rate = float(exposure["beta_tnx_bps"]) * float(factors["delta_tnx_bps"])
    expected = alpha + market + sector + rate
    base.update(
        {
            "expected_return_1d": expected,
            "residual_return_1d": float(stock_return) - expected,
            "market_contribution_1d": market,
            "sector_contribution_1d": sector,
            "rate_contribution_1d": rate,
            "alpha_contribution_1d": alpha,
            "data_quality_flag": exposure["data_quality_flag"],
        }
    )
    return base


def _add_cumulative_residuals(residuals: pd.DataFrame) -> pd.DataFrame:
    result = residuals.sort_values(["ticker", "date"]).copy()
    for lookback_window in (5, 20, 60):
        result[f"residual_return_{lookback_window}d"] = (
            result.groupby("ticker")["residual_return_1d"]
            .transform(
                lambda series, window=lookback_window: (
                    (1.0 + series).rolling(window).apply(np.prod, raw=True) - 1.0
                )
            )
        )
    return result


def _residual_diagnostic_row(
    ticker: str,
    clean: pd.DataFrame,
    as_of_date,
    model_name: str,
    lookback_window: int,
    window_days: int,
    ingested_at,
) -> dict:
    window = clean.tail(window_days).copy()
    residuals = window["residual_return_1d"].astype(float)
    abs_sum = float(residuals.abs().sum())
    top_abs = residuals.abs().sort_values(ascending=False)
    data_quality = "complete" if len(window) >= window_days else "insufficient_window"
    max_positive = window.loc[residuals.idxmax()] if not window.empty else None
    max_negative = window.loc[residuals.idxmin()] if not window.empty else None
    return {
        "as_of_date": as_of_date,
        "ticker": ticker,
        "model_name": model_name,
        "lookback_window": lookback_window,
        "window_days": window_days,
        "residual_return": float((1.0 + residuals).prod() - 1.0) if not window.empty else np.nan,
        "top_1_day_contribution_pct": (
            float(top_abs.head(1).sum() / abs_sum) if abs_sum else np.nan
        ),
        "top_3_days_contribution_pct": (
            float(top_abs.head(3).sum() / abs_sum) if abs_sum else np.nan
        ),
        "positive_residual_days": int((residuals > 0).sum()),
        "negative_residual_days": int((residuals < 0).sum()),
        "residual_hit_rate": float((residuals > 0).mean()) if not window.empty else np.nan,
        "max_positive_residual_day": (
            pd.to_datetime(max_positive["date"]).date() if max_positive is not None else None
        ),
        "max_negative_residual_day": (
            pd.to_datetime(max_negative["date"]).date() if max_negative is not None else None
        ),
        "data_quality_flag": data_quality,
        "ingested_at": ingested_at,
    }


def _market_factor_columns() -> list[str]:
    return [
        "date",
        "qqq_return_1d",
        "soxx_return_1d",
        "smh_return_1d",
        "spy_return_1d",
        "tnx_close",
        "delta_tnx_bps",
        "semi_specific_return_1d",
        "data_quality_flag",
        "source",
        "ingested_at",
    ]


def _factor_exposure_columns() -> list[str]:
    return [
        "date",
        "ticker",
        "model_name",
        "lookback_window",
        "n_obs",
        "alpha_daily",
        "beta_qqq",
        "beta_soxx",
        "beta_tnx_bps",
        "r2",
        "factor_corr_qqq_soxx",
        "data_quality_flag",
        "ingested_at",
    ]


def _factor_residual_columns() -> list[str]:
    return [
        "date",
        "ticker",
        "model_name",
        "lookback_window",
        "stock_return_1d",
        "expected_return_1d",
        "residual_return_1d",
        "market_contribution_1d",
        "sector_contribution_1d",
        "rate_contribution_1d",
        "alpha_contribution_1d",
        "residual_return_5d",
        "residual_return_20d",
        "residual_return_60d",
        "data_quality_flag",
        "ingested_at",
    ]


def _residual_diagnostic_columns() -> list[str]:
    return [
        "as_of_date",
        "ticker",
        "model_name",
        "lookback_window",
        "window_days",
        "residual_return",
        "top_1_day_contribution_pct",
        "top_3_days_contribution_pct",
        "positive_residual_days",
        "negative_residual_days",
        "residual_hit_rate",
        "max_positive_residual_day",
        "max_negative_residual_day",
        "data_quality_flag",
        "ingested_at",
    ]


def _fmt(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def _fmt_pct(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"
