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
: Legacy-compatible standardized research snapshot built from the normalized fundamentals layer.

`fundamentals_quarterly_normalized`
: Point-in-time quarterly fundamentals with `available_date`, source accession, XBRL tag lineage, YTD cash-flow fields, derived quarterly cash-flow fields, and data-quality flags. CapEx is normalized as a positive outflow and FCF is calculated as OCF minus CapEx.

`cash_flow_features`
: Cash-flow evidence features such as CapEx / OCF and FCF margin, keyed to normalized fundamental IDs.

`tsmc_monthly_revenue`
: TSMC monthly revenue in NT$ millions and YoY change from the official investor relations page.

`events`
: Manually curated event log for earnings, hyperscaler capex, product launches, export controls, and TSMC monthly revenue announcement dates. It separates `event_date` from `reaction_date` so after-market releases use the next trading session.

`event_impacts`
: Cross-ticker impact map. One event can affect multiple stocks, such as a TSMC monthly revenue release affecting `TSM`, `NVDA`, and `AMD`.

`event_metrics`
: Surprise and KPI evidence for an event. First-pass data includes EPS surprise for earnings events and TSMC monthly revenue YoY changes.

`event_returns`
: Long-format event-level CAR windows and abnormal returns versus QQQ, SOXX, SMH, and the PIT factor model when available. Rows are keyed by event, affected ticker, return window, and benchmark/model. It carries `data_quality_flag`, `missing_reason`, and `analysis_status`, so pending future windows are separated from true data issues.

`event_reviews`
: Rule-based summaries built from `events`, `event_impacts`, `event_metrics`, and `event_returns`. Each row explains one event impact with raw reaction, benchmark attribution, metric surprise, thesis impact, confidence, and data-quality status.

`segment_kpis`
: Flexible manually verified segment-level KPIs. This is manual-first because company segment disclosures are not reliably exposed through simple companyfacts calls. TSMC monthly revenue can be bridged automatically from the official monthly table.

`segments_view`
: Normalized view over `segment_kpis` for revenue, operating income, margin, and YoY growth where the source data supports it.

`segment_features`
: Segment-derived driver features for scorecards and future evidence cards.

`factor_dashboard`
: Daily derived metrics: returns, relative returns, rolling beta, realized vol, drawdown, residual return, and volume z-score.

`market_factor_inputs`
: Daily QQQ, SOXX, SMH, SPY, and 10Y inputs. Yahoo `^TNX` changes are normalized to basis points with `^TNX.diff() * 10`.

`factor_exposures`
: Rolling `QQQ + SOXX + Δ10Y bps` exposures. Exposures dated `t` are estimated using observations through `t-1`, preventing look-ahead.

`factor_residuals`
: Daily expected return, contribution, and residual-return decomposition, including 5/20/60-day compounded residual returns.

`residual_diagnostics`
: Residual concentration diagnostics for 20/60-day windows. It records whether a
factor-led residual move is broad-based or concentrated in the top 1/3 trading days.
Positive residual evidence that is too concentrated becomes a risk evidence card and can
cap confidence.

`valuation_metrics`
: Point-in-time trailing valuation metrics built from daily prices and the latest
fundamentals with `available_date <= date`. It includes market cap, enterprise value,
TTM revenue/gross profit/operating income/net income/FCF, trailing multiples, growth
rates, valuation percentiles, source fundamental IDs, and data-quality flags.

`valuation_features`
: Valuation evidence features such as valuation percentile, FCF yield, EV/Sales,
gross-profit multiple, growth-adjusted valuation, and GOOGL capex-adjusted FCF. If PIT
fundamentals cannot produce usable features for a ticker such as `TSM`, the builder can
fall back to the latest `valuation_snapshots` screening row with low confidence and
`data_quality_flag = snapshot_fallback`.

`evidence_cards`
: Source-linked evidence synthesized from event reactions, segment momentum,
cash-flow quality, factor residuals, and valuation features. Each card carries
direction, strength, confidence, materiality, thesis/risk tags, data-quality flags, and
source lineage.

`research_stance`
: Per-ticker research stance generated from evidence cards. Stance values are
`strong_constructive`, `constructive`, `neutral`, `cautious`, and `high_risk`.
Each row also carries a `stance_modifier` such as `factor_led`, `factor_conflicted`,
`mixed_cash_flow`, or `data_quality_capped`. Confidence is capped when evidence coverage
is thin, segment/cash-flow/factor evidence is missing, data-quality issues are material,
or TSM factor evidence lacks an FX factor.

Negative valuation evidence can cap high-confidence positive stances and add
`valuation_capped` to `stance_modifier`. Missing valuation evidence adds
`valuation_unknown`.

`stance_components`
: Audit table that decomposes each stance by evidence type and direction. It records
weighted score contribution, average confidence, evidence count, and top evidence IDs.

`stance_confidence_caps`
: Applied confidence caps with cap value and reason. This makes it clear when a stance
is confidence-limited by missing evidence, data-quality issues, conflicting evidence, or
the TSM FX-model gap.

`stance_conflicts`
: Explicit evidence conflicts such as positive segment evidence with negative factor
residual evidence, factor-dominated positive stance, and positive cash flow with negative
segment evidence.

`*_history`
: Append-style archives for `evidence_cards`, `research_stance`, `stance_components`,
`stance_confidence_caps`, and `stance_conflicts`. `build_evidence` archives the previous
state before replacing current tables, so prior memos can be traced back to the evidence
set that produced them.

