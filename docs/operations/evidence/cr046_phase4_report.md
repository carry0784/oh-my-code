# CR-046 Phase 4: Execution Realism Simulation -- Results Report

Date: 2026-04-01
Canonical Core: **SMC (pure-causal) + WaveTrend**
Scope: **BTC/SOL only** (per A's directive)
SMC Version: **B (pure-causal, canonical)**

---

## 1. Executive Summary

| Test | BTC/USDT | SOL/USDT | Overall |
|------|----------|----------|---------|
| 4.1 Slippage (0.05%) | **PASS** (Sharpe 1.32) | **PASS** (Sharpe 0.76) | **2/2 PASS** |
| 4.2 Funding rate (-0.01%/8h) | **PASS** (reduction 0.1%) | **PASS** (reduction 0.2%) | **2/2 PASS** |
| 4.3 Latency (1-bar delay) | **PASS** (Sharpe 0.12) | **PASS** (Sharpe 1.24) | **2/2 PASS** |
| 4.4 Realistic fee (0.1% taker) | **PASS** (PF 1.68) | **PASS** (PF 1.35) | **2/2 PASS** |

**Phase 4 Overall: PASS (8/8)**

---

## 2. Baseline vs Realism Comparison

### BTC/USDT

| Scenario | Sharpe | Return | PF | MDD | Trades |
|----------|--------|--------|----|-----|--------|
| **Baseline** (0.075% fee) | 1.40 | +24.81% | 1.71 | 8.83% | 32 |
| +Slippage (0.05%) | 1.32 | +20.90% | 1.65 | — | — |
| +Funding (-0.01%/8h) | 1.40 | +24.80% | — | — | — |
| +Latency (1-bar delay) | 0.12 | -1.97% | 1.04 | — | — |
| +Realistic fee (0.1%) | 1.36 | +22.84% | 1.68 | — | — |
| **Worst-case (all combined)** | -0.02 | -6.72% | 0.99 | 16.36% | 33 |

### SOL/USDT

| Scenario | Sharpe | Return | PF | MDD | Trades |
|----------|--------|--------|----|-----|--------|
| **Baseline** (0.075% fee) | 0.84 | +14.57% | 1.37 | 13.45% | 35 |
| +Slippage (0.05%) | 0.76 | +10.64% | 1.33 | — | — |
| +Funding (-0.01%/8h) | 0.84 | +14.55% | — | — | — |
| +Latency (1-bar delay) | 1.24 | +26.75% | 1.59 | — | — |
| +Realistic fee (0.1%) | 0.80 | +12.59% | 1.35 | — | — |
| **Worst-case (all combined)** | 1.13 | +20.25% | 1.52 | 13.27% | 35 |

---

## 3. Key Findings

### 3A. Slippage Impact: Minimal

- BTC: Sharpe 1.40 -> 1.32 (-5.7%), Return +24.81% -> +20.90% (-3.91pp)
- SOL: Sharpe 0.84 -> 0.76 (-9.5%), Return +14.57% -> +10.64% (-3.93pp)
- **Conclusion**: 0.05% slippage reduces returns by ~4pp but does not threaten profitability

### 3B. Funding Rate Impact: Negligible

- BTC: Return reduction 0.1% (from +24.81% to +24.80%)
- SOL: Return reduction 0.2% (from +14.57% to +14.55%)
- **Conclusion**: -0.01%/8h funding rate has near-zero impact on the 1H strategy. Short positions are infrequent and short-lived enough that funding costs are immaterial.

### 3C. Latency Impact: Asymmetric

- BTC: Sharpe 1.40 -> 0.12 (-91.4%), Return +24.81% -> -1.97% (**significant degradation**)
- SOL: Sharpe 0.84 -> 1.24 (+47.6%), Return +14.57% -> +26.75% (**improvement**)
- **Conclusion**: 1-bar entry delay has the largest single-factor impact. BTC entries are more timing-sensitive than SOL. Both remain Sharpe > 0 (pass criterion), but BTC latency sensitivity is a **risk factor**.

### 3D. Realistic Fee Impact: Moderate

- BTC: Sharpe 1.40 -> 1.36 (-2.9%), Return +24.81% -> +22.84% (-1.97pp)
- SOL: Sharpe 0.84 -> 0.80 (-4.8%), Return +14.57% -> +12.59% (-1.98pp)
- **Conclusion**: Moving from 0.075% to 0.1% taker fee reduces returns by ~2pp. Both assets remain profitable with PF > 1.3.

### 3E. Worst-Case Combined: Divergent

- BTC: Sharpe -0.02, Return -6.72%, PF 0.99, MDD 16.36% (**marginally negative**)
- SOL: Sharpe 1.13, Return +20.25%, PF 1.52, MDD 13.27% (**still profitable**)
- **Conclusion**: Under worst-case conditions (all friction combined), BTC becomes marginally unprofitable while SOL remains robust. The divergence is driven primarily by BTC's latency sensitivity.

---

## 4. Sensitivity Ranking (Impact on Sharpe)

| Rank | Factor | BTC Impact | SOL Impact |
|------|--------|------------|------------|
| 1 | **Latency** | -91.4% | +47.6% |
| 2 | **Slippage** | -5.7% | -9.5% |
| 3 | **Fee tier** | -2.9% | -4.8% |
| 4 | **Funding rate** | 0.0% | 0.0% |

**Latency is the dominant factor** for execution realism. Fee and slippage are secondary. Funding rate is negligible at 1H timeframe.

---

## 5. Phase 4 Acceptance Criteria

| AC | Check | Threshold | BTC | SOL | Verdict |
|----|-------|-----------|-----|-----|---------|
| AC-7 | Slippage Sharpe | > 0.5 | 1.32 | 0.76 | **PASS** |
| AC-8 | Funding reduction | < 30% | 0.1% | 0.2% | **PASS** |
| AC-9 | Latency Sharpe | > 0 | 0.12 | 1.24 | **PASS** |
| AC-10 | Realistic fee PF | > 1.0 | 1.68 | 1.35 | **PASS** |

---

## 6. Operational Implications

### For Live Deployment

1. **Latency mitigation is critical for BTC**: Use limit orders or reduce entry delay to < 1 bar
2. **SOL is latency-resilient**: Standard market order execution is acceptable
3. **Fee optimization**: VIP tier (0.075% or lower) adds ~2pp return on both assets
4. **Funding rate**: Not a concern at 1H timeframe with current hold durations

### Risk Warnings

1. BTC worst-case scenario shows marginally negative returns (Sharpe -0.02, PF 0.99). This means in a high-friction environment with poor execution, BTC could be breakeven-to-slightly-negative.
2. SOL shows unexpected improvement under latency (+47.6% Sharpe), which may indicate that 1-bar delay acts as a filter against false signals on SOL. This should not be relied upon.

---

## 7. Three-Tier Judgment Update

### Research Validity: CONDITIONAL (Phase 2-3)

- Phase 2: CONDITIONAL PASS (3/5)
- Phase 3: CONDITIONAL PASS (BTC/SOL positive, ETH negative)

### Execution Realism: PASS (Phase 4)

- 8/8 individual tests passed
- Worst-case: BTC marginal, SOL robust
- Latency is the dominant risk factor

### Operational Fit: CG-2B PROVEN (CR-047)

- CG-2B-1 (candidate generation): PROVEN
- CG-2B-2 (governance exercisability): PROVEN

---

## 8. Phase 4 Verdict

```
Phase 4 Overall: PASS

Passed (8/8):
  BTC/USDT: All 4 individual tests PASS
  SOL/USDT: All 4 individual tests PASS

Worst-Case:
  BTC/USDT: Sharpe -0.02, Return -6.72% (marginally negative)
  SOL/USDT: Sharpe 1.13, Return +20.25% (robust)

Key Finding:
  Latency (1-bar entry delay) is the dominant friction factor.
  BTC is latency-sensitive; SOL is latency-resilient.
  Fee/slippage/funding impacts are moderate-to-negligible.

Operational Implication:
  Live deployment should prioritize low-latency execution for BTC.
  SOL can tolerate standard execution infrastructure.
```

---

## Signature

```
CR-046 Phase 4 Report
Canonical Core: SMC (pure-causal) + WaveTrend
Scope: BTC/SOL only
Result: PASS (8/8)
Key Finding: Latency is dominant factor; BTC sensitive, SOL resilient
Prepared by: B (Implementer)
Date: 2026-04-01
```
