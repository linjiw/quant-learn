# CLAUDE.md

This file gives Claude Code guidance for working in this repository.

## What This Repository Is

`quant-learn` is a local, review-first equity research system. It has two related
product surfaces:

1. Core AI compute value-chain research for `GOOGL`, `NVDA`, `AMD`, and `TSM`.
2. An AI trusted-execution framework tracker and static dashboard covering a broader
   research portfolio and control-rights thesis.

The system is deliberately not an auto-trading or broker-execution system. Scores,
signals, stances, portfolio weights, and dashboards are decision-support artifacts for
human review. Preserve this framing in code, docs, and generated reports.

## Core Commands

Run commands from the repository root.

```bash
uv sync
uv run pytest
uv run pytest tests/test_ai_framework_tracker.py
uv run pytest tests/test_evidence.py::test_name
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .
```

Ruff is configured in `pyproject.toml` with line length 100 and Python 3.9 target
syntax. Runnable scripts are module entry points:

```bash
uv run python -m scripts.<script_name>
```

Do not run scripts by filesystem path when a module invocation is available.

## Important Entry Points

Core data and analytics:

```bash
export SEC_USER_AGENT="Your Name your.email@example.com"
uv run python -m scripts.init_db
uv run python -m scripts.ingest_prices --start 2018-01-01
uv run python -m scripts.ingest_sec
uv run python -m scripts.ingest_tsmc_revenue --years 2018 2019 2020 2021 2022 2023 2024 2025 2026
uv run python -m scripts.run_pipeline --full
```

AI trusted-execution tracker:

```bash
uv run python -m scripts.import_ai_framework
uv run python -m scripts.build_ai_framework_tracker
uv run python -m scripts.build_ai_strategy_signals
```

Daily website refresh and Pages artifact:

```bash
uv run python -m scripts.daily_ai_framework_refresh
uv run python -m scripts.daily_ai_framework_refresh --skip-market-data --skip-link-audit
```

Static framework website:

```bash
open site/ai-framework/index.html
```

The website has no build step. For browser testing through a local server:

```bash
cd site/ai-framework
python3 -m http.server 8765
```

Then open `http://127.0.0.1:8765/`.

## Architecture

Data flows one way:

```text
External sources and manual CSVs
  -> quant_learn/ingest/
  -> data/duckdb/quant_learn.duckdb
  -> quant_learn/analytics/
  -> data/exports/*.csv and reports/*.md
  -> optional static website views
```

Main directories:

- `quant_learn/`: library code. Keep real logic here.
- `quant_learn/ingest/`: adapters for external and manual data.
- `quant_learn/analytics/`: derived features, evidence, stances, reports, and AI
  framework decision support.
- `scripts/`: thin CLI wrappers. They should parse arguments and orchestrate, not
  contain business logic.
- `tests/`: pytest coverage. Tests isolate DuckDB through `tmp_path` and monkeypatching;
  they must not touch the real database file.
- `docs/`: system design, methodology, workflow, and audit notes.
- `data/manual/`: versioned seed CSVs for manually reviewed inputs.
- `reports/`: generated markdown reports and QA screenshots.
- `site/ai-framework/`: static dashboard for the trusted-execution framework.

## Database and Schema Rules

- DuckDB is the local research store. It supports many readers and one writer; run
  write-heavy ingest/build scripts sequentially.
- Schema is code. Table definitions live in `quant_learn/db.py` in `SCHEMA_SQL` and
  idempotent migrations live in `MIGRATION_SQL`.
- `initialize_database()` is called liberally and must remain idempotent.
- Write dataframe outputs through `upsert_dataframe(conn, df, table, key_columns)`.
- Dataframe columns should match table columns exactly unless a helper explicitly
  handles projection.
- Use `quant_learn.time.utc_now_naive()` for `created_at`, `updated_at`,
  `ingested_at`, and similar timestamps. DuckDB timestamps are naive UTC.
- CapEx is stored as a positive outflow. FCF is operating cash flow minus CapEx.

## Point-in-Time Discipline

Point-in-time correctness is a core invariant.

- Fundamentals carry `available_date` and `filed_date`.
- Valuation joins must only use fundamentals where `available_date <= date`.
- Rolling factor exposures dated `t` are estimated from windows ending at `t-1`.
- Event studies separate `event_date` from `reaction_date`.
- Do not introduce look-ahead into factor, valuation, fundamentals, event, evidence,
  stance, or backtest layers.

## Run Traceability

Pipeline-affecting scripts should preserve auditability:

- Generate a `run_id` with `generate_run_id` from `quant_learn.analytics.auditability`.
- Record `pipeline_runs` rows where applicable.
- Preserve `data_snapshot_hash` lineage in generated memos.
- Archive previous evidence, stance, and audit rows into `*_history` tables before
  replacing current rows.

