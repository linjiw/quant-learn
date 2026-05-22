"""Portfolio tracker for the AI framework allocation.

The default mode is public and GitHub-Pages friendly: initial lots and daily
history are stored in versioned data files, while generated site artifacts are
rebuilt by the workflow.
"""

from __future__ import annotations

import csv
import json
import math
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from quant_learn.config import DATA_DIR, MANUAL_DIR, PROJECT_ROOT, ensure_directories
from quant_learn.db import connect, initialize_database
from quant_learn.ingest.prices import ingest_prices

PORTFOLIO_DATA_DIR = DATA_DIR / "portfolio"
PORTFOLIO_REPORT_DIR = PROJECT_ROOT / "reports" / "portfolio"
SITE_DIR = PROJECT_ROOT / "site" / "ai-framework"
SITE_PORTFOLIO_DIR = SITE_DIR / "portfolio"
PORTFOLIO_CONFIG_PATH = MANUAL_DIR / "ai_portfolio_lots.json"
PORTFOLIO_SNAPSHOTS_PATH = PORTFOLIO_DATA_DIR / "ai_portfolio_snapshots.csv"
PORTFOLIO_SUMMARY_PATH = PORTFOLIO_DATA_DIR / "ai_portfolio_summary.csv"
SITE_DATA_PATH = SITE_DIR / "portfolio-data.json"

BASE_CURRENCY = "USD"
DEFAULT_INITIAL_CAPITAL = 1000.0
PORTFOLIO_HOLDINGS_PATH = MANUAL_DIR / "ai_framework_holdings.csv"
FX_TICKER_BY_CURRENCY = {"KRW": "KRW=X"}
TICKER_CURRENCY = {"000660.KS": "KRW"}

SNAPSHOT_COLUMNS = [
    "snapshot_date",
    "ticker",
    "holding_name",
    "target_weight",
    "quantity",
    "currency",
    "price_native",
    "fx_to_usd",
    "price_usd",
    "price_date",
    "market_value_usd",
    "cost_basis_usd",
    "pnl_usd",
    "return_pct",
    "source",
    "updated_at_utc",
]

SUMMARY_COLUMNS = [
    "snapshot_date",
    "total_value_usd",
    "invested_value_usd",
    "cash_value_usd",
    "cost_basis_usd",
    "pnl_usd",
    "return_pct",
    "daily_pnl_usd",
    "daily_return_pct",
    "annualized_return_pct",
    "updated_at_utc",
]


@dataclass
class PortfolioLot:
    ticker: str
    holding_name: str
    target_weight: float
    quantity: float
    currency: str
    initial_price_native: float | None
    initial_fx_to_usd: float
    initial_price_usd: float | None
    initial_price_date: str | None
    initial_value_usd: float
    cost_basis_usd: float


@dataclass
class PortfolioConfig:
    base_currency: str
    initial_capital_usd: float
    portfolio_start_date: str
    created_at_utc: str
    holdings_source: str
    lots: list[PortfolioLot]


