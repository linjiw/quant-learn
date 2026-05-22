# AI Strategy System

This is the Phase 1 translation of the trusted-execution framework into a
systematic-discretionary strategy process. It is deliberately not an automated
trading system.

## Design Boundary

The system can automate:

- indicator monitoring
- plateau alerts
- company-to-control-right score tracking
- research queues for valuation overlays and watchlist gaps

The system should not automate yet:

- broker execution
- tax-lot decisions
- regime-change calls
- short-term price predictions
- full portfolio turnover

The framework is structural and multi-year. A signal is a prompt for review, not
a trade order.

## Inputs

```bash
data/manual/ai_control_right_scores.csv
data/manual/ai_framework_indicators.csv
data/manual/ai_framework_predictions.csv
data/manual/ai_framework_scenarios.csv
data/manual/ai_framework_holdings.csv
```

`ai_control_right_scores.csv`
: Quarterly company-to-control-right score matrix. Scores are 0-100 for
  capacity, cost, authority, outcome, and physical AI. The first version is a
  manual seed. Later versions can be produced from filings, earnings calls, and
  LLM-assisted extraction with human review.

## Build Commands

```bash
uv run python -m scripts.import_ai_framework
uv run python -m scripts.build_ai_framework_tracker
uv run python -m scripts.build_ai_strategy_signals
```

Outputs:

```bash
reports/ai_strategy_system.md
data/exports/ai_strategy_signals.csv
data/exports/ai_control_right_scores_latest.csv
```

## Signal Types

`plateau_detection`
: Capability, economic, and trust plateau alerts. These are the only signals
  that can invalidate the framework. They require manual review before any
  rebalance.

`watchlist_gap`
: Tracks missing public-market exposure, especially agent runtime, security,
  observability, credential vaults, MCP gateways, and policy-as-code.

`mispricing_research`
: Identifies areas where the framework says a control right may matter but the
  system lacks a valuation-implied score. This is a research queue, not a trade.

## Recommended Operating Mode

Use this as a spreadsheet-plus discipline before building a full trading stack:

1. Update indicators weekly or monthly.
2. Update control-right scores quarterly.
3. Run the tracker and strategy signal report.
4. Rebalance manually only after reviewing plateau alerts and valuation overlays.
5. Do not connect execution APIs until the process has at least 6-12 months of
   live history.
