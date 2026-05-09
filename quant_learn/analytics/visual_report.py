"""Visual report generation for the four-stock AI compute research universe."""

from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quant_learn.config import EXPORT_DIR, ensure_directories
from quant_learn.db import connect, initialize_database

REPORT_TICKERS = ["AMD", "TSM", "NVDA", "GOOGL"]
BENCHMARKS = ["QQQ", "SOXX"]
LINE_COLORS = {
    "AMD": "#2f6fbb",
    "TSM": "#228b68",
    "NVDA": "#5f9f35",
    "GOOGL": "#d28b26",
    "QQQ": "#666666",
    "SOXX": "#9a5fb4",
}


def build_visual_report(
    output_dir: Optional[Path] = None,
    report_name: str = "ai_compute_quant_report.md",
) -> Path:
    """Generate charts and a markdown report from the current DuckDB data."""

    ensure_directories()
    target_dir = output_dir or EXPORT_DIR
    figures_dir = target_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    data = _load_data()
    price = data["price"]
    returns = price.pct_change()
    factor = data["factor"]
    tsmc_revenue = data["tsmc_revenue"]

    metrics = _build_summary_metrics(price, returns, factor)
    chart_paths = {
        "workflow": figures_dir / "workflow_quant_analysis.png",
        "cumulative": figures_dir / "cumulative_returns.png",
        "relative": figures_dir / "latest_relative_strength.png",
        "risk_return": figures_dir / "risk_return_scatter.png",
        "beta": figures_dir / "rolling_beta_qqq.png",
        "correlation": figures_dir / "correlation_heatmap.png",
        "drawdown": figures_dir / "drawdowns.png",
        "tsmc_revenue": figures_dir / "tsmc_monthly_revenue.png",
    }

    _plot_workflow(chart_paths["workflow"])
    _plot_cumulative_returns(price, chart_paths["cumulative"])
    _plot_latest_relative_strength(metrics, chart_paths["relative"])
    _plot_risk_return(metrics, chart_paths["risk_return"])
    _plot_rolling_beta(factor, chart_paths["beta"])
    _plot_correlation(returns[REPORT_TICKERS], chart_paths["correlation"])
    _plot_drawdowns(price[REPORT_TICKERS], chart_paths["drawdown"])
    _plot_tsmc_revenue(tsmc_revenue, chart_paths["tsmc_revenue"])

    report_path = target_dir / report_name
    report_path.write_text(
        _render_markdown_report(
            metrics,
            chart_paths,
            price,
            returns,
            tsmc_revenue,
            report_path.parent,
        ),
        encoding="utf-8",
    )
    return report_path


def _load_data() -> dict[str, pd.DataFrame]:
    initialize_database()
    with connect() as conn:
        prices = conn.execute(
            """
            SELECT date, ticker, adj_close, close, volume
            FROM prices
            WHERE ticker IN (
                'AMD', 'TSM', 'NVDA', 'GOOGL', 'QQQ', 'SOXX'
            )
            ORDER BY date, ticker
            """
        ).fetchdf()
        factor = conn.execute(
            """
            SELECT *
            FROM factor_dashboard
            WHERE ticker IN ('AMD', 'TSM', 'NVDA', 'GOOGL')
            ORDER BY date, ticker
            """
        ).fetchdf()
        tsmc_revenue = conn.execute(
            """
            SELECT period, revenue_ntd_million, yoy_pct
            FROM tsmc_monthly_revenue
            ORDER BY period
            """
        ).fetchdf()

    if prices.empty:
        raise ValueError("No prices found. Run scripts.ingest_prices first.")

    prices["date"] = pd.to_datetime(prices["date"])
    prices["price"] = prices["adj_close"].fillna(prices["close"])
    price = prices.pivot(index="date", columns="ticker", values="price").sort_index()
    price = price.dropna(how="all")

    if not factor.empty:
        factor["date"] = pd.to_datetime(factor["date"])
    if not tsmc_revenue.empty:
        tsmc_revenue["period"] = pd.to_datetime(tsmc_revenue["period"])

    return {"price": price, "factor": factor, "tsmc_revenue": tsmc_revenue}


