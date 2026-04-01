# CR-046: Overlay / Challenger Management Rules

Date: 2026-04-01
Authority: A (Decision Authority)
Status: **APPROVED**

---

## 1. Three-Layer Architecture

```
Layer 1: ANCHOR        -- SMC (pure-causal, Version B)
Layer 2: ASSET ADAPTER -- Asset-specific 2nd indicator
Layer 3: OVERLAY       -- Optional challenger, never canonical
```

---

## 2. Layer Definitions

### Layer 1: Anchor (SMC)

| Rule | Description |
|------|-------------|
| Immutability | SMC Version B is the universal anchor on all assets |
| No replacement | No indicator may replace SMC as anchor |
| Version policy | Version B (pure-causal) canonical; Version A reference only |
| Modification | Only via full CR cycle with Phase 1-4 re-validation |

### Layer 2: Asset Adapter

| Rule | Description |
|------|-------------|
| Asset-specific | Each asset has its own 2nd indicator |
| Current assignments | BTC: WaveTrend, SOL: WaveTrend, ETH: MACD (research) |
| Promotion criteria | Must pass Phase 2 OOS + Phase 3 multi-regime + Phase 4 execution |
| Consensus requirement | 2/2 agreement between anchor and adapter for signal |

### Layer 3: Overlay (Challengers)

| Rule | Description |
|------|-------------|
| Never canonical | Overlays may NOT become canonical members via any process |
| No operational judgment | Overlay results cannot be used for go/no-go decisions |
| Research only | Overlays exist for measurement and comparison purposes only |
| No signal contribution | Overlays do NOT participate in consensus voting |

---

## 3. Overlay Lifecycle

### 3.1 Registration

Any indicator may be registered as an overlay candidate. No approval required.

### 3.2 Measurement

Overlays are measured alongside canonical composition for comparison:
- In-sample Sharpe/Return/PF
- OOS performance (when canonical is tested)
- Incremental value (if added as 3rd indicator, what happens to Sharpe)

### 3.3 Promotion Path

Overlay -> Asset Adapter promotion requires:

| Step | Requirement |
|------|-------------|
| 1 | Overlay consistently outperforms current adapter on target asset (>= 3 consecutive measurement periods) |
| 2 | Full Phase 2-4 re-validation with proposed new composition |
| 3 | A (Decision Authority) explicit approval |
| 4 | CR filed and tracked through standard change control |

### 3.4 Retirement

An overlay is retired when:
- Negative incremental Sharpe on all assets for >= 3 consecutive measurements
- Implementer (B) proposes retirement, A approves

---

## 4. Current Overlay Registry

| Overlay | Status | Evidence | Notes |
|---------|--------|----------|-------|
| Supertrend | Active challenger (BTC only) | Phase 3: +0.55 Sharpe incremental on BTC | Selection stability 2/5 FAIL |
| MACD | Active research (ETH adapter candidate) | Phase 3: +5.39 Sharpe incremental on ETH | Track B research in progress |
| SqueezeMom | Low priority | Phase 2: appeared in 1/5 folds | Insufficient evidence |
| WilliamsVF | Excluded | Phase 2, Phase 3: consistently bottom-ranked | No promotion path |

---

## 5. Prohibited Actions

| # | Prohibition | Reason |
|---|-------------|--------|
| P-1 | Using overlay performance for operational decisions | Overlays are research-only |
| P-2 | Adaptive 3rd indicator operationalization | Embeds selection bias structurally |
| P-3 | 3-indicator fixed composition as canonical | Selection stability 2/5 FAIL (Phase 2) |
| P-4 | Overlay signal contributing to consensus | Only anchor + adapter vote |
| P-5 | Bypassing Phase 2-4 for overlay promotion | Full validation cycle required |
| P-6 | Modifying anchor based on overlay results | Anchor is immutable |

---

## 6. Reporting

Each Phase 3+ validation must include:
1. Canonical composition performance (anchor + adapter)
2. Each active overlay's incremental Sharpe
3. Overlay ranking relative to adapter
4. Recommendation: continue / promote / retire

---

## Signature

```
CR-046 Overlay/Challenger Management Rules
Anchor: SMC (pure-causal)
Active Overlays: Supertrend, MACD, SqueezeMom
Excluded: WilliamsVF
Approved by: A (Decision Authority)
Date: 2026-04-01
```
