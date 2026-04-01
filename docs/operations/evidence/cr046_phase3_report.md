# CR-046 Phase 3: Multi-Asset / Multi-Regime -- Results Report

Date: 2026-04-01
Canonical Core: **SMC (pure-causal) + WaveTrend**
Challengers: Supertrend, MACD (overlay candidates)

---

## 1. Multi-Asset Core Pair Results

| Asset | Buy & Hold | Core Sharpe | Core Return | Core PF | Core MDD | Trades | Core Survival |
|-------|------------|-------------|-------------|---------|----------|--------|---------------|
| **BTC/USDT** | -42.41% | **4.16** | **+32.77%** | 1.76 | 10.76% | 35 | **YES** |
| **ETH/USDT** | -51.90% | **-3.88** | **-25.06%** | 0.60 | 33.81% | 33 | **NO** |
| **SOL/USDT** | -63.18% | **0.85** | **+5.19%** | 1.13 | 20.49% | 39 | **YES** |

### Core Pair Survival Rate: 2/3 (67%)

- **BTC**: SMC #1, WaveTrend #2 -- **MATCH**
- **ETH**: SMC #1, MACD #2, WaveTrend #3 -- **NO MATCH** (MACD replaces WaveTrend as #2)
- **SOL**: SMC #1, WaveTrend #2 -- **MATCH**

**Key finding**: SMC is universally #1 across all 3 assets. WaveTrend is #2 on BTC and SOL but drops to #3 on ETH.

---

## 2. 3rd-Slot Incremental Value

| Asset | +Supertrend | +MACD | Better 3rd |
|-------|------------|-------|------------|
| BTC | +0.55 Sharpe | -2.86 Sharpe | Supertrend |
| ETH | +2.64 Sharpe | **+5.39 Sharpe** | **MACD** |
| SOL | -1.72 Sharpe | -1.14 Sharpe | Neither (both negative) |

**Key finding**: 3rd indicator value is **asset-dependent**. No single 3rd indicator is consistently positive across all assets.
- BTC: Supertrend helps, MACD hurts
- ETH: MACD dramatically helps (+5.39), Supertrend modest
- SOL: Both hurt (core pair alone is best)

---

## 3. BTC Regime Analysis

| Quarter | Regime | Buy & Hold | Core Return | Core Sharpe | Trades | Beats B&H |
|---------|--------|------------|-------------|-------------|--------|-----------|
| Q1 | **bear** | -20.4% | **+15.23%** | **8.46** | 9 | **YES** |
| Q2 | **sideways** | -8.4% | -8.66% | -8.13 | 7 | NO |
| Q3 | **bear** | -19.7% | **+14.12%** | **7.95** | 9 | **YES** |
| Q4 | **sideways** | -2.7% | **+13.14%** | **6.31** | 9 | **YES** |

**Key finding**: Core pair excels in bear markets (Q1, Q3) with Sharpe >7. Struggles in sideways (Q2, Sharpe -8.13). Q4 sideways is positive, suggesting inconsistency in sideways performance.

---

## 4. Three-Tier Judgment

### Research Validity: CONDITIONAL

| Check | BTC | ETH | SOL | Overall |
|-------|-----|-----|-----|---------|
| Core Sharpe > 0 | **PASS** (4.16) | **FAIL** (-3.88) | **PASS** (0.85) | 2/3 |
| Core PF > 1.0 | **PASS** (1.76) | FAIL (0.60) | **PASS** (1.13) | 2/3 |
| Core pair survival | **YES** | NO | **YES** | 2/3 |
| Beats Buy & Hold | **YES** (+75pp) | YES (+27pp) | **YES** (+68pp) | 3/3 |

### Execution Realism: Phase 4 (pending)

### Operational Fit: CG-2B PROVEN (CR-047)

---

## 5. Acceptance Criteria

| AC | Check | Threshold | Result | Verdict |
|----|-------|-----------|--------|---------|
| AC-6 | Multi-asset Sharpe (ETH or SOL) | > 0 | SOL: 0.85 | **PASS** (SOL) |
| AC-6b | ETH Sharpe | > 0 | -3.88 | **FAIL** |
| Core survival | >= 2/3 assets | >= 2/3 | 2/3 | **PASS** |

---

## 6. Key Findings Summary

### 6A. SMC is the universal anchor

SMC ranks #1 on all 3 assets tested. It is the strongest individual indicator across the board. This confirms SMC as the foundation of any composite strategy.

### 6B. WaveTrend is BTC/SOL-specific

WaveTrend is #2 on BTC and SOL but drops to #3 on ETH (replaced by MACD). This means the canonical core pair (SMC+WaveTrend) is not universally optimal -- it is **BTC/SOL-biased**.

### 6C. ETH requires different composition

On ETH, the optimal pair would be SMC+MACD (not SMC+WaveTrend). The core pair strategy loses -25% on ETH while B&H loses -52%. It beats B&H but still has negative absolute return.

### 6D. Bear market strength, sideways weakness

The core pair strongly outperforms in bear markets (Q1, Q3) but underperforms in sideways (Q2). This is a **regime-conditional strategy**.

### 6E. 3rd indicator is asset-specific, not universal

No single 3rd indicator adds value across all assets. This confirms A's decision to treat 3rd indicators as overlay candidates rather than canonical members.

---

## 7. Recommendations for A

| Decision Point | Options | B's Recommendation |
|---------------|---------|-------------------|
| ETH failure | (a) Accept ETH weakness (b) Create ETH-specific composition | Report to A for judgment |
| Regime dependency | (a) Accept as regime-conditional (b) Add regime filter | Report to A for judgment |
| Core pair scope | (a) BTC+SOL only (b) Universal with caveats | Report to A for judgment |

---

## 8. Phase 3 Verdict

```
Phase 3 Overall: CONDITIONAL PASS

Passed:
  - BTC/USDT: Core pair Sharpe 4.16, return +32.77% (strong)
  - SOL/USDT: Core pair Sharpe 0.85, return +5.19% (positive)
  - Core pair survival 2/3 (67%)
  - Beats Buy & Hold on all 3 assets
  - Bear market performance excellent

Failed:
  - ETH/USDT: Core pair Sharpe -3.88 (negative)
  - Sideways regime Q2: Sharpe -8.13
  - WaveTrend not universally #2

Interpretation:
  SMC+WaveTrend canonical core is BTC/SOL-effective, ETH-weak.
  The strategy is regime-conditional (bear > sideways).
  Universal deployment across all assets is not supported by current evidence.

  High performance observed on BTC, but treated as potentially
  regime-favorable rather than baseline expectation.
```

---

## Signature

```
CR-046 Phase 3 Report
Canonical Core: SMC (pure-causal) + WaveTrend
Result: CONDITIONAL PASS (BTC/SOL positive, ETH negative)
Key Finding: Asset-specific and regime-conditional performance
Prepared by: B (Implementer)
Date: 2026-04-01
```
