"""Forward scenario estimates and investability scorecards.

This module deliberately avoids single-point target prices. It builds a
probabilistic price cone and a decision-support scorecard from observable
factors: trend, residual strength, risk, quality, and valuation discipline.
"""

from dataclasses import dataclass
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
Z_SCORES = {
    "p10_price": -1.2815515655446004,
    "p25_price": -0.6744897501960817,
    "p50_price": 0.0,
    "p75_price": 0.6744897501960817,
    "p90_price": 1.2815515655446004,
}
METHOD = "momentum_residual_vol_cone_v1"


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
    store_forward_analysis(estimates, scorecard)
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
        annualized_vol = _safe_number(factor.loc[ticker, "realized_vol_60d"], default=np.nan)
        if pd.isna(annualized_vol) or annualized_vol <= 0:
            annualized_vol = 0.45

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

        investability_score = (
            0.25 * momentum_score
            + 0.20 * alpha_score
            + 0.20 * quality_score
            + 0.15 * valuation_score
            + 0.15 * risk_score
            + 0.05 * event_score
        )
        flags = valuation_flags + risk_flags + event_flags
        decision_label = _decision_label(
            investability_score,
            momentum_score,
            valuation_score,
            risk_score,
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
                "key_flags": "; ".join(flags),
                "notes": notes,
                "ingested_at": ingested_at,
            }
        )

    return pd.DataFrame(rows)


def store_forward_analysis(estimates: pd.DataFrame, scorecard: pd.DataFrame) -> tuple[int, int]:
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
    return estimate_count, scorecard_count


def export_forward_analysis_report(
    estimates: pd.DataFrame,
    scorecard: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> Path:
    """Export CSVs, charts, and a markdown report."""

    ensure_directories()
    target_dir = output_dir or EXPORT_DIR
    figures_dir = target_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    estimates.to_csv(target_dir / "forward_price_estimates.csv", index=False)
    scorecard.to_csv(target_dir / "investment_scorecard.csv", index=False)

    cone_path = figures_dir / "forward_price_cones.png"
    score_path = figures_dir / "investment_scorecard.png"
    _plot_forward_price_cones(estimates, cone_path)
    _plot_scorecard(scorecard, score_path)

    report_path = target_dir / "forward_investment_report.md"
    report_path.write_text(
        _render_report(
            estimates,
            scorecard,
            cone_path.relative_to(target_dir),
            score_path.relative_to(target_dir),
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
        return 50.0, []
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


def _decision_label(
    score: float,
    momentum_score: float,
    valuation_score: float,
    risk_score: float,
    flag_count: int,
) -> str:
    if momentum_score >= 75 and (risk_score < 40 or valuation_score < 35):
        return "Strong momentum, elevated risk"
    if score >= 75 and risk_score >= 45 and valuation_score >= 40 and flag_count <= 2:
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


def _render_report(
    estimates: pd.DataFrame,
    scorecard: pd.DataFrame,
    cone_path: Path,
    score_path: Path,
) -> str:
    as_of_date = scorecard["as_of_date"].max() if not scorecard.empty else ""
    score_table = _format_scorecard(scorecard)
    estimate_table = _format_estimates(estimates)
    return f"""# Forward Estimate And Investment Decision Report

As of: {as_of_date}

This is decision support, not investment advice. The price estimates are
distribution ranges from current trend, residual strength, and realized
volatility. They are not target prices.

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

## Price Cone Summary

![Forward price cones]({cone_path})

{estimate_table}

## How To Use This

- Use `p10-p90` as a risk range, not a forecast promise.
- A strong score means the setup deserves research time, not automatic buying.
- A weak valuation score does not mean the stock must fall; it means the margin
  for disappointment is lower.
- A high risk score is good. A low risk score means beta, volatility, or
  drawdown is already elevated.
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
