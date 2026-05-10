# Stance Audit Report

as_of_date: 2026-05-08

This report audits how `research_stance` was produced. It is designed to find overconfident outputs, missing evidence categories, and conflicts between operating evidence and factor residual evidence.

## GOOGL

- Stance: neutral
- Modifier: mixed_cash_flow
- Confidence: 0.75
- Net weighted score: 9.6

### Evidence Count By Type

| Evidence type | Direction | Count |
|---|---|---:|
| cash_flow_quality | negative | 1 |
| cash_flow_quality | positive | 1 |
| event_reaction | negative | 1 |
| event_reaction | neutral | 2 |
| event_reaction | positive | 2 |
| factor_residual | positive | 1 |
| segment_momentum | negative | 3 |
| segment_momentum | positive | 2 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| cash_flow_quality | positive | 13.5 | 0.90 | 1 |
| segment_momentum | positive | 10.8 | 0.90 | 2 |
| factor_residual | positive | 9.0 | 0.80 | 1 |
| event_reaction | positive | 2.6 | 0.82 | 2 |
| event_reaction | neutral | 0.0 | 0.80 | 2 |
| event_reaction | negative | -1.3 | 0.82 | 1 |
| cash_flow_quality | negative | -10.1 | 0.90 | 1 |
| segment_momentum | negative | -14.8 | 0.90 | 3 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| conflicting_evidence | 0.75 | positive and negative evidence are both material |

### Conflicts

- high: GOOGL has positive residual evidence but negative segment driver evidence.
- medium: GOOGL has positive cash-flow evidence but negative segment driver evidence.
- medium: GOOGL has positive operating-driver evidence but negative cash-flow evidence.

### Top Positive Evidence

- GOOGL cash-flow feature fcf_margin is positive with value 0.092. (strength very_high, confidence 0.90)
- GOOGL factor residual evidence is positive: 20d 8.2%, 60d 7.6%. (strength high, confidence 0.80)
- GOOGL google_cloud_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- GOOGL cloud_growth_score is positive with score 100.0. (strength very_high, confidence 0.90)
- GOOGL event reaction evidence for googl_earnings_2026_04_29: The reaction looks positive versus the pre-event factor model. (strength high, confidence 0.82)

### Top Negative Evidence

- GOOGL cash-flow feature capex_to_ocf is negative with value 0.779. (strength high, confidence 0.90)
- GOOGL fcf_quality_score is negative with score 9.2. (strength very_high, confidence 0.90)
- GOOGL other_bets_margin is negative with score 0.0. (strength very_high, confidence 0.90)
- GOOGL capex_pressure_score is negative with score 22.1. (strength high, confidence 0.90)
- GOOGL event reaction evidence for googl_earnings_2026_02_04: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.82)

### Final Stance Explanation

GOOGL remains a high-quality AI/Cloud compounder if Search resilience and Cloud margin expansion can offset AI CapEx pressure. Current stance is neutral with net evidence score 9.6. GOOGL cash-flow feature fcf_margin is positive with value 0.092.; GOOGL cash-flow feature capex_to_ocf is negative with value 0.779.

## NVDA

- Stance: constructive
- Modifier: factor_conflicted
- Confidence: 0.70
- Net weighted score: 11.7

### Evidence Count By Type

| Evidence type | Direction | Count |
|---|---|---:|
| cash_flow_quality | positive | 2 |
| event_reaction | mixed | 5 |
| event_reaction | negative | 2 |
| event_reaction | neutral | 3 |
| factor_residual | negative | 1 |
| segment_momentum | positive | 11 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| segment_momentum | positive | 19.7 | 0.88 | 11 |
| cash_flow_quality | positive | 5.0 | 0.80 | 2 |
| event_reaction | mixed | 0.0 | 0.39 | 5 |
| event_reaction | neutral | 0.0 | 0.80 | 3 |
| event_reaction | negative | -1.1 | 0.88 | 2 |
| factor_residual | negative | -12.0 | 0.80 | 1 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| data_quality_issues | 0.70 | multiple data-quality issues cap confidence |

### Conflicts

- high: NVDA has positive company-driver evidence but negative factor residual evidence.
- high: NVDA has a positive stance, but factor residual evidence is negative. Treat the stance as conflicted until residual pressure or operating evidence resolves.

### Top Positive Evidence

- NVDA cash-flow feature capex_to_ocf is positive with value 0.035. (strength very_high, confidence 0.80)
- NVDA oem_and_other_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA professional_visualization_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA data_center_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA ai_end_market_breadth_score is positive with score 87.3. (strength very_high, confidence 0.90)

### Top Negative Evidence

- NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%. (strength high, confidence 0.80)
- NVDA event reaction evidence for nvda_earnings_2026_02_25: The reaction looks negative versus the pre-event factor model. (strength medium, confidence 0.88)
- NVDA event reaction evidence for nvda_earnings_2025_02_26: The reaction looks negative versus the pre-event factor model. (strength medium, confidence 0.88)

### Final Stance Explanation

NVDA retains AI compute platform leadership if Data Center growth, gross margin, and supply visibility remain strong. Current stance is constructive with net evidence score 11.7. NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%.; NVDA cash-flow feature capex_to_ocf is positive with value 0.035.

