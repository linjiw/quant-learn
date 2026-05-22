# AI Strategy System Phase 1

As of: 2026-05-21

This is a systematic-discretionary research system, not an automated trading
system. It converts the control-rights framework into review signals, not broker
orders.

## System Boundary

- Position sizing can become algorithmic after the indicator set has a live
  history.
- Plateau detection is an alert, not an automatic trade.
- Regime change decisions require manual review.
- Execution APIs, tax-lot logic, and broker routing are intentionally out of
  scope for Phase 1.

## Strategy Signals

| signal_type         | severity   | action_bias                   | target_layer   | target_tickers                          | summary                                                           | suggested_review                                                   |
|:--------------------|:-----------|:------------------------------|:---------------|:----------------------------------------|:------------------------------------------------------------------|:-------------------------------------------------------------------|
| plateau_detection   | medium     | monitor_monthly               | capability     |                                         | Capability plateau watch                                          | Increase capability review cadence; no automatic rebalance.        |
| plateau_detection   | info       | collect_data                  | cost           |                                         | Economic plateau watch                                            | Collect better cost evidence before changing weights.              |
| plateau_detection   | high       | framework_review              | authority      |                                         | Trust plateau watch                                               | Pause automatic shifts and run manual authority framework review.  |
| watchlist_gap       | info       | no_position_until_clean_proxy | watchlist      | DDOG;CRWD;PANW;OKTA;private_agent_infra | Agent runtime security and observability monetization             | Track agent-specific revenue, IPOs, or disclosed product traction. |
| mispricing_research | medium     | run_valuation_overlay         | outcome        | MCO;MSFT;SPGI;VEEV                      | Outcome-control candidates need valuation-implied-score research. | Build a valuation overlay before sizing outcome mispricing trades. |

## Control-Right Score Matrix

| ticker    | holding_name         |   capacity_score |   cost_score |   authority_score |   outcome_score |   physical_ai_score | confidence   |
|:----------|:---------------------|-----------------:|-------------:|------------------:|----------------:|--------------------:|:-------------|
| 000660.KS | SK Hynix             |               85 |           10 |                 0 |               0 |                   0 | 40%          |
| AVGO      | Broadcom             |               75 |           65 |                10 |              10 |                   5 | 45%          |
| CASH      | Cash                 |                0 |            0 |                 0 |               0 |                   0 | 100%         |
| CEG       | Constellation Energy |               65 |            5 |                 0 |               0 |                   0 | 35%          |
| GOOGL     | Alphabet             |               65 |           70 |                60 |              55 |                  10 | 45%          |
| MCO       | Moody's              |                5 |            5 |                10 |              85 |                   0 | 40%          |
| MSCI      | MSCI                 |               10 |           10 |                20 |              65 |                   0 | 40%          |
| MSFT      | Microsoft            |               20 |           10 |                90 |              75 |                   5 | 45%          |
| NVDA      | NVIDIA               |               95 |           60 |                20 |              15 |                  10 | 45%          |
| SPGI      | S&P Global           |                5 |           10 |                10 |              80 |                   0 | 40%          |
| TER       | Teradyne             |               65 |           15 |                 0 |              10 |                  35 | 40%          |
| TSM       | TSMC                 |               90 |           20 |                 5 |               5 |                   5 | 45%          |
| VEEV      | Veeva Systems        |                5 |           10 |                15 |              85 |                   0 | 40%          |
| VRT       | Vertiv               |               70 |           10 |                 0 |               0 |                   5 | 40%          |

## Build Sequence

1. Keep running the tracker from `reports/ai_execution_tracker.md`.
2. Update control-right scores quarterly from filings, calls, and source memos.
3. Use this report to decide which research queue deserves attention.
4. Build valuation-implied scores before treating mispricing research as trades.