def _build_summary_metrics(
    price: pd.DataFrame,
    returns: pd.DataFrame,
    factor: pd.DataFrame,
) -> pd.DataFrame:
    latest_factor = pd.DataFrame()
    if not factor.empty:
        latest_date = factor["date"].max()
        latest_factor = factor[factor["date"] == latest_date].set_index("ticker")

    rows = []
    for ticker in REPORT_TICKERS:
        ticker_price = price[ticker].dropna()
        ticker_returns = returns[ticker].dropna()
        if ticker_price.empty:
            continue
        total_return = ticker_price.iloc[-1] / ticker_price.iloc[0] - 1.0
        annualized_vol = ticker_returns.std() * np.sqrt(252)
        max_drawdown = _max_drawdown(ticker_price)
        corr_qqq = ticker_returns.corr(returns["QQQ"])
        corr_soxx = ticker_returns.corr(returns["SOXX"])
        row = {
            "ticker": ticker,
            "total_return": total_return,
            "annualized_vol": annualized_vol,
            "max_drawdown": max_drawdown,
            "corr_qqq": corr_qqq,
            "corr_soxx": corr_soxx,
            "return_60d": np.nan,
            "rel_qqq_60d": np.nan,
            "rel_soxx_60d": np.nan,
            "beta_qqq_60d": np.nan,
            "realized_vol_60d": np.nan,
        }
        if ticker in latest_factor.index:
            for column in (
                "return_60d",
                "rel_qqq_60d",
                "rel_soxx_60d",
                "beta_qqq_60d",
                "realized_vol_60d",
            ):
                row[column] = latest_factor.loc[ticker, column]
        rows.append(row)

    return pd.DataFrame(rows).sort_values("ticker")


