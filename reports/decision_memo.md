# AI Compute Four-Stock Decision Memo

as_of_date: 2026-05-09
run_id: pipeline_20260510062147_42f1451e
data_snapshot_hash: 5bb452b6394f387c

## Executive Summary

| Ticker | Stance | Modifier | Confidence | Main caveat | One-line thesis |
|---|---|---|---:|---|---|
| AMD | constructive | valuation_capped+mixed | 0.70 | valuation evidence caps upside | AMD upside depends on becoming a credible second supplier in AI accelerators while sustaining EPYC/Data Center moment... |
| GOOGL | neutral | mixed_cash_flow+mixed | 0.70 | cash-flow evidence is mixed | GOOGL remains a high-quality AI/Cloud compounder if Search resilience and Cloud margin expansion can offset AI CapEx ... |
| NVDA | constructive | valuation_capped+factor_conflicted+mixed | 0.70 | valuation evidence caps upside | NVDA retains AI compute platform leadership if Data Center growth, gross margin, and supply visibility remain strong.... |
| TSM | neutral | data_quality_capped+mixed | 0.65 | missing cash-flow evidence caps confidence | TSM remains the manufacturing bottleneck of AI compute if monthly revenue momentum, HPC mix, advanced node mix, and m... |

## Cross-Stock Read

- Constructive evidence currently clusters around: AMD, NVDA.
- Cautious/high-risk evidence currently clusters around: none.
- Positive factor residual leadership: GOOGL, AMD.
- Negative factor residual pressure: NVDA, TSM.
- Stance is research output only; it is not an automatic buy/sell instruction.

## GOOGL

### Stance

neutral / mixed_cash_flow+mixed (confidence 0.70)

### Thesis

GOOGL remains a high-quality AI/Cloud compounder if Search resilience and Cloud margin expansion can offset AI CapEx pressure. Current stance is neutral with net evidence score -6.8. GOOGL cash-flow feature fcf_margin is positive with value 0.092.; GOOGL cash-flow feature capex_to_ocf is negative with value 0.779.

### Positive Evidence

- GOOGL cash-flow feature fcf_margin is positive with value 0.092. (strength very_high, confidence 0.90)
- GOOGL factor residual evidence is positive: 20d 8.2%, 60d 7.6%. (strength high, confidence 0.80)
- GOOGL google_cloud_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- GOOGL cloud_growth_score is positive with score 100.0. (strength very_high, confidence 0.90)
- GOOGL event reaction evidence for googl_earnings_2026_04_29: The reaction looks positive versus the pre-event factor model. (strength high, confidence 0.82)

### Negative / Mixed Evidence

- GOOGL cash-flow feature capex_to_ocf is negative with value 0.779. (strength high, confidence 0.90)
- GOOGL valuation feature valuation_percentile_score is negative with score 0.0. (strength very_high, confidence 0.75)
- GOOGL valuation feature capex_adjusted_fcf_score is negative with score 28.9. (strength high, confidence 0.75)
- GOOGL fcf_quality_score is negative with score 9.2. (strength very_high, confidence 0.90)
- GOOGL other_bets_margin is negative with score 0.0. (strength very_high, confidence 0.90)

### Mixed Evidence

- GOOGL event reaction evidence for googl_earnings_2025_04_24: The reaction was broadly in line with the pre-event factor model. (strength low, confidence 0.80)
- GOOGL event reaction evidence for googl_earnings_2025_07_23: The reaction was broadly in line with the pre-event factor model. (strength low, confidence 0.80)

### Risk Flags

capex_pressure; valuation_risk; negative_driver

### Falsifiers

- Search revenue growth decelerates materially.
- Google Cloud growth slows while Cloud margin stalls.
- CapEx / OCF rises further and FCF margin compresses.
- Regulatory outcomes impair core advertising economics.

### Next Catalysts

- next earnings
- Cloud margin update
- AI CapEx commentary
- regulatory rulings

### Data Quality Caveats

