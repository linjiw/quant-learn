"""Forward scenario estimates and investability scorecards.

This module deliberately avoids single-point target prices. It builds a
probabilistic price cone and a decision-support scorecard from observable
factors: trend, residual strength, risk, quality, and valuation discipline.
"""

from dataclasses import dataclass
from datetime import date
from math import erf, exp, sqrt
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quant_learn.config import CORE_TICKERS, EXPORT_DIR, ensure_directories
from quant_learn.db import connect, initialize_database, upsert_dataframe
from quant_learn.time import utc_now_naive

HORIZON_DAYS = [21, 63, 126, 252]
VALIDATION_HORIZON_DAYS = [21, 63, 126]
# Empirically calibrated on 2018-2026 data so p10-p90 cones avoid systematic
# undercoverage across the four-stock universe and 21/63/126 day horizons.
TAIL_RISK_MULTIPLIER = 1.45
MAX_MODEL_CONFIDENCE = 75.0
Z_SCORES = {
    "p10_price": -1.2815515655446004,
    "p25_price": -0.6744897501960817,
    "p50_price": 0.0,
    "p75_price": 0.6744897501960817,
    "p90_price": 1.2815515655446004,
}
METHOD = "momentum_residual_vol_cone_v2_tail_adjusted"


@dataclass(frozen=True)
class AnalysisInputs:
    latest_prices: pd.DataFrame
    latest_factor: pd.DataFrame
    fundamentals: pd.DataFrame
    valuations: pd.DataFrame
    events: pd.DataFrame


