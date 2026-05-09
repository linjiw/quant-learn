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
: Daily OHLCV, adjusted close, and 1/5/20/60-day returns for the core universe and benchmarks.

`sec_filings`
: Filing metadata from SEC submissions API.

`sec_facts`
: Selected XBRL facts from SEC companyfacts API. This table is intentionally sparse and does not enforce a primary key because SEC facts can omit fiscal fields.

`fundamentals_quarterly`
: A standardized research snapshot built from selected SEC facts. It is useful for trend review, but cash-flow fields can be cumulative depending on the issuer's filing format, so reviewed segment work should still use verified source tables.

`tsmc_monthly_revenue`
: TSMC monthly revenue in NT$ millions and YoY change from the official investor relations page.

`events`
: Manually curated event log for earnings, hyperscaler capex, product launches, export controls, and TSMC monthly revenue announcement dates. It separates `event_date` from `reaction_date` so after-market releases use the next trading session.

`event_impacts`
: Cross-ticker impact map. One event can affect multiple stocks, such as a TSMC monthly revenue release affecting `TSM`, `NVDA`, and `AMD`.

`event_metrics`
: Surprise and KPI evidence for an event. First-pass data includes EPS surprise for earnings events and TSMC monthly revenue YoY changes.

`event_returns`
: Long-format event-level CAR windows and abnormal returns versus QQQ, SOXX, and SMH. Rows are keyed by event, affected ticker, return window, and benchmark. This is the core table for repeatable event review.

`event_reviews`
: Rule-based summaries built from `events`, `event_impacts`, `event_metrics`, and `event_returns`. Each row explains one event impact with raw reaction, benchmark attribution, metric surprise, thesis impact, confidence, and data-quality status.

`segment_kpis`
: Manually verified segment-level KPIs. This is manual-first because company segment disclosures are not reliably exposed through simple companyfacts calls.

`factor_dashboard`
: Daily derived metrics: returns, relative returns, rolling beta, realized vol, drawdown, residual return, and volume z-score.

`valuation_snapshots`
: Current valuation multiples from yfinance. Treat these as screening data and verify important values against primary filings or a paid data source.

`forward_price_estimates`
: Scenario price cones for multiple horizons. These are probability ranges, not target prices.

`investment_scorecard`
: Current setup labels and component scores for investability review.

## Design Choices

1. DuckDB first
: It is local, fast, easy to inspect, and enough for the first 90 days. PostgreSQL can be added later if scheduling or concurrent writes become important.

2. Manual segment KPI import first
: Segment revenue is high-value but disclosure formats vary by company and filing. A brittle parser would create false precision. The first version supports clean manual CSV ingestion.

3. Event study requires curated event dates
: TSMC monthly revenue periods are not the same as announcement dates. For lead-lag research, use actual announcement dates in `events`.

4. Scores are decision support
: The scorecard ranks research priority and setup quality. It is not a buy/sell command.

5. Single writer
: DuckDB supports many reads but only one writer at a time. Run ingestion scripts sequentially when writing to the same database file.

## Implemented CLI

```bash
uv run python -m scripts.init_db
uv run python -m scripts.ingest_prices --start 2018-01-01
uv run python -m scripts.ingest_sec --tickers GOOGL NVDA AMD TSM
uv run python -m scripts.ingest_tsmc_revenue --years 2018 2019 2020 2021 2022 2023 2024 2025 2026
uv run python -m scripts.import_events data/manual/events_ai_compute.csv
uv run python -m scripts.import_event_impacts data/manual/event_impacts_ai_compute.csv
uv run python -m scripts.import_event_metrics data/manual/event_metrics_ai_compute.csv
uv run python -m scripts.import_segments data/manual/segment_kpis_template.csv
uv run python -m scripts.build_price_features
uv run python -m scripts.build_fundamentals
uv run python -m scripts.build_factor_dashboard
uv run python -m scripts.build_event_returns --benchmarks QQQ SOXX SMH
uv run python -m scripts.build_event_reviews
uv run python -m scripts.ingest_valuation
uv run python -m scripts.build_forward_analysis
uv run python -m scripts.run_event_study --event-type earnings --window-before 5 --window-after 20
```

## Next Implementation Steps

1. Add hyperscaler capex events and product/export-control events to the curated event set.
2. Add segment KPI extraction helpers one company at a time, starting with GOOGL and AMD because their segment tables are cleaner.
3. Add evidence cards and scorecard evidence IDs after the first event-review outputs are manually reviewed.
4. Add an IV monitor table and adapter after choosing an options data source.
