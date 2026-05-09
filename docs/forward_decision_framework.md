# Forward Estimate And Investability Framework

This system does not try to produce a single "correct" target price. For these
four stocks, a point forecast is usually less useful than a probability cone plus
a disciplined checklist.

## Forward Price Estimate

The first version uses:

- latest adjusted price
- 20/60/120-day trend
- residual 60-day return after QQQ/SOXX exposure
- 60-day realized volatility

It creates price cones for 21, 63, 126, and 252 trading days. The cone is a
scenario range, not a price target.

The cone uses a tail-risk multiplier calibrated against historical coverage. The
goal is not to maximize upside precision; it is to avoid understating downside
range.

Interpretation:

- `p10_price`: downside scenario if volatility works against the current drift
- `p50_price`: median drift scenario
- `p90_price`: upside scenario if volatility works with the current drift
- `probability_gain`: model-implied probability of a positive return

## Investability Score

The score is a research-priority score. It is not a buy/sell signal.
Model confidence is capped below 100% by design.

```text
Investability =
0.25 * Momentum
+ 0.20 * Residual alpha / relative strength
+ 0.20 * Quality
+ 0.15 * Valuation discipline
+ 0.15 * Risk control
+ 0.05 * Event setup
```

## Decision Labels

`Research candidate`
: Strong enough to justify deeper fundamental work now.

`Watchlist / wait for setup`
: Interesting, but either valuation, risk, or alpha evidence is not clean enough.

`Strong momentum, elevated risk`
: Price action is strong, but volatility, beta, drawdown, or valuation risk is high.

`High-risk / needs better setup`
: The current setup is weak or too risky for a clean research conclusion.

## Decision Checklist

Before investing, answer these in order:

1. Is the latest price data fresh?
2. Is the stock outperforming QQQ and SOXX/SMH, or just moving with beta?
3. Is residual return positive?
4. Is the forward cone acceptable if the p10 scenario happens?
5. Is fundamental quality improving?
6. Is valuation risk tolerable relative to growth quality?
7. Is there a near-term event that can invalidate the thesis?
8. What would prove the thesis wrong?

See `docs/strategy_loopholes.md` for the current loophole audit.