def _plot_workflow(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis("off")
    ax.set_title("How This Quant Research System Works", fontsize=16, weight="bold", pad=20)

    boxes = [
        ("Official + market data", 0.08, 0.68),
        ("Feature layer\nreturns, beta, vol,\nsegments, TSM revenue", 0.32, 0.68),
        ("Analysis layer\nrelative strength,\nevent study, risk", 0.56, 0.68),
        ("Research output\ncharts, tables,\nquestions to review", 0.80, 0.68),
        ("Value chain lens\nTSM -> NVDA/AMD -> GOOGL", 0.32, 0.24),
        ("Meaning\nseparate alpha,\nbeta, and risk", 0.62, 0.24),
    ]

    for text, x, y in boxes:
        ax.text(
            x,
            y,
            text,
            ha="center",
            va="center",
            fontsize=11,
            bbox={
                "boxstyle": "round,pad=0.5",
                "facecolor": "#f4f7fb",
                "edgecolor": "#38546d",
                "linewidth": 1.2,
            },
        )

    arrows = [
        ((0.18, 0.68), (0.24, 0.68)),
        ((0.44, 0.68), (0.50, 0.68)),
        ((0.68, 0.68), (0.74, 0.68)),
        ((0.32, 0.56), (0.32, 0.36)),
        ((0.45, 0.24), (0.52, 0.24)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "lw": 1.8})

    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_cumulative_returns(price: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    columns = REPORT_TICKERS + BENCHMARKS
    normalized = price[columns].dropna(how="all") / price[columns].dropna(how="all").iloc[0]
    for ticker in columns:
        linestyle = "--" if ticker in BENCHMARKS else "-"
        linewidth = 1.8 if ticker in BENCHMARKS else 2.3
        ax.plot(
            normalized.index,
            normalized[ticker],
            label=ticker,
            color=LINE_COLORS.get(ticker),
            linestyle=linestyle,
            linewidth=linewidth,
        )
    ax.set_title("Cumulative Return: Growth of $1")
    ax.set_ylabel("Growth multiple")
    ax.legend(ncol=3)
    ax.grid(True, alpha=0.25)
    _format_date_axis(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_latest_relative_strength(metrics: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(metrics))
    width = 0.36
    ax.bar(x - width / 2, metrics["return_60d"], width, label="60d return", color="#4c78a8")
    ax.bar(x + width / 2, metrics["rel_qqq_60d"], width, label="60d vs QQQ", color="#f58518")
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_xticks(x, metrics["ticker"])
    ax.set_title("Latest 60-Day Relative Strength")
    ax.set_ylabel("Return")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_risk_return(metrics: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    for _, row in metrics.iterrows():
        ticker = row["ticker"]
        ax.scatter(
            row["realized_vol_60d"],
            row["return_60d"],
            s=140,
            color=LINE_COLORS.get(ticker),
            label=ticker,
        )
        ax.annotate(ticker, (row["realized_vol_60d"], row["return_60d"]), xytext=(6, 6),
                    textcoords="offset points")
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_title("Latest 60-Day Risk vs Return")
    ax.set_xlabel("60d annualized realized volatility")
    ax.set_ylabel("60d return")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_rolling_beta(factor: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    if not factor.empty:
        for ticker in REPORT_TICKERS:
            subset = factor[factor["ticker"] == ticker].dropna(subset=["beta_qqq_60d"])
            ax.plot(
                subset["date"],
                subset["beta_qqq_60d"],
                label=ticker,
                color=LINE_COLORS.get(ticker),
                linewidth=2,
            )
    ax.axhline(1.0, color="#333333", linestyle="--", linewidth=1)
    ax.set_title("Rolling 60-Day Beta to QQQ")
    ax.set_ylabel("Beta")
    ax.legend(ncol=4)
    ax.grid(True, alpha=0.25)
    _format_date_axis(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_correlation(returns: pd.DataFrame, path: Path) -> None:
    corr = returns.dropna().corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(np.arange(len(corr.columns)), corr.columns)
    ax.set_yticks(np.arange(len(corr.index)), corr.index)
    for row in range(len(corr.index)):
        for column in range(len(corr.columns)):
            ax.text(column, row, f"{corr.iloc[row, column]:.2f}", ha="center", va="center")
    ax.set_title("Daily Return Correlation")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_drawdowns(price: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    for ticker in REPORT_TICKERS:
        series = price[ticker].dropna()
        drawdown = series / series.cummax() - 1.0
        ax.plot(drawdown.index, drawdown, label=ticker, color=LINE_COLORS.get(ticker), linewidth=2)
    ax.set_title("Drawdowns From Prior Peak")
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(ncol=4)
    ax.grid(True, alpha=0.25)
    _format_date_axis(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_tsmc_revenue(tsmc_revenue: pd.DataFrame, path: Path) -> None:
    fig, ax1 = plt.subplots(figsize=(11, 5))
    if not tsmc_revenue.empty:
        ax1.bar(
            tsmc_revenue["period"],
            tsmc_revenue["revenue_ntd_million"],
            width=24,
            color="#228b68",
            alpha=0.75,
            label="Revenue NT$ mn",
        )
        ax1.set_ylabel("Revenue NT$ million")
        ax2 = ax1.twinx()
        ax2.plot(
            tsmc_revenue["period"],
            tsmc_revenue["yoy_pct"],
            color="#d28b26",
            linewidth=2.4,
            marker="o",
            label="YoY %",
        )
        ax2.set_ylabel("YoY change")
        ax2.yaxis.set_major_formatter(lambda value, _: f"{value:.0f}%")
    ax1.set_title("TSMC Monthly Revenue")
    ax1.grid(True, axis="y", alpha=0.25)
    _format_date_axis(ax1)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _render_markdown_report(
    metrics: pd.DataFrame,
    chart_paths: dict[str, Path],
    price: pd.DataFrame,
    returns: pd.DataFrame,
    tsmc_revenue: pd.DataFrame,
    base_dir: Path,
) -> str:
    latest_date = price.dropna(how="all").index.max().date()
    start_date = price.dropna(how="all").index.min().date()
    metrics_table = _format_metrics_table(metrics)
    corr_table = returns[REPORT_TICKERS].dropna().corr().round(2).to_markdown()
    top_60d = metrics.sort_values("return_60d", ascending=False).iloc[0]
    strongest_relative = metrics.sort_values("rel_qqq_60d", ascending=False).iloc[0]
    highest_beta = metrics.sort_values("beta_qqq_60d", ascending=False).iloc[0]
    latest_tsmc = None
    if not tsmc_revenue.empty:
        latest_tsmc = tsmc_revenue.dropna(subset=["revenue_ntd_million"]).iloc[-1]

    tsmc_sentence = "No TSMC monthly revenue rows are available yet."
    if latest_tsmc is not None:
        tsmc_sentence = (
            f"Latest TSMC revenue row is {latest_tsmc['period'].date()}: "
            f"NT${latest_tsmc['revenue_ntd_million']:,.0f} million, "
            f"{latest_tsmc['yoy_pct']:.1f}% YoY."
        )

    relative_paths = {name: path.relative_to(base_dir) for name, path in chart_paths.items()}
    return f"""# AI Compute Four-Stock Quant Report

Coverage: AMD, TSM, NVDA, GOOGL

Data window: {start_date} to {latest_date}

This report is research output, not a buy/sell signal.
The goal is to separate trend, factor beta, relative strength, and risk.

## Workflow

![Quant workflow]({relative_paths["workflow"]})

Meaning:

- Data layer: prices, SEC facts, TSMC revenue, and curated events.
- Feature layer: returns, beta, realized volatility, drawdown, segment KPIs, and revenue growth.
- Analysis layer: relative strength, event study, and risk attribution.
- Research output: charts and questions that guide deeper fundamental review.

## Latest Snapshot

{metrics_table}

Interpretation:

- Best latest 60-day return: {top_60d["ticker"]} at {_pct(top_60d["return_60d"])}.
- Strongest 60-day return versus QQQ: {strongest_relative["ticker"]}
  at {_pct(strongest_relative["rel_qqq_60d"])}.
- Highest latest beta to QQQ: {highest_beta["ticker"]}
  at {highest_beta["beta_qqq_60d"]:.2f}. High beta means market direction matters more.
- {tsmc_sentence}

## Cumulative Return

![Cumulative returns]({relative_paths["cumulative"]})

Meaning: this shows growth of one dollar over the sample. It measures total trend,
not pure alpha. A stock can lead this chart because of market beta, sector beta,
or company-specific strength.

## Relative Strength

![Relative strength]({relative_paths["relative"]})

Meaning: 60-day relative strength versus QQQ is a first-pass alpha proxy.
Positive values mean the stock has recently outperformed broad Nasdaq exposure;
negative values mean it lagged.

## Risk vs Return

![Risk return]({relative_paths["risk_return"]})

Meaning: upper-left is better in a simple risk-return sense. Upper-right means
strong return with high volatility. Lower-right is the danger zone: high volatility
without compensation.

## Rolling Beta

![Rolling beta]({relative_paths["beta"]})

Meaning: beta to QQQ measures market sensitivity. A beta above 1.0 means the
position tends to amplify Nasdaq moves. This is risk exposure, not alpha.

## Correlation

![Correlation heatmap]({relative_paths["correlation"]})

Correlation table:

{corr_table}

Meaning: high correlations mean the four names may behave like one crowded
AI-compute risk bucket during stress. Diversification inside the cluster can
disappear when correlations rise.

## Drawdown

![Drawdowns]({relative_paths["drawdown"]})

Meaning: drawdown is the pain metric. It tells you how far each stock fell from
its prior peak and helps size positions before volatility becomes emotional.

## TSMC Monthly Revenue

![TSMC monthly revenue]({relative_paths["tsmc_revenue"]})

Meaning: TSMC monthly revenue is a manufacturing read-through for AI compute
demand. It is useful for lead-lag research, but the tradable event date should be
the actual announcement date, not the revenue period date.
"""


def _format_metrics_table(metrics: pd.DataFrame) -> str:
    display = metrics.copy()
    pct_columns = [
        "total_return",
        "annualized_vol",
        "max_drawdown",
        "return_60d",
        "rel_qqq_60d",
        "rel_soxx_60d",
        "realized_vol_60d",
    ]
    for column in pct_columns:
        display[column] = display[column].map(_pct)
    for column in ("corr_qqq", "corr_soxx", "beta_qqq_60d"):
        display[column] = display[column].map(_decimal)
    return display.to_markdown(index=False)


def _pct(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.1%}"


def _decimal(value: float) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.2f}"


def _max_drawdown(series: pd.Series) -> float:
    drawdown = series / series.cummax() - 1.0
    return float(drawdown.min())


def _format_date_axis(ax) -> None:
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
