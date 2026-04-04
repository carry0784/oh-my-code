# CR-046 Track B: CV_INSTABILITY Failure Cause Analysis

Date: 2026-04-01
Failure Type: `CV_INSTABILITY`
Sealed Status: NO-GO SEALED

---

## 1. Fold-by-Fold Decomposition

| Fold | Bars | Signals | Density | Volatility | Trend | Sharpe | PF | WinRate | Return | PASS |
|------|------|---------|---------|-----------|-------|--------|----|---------|--------|------|
| 1 | 864 | 11 | 0.0127 | 0.01018 | +71.2% | 6.97 | 2.41 | 60.0% | +15.85% | YES |
| 2 | 816 | 8 | 0.0098 | 0.00972 | +11.1% | 3.87 | 1.65 | 50.0% | +6.79% | YES |
| 3 | 816 | 3 | 0.0037 | 0.00985 | +17.6% | 10.70 | 3.74 | 66.7% | +5.99% | YES |
| 4 | 816 | 8 | 0.0098 | 0.00995 | **-11.7%** | -5.61 | 0.49 | 25.0% | -8.99% | **NO** |
| 5 | 816 | 8 | 0.0098 | 0.01018 | +12.0% | -4.49 | 0.56 | 25.0% | -6.69% | **NO** |

---

## 2. Root Cause Analysis

### Q1: Is the failure volatility-dependent?

**NO.** Volatility is nearly identical across all 5 folds (0.0097-0.0102). The failing folds do not have anomalous volatility. This is not a volatility-regime problem.

### Q2: Is the failure trend-dependent?

**PARTIALLY.** Fold 4 has the only negative trend (-11.7%), and it fails hardest (Sharpe=-5.61). However, Fold 5 has a positive trend (+12.0%) and still fails (Sharpe=-4.49). So trend alone doesn't explain it.

### Q3: Is the failure signal-density-dependent?

**NO.** Folds 2, 4, and 5 all have identical signal density (0.0098) but opposite outcomes. Fold 3 has the lowest density (0.0037) and the best Sharpe. Signal density is not discriminative.

### Q4: What actually distinguishes passing vs failing folds?

**Win rate collapse.** The distinguishing factor is clear:

| Fold Group | Win Rate | Sharpe |
|------------|----------|--------|
| Passing (1-3) | 50-67% | +3.87 to +10.70 |
| Failing (4-5) | **25%** | -4.49 to -5.61 |

Folds 4 and 5 have identical 25% win rate regardless of trend direction. The strategy simply stops finding winning trades in the latter half of the data.

---

## 3. Interpretation

This is a **temporal decay pattern**: the SMC+MACD consensus works in earlier data but degrades in later data. This is characteristic of:

1. **Regime shift in price microstructure** -- the relationship between SMC structure breaks and MACD crossovers changes over time
2. **Overfitting to early-period price patterns** -- the consensus filter captures a feature that exists in bars 0-2592 but not in bars 2592-4320
3. **Not random noise** -- the failure is consistent (both late folds fail with identical 25% win rate)

### Conclusion

The failure is **not** caused by:
- Volatility regime changes
- Signal density variance
- Single outlier fold

The failure **is** caused by:
- Temporal instability in the SMC+MACD consensus edge
- Win rate collapse from ~55% to 25% in the latter 40% of data
- Strategy captures a non-stationary feature

This confirms NO-GO SEALED is the correct decision. The strategy is a partial-interval fit.

---

```
CR-046 Track B Failure Analysis
Type: CV_INSTABILITY
Cause: Temporal win-rate decay (55% -> 25% in late folds)
Sealed: NO-GO
```