`pipeline_runs`
: Pipeline run ledger with `run_id`, status, selected step range, freshness snapshot,
and `data_snapshot_hash`. The hash is written into the decision memo for reproducibility.

`valuation_snapshots`
: Current valuation multiples from yfinance. Treat these as screening data and verify important values against primary filings or a paid data source.

`forward_price_estimates`
: Scenario price cones for multiple horizons. These are probability ranges, not target prices.

`investment_scorecard`
: Current setup labels and component scores for investability review.

`ai_framework_indicators`
: Dated leading-indicator observations for the trusted-execution framework.
Rows are keyed by `as_of_date` and `indicator_id`, grouped by control layer
such as capacity, cost, authority, outcome, and meta.

`ai_framework_predictions`
: Dated falsifiable predictions with deadlines, target thresholds, current
values, probability estimates, confidence, and explicit falsifiers.

`ai_framework_scenarios`
: Scenario probability weights and portfolio posture notes. Risk and tail
scenario probabilities feed the dry-powder decision and risk-control scoring.

`ai_framework_holdings`
: Research portfolio illustration rows with target/current weights, bands,
mapped control layers, optional overlapping `exposure_map`, thesis text, risk
flags, and action bias.

`ai_framework_decisions`
: Derived decision-support output for the AI framework tracker. It combines
indicator support, prediction support, thesis alignment, risk control, scenario
risk, and target bands into a label, suggested weight, and rebalance flag.

`ai_control_right_scores`
: Dated company-to-control-right score matrix for capacity, cost, authority,
outcome, and physical AI exposure. This is the Phase 1 bridge from structural
framework to systematic-discretionary research signals.

`ai_strategy_signals`
: Non-executional review signals generated from plateau detection, watchlist
gaps, and mispricing research queues. These rows are alerts for human review,
not broker orders.

## Design Choices

1. DuckDB first
: It is local, fast, easy to inspect, and enough for the first 90 days. PostgreSQL can be added later if scheduling or concurrent writes become important.

2. Manual segment KPI import first
: Segment revenue is high-value but disclosure formats vary by company and filing. A brittle parser would create false precision. The first version supports clean manual CSV ingestion.

3. Event study requires curated event dates
: TSMC monthly revenue periods are not the same as announcement dates. For lead-lag research, use actual announcement dates in `events`.

4. Scores are decision support
: The scorecard ranks research priority and setup quality. It is not a buy/sell command.

5. Evidence before stance
: Research stance is generated from evidence cards, not directly from raw features.
Every stance includes positive evidence, negative/mixed evidence, falsifiers, next
catalysts, and data-quality caveats. A high-confidence stance requires enough evidence
coverage.

6. Audit before expansion
: Stance outputs are audited through `stance_components`, `stance_confidence_caps`, and
`stance_conflicts` before adding new model layers. This prevents a plausible memo from
hiding evidence imbalance or factor/operating-driver conflicts.

7. Strong stance needs non-factor confirmation
: `strong_constructive` is capped when positive evidence is factor-dominated and lacks
at least two non-factor positive evidence categories. Factor-led upside can still be
shown through `stance_modifier = factor_led`, but the memo must make the caveat visible.

8. Factor-led stance needs row-level confirmation
: If positive factor residual score is at least as large as positive non-factor score and
there are fewer than three non-factor positive evidence rows, the stance is capped at
`neutral`. Residual is evidence, not proof of alpha.

9. Research views live outside code
: `quant_learn/universe.py` stores structural configuration only: role, weights,
required KPIs, driver features, and structural risks. Thesis text, falsifiers, and next
catalysts live in `data/manual/research_views.csv` so research views can be updated
without code changes.

10. Valuation is price discipline, not a price target
: The valuation layer separates "company quality" from "stock setup." First-pass
valuation is trailing and reported, not forward consensus. Snapshot fallbacks are
screening evidence only and carry lower confidence.

11. Single writer
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
uv run python -m scripts.build_tsmc_segment_kpis --months 24
uv run python -m scripts.build_segment_features
uv run python -m scripts.build_segment_dashboard
uv run python -m scripts.build_price_features
uv run python -m scripts.build_fundamentals
uv run python -m scripts.build_factor_dashboard
uv run python -m scripts.build_factor_model
uv run python -m scripts.build_event_returns --benchmarks QQQ SOXX SMH
uv run python -m scripts.build_event_reviews
uv run python -m scripts.build_valuation
uv run python -m scripts.build_evidence
uv run python -m scripts.build_weekly_digest
uv run python -m scripts.run_pipeline --full
uv run python -m scripts.ingest_valuation
uv run python -m scripts.build_forward_analysis
uv run python -m scripts.import_ai_framework
uv run python -m scripts.build_ai_framework_tracker
uv run python -m scripts.build_ai_strategy_signals
uv run python -m scripts.run_event_study --event-type earnings --window-before 5 --window-after 20
```

## Next Implementation Steps

1. Add a TSM-specific FX/local-market diagnostic before changing the TSM factor model.
2. Add a stance backtest over archived evidence/stance rows.
3. Add event abnormal-return z-scores using pre-event residual volatility.
4. Add a TSM-specific FX model with USD/TWD after validating the current
   QQQ/SOXX/10Y residual layer.
5. Add a catalyst calendar for earnings, TSMC monthly revenue, product events, and
   export-control/regulatory windows.
6. Add an IV monitor table and adapter after choosing an options data source.
