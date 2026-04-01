# CR-046 Track B: ETH Branch Research Plan (SMC+MACD)

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED -- RESEARCH ONLY**

---

## 1. Background

Phase 3 revealed that the canonical core pair (SMC+WaveTrend) fails on ETH:
- ETH Core Pair Sharpe: **-3.88** (negative)
- ETH Core Pair Return: **-25.06%** (negative absolute)
- ETH ranking: SMC #1, **MACD #2**, WaveTrend #3

Adding MACD as 3rd indicator to ETH showed **+5.39 Sharpe incremental** -- the strongest 3rd-slot improvement across all assets.

A's directive: "ETH-specific composition (SMC+MACD) branch research."

---

## 2. Research Objective

Validate whether **SMC+MACD** is a viable canonical composition for ETH/USDT, independent of the BTC/SOL canonical core (SMC+WaveTrend).

---

## 3. Research Plan

### Phase B-1: ETH SMC+MACD Baseline (1 day)

| Step | Test | Pass Criteria |
|------|------|---------------|
| B-1.1 | In-sample Sharpe/Return/PF | Sharpe > 0, PF > 1.0 |
| B-1.2 | Compare vs SMC+WaveTrend on same ETH data | SMC+MACD Sharpe > SMC+WaveTrend Sharpe |
| B-1.3 | Compare vs Buy & Hold | Absolute return > B&H |

### Phase B-2: ETH OOS Validation (1 day)

| Step | Test | Pass Criteria |
|------|------|---------------|
| B-2.1 | Temporal OOS (4mo train / 2mo test) | OOS Sharpe > 0 |
| B-2.2 | Purged CV (5-fold, 48-bar embargo) | CV mean Sharpe > 0.3 |
| B-2.3 | Selection stability (SMC+MACD in Top 2) | >= 4/5 folds |

### Phase B-3: ETH Execution Realism (1 day)

| Step | Test | Pass Criteria |
|------|------|---------------|
| B-3.1 | Slippage (0.05%) | Sharpe > 0.5 |
| B-3.2 | Latency (1-bar delay) | Sharpe > 0 |
| B-3.3 | Realistic fee (0.1%) | PF > 1.0 |
| B-3.4 | Worst-case combined | Sharpe > 0 |

---

## 4. Success Criteria for ETH Canonical Promotion

ALL of the following must be met:

| Criterion | Threshold |
|-----------|-----------|
| B-2.1 OOS Sharpe | > 0 |
| B-2.2 CV mean Sharpe | > 0.3 |
| B-2.3 Selection stability | >= 4/5 |
| B-3.4 Worst-case Sharpe | > 0 |

If ALL pass: SMC+MACD becomes ETH canonical adapter.
If ANY fail: ETH remains research-only, no canonical composition.

---

## 5. Prohibited Actions

| Prohibition | Reason |
|-------------|--------|
| Using ETH research results to modify BTC/SOL canonical | Asset compositions are independent |
| Adding WaveTrend as 3rd indicator on ETH | Phase 3 showed WaveTrend is #3 on ETH, not #2 |
| Adaptive indicator selection on ETH | Embeds selection bias structurally |
| Deploying ETH composition before all B-phases pass | Research-only until proven |

---

## 6. Deliverables

| # | Deliverable | Format |
|---|-------------|--------|
| 1 | ETH SMC+MACD baseline results | JSON + report |
| 2 | ETH OOS validation results | JSON + report |
| 3 | ETH execution realism results | JSON + report |
| 4 | ETH canonical promotion decision (A) | Decision record |

---

## Signature

```
CR-046 Track B: ETH Branch Research Plan
Composition: SMC (pure-causal) + MACD
Status: RESEARCH ONLY
Approved by: A (Decision Authority)
Date: 2026-04-01
```