positive and negative evidence are both material; negative valuation evidence caps high-confidence positive stance


## NVDA

### Stance

constructive / valuation_capped+factor_conflicted+mixed (confidence 0.70)

### Thesis

NVDA retains AI compute platform leadership if Data Center growth, gross margin, and supply visibility remain strong. Current stance is constructive with net evidence score 13.0. NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%.; NVDA valuation feature growth_adjusted_valuation_score is positive with score 100.0.

### Positive Evidence

- NVDA valuation feature growth_adjusted_valuation_score is positive with score 100.0. (strength very_high, confidence 0.75)
- NVDA cash-flow feature capex_to_ocf is positive with value 0.035. (strength very_high, confidence 0.80)
- NVDA oem_and_other_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA data_center_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)
- NVDA professional_visualization_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.90)

### Negative / Mixed Evidence

- NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%. (strength high, confidence 0.80)
- NVDA valuation feature ev_sales_score is negative with score 20.7. (strength high, confidence 0.75)
- NVDA event reaction evidence for nvda_earnings_2026_02_25: The reaction looks negative versus the pre-event factor model. (strength medium, confidence 0.88)
- NVDA event reaction evidence for nvda_earnings_2025_02_26: The reaction looks negative versus the pre-event factor model. (strength medium, confidence 0.88)

### Mixed Evidence

- NVDA event reaction evidence for nvda_earnings_2025_08_27: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.43)
- NVDA event reaction evidence for nvda_earnings_2025_11_19: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.43)
- NVDA event reaction evidence for tsmc_monthly_revenue_2025_12: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.37)
- NVDA event reaction evidence for tsmc_monthly_revenue_2026_01: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.38)
- NVDA event reaction evidence for tsmc_monthly_revenue_2026_04: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.38)

### Risk Flags

NVDA factor residual evidence is negative: 20d -8.6%, 60d -11.1%.; valuation_risk; NVDA event reaction evidence for nvda_earnings_2026_02_25: The reaction looks negative versus the pre-event factor model.; NVDA event reaction evidence for nvda_earnings_2025_02_26: The reaction looks negative versus the pre-event factor model.

### Falsifiers

- Data Center growth or guidance decelerates sharply.
- Gross margin compresses materially.
- Hyperscaler CapEx commentary weakens.
- AMD / ASIC competition begins pressuring pricing.
- Export control impact becomes larger than expected.

### Next Catalysts

- next earnings
- Data Center guidance
- product roadmap events
- export-control updates

### Data Quality Caveats

multiple data-quality issues cap confidence; positive and negative evidence are both material; negative valuation evidence caps high-confidence positive stance


## AMD

### Stance

constructive / valuation_capped+mixed (confidence 0.70)

### Thesis

AMD upside depends on becoming a credible second supplier in AI accelerators while sustaining EPYC/Data Center momentum. Current stance is constructive with net evidence score 10.5. AMD factor residual evidence is positive: 20d 28.0%, 60d 54.3%.; AMD valuation feature valuation_percentile_score is negative with score 0.0.

### Positive Evidence

- AMD factor residual evidence is positive: 20d 28.0%, 60d 54.3%. (strength very_high, confidence 0.80)
- AMD cash-flow feature capex_to_ocf is positive with value 0.132. (strength very_high, confidence 0.90)
- AMD cash-flow feature fcf_margin is positive with value 0.250. (strength high, confidence 0.90)
- AMD data_center_revenue_growth_yoy is positive with score 100.0. (strength very_high, confidence 0.70)
- AMD data_center_momentum_score is positive with score 100.0. (strength very_high, confidence 0.70)

### Negative / Mixed Evidence

- AMD valuation feature valuation_percentile_score is negative with score 0.0. (strength very_high, confidence 0.75)
- AMD operating_margin_quality_score is negative with score 14.4. (strength very_high, confidence 0.90)
- AMD client_and_gaming_margin is negative with score 16.0. (strength high, confidence 0.70)
- AMD data_center_margin is negative with score 27.7. (strength high, confidence 0.70)
- AMD data_center_margin_score is negative with score 27.7. (strength high, confidence 0.70)

