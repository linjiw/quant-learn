# Stance Audit Report

as_of_date: 2026-05-09

This report audits how `research_stance` was produced. It is designed to find overconfident outputs, missing evidence categories, and conflicts between operating evidence and factor residual evidence.

## GOOGL

- Stance: neutral
- Modifier: mixed_cash_flow
- Confidence: 0.70
- Net weighted score: -6.8

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
| valuation | negative | 2 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| cash_flow_quality | positive | 11.2 | 0.90 | 1 |
| segment_momentum | positive | 9.0 | 0.90 | 2 |
| factor_residual | positive | 6.0 | 0.80 | 1 |
| event_reaction | positive | 1.7 | 0.82 | 2 |
| event_reaction | neutral | 0.0 | 0.80 | 2 |
| event_reaction | negative | -0.9 | 0.82 | 1 |
| cash_flow_quality | negative | -8.4 | 0.90 | 1 |
| segment_momentum | negative | -12.4 | 0.90 | 3 |
| valuation | negative | -13.1 | 0.75 | 2 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| conflicting_evidence | 0.75 | positive and negative evidence are both material |
| negative_valuation_evidence | 0.70 | negative valuation evidence caps high-confidence positive stance |

### Conflicts

- high: GOOGL has positive residual evidence but negative segment driver evidence.
- medium: GOOGL has positive cash-flow evidence but negative segment driver evidence.
- medium: GOOGL has positive factor residual evidence but negative valuation evidence.
- medium: GOOGL has positive operating-driver evidence but negative cash-flow evidence.

### Top Positive Evidence

- GOOGL cash-flow feature fcf_margin is positive with value 0.092. (strength very_high, confidence 0.90)
- GOOGL factor residual evidence is positive: 20d 8.2%, 60d 7.6%. (strength high, confidence 0.80)
- GOOGL google_cloud_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- GOOGL cloud_growth_score is positive with score 100.0. (strength very_high, confidence 0.90)
- GOOGL event reaction evidence for googl_earnings_2026_04_29: The reaction looks positive versus the pre-event factor model. (strength high, confidence 0.82)

### Top Negative Evidence

- GOOGL cash-flow feature capex_to_ocf is negative with value 0.779. (strength high, confidence 0.90)
- GOOGL valuation feature valuation_percentile_score is negative with score 0.0. (strength very_high, confidence 0.75)
- GOOGL valuation feature capex_adjusted_fcf_score is negative with score 28.9. (strength high, confidence 0.75)
- GOOGL fcf_quality_score is negative with score 9.2. (strength very_high, confidence 0.90)
- GOOGL other_bets_margin is negative with score 0.0. (strength very_high, confidence 0.90)

### Final Stance Explanation

GOOGL remains a high-quality AI/Cloud compounder if Search resilience and Cloud margin expansion can offset AI CapEx pressure. Current stance is neutral with net evidence score -6.8. GOOGL cash-flow feature fcf_margin is positive with value 0.092.; GOOGL cash-flow feature capex_to_ocf is negative with value 0.779.

## NVDA

- Stance: constructive
- Modifier: valuation_capped+factor_conflicted
- Confidence: 0.70
- Net weighted score: 13.0

### Evidence Count By Type

| Evidence type | Direction | Count |
|---|---|---:|
| cash_flow_quality | positive | 2 |
| event_reaction | mixed | 5 |
| event_reaction | negative | 2 |
| event_reaction | neutral | 3 |
| factor_residual | negative | 1 |
| segment_momentum | positive | 11 |
| valuation | negative | 1 |
| valuation | positive | 1 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| segment_momentum | positive | 16.9 | 0.88 | 11 |
| valuation | positive | 7.5 | 0.75 | 1 |
| cash_flow_quality | positive | 4.0 | 0.80 | 2 |
| event_reaction | mixed | 0.0 | 0.39 | 5 |
| event_reaction | neutral | 0.0 | 0.80 | 3 |
| event_reaction | negative | -0.8 | 0.88 | 2 |
| valuation | negative | -5.6 | 0.75 | 1 |
| factor_residual | negative | -9.0 | 0.80 | 1 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| conflicting_evidence | 0.75 | positive and negative evidence are both material |
| data_quality_issues | 0.70 | multiple data-quality issues cap confidence |
| negative_valuation_evidence | 0.70 | negative valuation evidence caps high-confidence positive stance |

### Conflicts

- high: NVDA has positive company-driver evidence but negative factor residual evidence.
- high: NVDA has a positive stance, but factor residual evidence is negative. Treat the stance as conflicted until residual pressure or operating evidence resolves.
- high: NVDA has a positive stance, but valuation evidence is negative. Treat upside as valuation-capped until price or fundamentals improve.
- medium: NVDA has positive valuation evidence but negative factor residual evidence.

### Top Positive Evidence

- NVDA valuation feature growth_adjusted_valuation_score is positive with score 100.0. (strength very_high, confidence 0.75)
- NVDA cash-flow feature capex_to_ocf is positive with value 0.035. (strength very_high, confidence 0.80)
- NVDA oem_and_other_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA professional_visualization_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA data_center_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)

### Top Negative Evidence

- NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%. (strength high, confidence 0.80)
- NVDA valuation feature ev_sales_score is negative with score 20.7. (strength high, confidence 0.75)
- NVDA event reaction evidence for nvda_earnings_2026_02_25: The reaction looks negative versus the pre-event factor model. (strength medium, confidence 0.88)
- NVDA event reaction evidence for nvda_earnings_2025_02_26: The reaction looks negative versus the pre-event factor model. (strength medium, confidence 0.88)

### Final Stance Explanation

