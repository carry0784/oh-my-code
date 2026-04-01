# CR-046: Canonical Core Definition (v2)

Date: 2026-04-01 (revised after Phase 3)
Authority: A (Decision Authority)
Status: **APPROVED v2**

---

## 1. Three-Layer Architecture

| Layer | Role | Content |
|-------|------|---------|
| **Anchor** | Universal foundation (#1 on 3/3 assets) | **SMC (Version B, pure-causal)** |
| **Asset Adapter** | Asset-specific 2nd leg | BTC/SOL: **WaveTrend** / ETH: **MACD (research)** |
| **Overlay** | Optional challenger, never canonical | Supertrend, others |

## 2. Asset-Specific Compositions

| Asset | Composition | Status | Evidence |
|-------|-------------|--------|----------|
| **BTC/USDT** | SMC + WaveTrend | **Canonical** | Phase 2 OOS PASS, Phase 3 Sharpe 4.16 |
| **SOL/USDT** | SMC + WaveTrend | **Canonical** | Phase 3 Sharpe 0.85, PF 1.13 |
| **ETH/USDT** | SMC + MACD | **Research** | Phase 3 core pair FAIL, MACD incremental +5.39 |

**Consensus**: 2/2 agreement = signal per asset composition.

## 3. Regime Caveat

Strategy is regime-conditional: bear market strong, sideways weak.
Regime filter research required before universal deployment.

---

## 4. Overlay Layer (Challenger Management)

| Challenger | Role | Evidence |
|------------|------|----------|
| Supertrend | Overlay candidate (BTC only, incremental +0.55) | Phase 3 |
| MACD | ETH adapter candidate / BTC overlay negative | Phase 3 |
| SqueezeMom | Low priority | Phase 2 |
| WilliamsVF | Excluded | Phase 2, Phase 3 |

**Policy**:
- Overlays are **never canonical members**
- Overlays may NOT be used for operational judgment
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
