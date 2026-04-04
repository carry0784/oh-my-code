# CR-046 Track C-v2: Alternative Regime Indicator Research Plan

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED -- research track, non-blocking**

---

## 1. Background

Track C v1 tested ADX, BB Width percentile, and ATR ratio as regime indicators. All failed on crypto 1H data because:

- ADX remains > 30 even in sideways periods (delta of 2 points between regimes)
- BB Width and ATR ratio are regime-indifferent
- Classification accuracy for sideways was 9-13%

> **Current strategy is accepted as regime-conditional; no production filter is adopted from Track C v1.**

---

## 2. Candidate Indicators (v2)

| # | Indicator | Hypothesis | Why Different from v1 |
|---|-----------|------------|----------------------|
| 1 | **Realized Volatility Percentile** | Rolling realized vol rank within 90-day history | Measures actual return dispersion, not ATR-smoothed range |
| 2 | **Range Compression Ratio** | (High-Low range) / close over N bars, normalized | Direct price range measurement, not indicator-derived |
| 3 | **Choppiness Index** | ATR(1) sum / (Highest-Lowest) over N bars | Specifically designed for range-bound detection |
| 4 | **Directional Efficiency** | abs(close[i] - close[i-N]) / sum(abs(close[j]-close[j-1])) | Measures how efficiently price moves in one direction |
| 5 | **Hurst Exponent (simplified)** | R/S analysis over rolling window | Distinguishes mean-reversion (H<0.5) from trending (H>0.5) |

---

## 3. Research Plan

### Phase C2-1: Individual Indicator Testing (1 day)

For each candidate:
1. Implement (causal, no lookahead)
2. Compute on BTC/SOL 6-month data
3. Measure classification accuracy vs known quarterly regimes
4. Compare accuracy to v1 results (baseline: 49.6% BTC, 68.1% SOL)

**Pass criterion**: Sideways classification accuracy > 50% on both assets

### Phase C2-2: Best Candidate Integration (1 day)

1. Select top 1-2 indicators by accuracy
2. Redesign composite regime score
3. Backtest canonical core + v2 regime filter
4. Measure Sharpe improvement vs unfiltered baseline

**Pass criterion**: Overall Sharpe with filter > unfiltered Sharpe on both assets

### Phase C2-3: Cross-Asset Validation (1 day)

1. Verify filter works on both BTC and SOL
2. Check bear-period preservation (< 10% degradation)
3. Check sideways-period improvement

---

## 4. Success Criteria

| Criterion | Threshold |
|-----------|-----------|
| Sideways classification accuracy | > 50% on both assets |
| Overall Sharpe with filter | > unfiltered on both assets |
| Bear period degradation | < 10% relative |
| Filter stability | Same parameters work on BTC and SOL |

---

## 5. Constraints

| Constraint | Reason |
|------------|--------|
| All indicators must be causal | Consistency with SMC Version B |
| No lookahead in any calculation | Structural safety |
| Research-only until proven | A's directive |
| Does NOT block Phase 5 paper rollout | Non-blocking track |
| Results do not retroactively change deployment grades | Separate axis |

---

## 6. Priority

- **Non-blocking**: Does not block SOL/BTC paper rollout
- **Next session**: Can be executed alongside Track B (ETH)
- **Judgment axis**: `regime_robustness` (separate from `deployment_readiness`)

---

## Signature

```
CR-046 Track C-v2: Alternative Regime Indicator Research
Status: Research track, non-blocking
Priority: Next session (alongside Track B)
Approved by: A (Decision Authority)
Date: 2026-04-01
```
