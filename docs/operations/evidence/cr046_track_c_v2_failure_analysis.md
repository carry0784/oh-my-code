# CR-046 Track C-v2: CROSS_ASSET_NON_GENERALIZABLE Failure Cause Analysis

Date: 2026-04-01
Failure Type: `CROSS_ASSET_NON_GENERALIZABLE`
Sealed Status: NO-GO SEALED

---

## 1. Filter Pass-Rate and Signal Distribution

| Metric | BTC | SOL |
|--------|-----|-----|
| Filter pass-rate (DE >= 0.3) | 24.2% | 25.6% |
| Total signals | 30 | 33 |
| Signals blocked by filter | 17 (57%) | 17 (52%) |
| Signals passed by filter | 13 (43%) | 16 (48%) |

Pass-rates are similar (~25%), and both assets have roughly half their signals blocked. The asymmetry is NOT in how many signals get blocked.

---

## 2. Trade Quality: Blocked vs Passed

| Metric | BTC Blocked | BTC Passed | SOL Blocked | SOL Passed |
|--------|------------|------------|-------------|------------|
| Trades | 14 | 12 | 15 | 14 |
| Sharpe | **-11.29** | **-5.12** | **-3.34** | **+1.38** |
| Win Rate | 14.3% | 25.0% | 26.7% | **42.9%** |
| Return | -21.67% | -10.97% | -10.01% | **+3.66%** |
| PF | 0.49 | 0.49 | - | 1.38+ |

---

## 3. Root Cause Analysis

### Q1: Does the filter remove different quality trades per asset?

**YES -- this is the core asymmetry.**

- **SOL**: Filter correctly separates bad trades (blocked: -3.34 Sharpe, 26.7% WR) from good trades (passed: +1.38 Sharpe, 42.9% WR). The filter **works as intended** on SOL.
- **BTC**: Filter removes bad trades (blocked: -11.29 Sharpe) but the remaining passed trades are **also bad** (-5.12 Sharpe, 25% WR). The filter removes the worst trades but cannot save the rest.

### Q2: Why does the filter improve SOL but destroy BTC?

The root cause is that **BTC's baseline strategy is already deeply negative** (all trades Sharpe=-8.05, return=-30.26%). The directional efficiency filter can separate "very bad" from "bad" on BTC, but there are no "good" trades to preserve.

On SOL, the baseline is mildly negative (Sharpe=-0.45, return=-4.43%). The filter can successfully separate losing trades from winning trades because **winning trades actually exist** in the SOL data.

| Condition | BTC | SOL |
|-----------|-----|-----|
| Baseline has winning subset? | **NO** (25% WR even in passed) | **YES** (42.9% WR in passed) |
| Filter separates winners from losers? | No (both subsets lose) | **Yes** (clear quality separation) |
| Filter improves Sharpe? | No (-8.05 -> -0.92 in full filtered) | **Yes** (-0.45 -> +1.82) |

### Q3: Is this an asset-specific microstructure artifact?

**YES.** The directional efficiency indicator measures price path efficiency, which is inherently asset-specific:

- SOL's microstructure produces distinct "efficient" (trending) and "inefficient" (choppy) periods where the SMC+WT strategy has different performance
- BTC's microstructure under the synthetic data produces uniformly poor SMC+WT performance regardless of directional efficiency

This means directional efficiency is **not a universal regime filter** but an **asset-conditional signal quality indicator**.

---

## 4. Conclusion

The filter failure is caused by:

1. **BTC baseline is too weak** -- no winning trade subset exists to preserve
2. **Filter is explanatory but not operational** -- it can classify regimes but cannot create alpha where none exists
3. **Asset-specific microstructure** -- directional efficiency captures SOL-specific patterns that don't transfer to BTC

This confirms NO-GO SEALED is correct. A cross-asset regime filter must work on assets where the base strategy already has an edge. On assets where the base strategy has no edge (BTC with SMC+WT on this data), no filter can rescue it.

---

```
CR-046 Track C-v2 Failure Analysis
Type: CROSS_ASSET_NON_GENERALIZABLE
Cause: BTC baseline too weak for filter to rescue; SOL-specific artifact
Sealed: NO-GO
```