def update_portfolio(
    *,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    holdings_path: Path = PORTFOLIO_HOLDINGS_PATH,
    config_path: Path = PORTFOLIO_CONFIG_PATH,
    snapshots_path: Path = PORTFOLIO_SNAPSHOTS_PATH,
    summary_path: Path = PORTFOLIO_SUMMARY_PATH,
    site_data_path: Path = SITE_DATA_PATH,
    report_dir: Path = PORTFOLIO_REPORT_DIR,
    site_portfolio_dir: Path = SITE_PORTFOLIO_DIR,
    snapshot_date: date | None = None,
    ingest_latest_prices: bool = True,
    force_reinitialize: bool = False,
) -> dict:
    """Update the portfolio ledger and generated site data."""

    ensure_portfolio_directories(
        data_dir=snapshots_path.parent,
        report_dir=report_dir,
        site_portfolio_dir=site_portfolio_dir,
    )
    run_date = snapshot_date or date.today()
    holdings = load_framework_holdings(holdings_path)
    tickers = portfolio_price_tickers(holdings["ticker"].tolist())

    if ingest_latest_prices:
        start = (run_date - timedelta(days=10)).isoformat()
        end = (run_date + timedelta(days=1)).isoformat()
        ingest_prices(tickers=tickers, start=start, end=end)

    latest_prices = load_latest_prices(tickers, as_of_date=run_date)
    config = load_or_create_config(
        holdings=holdings,
        latest_prices=latest_prices,
        initial_capital=initial_capital,
        start_date=run_date,
        holdings_path=holdings_path,
        config_path=config_path,
        force_reinitialize=force_reinitialize,
    )
    snapshot = build_snapshot(config=config, latest_prices=latest_prices, snapshot_date=run_date)
    summary = build_summary(
        config=config,
        snapshot=snapshot,
        snapshot_date=run_date,
        summary_path=summary_path,
    )

    upsert_csv(
        snapshots_path,
        snapshot,
        SNAPSHOT_COLUMNS,
        "snapshot_date",
        run_date.isoformat(),
    )
    upsert_csv(summary_path, summary, SUMMARY_COLUMNS, "snapshot_date", run_date.isoformat())

    summary_history = read_csv_if_exists(summary_path, SUMMARY_COLUMNS)
    snapshot_history = read_csv_if_exists(snapshots_path, SNAPSHOT_COLUMNS)
    plot_paths = write_plots(
        summary_history=summary_history,
        latest_snapshot=snapshot,
        report_dir=report_dir,
        site_portfolio_dir=site_portfolio_dir,
    )
    site_data = build_site_data(
        config=config,
        latest_snapshot=snapshot,
        summary_history=summary_history,
        snapshot_history=snapshot_history,
        plot_paths=plot_paths,
    )
    write_json(site_data_path, site_data)
    return site_data


def ensure_portfolio_directories(
    *,
    data_dir: Path,
    report_dir: Path,
    site_portfolio_dir: Path,
) -> None:
    ensure_directories()
    for path in (data_dir, report_dir, site_portfolio_dir):
        path.mkdir(parents=True, exist_ok=True)


def load_framework_holdings(path: Path = PORTFOLIO_HOLDINGS_PATH) -> pd.DataFrame:
    holdings = pd.read_csv(path)
    required = {"ticker", "holding_name", "target_weight"}
    missing = required - set(holdings.columns)
    if missing:
        raise ValueError(f"Missing required holdings columns: {sorted(missing)}")
    holdings = holdings[["ticker", "holding_name", "target_weight"]].copy()
    holdings["target_weight"] = pd.to_numeric(holdings["target_weight"], errors="raise")
    if abs(float(holdings["target_weight"].sum()) - 100.0) > 0.0001:
        raise ValueError("Target weights must sum to 100.")
    return holdings


def portfolio_price_tickers(tickers: Iterable[str]) -> list[str]:
    values = [ticker for ticker in tickers if ticker != "CASH"]
    currencies = {currency_for_ticker(ticker) for ticker in values}
    for currency in sorted(currencies):
        fx_ticker = FX_TICKER_BY_CURRENCY.get(currency)
        if fx_ticker:
            values.append(fx_ticker)
    return sorted(dict.fromkeys(values))


def currency_for_ticker(ticker: str) -> str:
    return TICKER_CURRENCY.get(ticker, BASE_CURRENCY)


def load_latest_prices(tickers: Iterable[str], *, as_of_date: date) -> dict[str, dict]:
    initialize_database()
    ticker_list = list(tickers)
    if not ticker_list:
        return {}
    placeholders = ", ".join(["?"] * len(ticker_list))
    with connect() as conn:
        frame = conn.execute(
            f"""
            SELECT date, ticker, close, adj_close, source
            FROM prices
            WHERE ticker IN ({placeholders})
              AND date <= ?
            QUALIFY row_number() OVER (PARTITION BY ticker ORDER BY date DESC) = 1
            """,
            [*ticker_list, as_of_date],
        ).fetchdf()
    if frame.empty:
        return {}
    frame["price"] = frame["adj_close"].fillna(frame["close"])
    prices: dict[str, dict] = {}
    for _, row in frame.iterrows():
        prices[str(row["ticker"])] = {
            "price_native": float(row["price"]),
            "price_date": pd.to_datetime(row["date"]).date().isoformat(),
            "source": str(row["source"]),
        }
    return prices