### Mixed Evidence

- AMD event reaction evidence for tsmc_monthly_revenue_2025_12: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.35)
- AMD event reaction evidence for tsmc_monthly_revenue_2026_01: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.37)
- AMD event reaction evidence for amd_earnings_2026_05_05: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.41)
- AMD event reaction evidence for tsmc_monthly_revenue_2026_04: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.37)
- AMD event reaction evidence for amd_earnings_2025_05_06: The reaction was broadly in line with the pre-event factor model. (strength low, confidence 0.82)

### Risk Flags

valuation_risk; margin_pressure

### Falsifiers

- Data Center growth fails to translate into margin improvement.
- MI accelerator commentary or guidance disappoints.
- Client/Gaming cyclicality masks weak AI traction.
- NVDA platform dominance prevents meaningful share gain.

### Next Catalysts

- next earnings
- MI accelerator commentary
- EPYC/Data Center margins
- AI event updates

### Data Quality Caveats

multiple data-quality issues cap confidence; positive and negative evidence are both material; negative valuation evidence caps high-confidence positive stance


## TSM

### Stance

neutral / data_quality_capped+mixed (confidence 0.65)

### Thesis

TSM remains the manufacturing bottleneck of AI compute if monthly revenue momentum, HPC mix, advanced node mix, and margin quality remain strong. Current stance is neutral with net evidence score 3.0. TSM advanced_node_mix_score is positive with score 74.0.; TSM factor residual evidence is negative: 20d -13.7%, 60d -24.0%. Confidence is capped for missing FX/geopolitical factor.

### Positive Evidence

- TSM advanced_node_mix_score is positive with score 74.0. (strength high, confidence 0.90)

### Negative / Mixed Evidence

- TSM factor residual evidence is negative: 20d -13.7%, 60d -24.0%. Confidence is capped for missing FX/geopolitical factor. (strength very_high, confidence 0.60)
- TSM valuation feature snapshot_pe_score is negative with score 28.0. (strength high, confidence 0.45)
- TSM event reaction evidence for tsmc_monthly_revenue_2026_03: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)
- TSM event reaction evidence for tsm_earnings_2026_04_15: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)
- TSM event reaction evidence for tsm_earnings_2025_10_15: The reaction looks negative versus the pre-event factor model. (strength high, confidence 0.85)

### Mixed Evidence

- TSM event reaction evidence for tsmc_monthly_revenue_2025_12: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.40)
- TSM event reaction evidence for tsm_earnings_2026_01_15: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.41)
- TSM event reaction evidence for tsmc_monthly_revenue_2026_01: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.41)
- TSM event reaction evidence for tsmc_monthly_revenue_2026_04: Price attribution is incomplete; defer interpretation until enough prices exist. (strength low, confidence 0.41)
- TSM event reaction evidence for tsm_earnings_2025_04_17: The reaction was broadly in line with the pre-event factor model. (strength low, confidence 0.82)

### Risk Flags

fx_model_gap; valuation_risk; TSM event reaction evidence for tsmc_monthly_revenue_2026_03: The reaction looks negative versus the pre-event factor model.; TSM event reaction evidence for tsm_earnings_2026_04_15: The reaction looks negative versus the pre-event factor model.

### Falsifiers

- Monthly revenue decelerates.
- HPC or advanced node mix weakens.
- Overseas fab costs pressure gross margin.
- CapEx rises without revenue/margin validation.
- Taiwan/geopolitical risk widens valuation discount.

### Next Catalysts

- monthly revenue
- quarterly earnings
- HPC/node mix update
- CapEx and margin guidance

### Data Quality Caveats

missing cash-flow evidence caps confidence; multiple data-quality issues cap confidence; positive and negative evidence are both material; negative valuation evidence caps high-confidence positive stance; TSM factor evidence is capped until USD/TWD is added to the model
