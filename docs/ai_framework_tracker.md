# AI Trusted Execution Tracker

This tracker turns the trusted-execution framework into an auditable monthly
research loop. It is not a trading system and not investment advice.

## Operating Thesis

The core asset is not intelligence by itself. The core asset is trusted
execution of intelligence:

- who authorizes an agent to act
- who executes the real-world action
- who verifies success or failure
- who owns rollback, liability, and audit
- how many expert review minutes are needed per verified task

## Manual Inputs

Update these CSVs first:

```bash
data/manual/ai_framework_indicators.csv
data/manual/ai_framework_predictions.csv
data/manual/ai_framework_scenarios.csv
data/manual/ai_framework_holdings.csv
```

`ai_framework_indicators.csv`
: Leading indicators across capacity, cost, authority, outcome, meta, and
  watchlist layers. Each row has an `as_of_date`, directional threshold, status,
  confidence, source, and notes.

`ai_framework_predictions.csv`
: Falsifiable predictions with deadlines, current values, probability estimates,
  and explicit falsifiers.

`ai_framework_scenarios.csv`
: Scenario probability weights. Risk and tail scenarios affect the cash decision
  and lower risk-control scores for non-core holdings.

`ai_framework_holdings.csv`
: Research portfolio illustration with target weights, bands, mapped control
  layers, thesis text, and risk flags. Basket allocations should be stored as
  their investable subholdings, such as `MSCI`, `MCO`, `SPGI`, and `VEEV` for
  the vertical-verifier basket. Use `exposure_map` for overlapping control-right
  exposure, such as `authority:18;outcome:10`.

## Build Commands

```bash
uv run python -m scripts.import_ai_framework
uv run python -m scripts.build_ai_framework_tracker
```

Outputs:

```bash
reports/ai_execution_tracker.md
data/exports/ai_framework_indicators_scored.csv
data/exports/ai_framework_predictions_scored.csv
data/exports/ai_framework_portfolio_exposure.csv
data/exports/ai_framework_decisions.csv
```

## Scoring Logic

Indicator status maps to a 0-100 support score:

- green: 85
- yellow: 55
- red: 20
- unknown: 45

Prediction status maps similarly, blended with probability:

- confirmed: 90
- on_track: 75
- watch: 55
- unknown: 45
- at_risk: 30
- falsified: 10

Holding decision score:

```text
0.35 * indicator_support
+ 0.30 * prediction_support
+ 0.20 * thesis_alignment
+ 0.15 * risk_control
```

Cash is scored separately as dry powder. When risk and tail scenario probability
is high, the system can suggest raising cash inside its target band.

## Review Discipline

Use the report as a monthly review queue:

1. Investigate red and unknown indicators before changing weights.
2. Update prediction probabilities only when new evidence changes the base rate.
3. Treat `watch` labels as research priority, not automatic sell signals.
4. Trim only when the score falls below the watch range or a falsifier is hit.
5. Keep source URLs and notes specific enough to audit later.

## Rebalance Gates

The three framework-level questions are tracked explicitly in the generated
report:

1. Does METR task horizon keep extending?
2. Does risk-adjusted cost per verified task keep declining?
3. Do enterprise agents keep gaining write/execute permission?

If any one of these flips to `red` or a prediction is falsified, the right
response is a framework review before a portfolio rebalance.

## Agent Runtime Watchlist

The public portfolio does not force a position in agent security/runtime/
observability until there is a clean proxy. Track agent-specific revenue share,
IPO candidates, or disclosed product traction from names such as DDOG, CRWD,
PANW, OKTA, and private agent-infrastructure companies.