def load_or_create_config(
    *,
    holdings: pd.DataFrame,
    latest_prices: dict[str, dict],
    initial_capital: float,
    start_date: date,
    holdings_path: Path,
    config_path: Path = PORTFOLIO_CONFIG_PATH,
    force_reinitialize: bool = False,
) -> PortfolioConfig:
    if config_path.exists() and not force_reinitialize:
        return read_config(config_path)

    lots = []
    for _, holding in holdings.iterrows():
        ticker = str(holding["ticker"])
        target_weight = float(holding["target_weight"])
        initial_value = initial_capital * target_weight / 100.0
        if ticker == "CASH":
            lots.append(
                PortfolioLot(
                    ticker=ticker,
                    holding_name=str(holding["holding_name"]),
                    target_weight=target_weight,
                    quantity=initial_value,
                    currency=BASE_CURRENCY,
                    initial_price_native=1.0,
                    initial_fx_to_usd=1.0,
                    initial_price_usd=1.0,
                    initial_price_date=start_date.isoformat(),
                    initial_value_usd=initial_value,
                    cost_basis_usd=initial_value,
                )
            )
            continue
        price = latest_prices.get(ticker)
        if not price:
            raise ValueError(f"No latest price found for {ticker}.")
        currency = currency_for_ticker(ticker)
        fx_to_usd = fx_to_usd_for_currency(currency, latest_prices)
        price_usd = price["price_native"] * fx_to_usd
        if price_usd <= 0:
            raise ValueError(f"Invalid USD price for {ticker}: {price_usd}")
        lots.append(
            PortfolioLot(
                ticker=ticker,
                holding_name=str(holding["holding_name"]),
                target_weight=target_weight,
                quantity=initial_value / price_usd,
                currency=currency,
                initial_price_native=price["price_native"],
                initial_fx_to_usd=fx_to_usd,
                initial_price_usd=price_usd,
                initial_price_date=price["price_date"],
                initial_value_usd=initial_value,
                cost_basis_usd=initial_value,
            )
        )

    config = PortfolioConfig(
        base_currency=BASE_CURRENCY,
        initial_capital_usd=initial_capital,
        portfolio_start_date=start_date.isoformat(),
        created_at_utc=utc_iso(),
        holdings_source=display_path(holdings_path),
        lots=lots,
    )
    write_config(config_path, config)
    return config


def fx_to_usd_for_currency(currency: str, latest_prices: dict[str, dict]) -> float:
    if currency == BASE_CURRENCY:
        return 1.0
    fx_ticker = FX_TICKER_BY_CURRENCY.get(currency)
    if not fx_ticker:
        raise ValueError(f"No FX ticker configured for {currency}.")
    fx_price = latest_prices.get(fx_ticker)
    if not fx_price or fx_price["price_native"] <= 0:
        raise ValueError(f"No FX price found for {currency} via {fx_ticker}.")
    if currency == "KRW":
        return 1.0 / fx_price["price_native"]
    raise ValueError(f"Unsupported FX conversion for {currency}.")


