# Quant Learn System Design

## Objective

Build a focused research system for `GOOGL`, `NVDA`, `AMD`, and `TSM`. The system is optimized for repeatable equity research:

- daily market dashboard
- official financial data ingestion
- TSMC monthly revenue tracking
- curated event studies
- segment KPI tracking

It is intentionally not an execution or auto-trading system.

## Architecture

```text
External Sources
  - Yahoo Finance prices
  - SEC EDGAR APIs
  - TSMC investor relations monthly revenue
  - Manual verified event and segment CSVs
        |
        v
Ingest Layer
  quant_learn/ingest/
        |
        v
DuckDB Research Store
  data/duckdb/quant_learn.duckdb
        |
        v
Analytics Layer
  quant_learn/analytics/
        |
        v
CSV Exports
  data/exports/
```

## Tables

`prices`
: Daily OHLCV and adjusted close for the core universe and benchmarks.

`sec_filings`
: Filing metadata from SEC submissions API.

`sec_facts`
: Selected XBRL facts from SEC companyfacts API. This table is intentionally sparse and does not enforce a primary key because SEC facts can omit fiscal fields.

`tsmc_monthly_revenue`
: TSMC monthly revenue in NT$ millions and YoY change from the official investor relations page.

`events`
: Manually curated event log for earnings, hyperscaler capex, product launches, export controls, and TSMC monthly revenue announcement dates.

`segment_kpis`
: Manually verified segment-level KPIs. This is manual-first because company segment disclosures are not reliably exposed through simple companyfacts calls.

`factor_dashboard`
: Daily derived metrics: returns, relative returns, rolling beta, realized vol, drawdown, residual return, and volume z-score.

## Design Choices

1. DuckDB first
: It is local, fast, easy to inspect, and enough for the first 90 days. PostgreSQL can be added later if scheduling or concurrent writes become important.

2. Manual segment KPI import first
: Segment revenue is high-value but disclosure formats vary by company and filing. A brittle parser would create false precision. The first version supports clean manual CSV ingestion.

3. Event study requires curated event dates
: TSMC monthly revenue periods are not the same as announcement dates. For lead-lag research, use actual announcement dates in `events`.

4. Scores are not implemented yet
: The scoring model should come after the dashboard and event-study data are validated. Otherwise the score becomes a false buy/sell signal.

5. Single writer
: DuckDB supports many reads but only one writer at a time. Run ingestion scripts sequentially when writing to the same database file.

## Implemented CLI

```bash
uv run python -m scripts.init_db
uv run python -m scripts.ingest_prices --start 2018-01-01
uv run python -m scripts.ingest_sec --tickers GOOGL NVDA AMD TSM
uv run python -m scripts.ingest_tsmc_revenue --years 2018 2019 2020 2021 2022 2023 2024 2025 2026
uv run python -m scripts.import_events data/manual/events_template.csv
uv run python -m scripts.import_segments data/manual/segment_kpis_template.csv
uv run python -m scripts.build_factor_dashboard
uv run python -m scripts.run_event_study --event-type earnings --window-before 5 --window-after 20
```

## Next Implementation Steps

1. Add a curated `events_ai_compute.csv` with real earnings dates, hyperscaler capex events, and TSMC announcement dates.
2. Add a first event-study summary table: CAR[-1,+1], CAR[0,+5], CAR[0,+20].
3. Add an IV monitor table and adapter after choosing an options data source.
4. Add segment KPI extraction helpers one company at a time, starting with GOOGL and AMD because their segment tables are cleaner.
5. Add the research score only after the first dashboard and event-study outputs are manually reviewed.
