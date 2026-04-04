# CR-046 Track C: Regime Filter Research Plan

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED -- RESEARCH ONLY**

---

## 1. Background

Phase 3 regime analysis (BTC) revealed:

| Quarter | Regime | Core Sharpe | Core Return |
|---------|--------|-------------|-------------|
| Q1 | **bear** | **8.46** | +15.23% |
| Q2 | **sideways** | **-8.13** | -8.66% |
| Q3 | **bear** | **7.95** | +14.12% |
| Q4 | **sideways** | **6.31** | +13.14% |

Key findings:
- Bear market: consistently strong (Sharpe > 7)
- Sideways: inconsistent (Q2 -8.13 vs Q4 +6.31)
- The strategy is **regime-conditional**

A's directive: "Regime filter research -- trend/non-trend, volatility expansion/contraction identification."

---

## 2. Research Objective

Develop a regime filter that:
1. Identifies the current market regime (trending vs sideways)
2. Adjusts position sizing or signal filtering based on regime
3. Improves worst-case sideways performance without degrading bear/bull performance

---

## 3. Candidate Regime Indicators

| Indicator | Measures | Implementation |
|-----------|----------|----------------|
| **ADX (Average Directional Index)** | Trend strength | ADX > 25 = trending, < 20 = sideways |
| **Bollinger Band Width** | Volatility expansion/contraction | Percentile rank of BB width |
| **ATR Ratio** | Short-term vs long-term volatility | ATR(14) / ATR(50) |
| **Price vs SMA** | Trend direction | Close > SMA(200) = bull, < = bear |
| **Hurst Exponent** | Mean-reversion vs trending | H > 0.5 = trending, < 0.5 = mean-reverting |

---

## 4. Research Plan

### Phase C-1: Regime Identification Accuracy (2 days)

| Step | Task |
|------|------|
| C-1.1 | Implement each candidate regime indicator |
| C-1.2 | Label historical periods using known regime (Phase 3 quarterly labels) |
| C-1.3 | Measure classification accuracy of each indicator vs known labels |
| C-1.4 | Select top 1-2 regime indicators by accuracy |

### Phase C-2: Filter Integration (2 days)

| Step | Task |
|------|------|
| C-2.1 | Design filter modes: (a) signal suppression, (b) position sizing reduction, (c) both |
| C-2.2 | Backtest canonical core + regime filter on BTC (full period) |
| C-2.3 | Measure sideways-period improvement vs bear-period degradation |
| C-2.4 | Optimize filter threshold via walk-forward |

### Phase C-3: Multi-Asset Validation (1 day)

| Step | Task |
|------|------|
| C-3.1 | Apply selected filter to SOL/USDT |
| C-3.2 | Verify no performance degradation on SOL |
| C-3.3 | If ETH branch (Track B) succeeds, test filter on ETH |

### Phase C-4: OOS Validation (1 day)

| Step | Task |
|------|------|
| C-4.1 | Temporal OOS with filter |
| C-4.2 | Purged CV with filter |
| C-4.3 | Compare filtered vs unfiltered across all validation methods |

---

## 5. Success Criteria

| Criterion | Threshold |
|-----------|-----------|
| Sideways-period Sharpe improvement | > 2.0 absolute improvement |
| Bear-period Sharpe degradation | < 10% relative |
| Overall Sharpe with filter | > unfiltered overall Sharpe |
| OOS validation | Temporal OOS Sharpe > 0.5 |
| Filter stability | Same filter threshold works on BTC and SOL |

---

## 6. Filter Design Constraints

| Constraint | Reason |
|------------|--------|
| Filter must be causal (no lookahead) | Consistency with SMC Version B canonical |
| Filter parameters fixed at deployment | No adaptive/rolling regime detection |
| Filter is overlay, not canonical member | Per three-layer architecture |
| Filter cannot override SMC anchor signals | SMC remains foundation |

---

## 7. Expected Outcomes

| Outcome | Probability | Action |
|---------|-------------|--------|
| Filter improves sideways without hurting bear | 40% | Promote to canonical overlay |
| Filter improves sideways but degrades bear | 30% | Reject (net negative) |
| No regime indicator classifies accurately | 20% | Accept regime-conditional strategy as-is |
| Filter overfits to historical regimes | 10% | Reject |

---

## Signature

```
CR-046 Track C: Regime Filter Research Plan
Target: Sideways regime improvement
Status: RESEARCH ONLY
Approved by: A (Decision Authority)
Date: 2026-04-01
```