def build_snapshot(
    *,
    config: PortfolioConfig,
    latest_prices: dict[str, dict],
    snapshot_date: date,
) -> pd.DataFrame:
    rows = []
    updated_at = utc_iso()
    for lot in config.lots:
        if lot.ticker == "CASH":
            price_native = 1.0
            fx_to_usd = 1.0
            price_usd = 1.0
            price_date = snapshot_date.isoformat()
            source = "cash"
        else:
            price = latest_prices.get(lot.ticker)
            if not price:
                raise ValueError(f"No latest price found for {lot.ticker}.")
            price_native = float(price["price_native"])
            fx_to_usd = fx_to_usd_for_currency(lot.currency, latest_prices)
            price_usd = price_native * fx_to_usd
            price_date = price["price_date"]
            source = str(price["source"])
        market_value = lot.quantity * price_usd
        pnl = market_value - lot.cost_basis_usd
        return_pct = pct(pnl, lot.cost_basis_usd)
        rows.append(
            {
                "snapshot_date": snapshot_date.isoformat(),
                "ticker": lot.ticker,
                "holding_name": lot.holding_name,
                "target_weight": lot.target_weight,
                "quantity": lot.quantity,
                "currency": lot.currency,
                "price_native": price_native,
                "fx_to_usd": fx_to_usd,
                "price_usd": price_usd,
                "price_date": price_date,
                "market_value_usd": market_value,
                "cost_basis_usd": lot.cost_basis_usd,
                "pnl_usd": pnl,
                "return_pct": return_pct,
                "source": source,
                "updated_at_utc": updated_at,
            }
        )
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def build_summary(
    *,
    config: PortfolioConfig,
    snapshot: pd.DataFrame,
    snapshot_date: date,
    summary_path: Path = PORTFOLIO_SUMMARY_PATH,
) -> pd.DataFrame:
    previous = latest_summary_before(snapshot_date, summary_path=summary_path)
    total_value = float(snapshot["market_value_usd"].sum())
    cash_value = float(snapshot.loc[snapshot["ticker"] == "CASH", "market_value_usd"].sum())
    invested_value = total_value - cash_value
    cost_basis = float(snapshot["cost_basis_usd"].sum())
    pnl = total_value - config.initial_capital_usd
    return_pct = pct(pnl, config.initial_capital_usd)
    if previous is None:
        daily_pnl = 0.0
        daily_return = 0.0
    else:
        previous_value = float(previous["total_value_usd"])
        daily_pnl = total_value - previous_value
        daily_return = pct(daily_pnl, previous_value)
    start_date = date.fromisoformat(config.portfolio_start_date)
    elapsed_days = (snapshot_date - start_date).days
    annualized = (
        0.0
        if elapsed_days < 1
        else ((total_value / config.initial_capital_usd) ** (365.0 / elapsed_days) - 1.0) * 100.0
    )
    if not math.isfinite(annualized):
        annualized = 0.0
    return pd.DataFrame(
        [
            {
                "snapshot_date": snapshot_date.isoformat(),
                "total_value_usd": total_value,
                "invested_value_usd": invested_value,
                "cash_value_usd": cash_value,
                "cost_basis_usd": cost_basis,
                "pnl_usd": pnl,
                "return_pct": return_pct,
                "daily_pnl_usd": daily_pnl,
                "daily_return_pct": daily_return,
                "annualized_return_pct": annualized,
                "updated_at_utc": utc_iso(),
            }
        ],
        columns=SUMMARY_COLUMNS,
    )


def latest_summary_before(
    snapshot_date: date,
    *,
    summary_path: Path = PORTFOLIO_SUMMARY_PATH,
) -> pd.Series | None:
    frame = read_csv_if_exists(summary_path, SUMMARY_COLUMNS)
    if frame.empty:
        return None
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"]).dt.date
    previous = frame[frame["snapshot_date"] < snapshot_date].sort_values("snapshot_date")
    if previous.empty:
        return None
    return previous.iloc[-1]


