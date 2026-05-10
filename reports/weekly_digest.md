# Weekly AI Compute Research Digest

## Latest Pipeline Runs

- evidence_20260510054956_e1ab0916: success (evidence -> evidence), snapshot 9f6172889b4e91de

## Stance Summary

| Ticker | Stance | Modifier | Confidence | Caveat |
|---|---|---|---:|---|
| AMD | constructive | valuation_capped+mixed | 0.70 | multiple data-quality issues cap confidence |
| GOOGL | neutral | mixed_cash_flow+mixed | 0.70 | positive and negative evidence are both material |
| NVDA | constructive | valuation_capped+factor_conflicted+mixed | 0.70 | multiple data-quality issues cap confidence |
| TSM | neutral | data_quality_capped+mixed | 0.65 | missing cash-flow evidence caps confidence |

## High-Severity Conflicts

- AMD: AMD has positive residual evidence but negative segment driver evidence.
- AMD: AMD has a positive stance, but valuation evidence is negative. Treat upside as valuation-capped until price or fundamentals improve.
- GOOGL: GOOGL has positive residual evidence but negative segment driver evidence.
- NVDA: NVDA has positive company-driver evidence but negative factor residual evidence.
- NVDA: NVDA has a positive stance, but factor residual evidence is negative. Treat the stance as conflicted until residual pressure or operating evidence resolves.
- NVDA: NVDA has a positive stance, but valuation evidence is negative. Treat upside as valuation-capped until price or fundamentals improve.
- TSM: TSM has positive company-driver evidence but negative factor residual evidence.

## Confidence Caps

- AMD: conflicting_evidence (positive and negative evidence are both material)
- AMD: data_quality_issues (multiple data-quality issues cap confidence)
- AMD: negative_valuation_evidence (negative valuation evidence caps high-confidence positive stance)
- GOOGL: conflicting_evidence (positive and negative evidence are both material)
- GOOGL: negative_valuation_evidence (negative valuation evidence caps high-confidence positive stance)
- NVDA: conflicting_evidence (positive and negative evidence are both material)
- NVDA: data_quality_issues (multiple data-quality issues cap confidence)
- NVDA: negative_valuation_evidence (negative valuation evidence caps high-confidence positive stance)
- TSM: conflicting_evidence (positive and negative evidence are both material)
- TSM: data_quality_issues (multiple data-quality issues cap confidence)
- TSM: missing_cash_flow_evidence (missing cash-flow evidence caps confidence)
- TSM: negative_valuation_evidence (negative valuation evidence caps high-confidence positive stance)
- TSM: tsm_fx_model_gap (TSM factor evidence is capped until USD/TWD is added to the model)

## Residual Concentration Warnings

- none

## Missing Human Thesis Warnings

- none