## Core Research Pipeline

`scripts/run_pipeline.py` runs ordered stages:

```text
fundamentals
-> segments
-> factor
-> events
-> valuation
-> evidence
-> stance_backtest
-> weekly_digest
```

Conceptual dependency chain:

```text
fundamentals_quarterly_normalized
+ segment_features
+ factor_residuals
+ valuation_features
+ event_reviews
-> evidence_cards
-> research_stance
-> stance audit tables
-> reports/decision_memo.md
```

The runner fails fast on stale or empty upstream tables unless `--force-stale` is used.

## AI Trusted-Execution Framework Layer

The AI framework tracker is a structural research layer, not a trading robot.

Primary docs:

- `docs/ai_framework_tracker.md`
- `docs/ai_strategy_system.md`
- `docs/ai_framework_website_design.md`

Primary data:

- `data/manual/ai_framework_indicators.csv`
- `data/manual/ai_framework_predictions.csv`
- `data/manual/ai_framework_scenarios.csv`
- `data/manual/ai_framework_holdings.csv`
- `data/manual/ai_control_right_scores.csv`

Primary code:

- `quant_learn/ingest/ai_framework.py`
- `quant_learn/analytics/ai_framework_tracker.py`
- `quant_learn/analytics/ai_strategy_signals.py`
- `scripts/import_ai_framework.py`
- `scripts/build_ai_framework_tracker.py`
- `scripts/build_ai_strategy_signals.py`

Outputs:

- `reports/ai_execution_tracker.md`
- `reports/ai_strategy_system.md`
- `ai_framework_decisions` table
- `ai_strategy_signals` table

Framework invariants:

- Signals are review prompts, not orders.
- Portfolio weights are research illustrations, not advice.
- Control-right exposures can overlap and should not be forced to sum to 100.
- Plateau detection needs human judgment; do not convert it into blind execution.
- Treat risk-adjusted cost per verified task, human-review minutes, and enterprise
  write-permission penetration as partially observed variables unless direct data exists.

## Static Website Rules

The static dashboard lives in `site/ai-framework/`.

- `index.html`: shell and view containers.
- `styles.css`: design system and responsive layout.
- `app.js`: deterministic rendering and view/filter interactions.
- `research-data.js`: site data, thesis text, and source registry.
- `README.md`: local usage notes.

Design expectations:

- First screen should be the usable dashboard, not a marketing landing page.
- Keep the tone work-focused, dense, and readable.
- Use cards for repeated holdings, metrics, signals, and source rows only.
- Keep source/auditability visible, especially on narrow screens.
- No decorative orbs, marketing hero gradients, or unnecessary illustration.
- Do not use viewport-width font scaling. Use fixed sizes and breakpoints.
- Watch for text overflow, horizontal scrolling, and source URL wrapping.

When editing the website:

```bash
node --check site/ai-framework/app.js
node --check site/ai-framework/research-data.js
node scripts/validate_ai_framework_site.mjs
node scripts/check_ai_framework_sources.mjs
```

Verify these invariants:

- Holding weights sum to 100.
- All holding, signal, and monitoring-question source IDs resolve.
- Claim-level provenance source IDs resolve.
- No duplicate tickers unless intentionally modeling a basket.
- Browser console has no errors.
- Link-health results are reviewed; bot-blocked 403s should be documented rather than
  treated as proof that a claim is false.

## Research Writing Rules

Be explicit about what the evidence does and does not prove.

- Product existence is not production adoption.
- Architecture strength is not monetization durability.
- Trusted data or workflow ownership is not automatically outcome-verification revenue.
- Token price decline is not total cost of agent ownership.
- Capacity bottlenecks can be cyclical; do not describe them as authority or outcome moats.
- Any generated report should say it is research support, not investment advice or a
  buy/sell instruction.

Prefer primary sources where practical. If using secondary sources, label the limitation
and avoid over-precision.

## Testing Expectations

Before finishing non-trivial changes, run the narrowest relevant tests plus the full
suite when feasible:

```bash
uv run ruff check .
uv run pytest
```

For website-only changes, also run JS syntax and data integrity checks. For analytics or
database changes, add or update pytest coverage.

## Dirty Worktree and Generated Files

This repo can have generated reports and user edits in progress.

- Do not revert changes you did not make.
- Do not use destructive git commands.
- Ignore unrelated dirty files unless they block the task.
- Generated outputs under `reports/` may be intentionally refreshed; avoid churn unless
  the task requires it.
- `data/duckdb/`, `data/exports/`, and historical generated outputs may be ignored by
  git; do not assume missing generated files are errors.
