# CR-046 Track C-v2: Alternative Regime Indicators -- NO-GO SEALED

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **NO-GO SEALED**
Failure Type: `CROSS_ASSET_NON_GENERALIZABLE`

---

## Verdict

All 5 regime indicator candidates are **permanently excluded from operational integration**.
RegimeDetector modification remains **PROHIBITED**.

## Evidence Summary

| Phase | Status | Key Finding |
|-------|--------|------------|
| C2-1: Individual tests | PASS | Best: directional_efficiency (avg sw_acc=71.5%) |
| C2-2: Integration | **FAIL** | SOL improved (0.85->1.82), BTC collapsed (4.16->-0.92) |
| C2-3: Cross-asset | **FAIL** | Not generalizable |

## Failure Analysis

- **Failure type**: `CROSS_ASSET_NON_GENERALIZABLE` -- filter improves one asset while destroying another
- **Root cause**: Directional efficiency captures asset-specific microstructure, not universal regime signal
- **Interpretation**: "Explanatory power exists but operational filter it is not" -- good research, bad filter

### Candidate Results

| Indicator | BTC sw_acc | SOL sw_acc | Both Pass |
|-----------|-----------|-----------|-----------|
| realized_vol_percentile | 0.2565 | 0.2282 | FAIL |
| range_compression | 0.3832 | 0.1024 | FAIL |
| choppiness_index | 0.0709 | 0.0931 | FAIL |
| **directional_efficiency** | **0.7176** | **0.7124** | **PASS** |
| hurst_exponent | 0.0048 | 0.0021 | FAIL |

Only directional_efficiency passed C2-1, but failed C2-2 and C2-3.

## Prohibitions (permanent)

1. RegimeDetector must NOT be modified
2. No regime indicator from this research may enter signal pipeline
3. No filter from this research may be applied to operational strategies
4. Cross-asset filter concept is invalidated for these 5 indicators
5. Results must NOT override Track C v1 FAIL status

## Permitted Follow-up

- SOL/BTC asymmetry cause analysis
- Filter pass-rate decomposition (loss reduction vs good-trade removal)
- Academic documentation only

## Linked Evidence

- Full results: `cr046_track_c_v2_results.json`
- Full report: `cr046_track_c_v2_report.md`
- Tests: `tests/test_cr046_track_c_v2.py` (18/18 PASS)

---

```
CR-046 Track C-v2: NO-GO SEALED
Sealed by: A (Decision Authority)
Date: 2026-04-01
Failure type: CROSS_ASSET_NON_GENERALIZABLE
```
