# CR-046: Asset-Specific Deployment Readiness Table

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **ACTIVE -- updated per A's decisions**

---

## Deployment Readiness Matrix

| Axis | SOL/USDT | BTC/USDT | ETH/USDT |
|------|----------|----------|----------|
| **Deployment Grade** | `conditionally ready` | `conditionally hold` | `research only` |
| **Phase 5 Status** | Paper rollout GO | Guarded paper GO | EXCLUDED |
| **Priority** | **1st** | **2nd** | **3rd (pending Track B)** |

---

## Per-Asset Evidence Summary

### SOL/USDT

| Dimension | Result | Reference |
|-----------|--------|-----------|
| Research Validity | Sharpe 0.85, PF 1.37 | Phase 3 |
| Execution Realism | Worst-case Sharpe 1.13 | Phase 4 |
| Latency Sensitivity | LOW (Sharpe improves with delay) | Phase 4 |
| Regime Risk | Bear strong, sideways accept | Phase 3, Track C |
| Operational Fit | CG-2B PROVEN | CR-047 |
| Regime Filter | Not adopted (v1 FAIL) | Track C |

### BTC/USDT

| Dimension | Result | Reference |
|-----------|--------|-----------|
| Research Validity | Sharpe 4.16, PF 1.71 | Phase 3 |
| Execution Realism | Worst-case Sharpe -0.02 | Phase 4 |
| Latency Sensitivity | **HIGH** (Sharpe -91% with 1-bar delay) | Phase 4 |
| Regime Risk | Bear excellent, sideways Q2 -8.13 | Phase 3 |
| Operational Fit | CG-2B PROVEN | CR-047 |
| Regime Filter | Not adopted (v1 FAIL) | Track C |
| Guard Required | Latency guard checklist | cr046_btc_latency_guard_checklist.md |

### ETH/USDT

| Dimension | Result | Reference |
|-----------|--------|-----------|
| Research Validity | Core pair Sharpe -3.88 (FAIL) | Phase 3 |
| Execution Realism | NOT TESTED | -- |
| Alternative Composition | SMC+MACD (research) | Track B |
| Deployment | PROHIBITED | A's decision |

---

## Three Judgment Axes (A's Directive)

| Axis | SOL | BTC | ETH |
|------|-----|-----|-----|
| `asset_adapter_validity` | PROVEN (WaveTrend) | PROVEN (WaveTrend) | PENDING (MACD research) |
| `regime_robustness` | Accepted as conditional | Accepted as conditional | N/A |
| `deployment_readiness` | Paper rollout GO | Guarded paper GO | EXCLUDED |

---

## Regime-Conditional Acceptance

> **Current strategy is accepted as regime-conditional; no production filter is adopted from Track C v1.**

| Regime | Expected Performance | Management |
|--------|---------------------|------------|
| Bear market | Strong (BTC Sharpe >7, SOL positive) | Full position sizing |
| Sideways market | Weak (BTC Q2 Sharpe -8.13) | Accept via daily loss limits |
| Bull market | Not yet tested at scale | Monitor via Phase 5a |

---

## Status Tracking

| Date | Event | SOL | BTC | ETH |
|------|-------|-----|-----|-----|
| 2026-04-01 | Phase 4 sealed | conditionally ready | conditionally hold | research only |
| 2026-04-01 | Track C FAIL | no change | no change | no change |
| 2026-04-01 | Phase 5 approved | paper GO | guarded paper GO | excluded |
| TBD | Phase 5a complete | -> 5b decision | -> 5b decision | -- |
| TBD | Track B complete | -- | -- | -> adapter decision |

---

## Signature

```
CR-046 Deployment Readiness Table
SOL: conditionally ready for paper rollout (1st priority)
BTC: guarded paper rollout only (2nd priority)
ETH: research only (excluded)
Approved by: A (Decision Authority)
Date: 2026-04-01
```