NVDA retains AI compute platform leadership if Data Center growth, gross margin, and supply visibility remain strong. Current stance is constructive with net evidence score 13.0. NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%.; NVDA valuation feature growth_adjusted_valuation_score is positive with score 100.0.

## AMD

- Stance: constructive
- Modifier: valuation_capped
- Confidence: 0.70
- Net weighted score: 10.5

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
| valuation | negative | 1 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| factor_residual | positive | 16.0 | 0.80 | 1 |
| segment_momentum | positive | 9.1 | 0.78 | 5 |
| cash_flow_quality | positive | 7.9 | 0.90 | 2 |
| event_reaction | positive | 0.6 | 0.75 | 1 |
| event_reaction | mixed | 0.0 | 0.37 | 4 |
| event_reaction | neutral | 0.0 | 0.80 | 3 |
| event_reaction | negative | -1.1 | 0.84 | 2 |
| segment_momentum | negative | -6.9 | 0.75 | 4 |
| valuation | negative | -15.0 | 0.75 | 1 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| conflicting_evidence | 0.75 | positive and negative evidence are both material |
| data_quality_issues | 0.70 | multiple data-quality issues cap confidence |
| negative_valuation_evidence | 0.70 | negative valuation evidence caps high-confidence positive stance |

### Conflicts

- high: AMD has positive residual evidence but negative segment driver evidence.
- high: AMD has a positive stance, but valuation evidence is negative. Treat upside as valuation-capped until price or fundamentals improve.
- medium: AMD has positive cash-flow evidence but negative segment driver evidence.
- medium: AMD has positive factor residual evidence but negative valuation evidence.

### Top Positive Evidence

- AMD factor residual evidence is positive: 20d 28.0%, 60d 54.3%. (strength very_high, confidence 0.80)
- AMD cash-flow feature capex_to_ocf is positive with value 0.132. (strength very_high, confidence 0.90)
- AMD cash-flow feature fcf_margin is positive with value 0.250. (strength high, confidence 0.90)
- AMD data_center_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.70)
- AMD data_center_momentum_score is positive with score 100.0. (strength very_high, confidence 0.70)

### Top Negative Evidence

- AMD valuation feature valuation_percentile_score is negative with score 0.0. (strength very_high, confidence 0.75)
- AMD operating_margin_quality_score is negative with score 14.4. (strength very_high, confidence 0.90)
- AMD data_center_margin is negative with score 27.7. (strength high, confidence 0.70)
- AMD client_and_gaming_margin is negative with score 16.0. (strength high, confidence 0.70)
- AMD data_center_margin_score is negative with score 27.7. (strength high, confidence 0.70)

### Final Stance Explanation

AMD upside depends on becoming a credible second supplier in AI accelerators while sustaining EPYC/Data Center momentum. Current stance is constructive with net evidence score 10.5. AMD factor residual evidence is positive: 20d 28.0%, 60d 54.3%.; AMD valuation feature valuation_percentile_score is negative with score 0.0.

## TSM

- Stance: neutral
- Modifier: data_quality_capped
- Confidence: 0.65
- Net weighted score: 3.0

### Evidence Count By Type

| Evidence type | Direction | Count |
|---|---|---:|
| event_reaction | mixed | 4 |
| event_reaction | negative | 3 |
| event_reaction | neutral | 3 |
| factor_residual | negative | 1 |
| segment_momentum | positive | 1 |
| valuation | negative | 1 |

### Score Contribution By Type

| Evidence type | Direction | Weighted score | Avg confidence | Count |
|---|---:|---:|---:|---:|
| segment_momentum | positive | 20.2 | 0.90 | 1 |
| event_reaction | mixed | 0.0 | 0.41 | 4 |
| event_reaction | neutral | 0.0 | 0.82 | 3 |
| event_reaction | negative | -1.5 | 0.85 | 3 |
| valuation | negative | -6.8 | 0.45 | 1 |
| factor_residual | negative | -9.0 | 0.60 | 1 |

### Confidence Caps Applied

| Cap type | Cap value | Reason |
|---|---:|---|
| conflicting_evidence | 0.75 | positive and negative evidence are both material |
| data_quality_issues | 0.70 | multiple data-quality issues cap confidence |
| missing_cash_flow_evidence | 0.75 | missing cash-flow evidence caps confidence |
| negative_valuation_evidence | 0.70 | negative valuation evidence caps high-confidence positive stance |
| tsm_fx_model_gap | 0.65 | TSM factor evidence is capped until USD/TWD is added to the model |

### Conflicts

- high: TSM has positive company-driver evidence but negative factor residual evidence.

### Top Positive Evidence

- TSM advanced_node_mix_score is positive with score 74.0. (strength high, confidence 0.90)

### Top Negative Evidence

- TSM factor residual evidence is negative: 20d -13.7%, 60d -24.0%. Confidence is capped for missing FX/geopolitical factor. (strength very_high, confidence 0.60)
- TSM valuation feature snapshot_pe_score is negative with score 28.0. (strength high, confidence 0.45)
- TSM event reaction evidence for tsmc_monthly_revenue_2026_03: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)
- TSM event reaction evidence for tsm_earnings_2026_04_15: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)
- TSM event reaction evidence for tsm_earnings_2025_10_15: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)

### Final Stance Explanation

TSM remains the manufacturing bottleneck of AI compute if monthly revenue momentum, HPC mix, advanced node mix, and margin quality remain strong. Current stance is neutral with net evidence score 3.0. TSM advanced_node_mix_score is positive with score 74.0.; TSM factor residual evidence is negative: 20d -13.7%, 60d -24.0%. Confidence is capped for missing FX/geopolitical factor.
