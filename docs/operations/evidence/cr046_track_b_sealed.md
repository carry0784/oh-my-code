# CR-046 Track B: ETH SMC+MACD -- NO-GO SEALED

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **NO-GO SEALED**
Failure Type: `CV_INSTABILITY`

---

## Verdict

ETH SMC+MACD consensus strategy is **permanently excluded from operational paths**.

## Evidence Summary

| Phase | Status | Key Metric |
|-------|--------|-----------|
| B-1: In-sample baseline | PASS | Sharpe=0.66, PF=1.09 |
| B-2: OOS + Purged CV | **FAIL** | CV stability 2/5 (threshold: 4/5) |
| B-3: Execution realism | PASS | Worst-case Sharpe=1.82 |

## Failure Analysis

- **Failure type**: `CV_INSTABILITY` -- strategy passes in-sample and OOS but fails purged cross-validation stability
- **Root cause**: Partial-interval fit. Strategy works in 2 of 5 temporal folds, indicating regime-specific overfitting
- **Interpretation**: "Looks like it works but doesn't generalize" -- classic overfitting pattern

## Prohibitions (permanent)

1. ETH must NOT enter beat_schedule
2. ETH must NOT get a paper trading session
3. ETH SMC+MACD must NOT be imported into operational code
4. No PromotionReceipt may reference ETH SMC+MACD
5. Results must NOT be used as basis for operational path decisions

## Permitted Follow-up

- Failure cause decomposition (fold-by-fold analysis, regime bucketing)
- Academic documentation only
- No new strategy variants derived from this research

## Linked Evidence

- Full results: `cr046_track_b_results.json`
- Full report: `cr046_track_b_report.md`
- Tests: `tests/test_cr046_track_b_research.py` (23/23 PASS)

---

```
CR-046 Track B: NO-GO SEALED
Sealed by: A (Decision Authority)
Date: 2026-04-01
Failure type: CV_INSTABILITY
```
