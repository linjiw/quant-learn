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
8. Event-level return windows and data-quality flags in `event_returns`
9. Rule-based event review summaries in `event_reviews`
10. SEC-derived segment KPI extraction for GOOGL/NVDA/AMD filing tables
11. Flexible segment KPI layer with `segments_view` and `segment_features`
12. Event data-quality markdown report
13. PIT-safe `fundamentals_quarterly_normalized` snapshots with cash-flow lineage
14. `cash_flow_features` for CapEx / OCF and FCF margin evidence
15. PIT three-factor residual model using `QQQ + SOXX + Δ10Y bps`
16. PIT trailing valuation metrics and valuation features
17. `evidence_cards` synthesized from event, segment, cash-flow, factor, and
    valuation layers
18. `research_stance` and `reports/decision_memo.md` with falsifiers and caveats
19. Stance audit tables and `reports/stance_audit_report.md` for score contributions,
    confidence caps, and conflict flags
20. Audit-driven stance modifiers such as `factor_led`, `factor_conflicted`,
    `mixed_cash_flow`, `valuation_capped`, and `data_quality_capped`
21. Research auditability tools: `pipeline_runs`, evidence/stance history tables,
    residual concentration diagnostics, and `reports/weekly_digest.md`
22. AI trusted-execution framework tracker with leading indicators,
    falsifiable predictions, scenario weights, portfolio bands, and
    `reports/ai_execution_tracker.md`

For the design rationale and table definitions, see `docs/system_design.md`.
For the current loophole audit, see `docs/strategy_loopholes.md`.
For the trusted-execution tracker workflow, see `docs/ai_framework_tracker.md`.
For the Phase 1 systematic-discretionary strategy workflow, see
`docs/ai_strategy_system.md`.
For the daily website refresh and GitHub Pages deployment workflow, see
`docs/ai_framework_daily_automation.md`.
For the private local paper-portfolio tracker, see `docs/local_portfolio_tracker.md`.

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
uv run python -m scripts.import_events data/manual/events_ai_compute.csv
uv run python -m scripts.import_event_impacts data/manual/event_impacts_ai_compute.csv
uv run python -m scripts.import_event_metrics data/manual/event_metrics_ai_compute.csv
uv run python -m scripts.build_event_returns --benchmarks QQQ SOXX SMH
uv run python -m scripts.build_event_reviews
uv run python -m scripts.build_event_data_quality_report
```

`events` records the event itself, `event_impacts` records which stocks the event can
move, and `event_metrics` stores surprise/KPI evidence. `event_returns` is a
long-format attribution table keyed by event, affected ticker, return window,
and benchmark. `event_reviews` turns the event loop into readable review rows with
raw reaction, benchmark attribution, metric surprise, thesis impact, confidence,
and data-quality status.

Manual segment KPIs:

```bash
uv run python -m scripts.import_segments data/manual/segment_kpis_googl.csv
uv run python -m scripts.import_segments data/manual/segment_kpis_nvda.csv
uv run python -m scripts.import_segments data/manual/segment_kpis_amd.csv
uv run python -m scripts.import_segments data/manual/segment_kpis_tsm.csv
uv run python -m scripts.build_tsmc_segment_kpis --months 24
uv run python -m scripts.build_sec_segment_kpis --tickers GOOGL NVDA AMD --max-filings 16
uv run python -m scripts.build_company_segment_kpis --tickers GOOGL NVDA AMD --quarters 8
uv run python -m scripts.build_segment_features
uv run python -m scripts.build_segment_dashboard
```

`segment_kpis` is manual-first for company segment disclosures. TSMC monthly revenue is
bridged automatically from the official `tsmc_monthly_revenue` table. GOOGL/NVDA/AMD
segment rows can be extracted from official SEC filing tables with
`build_sec_segment_kpis`; review the exported CSV before treating any extracted value
as investment evidence. The split files under `data/manual/segment_kpis_*.csv` are the
versioned, reviewable seed set for the AI compute segment layer.

SEC-derived quarterly fundamentals and cash-flow features:

```bash
uv run python -m scripts.build_fundamentals
```

This creates both `fundamentals_quarterly_normalized` and the legacy-compatible
`fundamentals_quarterly` export. Cash-flow fields are stored as YTD and derived
quarterly values; CapEx is normalized as a positive outflow and FCF is calculated
as `operating_cash_flow_quarterly - capex_quarterly`. Use `available_date` /
`filed_date` for point-in-time research.

DuckDB allows many readers but only one writer. Run ingestion scripts sequentially when writing to the same database file.

## Run First Analytics

Generate a daily factor dashboard snapshot:

```bash
uv run python -m scripts.build_factor_dashboard
```

Generate PIT three-factor exposures, residuals, and factor-model event attribution inputs:

```bash
uv run python -m scripts.build_factor_model
uv run python -m scripts.build_event_returns --benchmarks QQQ SOXX SMH
uv run python -m scripts.build_event_reviews
```

`build_factor_model` uses `QQQ`, `SOXX`, and daily 10-year yield changes. With Yahoo
`^TNX`, the system normalizes `^TNX.diff() * 10` into basis points. Rolling exposures
use prior observations only: the exposure dated `t` is estimated from the window ending
at `t-1`, then applied to date `t` returns.

Generate evidence cards, research stance, and the decision memo:

```bash
uv run python -m scripts.build_valuation
uv run python -m scripts.build_evidence
```

`build_valuation` creates PIT trailing valuation metrics and valuation features from
available fundamentals and prices. For TSM, where normalized ADR fundamentals are
incomplete, the system can use the latest `valuation_snapshots` row as a low-confidence
current-screening fallback and marks those features as `snapshot_fallback`.
`evidence_cards` converts event reviews, segment features, cash-flow features, factor
residuals, and valuation features into source-linked evidence rows. `research_stance`
turns those rows into a research stance with confidence caps, stance modifiers,
falsifiers, next catalysts, and data-quality caveats. It also writes stance audit tables
for component contribution, confidence-cap lineage, and explicit conflict flags.
`build_evidence` archives the prior evidence/stance/audit rows into history tables
before rebuilding, records a `pipeline_runs` row, adds a `data_snapshot_hash` to the
memo, and writes an ignored point-in-time memo copy under `reports/history/`. The
output is a research memo, not a buy/sell instruction.

Generate the weekly governance digest:

```bash
uv run python -m scripts.build_weekly_digest
```

Run the analytics pipeline sequentially with freshness checks:

```bash
uv run python -m scripts.run_pipeline --full
```

If you intentionally skip stale upstream steps, pass `--force-stale`; otherwise the
runner fails fast when core upstream tables are stale or empty.

Generate the visual research report:

```bash
uv run python -m scripts.build_visual_report
```

Generate forward scenario estimates and an investability scorecard:

```bash
uv run python -m scripts.ingest_valuation
uv run python -m scripts.build_forward_analysis
```

Generate the AI trusted-execution tracker and decision system:

```bash
uv run python -m scripts.import_ai_framework
uv run python -m scripts.build_ai_framework_tracker
uv run python -m scripts.build_ai_strategy_signals
```

Update the private local $1,000 portfolio tracker:

```bash
uv run python -m scripts.update_local_portfolio
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