def run_forward_analysis(tickers: Optional[list[str]] = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build and store forward price estimates and investability scorecards."""

    ticker_list = tickers or CORE_TICKERS
    inputs = _load_inputs(ticker_list)
    estimates = build_forward_price_estimates(inputs, ticker_list)
    scorecard = build_investment_scorecard(inputs, estimates, ticker_list)
    validation = build_forward_model_validation(ticker_list)
    store_forward_analysis(estimates, scorecard, validation)
    return estimates, scorecard


def build_forward_price_estimates(
    inputs: AnalysisInputs,
    tickers: list[str],
) -> pd.DataFrame:
    """Create lognormal price cones from drift and realized-vol assumptions."""

    rows = []
    ingested_at = utc_now_naive()
    as_of_date = inputs.latest_prices["date"].max()
    factor = inputs.latest_factor.set_index("ticker")
    prices = inputs.latest_prices.set_index("ticker")

    for ticker in tickers:
        if ticker not in prices.index or ticker not in factor.index:
            continue
        current_price = float(prices.loc[ticker, "price"])
        annualized_mu = _estimate_annualized_drift(factor.loc[ticker])
        realized_vol = _safe_number(factor.loc[ticker, "realized_vol_60d"], default=np.nan)
        annualized_vol = realized_vol * TAIL_RISK_MULTIPLIER
        if pd.isna(annualized_vol) or annualized_vol <= 0:
            annualized_vol = 0.55

        for horizon_days in HORIZON_DAYS:
            years = horizon_days / 252.0
            expected_return = exp(annualized_mu * years) - 1.0
            expected_price = current_price * (1.0 + expected_return)
            row = {
                "as_of_date": as_of_date,
                "ticker": ticker,
                "horizon_days": horizon_days,
                "current_price": current_price,
                "expected_return": expected_return,
                "expected_price": expected_price,
                "probability_gain": _probability_gain(annualized_mu, annualized_vol, years),
                "annualized_mu": annualized_mu,
                "annualized_vol": annualized_vol,
                "method": METHOD,
                "ingested_at": ingested_at,
            }
            for column, z_score in Z_SCORES.items():
                row[column] = current_price * exp(
                    annualized_mu * years + z_score * annualized_vol * sqrt(years)
                )
            rows.append(row)

    return pd.DataFrame(rows)


def build_investment_scorecard(
    inputs: AnalysisInputs,
    estimates: pd.DataFrame,
    tickers: list[str],
) -> pd.DataFrame:
    """Build a current investability scorecard."""

    rows = []
    ingested_at = utc_now_naive()
    as_of_date = inputs.latest_prices["date"].max()
    factor = inputs.latest_factor.set_index("ticker")
    fundamentals = inputs.fundamentals.set_index("ticker")
    valuations = inputs.valuations.set_index("ticker")

    for ticker in tickers:
        if ticker not in factor.index:
            continue
        factor_row = factor.loc[ticker]
        fundamental_row = fundamentals.loc[ticker] if ticker in fundamentals.index else pd.Series()
        valuation_row = valuations.loc[ticker] if ticker in valuations.index else pd.Series()

        momentum_score = _momentum_score(factor_row)
        alpha_score = _alpha_score(factor_row)
        quality_score = _quality_score(fundamental_row)
        valuation_score, valuation_flags = _valuation_score(valuation_row)
        risk_score, risk_flags = _risk_score(factor_row)
        event_score, event_flags = _event_score(inputs.events, ticker, as_of_date)
        data_quality_score, data_quality_flags = _data_quality_score(
            inputs,
            ticker,
            as_of_date,
        )

        investability_score = (
            0.25 * momentum_score
            + 0.20 * alpha_score
            + 0.20 * quality_score
            + 0.15 * valuation_score
            + 0.15 * risk_score
            + 0.05 * event_score
        )
        flags = valuation_flags + risk_flags + event_flags + data_quality_flags
        model_confidence, confidence_cap_reason = _model_confidence(
            investability_score,
            data_quality_score,
            risk_score,
            flags,
        )
        decision_label = _decision_label(
            investability_score,
            momentum_score,
            valuation_score,
            risk_score,
            data_quality_score,
            model_confidence,
            len(flags),
        )
        notes = _decision_notes(
            ticker,
            factor_row,
            fundamental_row,
            valuation_row,
            estimates,
            decision_label,
        )
        rows.append(
            {
                "as_of_date": as_of_date,
                "ticker": ticker,
                "decision_label": decision_label,
                "investability_score": round(investability_score, 2),
                "momentum_score": round(momentum_score, 2),
                "alpha_score": round(alpha_score, 2),
                "quality_score": round(quality_score, 2),
                "valuation_score": round(valuation_score, 2),
                "risk_score": round(risk_score, 2),
                "event_score": round(event_score, 2),
                "data_quality_score": round(data_quality_score, 2),
                "model_confidence": round(model_confidence, 2),
                "confidence_cap_reason": confidence_cap_reason,
                "key_flags": "; ".join(flags),
                "notes": notes,
                "ingested_at": ingested_at,
            }
        )

    return pd.DataFrame(rows)


def build_forward_model_validation(tickers: Optional[list[str]] = None) -> pd.DataFrame:
    """Validate historical price-cone coverage using factor data available at each date."""

    ticker_list = tickers or CORE_TICKERS
    initialize_database()
    with connect() as conn:
        factors = conn.execute(
            """
            SELECT date, ticker, return_20d, return_60d, return_120d,
                   rel_qqq_60d, rel_soxx_60d, residual_return_60d,
                   realized_vol_60d
            FROM factor_dashboard
            WHERE ticker IN (SELECT unnest(?))
            ORDER BY ticker, date
            """,
            [ticker_list],
        ).fetchdf()
        prices = conn.execute(
            """
            SELECT date, ticker, coalesce(adj_close, close) AS price
            FROM prices
            WHERE ticker IN (SELECT unnest(?))
            ORDER BY ticker, date
            """,
            [ticker_list],
        ).fetchdf()

    if factors.empty or prices.empty:
        return pd.DataFrame()

    factors["date"] = pd.to_datetime(factors["date"])
    prices["date"] = pd.to_datetime(prices["date"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    validation_date = pd.Timestamp(date.today()).date()
    ingested_at = utc_now_naive()
    rows = []

    for ticker in ticker_list:
        ticker_factors = factors[factors["ticker"] == ticker].dropna(
            subset=["return_60d", "realized_vol_60d"]
        )
        if ticker_factors.empty or ticker not in price.columns:
            continue
        for horizon_days in VALIDATION_HORIZON_DAYS:
            observations = []
            for _, factor_row in ticker_factors.iterrows():
                as_of = factor_row["date"]
                if as_of not in price.index:
                    continue
                start_index = price.index.get_loc(as_of)
                end_index = start_index + horizon_days
                if end_index >= len(price.index):
                    continue
                current_price = price.iloc[start_index][ticker]
                future_price = price.iloc[end_index][ticker]
                if pd.isna(current_price) or pd.isna(future_price) or current_price <= 0:
                    continue
                mu = _estimate_annualized_drift(factor_row)
                vol = _safe_number(factor_row["realized_vol_60d"], np.nan) * TAIL_RISK_MULTIPLIER
                if pd.isna(vol) or vol <= 0:
                    continue
                years = horizon_days / 252.0
                p10 = current_price * exp(mu * years + Z_SCORES["p10_price"] * vol * sqrt(years))
                p25 = current_price * exp(mu * years + Z_SCORES["p25_price"] * vol * sqrt(years))
                p50 = current_price * exp(mu * years)
                p75 = current_price * exp(mu * years + Z_SCORES["p75_price"] * vol * sqrt(years))
                p90 = current_price * exp(mu * years + Z_SCORES["p90_price"] * vol * sqrt(years))
                realized_return = future_price / current_price - 1.0
                expected_return = p50 / current_price - 1.0
                observations.append(
                    {
                        "inside_10_90": p10 <= future_price <= p90,
                        "inside_25_75": p25 <= future_price <= p75,
                        "direction_correct": (p50 >= current_price)
                        == (future_price >= current_price),
                        "realized_return": realized_return,
                        "expected_return": expected_return,
                    }
                )
            if not observations:
                continue
            sample = pd.DataFrame(observations)
            rows.append(
                {
                    "validation_date": validation_date,
                    "ticker": ticker,
                    "horizon_days": horizon_days,
                    "sample_size": len(sample),
                    "p10_p90_coverage": sample["inside_10_90"].mean(),
                    "p25_p75_coverage": sample["inside_25_75"].mean(),
                    "median_direction_accuracy": sample["direction_correct"].mean(),
                    "mean_realized_return": sample["realized_return"].mean(),
                    "mean_expected_return": sample["expected_return"].mean(),
                    "method": METHOD,
                    "ingested_at": ingested_at,
                }
            )

    return pd.DataFrame(rows)


def store_forward_analysis(
    estimates: pd.DataFrame,
    scorecard: pd.DataFrame,
    validation: Optional[pd.DataFrame] = None,
) -> tuple[int, int, int]:
    """Store forward-analysis tables."""

    initialize_database()
    with connect() as conn:
        estimate_count = upsert_dataframe(
            conn,
            estimates,
            "forward_price_estimates",
            ["as_of_date", "ticker", "horizon_days", "method"],
        )
        scorecard_count = upsert_dataframe(
            conn,
            scorecard,
            "investment_scorecard",
            ["as_of_date", "ticker"],
        )
        validation_count = 0
        if validation is not None and not validation.empty:
            validation_count = upsert_dataframe(
                conn,
                validation,
                "forward_model_validation",
                ["validation_date", "ticker", "horizon_days", "method"],
            )
    return estimate_count, scorecard_count, validation_count


def export_forward_analysis_report(
    estimates: pd.DataFrame,
    scorecard: pd.DataFrame,
    validation: Optional[pd.DataFrame] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Export CSVs, charts, and a markdown report."""

    ensure_directories()
    target_dir = output_dir or EXPORT_DIR
    figures_dir = target_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    estimates.to_csv(target_dir / "forward_price_estimates.csv", index=False)
    scorecard.to_csv(target_dir / "investment_scorecard.csv", index=False)
    if validation is None:
        validation = build_forward_model_validation(list(scorecard["ticker"].unique()))
    validation.to_csv(target_dir / "forward_model_validation.csv", index=False)

    cone_path = figures_dir / "forward_price_cones.png"
    score_path = figures_dir / "investment_scorecard.png"
    validation_path = figures_dir / "forward_model_validation.png"
    _plot_forward_price_cones(estimates, cone_path)
    _plot_scorecard(scorecard, score_path)
    _plot_validation(validation, validation_path)

    report_path = target_dir / "forward_investment_report.md"
    report_path.write_text(
        _render_report(
            estimates,
            scorecard,
            validation,
            cone_path.relative_to(target_dir),
            score_path.relative_to(target_dir),
            validation_path.relative_to(target_dir),
        ),
        encoding="utf-8",
    )
    return report_path


def _load_inputs(tickers: list[str]) -> AnalysisInputs:
    initialize_database()
    with connect() as conn:
        latest_price_date = conn.execute("SELECT max(date) FROM prices").fetchone()[0]
        latest_factor_date = conn.execute("SELECT max(date) FROM factor_dashboard").fetchone()[0]
        latest_valuation_date = conn.execute(
            "SELECT max(snapshot_date) FROM valuation_snapshots"
        ).fetchone()[0]

        latest_prices = conn.execute(
            """
            SELECT date, ticker, coalesce(adj_close, close) AS price
            FROM prices
            WHERE date = ?
              AND ticker IN (SELECT unnest(?))
            ORDER BY ticker
            """,
            [latest_price_date, tickers],
        ).fetchdf()
        latest_factor = conn.execute(
            """
            SELECT *
            FROM factor_dashboard
            WHERE date = ?
              AND ticker IN (SELECT unnest(?))
            ORDER BY ticker
            """,
            [latest_factor_date, tickers],
        ).fetchdf()
        fundamentals = conn.execute(
            """
            SELECT ticker, fiscal_year, fiscal_quarter, period_end, revenue,
                   gross_margin, operating_margin, free_cash_flow
            FROM fundamentals_quarterly
            WHERE ticker IN (SELECT unnest(?))
            QUALIFY row_number() OVER (
                PARTITION BY ticker ORDER BY period_end DESC, fiscal_quarter DESC
            ) = 1
            ORDER BY ticker
            """,
            [tickers],
        ).fetchdf()
        if latest_valuation_date is None:
            valuations = pd.DataFrame()
        else:
            valuations = conn.execute(
                """
                SELECT *
                FROM valuation_snapshots
                WHERE snapshot_date = ?
                  AND ticker IN (SELECT unnest(?))
                ORDER BY ticker
                """,
                [latest_valuation_date, tickers],
            ).fetchdf()
        events = conn.execute(
            """
            SELECT event_date, ticker, event_type, event_name, importance_score
            FROM events
            WHERE ticker IN (SELECT unnest(?))
            ORDER BY event_date
            """,
            [tickers],
        ).fetchdf()

    latest_prices["date"] = pd.to_datetime(latest_prices["date"]).dt.date
    if not latest_factor.empty:
        latest_factor["date"] = pd.to_datetime(latest_factor["date"]).dt.date
    if not fundamentals.empty:
        fundamentals["period_end"] = pd.to_datetime(fundamentals["period_end"]).dt.date
    if not valuations.empty:
        valuations["snapshot_date"] = pd.to_datetime(valuations["snapshot_date"]).dt.date
    if not events.empty:
        events["event_date"] = pd.to_datetime(events["event_date"]).dt.date

    return AnalysisInputs(
        latest_prices=latest_prices,
        latest_factor=latest_factor,
        fundamentals=fundamentals,
        valuations=valuations,
        events=events,
    )


def _estimate_annualized_drift(factor_row: pd.Series) -> float:
    return_60d = _safe_number(factor_row.get("return_60d"), 0.0)
    return_120d = _safe_number(factor_row.get("return_120d"), 0.0)
    residual_60d = _safe_number(factor_row.get("residual_return_60d"), 0.0)
    mom60 = _annualize_return(return_60d, 60, -0.60, 1.20)
    mom120 = _annualize_return(return_120d, 120, -0.50, 1.00)
    residual = _annualize_return(residual_60d, 60, -0.40, 0.80)
    raw_mu = 0.45 * mom60 + 0.25 * mom120 + 0.30 * residual
    return float(np.clip(0.35 * raw_mu, -0.35, 0.55))


def _annualize_return(period_return: float, days: int, low: float, high: float) -> float:
    if period_return <= -0.95:
        return low
    annualized = (1.0 + period_return) ** (252.0 / days) - 1.0
    return float(np.clip(annualized, low, high))


def _probability_gain(mu: float, sigma: float, years: float) -> float:
    if sigma <= 0 or years <= 0:
        return 1.0 if mu > 0 else 0.0
    z = (mu * years) / (sigma * sqrt(years))
    return float(_normal_cdf(z))


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _momentum_score(row: pd.Series) -> float:
    return float(
        np.mean(
            [
                _centered_score(_safe_number(row.get("return_20d"), 0.0), 0.12),
                _centered_score(_safe_number(row.get("return_60d"), 0.0), 0.25),
                _centered_score(_safe_number(row.get("return_120d"), 0.0), 0.35),
                _centered_score(_safe_number(row.get("rel_qqq_60d"), 0.0), 0.18),
            ]
        )
    )


def _alpha_score(row: pd.Series) -> float:
    return float(
        0.55 * _centered_score(_safe_number(row.get("residual_return_60d"), 0.0), 0.16)
        + 0.25 * _centered_score(_safe_number(row.get("rel_qqq_60d"), 0.0), 0.18)
        + 0.20 * _centered_score(_safe_number(row.get("rel_soxx_60d"), 0.0), 0.18)
    )


def _quality_score(row: pd.Series) -> float:
    if row.empty:
        return 50.0
    gross_margin = _safe_number(row.get("gross_margin"), np.nan)
    operating_margin = _safe_number(row.get("operating_margin"), np.nan)
    revenue = _safe_number(row.get("revenue"), np.nan)
    free_cash_flow = _safe_number(row.get("free_cash_flow"), np.nan)
    fcf_margin = free_cash_flow / revenue if revenue and not pd.isna(free_cash_flow) else np.nan
    components = []
    if not pd.isna(gross_margin):
        components.append(_range_score(gross_margin, 0.35, 0.75))
    if not pd.isna(operating_margin):
        components.append(_range_score(operating_margin, 0.10, 0.55))
    if not pd.isna(fcf_margin):
        components.append(_range_score(fcf_margin, 0.05, 0.45))
    return float(np.mean(components)) if components else 50.0


def _valuation_score(row: pd.Series) -> tuple[float, list[str]]:
    if row.empty:
        return 50.0, ["missing valuation snapshot"]
    flags = []
    components = []
    multiple_specs = [
        ("forward_pe", 15.0, 60.0),
        ("trailing_pe", 18.0, 90.0),
        ("price_to_sales", 4.0, 25.0),
        ("ev_to_ebitda", 10.0, 65.0),
    ]
    for column, low, high in multiple_specs:
        value = _safe_number(row.get(column), np.nan)
        if pd.isna(value) or value <= 0:
            continue
        components.append(100.0 - _range_score(value, low, high))
        if value >= high:
            flags.append(f"high {column} {value:.1f}")
    if not components:
        return 50.0, ["valuation fields unavailable"]
    score = float(np.mean(components))
    if row.name == "TSM":
        flags.append("ADR valuation fields need source verification")
    return score, flags


def _risk_score(row: pd.Series) -> tuple[float, list[str]]:
    flags = []
    vol = _safe_number(row.get("realized_vol_60d"), np.nan)
    beta = _safe_number(row.get("beta_qqq_60d"), np.nan)
    drawdown = _safe_number(row.get("max_drawdown_120d"), np.nan)

    vol_score = 50.0 if pd.isna(vol) else 100.0 - _range_score(vol, 0.25, 0.90)
    beta_score = 50.0 if pd.isna(beta) else 100.0 - _range_score(beta, 0.9, 2.5)
    drawdown_score = 50.0 if pd.isna(drawdown) else 100.0 - _range_score(abs(drawdown), 0.08, 0.35)

    if not pd.isna(vol) and vol > 0.65:
        flags.append(f"high 60d vol {vol:.0%}")
    if not pd.isna(beta) and beta > 1.8:
        flags.append(f"high QQQ beta {beta:.2f}")
    if not pd.isna(drawdown) and drawdown < -0.25:
        flags.append(f"large 120d drawdown {drawdown:.0%}")

    return float(np.mean([vol_score, beta_score, drawdown_score])), flags


def _event_score(events: pd.DataFrame, ticker: str, as_of_date) -> tuple[float, list[str]]:
    if events.empty:
        return 40.0, ["no curated event calendar loaded"]
    upcoming = events[(events["ticker"] == ticker) & (events["event_date"] >= as_of_date)].copy()
    if upcoming.empty:
        return 50.0, []
    upcoming["days_until"] = (
        pd.to_datetime(upcoming["event_date"]) - pd.Timestamp(as_of_date)
    ).dt.days
    near = upcoming[upcoming["days_until"] <= 14]
    if near.empty:
        return 55.0, []
    event_names = ", ".join(near["event_type"].head(3).astype(str).tolist())
    return 35.0, [f"near-term event risk: {event_names}"]


def _data_quality_score(
    inputs: AnalysisInputs,
    ticker: str,
    as_of_date,
) -> tuple[float, list[str]]:
    score = 100.0
    flags = []
    price_row = inputs.latest_prices[inputs.latest_prices["ticker"] == ticker]
    factor_row = inputs.latest_factor[inputs.latest_factor["ticker"] == ticker]
    fundamental_row = inputs.fundamentals[inputs.fundamentals["ticker"] == ticker]
    valuation_row = inputs.valuations[inputs.valuations["ticker"] == ticker]

    if price_row.empty:
        score -= 35
        flags.append("missing latest price")
    else:
        price_date = price_row.iloc[0]["date"]
        staleness_days = (date.today() - price_date).days
        if staleness_days > 5:
            score -= 20
            flags.append(f"stale price data {staleness_days}d")

    if factor_row.empty:
        score -= 25
        flags.append("missing factor row")
    if fundamental_row.empty:
        score -= 15
        flags.append("missing standardized fundamentals")
    if valuation_row.empty:
        score -= 20
        flags.append("missing valuation snapshot")
    if inputs.events.empty:
        score -= 15
        flags.append("no event data for decision gating")
    elif inputs.events[inputs.events["ticker"] == ticker].empty:
        score -= 10
        flags.append("no ticker-specific events")

    return float(np.clip(score, 0.0, 100.0)), flags


def _model_confidence(
    investability_score: float,
    data_quality_score: float,
    risk_score: float,
    flags: list[str],
) -> tuple[float, str]:
    confidence = min(MAX_MODEL_CONFIDENCE, data_quality_score, 35.0 + 0.45 * investability_score)
    reasons = [f"hard cap {MAX_MODEL_CONFIDENCE:.0f}% because market outcomes are uncertain"]
    if data_quality_score < MAX_MODEL_CONFIDENCE:
        reasons.append(f"data quality cap {data_quality_score:.0f}%")
    if risk_score < 40:
        confidence = min(confidence, 55.0)
        reasons.append("risk cap 55%")
    if any("no curated event" in flag or "no event data" in flag for flag in flags):
        confidence = min(confidence, 60.0)
        reasons.append("event-data cap 60%")
    if any("valuation" in flag and "unavailable" not in flag for flag in flags):
        confidence = min(confidence, 65.0)
        reasons.append("valuation-verification cap 65%")
    return float(np.clip(confidence, 0.0, MAX_MODEL_CONFIDENCE)), "; ".join(reasons)


def _decision_label(
    score: float,
    momentum_score: float,
    valuation_score: float,
    risk_score: float,
    data_quality_score: float,
    model_confidence: float,
    flag_count: int,
) -> str:
    if data_quality_score < 60 or model_confidence < 50:
        return "Insufficient confidence / improve data"
    if momentum_score >= 75 and (risk_score < 40 or valuation_score < 35):
        return "Strong momentum, elevated risk"
    if (
        score >= 75
        and risk_score >= 45
        and valuation_score >= 40
        and model_confidence >= 65
        and flag_count <= 2
    ):
        return "Research candidate"
    if score >= 60 and risk_score >= 35:
        return "Watchlist / wait for setup"
    return "High-risk / needs better setup"


def _decision_notes(
    ticker: str,
    factor_row: pd.Series,
    fundamental_row: pd.Series,
    valuation_row: pd.Series,
    estimates: pd.DataFrame,
    decision_label: str,
) -> str:
    one_year = estimates[(estimates["ticker"] == ticker) & (estimates["horizon_days"] == 252)]
    if one_year.empty:
        cone_text = "no price cone available"
    else:
        row = one_year.iloc[0]
        cone_text = (
            f"1y cone p10/p50/p90={row['p10_price']:.2f}/"
            f"{row['p50_price']:.2f}/{row['p90_price']:.2f}"
        )
    return_60d = _safe_number(factor_row.get("return_60d"), np.nan)
    rel_qqq = _safe_number(factor_row.get("rel_qqq_60d"), np.nan)
    forward_pe = _safe_number(valuation_row.get("forward_pe"), np.nan)
    operating_margin = _safe_number(fundamental_row.get("operating_margin"), np.nan)
    parts = [
        decision_label,
        cone_text,
        f"60d return={return_60d:.1%}" if not pd.isna(return_60d) else "60d return unavailable",
        f"vs QQQ={rel_qqq:.1%}" if not pd.isna(rel_qqq) else "relative strength unavailable",
    ]
    if not pd.isna(forward_pe):
        parts.append(f"forward PE={forward_pe:.1f}")
    if not pd.isna(operating_margin):
        parts.append(f"operating margin={operating_margin:.1%}")
    return "; ".join(parts)


def _centered_score(value: float, scale: float) -> float:
    return float(np.clip(50.0 + 50.0 * np.tanh(value / scale), 0.0, 100.0))


def _range_score(value: float, low: float, high: float) -> float:
    if pd.isna(value):
        return 50.0
    return float(np.clip(100.0 * (value - low) / (high - low), 0.0, 100.0))


def _safe_number(value, default=np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _plot_forward_price_cones(estimates: pd.DataFrame, path: Path) -> None:
    if estimates.empty:
        return
    tickers = list(estimates["ticker"].unique())
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for ax, ticker in zip(axes.flatten(), tickers):
        subset = estimates[estimates["ticker"] == ticker].sort_values("horizon_days")
        x = subset["horizon_days"]
        ax.plot(x, subset["p50_price"], label="p50", linewidth=2.4)
        ax.fill_between(x, subset["p10_price"], subset["p90_price"], alpha=0.18, label="p10-p90")
        ax.fill_between(x, subset["p25_price"], subset["p75_price"], alpha=0.25, label="p25-p75")
        ax.axhline(subset["current_price"].iloc[0], color="#333333", linestyle="--", linewidth=1)
        ax.set_title(ticker)
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.25)
    axes[-1, 0].set_xlabel("Horizon days")
    axes[-1, 1].set_xlabel("Horizon days")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3)
    fig.suptitle("Forward Price Cones: Scenario Ranges, Not Targets", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_scorecard(scorecard: pd.DataFrame, path: Path) -> None:
    if scorecard.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    sorted_scorecard = scorecard.sort_values("investability_score", ascending=True)
    ax.barh(sorted_scorecard["ticker"], sorted_scorecard["investability_score"], color="#4c78a8")
    ax.axvline(60, color="#d28b26", linestyle="--", linewidth=1)
    ax.axvline(75, color="#228b68", linestyle="--", linewidth=1)
    ax.set_xlim(0, 100)
    ax.set_title("Investability Scorecard")
    ax.set_xlabel("Score, 0-100")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_validation(validation: pd.DataFrame, path: Path) -> None:
    if validation.empty:
        return
    latest_validation_date = validation["validation_date"].max()
    latest = validation[validation["validation_date"] == latest_validation_date]
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = [f"{row.ticker}-{row.horizon_days}d" for row in latest.itertuples()]
    ax.bar(labels, latest["p10_p90_coverage"], color="#4c78a8", label="p10-p90 coverage")
    ax.axhline(0.80, color="#d28b26", linestyle="--", linewidth=1, label="Expected 80%")
    ax.set_ylim(0, 1)
    ax.set_title("Historical Price-Cone Coverage")
    ax.set_ylabel("Empirical coverage")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _render_report(
    estimates: pd.DataFrame,
    scorecard: pd.DataFrame,
    validation: pd.DataFrame,
    cone_path: Path,
    score_path: Path,
    validation_path: Path,
) -> str:
    as_of_date = scorecard["as_of_date"].max() if not scorecard.empty else ""
    score_table = _format_scorecard(scorecard)
    estimate_table = _format_estimates(estimates)
    validation_table = _format_validation(validation)
    return f"""# Forward Estimate And Investment Decision Report

As of: {as_of_date}

This is decision support, not investment advice. The price estimates are
distribution ranges from current trend, residual strength, and realized
volatility. They are not target prices. Model confidence is deliberately capped
below 100% because market outcomes cannot be known with certainty.

## Decision Process

1. Check data freshness.
2. Estimate forward price distribution, not a point target.
3. Separate trend from QQQ/SOXX beta.
4. Check quality from fundamentals.
5. Check valuation discipline from current multiples.
6. Penalize high beta, volatility, drawdown, and near-term event risk.
7. Label the setup as research candidate, watchlist, strong momentum/elevated
   risk, or high-risk.

## Scorecard

![Investment scorecard]({score_path})

{score_table}

Confidence means process confidence, not outcome certainty. A 60% confidence row
can still be wrong, and a low-confidence row can still rise.

## Price Cone Summary

![Forward price cones]({cone_path})

{estimate_table}

## Historical Coverage Check

![Forward model validation]({validation_path})

{validation_table}

Expected coverage is roughly 80% for p10-p90 and 50% for p25-p75. Persistent
undercoverage means the cone is too narrow or the drift assumption is unstable.

## How To Use This

- Use `p10-p90` as a risk range, not a forecast promise.
- A strong score means the setup deserves research time, not automatic buying.
- A weak valuation score does not mean the stock must fall; it means the margin
  for disappointment is lower.
- A high risk score is good. A low risk score means beta, volatility, or
  drawdown is already elevated.
- Never use this report alone to invest. It must be paired with event review,
  source-verified fundamentals, valuation work, and a written invalidation rule.
"""


def _format_scorecard(scorecard: pd.DataFrame) -> str:
    if scorecard.empty:
        return "No scorecard rows available."
    columns = [
        "ticker",
        "decision_label",
        "investability_score",
        "momentum_score",
        "alpha_score",
        "quality_score",
        "valuation_score",
        "risk_score",
        "data_quality_score",
        "model_confidence",
        "confidence_cap_reason",
        "key_flags",
    ]
    display = scorecard[columns].copy()
    return display.to_markdown(index=False)


def _format_estimates(estimates: pd.DataFrame) -> str:
    if estimates.empty:
        return "No forward estimate rows available."
    one_year = estimates[estimates["horizon_days"] == 252].copy()
    columns = [
        "ticker",
        "current_price",
        "expected_price",
        "p10_price",
        "p50_price",
        "p90_price",
        "probability_gain",
        "annualized_mu",
        "annualized_vol",
    ]
    display = one_year[columns].copy()
    for column in ("current_price", "expected_price", "p10_price", "p50_price", "p90_price"):
        display[column] = display[column].map(lambda value: f"{value:.2f}")
    for column in ("probability_gain", "annualized_mu", "annualized_vol"):
        display[column] = display[column].map(lambda value: f"{value:.1%}")
    return display.to_markdown(index=False)


def _format_validation(validation: pd.DataFrame) -> str:
    if validation.empty:
        return "No validation rows available."
    latest_date = validation["validation_date"].max()
    latest = validation[validation["validation_date"] == latest_date].copy()
    columns = [
        "ticker",
        "horizon_days",
        "sample_size",
        "p10_p90_coverage",
        "p25_p75_coverage",
        "median_direction_accuracy",
    ]
    display = latest[columns]
    for column in ("p10_p90_coverage", "p25_p75_coverage", "median_direction_accuracy"):
        display[column] = display[column].map(lambda value: f"{value:.1%}")
    return display.to_markdown(index=False)
