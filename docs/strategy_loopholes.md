# Strategy Loopholes, Fixes, And Residual Risk

I am not 100% confident in any stock-price strategy. The correct engineering
goal is to make every known loophole visible, reduce avoidable error, and prevent
the system from presenting uncertainty as certainty.

## Fixed In The Hardened Forward Framework

1. Overconfident price targets
: Replaced target-price language with p10/p25/p50/p75/p90 scenario cones.

2. Narrow normal-distribution tails
: Added a tail-risk multiplier calibrated on 2018-2026 historical coverage. The
current multiplier is `1.45`.

3. No coverage validation
: Added `forward_model_validation`, which checks historical p10-p90 and p25-p75
coverage by ticker and horizon.

4. No confidence cap
: Added `model_confidence`, capped at 75% before data, risk, valuation, and event
penalties. The model is structurally prevented from claiming 100% confidence.

5. Missing event calendar
: Scorecards now flag `no curated event calendar loaded` and cap confidence when
event data is absent.

6. Data-source fragility
: Scorecards now include data-quality flags and call out valuation fields that
need source verification, especially for ADRs.

7. High momentum mistaken for low risk
: High volatility, high beta, large drawdown, and stretched valuation now force
the `Strong momentum, elevated risk` label instead of a positive research label.

## Still Not Solved

1. Non-stationarity
: 2018-2026 calibration can fail in a new market regime.

2. Point-in-time fundamentals
: The standardized SEC fundamental table is useful for current review, but not
yet safe for historical point-in-time fundamental backtests.

3. Valuation normalization
: yfinance fields can be stale or normalized differently across US listings and
ADRs. Important valuation work must be verified from filings or a paid data set.

4. Event data incompleteness
: Until curated events are populated, the system cannot answer whether a setup is
clean into earnings, TSMC revenue, export controls, or product launches.

5. Options and positioning
: The framework does not yet include implied volatility, skew, dealer positioning,
or options-market event expectations.

6. Liquidity and execution
: No slippage, spread, taxes, or portfolio concentration rules are included.

7. Causal attribution
: Residual return is an alpha proxy, not proof of causality.

8. Human thesis quality
: The system cannot replace a written thesis, invalidation rule, and source-level
fundamental review.

## Required Decision Gate

The framework is not allowed to call something a clean investment candidate until:

1. Current price and factor data are fresh.
2. Valuation data exists and suspicious values are verified.
3. Curated events are loaded.
4. Risk score is not impaired by beta, volatility, or drawdown.
5. Historical cone coverage is reviewed.
6. The p10 scenario is acceptable before position sizing.
7. A written invalidation rule exists.

If any gate fails, the output should be treated as `watchlist`, `elevated risk`,
or `insufficient confidence`, not a buy signal.