def upsert_csv(
    path: Path,
    rows: pd.DataFrame,
    columns: list[str],
    key: str,
    key_value: str,
) -> None:
    existing = read_csv_if_exists(path, columns)
    if not existing.empty:
        existing = existing[existing[key].astype(str) != key_value]
    combined = pd.concat([existing, rows], ignore_index=True)
    combined = combined[columns].sort_values(columns[:2] if len(columns) > 2 else [key])
    combined.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def read_csv_if_exists(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def write_plots(
    *,
    summary_history: pd.DataFrame,
    latest_snapshot: pd.DataFrame,
    report_dir: Path = PORTFOLIO_REPORT_DIR,
    site_portfolio_dir: Path = SITE_PORTFOLIO_DIR,
) -> dict[str, str]:
    report_value = report_dir / "ai_portfolio_value.png"
    report_allocation = report_dir / "ai_portfolio_allocation.png"
    site_value = site_portfolio_dir / "portfolio-value.png"
    site_allocation = site_portfolio_dir / "portfolio-allocation.png"

    plot_value_history(summary_history, report_value)
    plot_allocation(latest_snapshot, report_allocation)
    shutil.copyfile(report_value, site_value)
    shutil.copyfile(report_allocation, site_allocation)
    return {
        "value": "./portfolio/portfolio-value.png",
        "allocation": "./portfolio/portfolio-allocation.png",
    }


def plot_value_history(summary_history: pd.DataFrame, path: Path) -> None:
    frame = summary_history.copy()
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"])
    frame = frame.sort_values("snapshot_date")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(frame["snapshot_date"], frame["total_value_usd"], marker="o", linewidth=2.3)
    ax.axhline(DEFAULT_INITIAL_CAPITAL, color="#8b9992", linewidth=1, linestyle="--")
    ax.set_title("Portfolio Value")
    ax.set_ylabel("USD")
    ax.grid(axis="y", alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_allocation(latest_snapshot: pd.DataFrame, path: Path) -> None:
    frame = latest_snapshot.copy()
    frame = frame.sort_values("market_value_usd", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 5.2))
    colors = ["#0f766e" if value >= 0 else "#a33a2b" for value in frame["pnl_usd"]]
    ax.barh(frame["ticker"], frame["market_value_usd"], color=colors)
    ax.set_title("Current Market Value by Holding")
    ax.set_xlabel("USD")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def build_site_data(
    *,
    config: PortfolioConfig,
    latest_snapshot: pd.DataFrame,
    summary_history: pd.DataFrame,
    snapshot_history: pd.DataFrame,
    plot_paths: dict[str, str],
) -> dict:
    latest_summary = summary_history.sort_values("snapshot_date").iloc[-1].to_dict()
    holdings = latest_snapshot.sort_values("target_weight", ascending=False).to_dict(
        orient="records"
    )
    return {
        "enabled": True,
        "baseCurrency": BASE_CURRENCY,
        "initialCapitalUsd": round(config.initial_capital_usd, 2),
        "startDate": config.portfolio_start_date,
        "asOfDate": latest_summary["snapshot_date"],
        "updatedAtUtc": latest_summary["updated_at_utc"],
        "summary": clean_numbers(latest_summary),
        "holdings": [clean_numbers(row) for row in holdings],
        "history": [
            clean_numbers(row)
            for row in summary_history.sort_values("snapshot_date").to_dict(orient="records")
        ],
        "snapshotRows": [
            clean_numbers(row)
            for row in snapshot_history.sort_values(["snapshot_date", "ticker"]).to_dict(
                orient="records"
            )
        ],
        "plots": plot_paths,
        "publication": "public GitHub Pages tracker backed by versioned initial lots and history",
    }


def clean_numbers(row: dict) -> dict:
    cleaned = {}
    for key, value in row.items():
        if pd.isna(value):
            cleaned[key] = None
        elif isinstance(value, float):
            cleaned[key] = round(value, 6)
        else:
            cleaned[key] = value
    return cleaned


def read_config(path: Path) -> PortfolioConfig:
    raw = json.loads(path.read_text())
    lots = [PortfolioLot(**lot) for lot in raw["lots"]]
    return PortfolioConfig(
        base_currency=raw["base_currency"],
        initial_capital_usd=float(raw["initial_capital_usd"]),
        portfolio_start_date=raw["portfolio_start_date"],
        created_at_utc=raw["created_at_utc"],
        holdings_source=raw["holdings_source"],
        lots=lots,
    )


def write_config(path: Path, config: PortfolioConfig) -> None:
    payload = asdict(config)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator * 100.0


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
