# Quant Learn

Focused quant research system for four AI compute value-chain stocks:

- `TSM`: foundry and advanced packaging bottleneck
- `NVDA`: AI accelerator platform leader
- `AMD`: second-source AI accelerator and server CPU challenger
- `GOOGL`: hyperscaler demand, cloud, search cash flow, and AI capex

The first version is deliberately a research system, not an auto-trading system.

## What This Builds First

1. A DuckDB database at `data/duckdb/quant_learn.duckdb`
2. Daily prices for core tickers and market benchmarks
3. SEC filing metadata and selected XBRL facts
4. TSMC monthly revenue from the official investor page
5. Factor dashboard metrics: returns, volatility, drawdown, rolling beta, residual returns
6. Event-study helpers for earnings, TSMC monthly revenue, and hyperscaler capex events
7. Manual CSV import path for verified segment KPIs
8. Event-level return windows in `event_returns`
9. Standardized SEC-derived `fundamentals_quarterly` research snapshots

For the design rationale and table definitions, see `docs/system_design.md`.

## Setup

```bash
uv sync
```

Set a real SEC user agent before hitting SEC endpoints:

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
```

## Initialize Database

```bash
uv run python -m scripts.init_db
```

## Ingest Data

Prices:

```bash
uv run python -m scripts.ingest_prices --start 2018-01-01
```

The price ingestion step also updates `return_1d`, `return_5d`, `return_20d`, and `return_60d`.

SEC facts and filings:

```bash
uv run python -m scripts.ingest_sec
```

TSMC monthly revenue:

```bash
uv run python -m scripts.ingest_tsmc_revenue --years 2018 2019 2020 2021 2022 2023 2024 2025 2026
```

Manual events:

```bash
uv run python -m scripts.import_events data/manual/events_template.csv
uv run python -m scripts.build_event_returns
```

Manual segment KPIs:

```bash
uv run python -m scripts.import_segments data/manual/segment_kpis_template.csv
```

SEC-derived quarterly fundamentals:

```bash
uv run python -m scripts.build_fundamentals
```

DuckDB allows many readers but only one writer. Run ingestion scripts sequentially when writing to the same database file.

## Run First Analytics

Generate a daily factor dashboard snapshot:

```bash
uv run python -m scripts.build_factor_dashboard
```

Generate the visual research report:

```bash
uv run python -m scripts.build_visual_report
```

Generate forward scenario estimates and an investability scorecard:

```bash
uv run python -m scripts.ingest_valuation
uv run python -m scripts.build_forward_analysis
```

Notebook entry points:

```text
notebooks/01_factor_dashboard.ipynb
notebooks/02_event_study.ipynb
```

Run event study:

```bash
uv run python -m scripts.run_event_study --event-type earnings --window-before 5 --window-after 20
uv run python -m scripts.run_event_study --event-type tsmc_monthly_revenue --window-before 1 --window-after 20
uv run python -m scripts.run_event_study --event-type hyperscaler_capex --window-before 1 --window-after 20
```

Exports are written to `data/exports/`.

## Suggested 90-Day Sequence

Weeks 1-2: Build the data base layer. Run price, SEC, TSMC, and manual KPI ingestion.

Weeks 3-4: Review factor dashboard outputs. Validate beta, residual return, drawdown, and correlation behavior.

Weeks 5-8: Build event logs for earnings, TSMC monthly revenue, and hyperscaler capex. Use event study outputs for repeatable post-event reviews.

Weeks 9-12: Add scoring. Treat scores as research priorities and risk flags, not buy/sell commands.