## AMD

- Stance: strong_constructive
- Modifier: factor_led
- Confidence: 0.70
- Net weighted score: 29.8

### Evidence Count By Type

| Evidence type | Direction | Count |
|---|---|---:|
| cash_flow_quality | positive | 2 |
| event_reaction | mixed | 4 |
| event_reaction | negative | 2 |
| event_reaction | neutral | 3 |
| event_reaction | positive | 1 |
| factor_residual | positive | 1 |
| segment_momentum | negative | 4 |
| segment_momentum | positive | 5 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| factor_residual | positive | 20.0 | 0.80 | 1 |
| segment_momentum | positive | 10.9 | 0.78 | 5 |
| cash_flow_quality | positive | 7.9 | 0.90 | 2 |
| event_reaction | positive | 0.8 | 0.75 | 1 |
| event_reaction | mixed | 0.0 | 0.37 | 4 |
| event_reaction | neutral | 0.0 | 0.80 | 3 |
| event_reaction | negative | -1.5 | 0.84 | 2 |
| segment_momentum | negative | -8.2 | 0.75 | 4 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| data_quality_issues | 0.70 | multiple data-quality issues cap confidence |

### Conflicts

- high: AMD has positive residual evidence but negative segment driver evidence.
- medium: AMD positive stance is materially supported by factor residual evidence; audit non-factor confirmation before raising confidence.
- medium: AMD has positive cash-flow evidence but negative segment driver evidence.

### Top Positive Evidence

- AMD factor residual evidence is positive: 20d 28.0%, 60d 54.3%. (strength very_high, confidence 0.80)
- AMD cash-flow feature capex_to_ocf is positive with value 0.132. (strength very_high, confidence 0.90)
- AMD cash-flow feature fcf_margin is positive with value 0.250. (strength high, confidence 0.90)
- AMD data_center_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.70)
- AMD data_center_momentum_score is positive with score 100.0. (strength very_high, confidence 0.70)

### Top Negative Evidence

- AMD operating_margin_quality_score is negative with score 14.4. (strength very_high, confidence 0.90)
- AMD data_center_margin is negative with score 27.7. (strength high, confidence 0.70)
- AMD client_and_gaming_margin is negative with score 16.0. (strength high, confidence 0.70)
- AMD data_center_margin_score is negative with score 27.7. (strength high, confidence 0.70)
- AMD event reaction evidence for amd_earnings_2026_02_03: The reaction looks negative versus the pre-event factor model. (strength very_high, confidence 0.85)

### Final Stance Explanation

AMD upside depends on becoming a credible second supplier in AI accelerators while sustaining EPYC/Data Center momentum. Current stance is strong_constructive with net evidence score 29.8. AMD factor residual evidence is positive: 20d 28.0%, 60d 54.3%.; AMD cash-flow feature capex_to_ocf is positive with value 0.132.

## TSM

- Stance: constructive
- Modifier: data_quality_capped
- Confidence: 0.65
- Net weighted score: 10.1

### Evidence Count By Type

| Evidence type | Direction | Count |
|---|---|---:|
| event_reaction | mixed | 4 |
| event_reaction | negative | 3 |
| event_reaction | neutral | 3 |
| factor_residual | negative | 1 |
| segment_momentum | positive | 1 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| segment_momentum | positive | 23.6 | 0.90 | 1 |
| event_reaction | mixed | 0.0 | 0.41 | 4 |
| event_reaction | neutral | 0.0 | 0.82 | 3 |
| event_reaction | negative | -1.5 | 0.85 | 3 |
| factor_residual | negative | -12.0 | 0.60 | 1 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| data_quality_issues | 0.70 | multiple data-quality issues cap confidence |
| missing_cash_flow_evidence | 0.75 | missing cash-flow evidence caps confidence |
| tsm_fx_model_gap | 0.65 | TSM factor evidence is capped until USD/TWD is added to the model |

### Conflicts

- high: TSM has positive company-driver evidence but negative factor residual evidence.
- high: TSM has a positive stance, but factor residual evidence is negative. Treat the stance as conflicted until residual pressure or operating evidence resolves.

### Top Positive Evidence

- TSM advanced_node_mix_score is positive with score 74.0. (strength high, confidence 0.90)

### Top Negative Evidence

- TSM factor residual evidence is negative: 20d -13.7%, 60d -24.0%. Confidence is capped for missing FX/geopolitical factor. (strength very_high, confidence 0.60)
- TSM event reaction evidence for tsmc_monthly_revenue_2026_03: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)
- TSM event reaction evidence for tsm_earnings_2026_04_15: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)
- TSM event reaction evidence for tsm_earnings_2025_10_15: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)

### Final Stance Explanation

TSM remains the manufacturing bottleneck of AI compute if monthly revenue momentum, HPC mix, advanced node mix, and margin quality remain strong. Current stance is constructive with net evidence score 10.1. TSM advanced_node_mix_score is positive with score 74.0.; TSM factor residual evidence is negative: 20d -13.7%, 60d -24.0%. Confidence is capped for missing FX/geopolitical factor.
