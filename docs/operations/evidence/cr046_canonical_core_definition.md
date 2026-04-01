# CR-046: Canonical Core Definition

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED**

---

## 1. Canonical Core

| Role | Indicator | Stability | Evidence |
|------|-----------|-----------|----------|
| **Core #1** | **SMC** (Version B, pure-causal) | 5/5 folds Top 2 | Phase 2 purged CV |
| **Core #2** | **WaveTrend** | 5/5 folds Top 2 | Phase 2 purged CV |

**Consensus**: 2/2 agreement = signal.
**Threshold**: Both SMC and WaveTrend must agree (weighted_score >= 2 or <= -2).

---

## 2. Challenger Slot (3rd Indicator -- Research Only)

| Challenger | Fold Appearances | Role |
|------------|-----------------|------|
| MACD | 3/5 | Overlay candidate |
| Supertrend | 2/5 | Overlay candidate |
| SqueezeMom | 1/5 | Low priority |
| WilliamsVF | 0/5 | Excluded |

**Policy**:
- Challengers are **overlay candidates**, not core members
- Challengers may NOT be used for operational judgment
- Challenger evaluation is a separate research track (Track B)
- Adaptive 3rd indicator operationalization is **FORBIDDEN**

---

## 3. Version Policy

| Version | Role |
|---------|------|
| SMC Version B (pure-causal) | **Canonical** |
| SMC Version A (delay-compensated) | Reference only |

---

## 4. Temporal OOS Caveat

> High performance observed (Sharpe 8.34), but treated as potentially
> regime-favorable rather than baseline expectation.

---

## 5. Prohibited Actions

| Prohibition | Reason |
|-------------|--------|
| 3-indicator fixed composition as canonical | Selection stability 2/5 FAIL |
| Adaptive 3rd indicator in operations | Embeds selection bias structurally |
| Version A for judgment | Structural safety concern |
| Supertrend as canonical member | Only 2/5 fold stability |

---

## Signature

```
Canonical Core: SMC (pure-causal) + WaveTrend
Challengers: Supertrend, MACD (research only)
Approved by: A (Decision Authority)
Date: 2026-04-01
```
