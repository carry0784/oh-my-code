# CR-046 Track C: Regime Filter Research -- Results Report

Date: 2026-04-01
Canonical Core: **SMC (pure-causal) + WaveTrend**
Scope: BTC/SOL (canonical assets only)

---

## 1. Executive Summary

| Check | BTC/USDT | SOL/USDT | Verdict |
|-------|----------|----------|---------|
| Regime classification accuracy | 49.6% | 68.1% | **INSUFFICIENT** |
| Sideways identification | 9-13% | 9-10% | **FAIL** |
| Filter Sharpe improvement | -0.27 | -0.22 | **FAIL** |
| Bear preservation | PASS | PASS | **PASS** |

**Track C Phase C-1/C-2 Overall: FAIL**

The current regime filter implementation does not improve strategy performance. The filter correctly identifies trending/bear regimes (86-90% accuracy) but **fails to identify sideways regimes** (9-13% accuracy). As a result, the filter removes some profitable trades while failing to suppress the unprofitable sideways trades it was designed to catch.

---

## 2. Phase C-1: Regime Identification Results

### BTC/USDT

| Quarter | Known Regime | Classification Accuracy | ADX Mean | BB% Mean | ATR Ratio |
|---------|-------------|------------------------|----------|----------|-----------|
| Q1 | bear | **86.2%** | 36.12 | 46.7 | 1.013 |
| Q2 | sideways | **9.3%** | 34.44 | 50.1 | 1.001 |
| Q3 | bear | **89.8%** | 37.31 | 50.1 | 1.012 |
| Q4 | sideways | **13.0%** | 34.26 | 48.0 | 1.011 |

### SOL/USDT

| Quarter | Known Regime | Classification Accuracy | ADX Mean | BB% Mean | ATR Ratio |
|---------|-------------|------------------------|----------|----------|-----------|
| Q1 | bear | **85.6%** | 35.20 | 45.2 | 1.004 |
| Q2 | bear | **89.4%** | 33.28 | 51.4 | 0.997 |
| Q3 | bear | **88.3%** | 36.09 | 51.6 | 1.001 |
| Q4 | sideways | **9.0%** | 34.73 | 49.0 | 1.006 |

### Root Cause of Sideways Misclassification

**The problem is clear**: ADX values in sideways quarters (34.26-34.44 BTC, 34.73 SOL) are **nearly identical** to ADX in bear quarters (36.12-37.31 BTC). The ADX threshold of 25 (trending) is crossed in both regimes, making the indicator unable to discriminate.

Similarly, BB Width percentile and ATR ratio show minimal difference between regimes:
- BB%: 46-50 in both bear and sideways
- ATR ratio: 0.997-1.013 in both regimes

**Conclusion**: The crypto market on 1H timeframe maintains high ADX even during sideways periods. Traditional equity-market ADX thresholds (20/25) do not transfer to crypto.

---

## 3. Phase C-2: Filter Integration Results

### BTC/USDT

| Metric | Baseline | Filtered | Delta |
|--------|----------|----------|-------|
| Sharpe | 1.40 | 1.13 | **-0.27** |
| Return | +24.81% | +17.18% | **-7.64pp** |
| PF | 1.71 | 1.59 | -0.12 |
| MDD | 8.83% | 8.83% | 0 |
| Trades | 32 | 28 | -4 |

**Regime distribution**: Trending 89.5%, Sideways 11.7%

### SOL/USDT

| Metric | Baseline | Filtered | Delta |
|--------|----------|----------|-------|
| Sharpe | 0.84 | 0.62 | **-0.22** |
| Return | +14.57% | +8.52% | **-6.06pp** |
| PF | 1.37 | 1.28 | -0.09 |
| MDD | 13.45% | 10.81% | -2.64 (improvement) |
| Trades | 35 | 31 | -4 |

**Regime distribution**: Trending 89.6%, Sideways 11.5%

### Per-Quarter Analysis

#### BTC/USDT

| Quarter | Regime | Unfiltered Sharpe | Filtered Sharpe | Delta | Sideways% |
|---------|--------|-------------------|-----------------|-------|-----------|
| Q1 | bear | 1.26 | 1.43 | **+0.17** | 13.8% |
| Q2 | **sideways** | -1.29 | -1.29 | **0.00** | 9.3% |
| Q3 | bear | 1.19 | 1.19 | 0.00 | 10.2% |
| Q4 | **sideways** | 1.21 | 0.64 | **-0.57** | 13.0% |

**Critical observation**: Q2 (the worst sideways quarter, Sharpe -1.29) shows **zero filter improvement** because the filter classifies only 9.3% of Q2 bars as sideways -- it misses the very bars it should suppress.

Q4 (mild sideways but actually profitable) gets hurt by the filter (-0.57 Sharpe) because the few bars it does suppress happen to be profitable ones.

#### SOL/USDT

| Quarter | Regime | Unfiltered Sharpe | Filtered Sharpe | Delta | Sideways% |
|---------|--------|-------------------|-----------------|-------|-----------|
| Q1 | bear | -0.05 | 0.25 | **+0.30** | 14.4% |
| Q2 | bear | -0.09 | -0.09 | 0.00 | 10.6% |
| Q3 | bear | 1.05 | 1.39 | **+0.34** | 11.7% |
| Q4 | **sideways** | 0.89 | -0.45 | **-1.34** | 9.0% |

Same pattern: sideways quarters are not identified, and profitable bear quarters occasionally get improved (by removing a few noisy trades in micro-sideways moments).

---

## 4. Why This Filter Failed

### 4A. Crypto ADX is structurally high

In traditional equity markets, ADX < 20 indicates sideways. In 1H crypto, ADX averages 33-37 even during sideways periods due to:
- Higher baseline volatility
- 24/7 trading (no overnight gaps)
- Constant microtrend oscillations within range

### 4B. Bollinger Band Width is regime-indifferent

BB Width percentile averages 46-51 across both bear and sideways quarters. The squeeze/expansion cycle in crypto operates on shorter timescales than quarterly classification can capture.

### 4C. ATR Ratio near unity everywhere

ATR(14)/ATR(50) hovers at 0.997-1.013 regardless of regime. Short-term and long-term volatility track each other closely in crypto, making this ratio nearly useless for regime detection.

### 4D. The filter removes good trades, not bad ones

With only 9-13% of bars classified as sideways, the filter removes ~4 trades. But those trades are essentially random with respect to the actual sideways periods, so the filter hurts more than it helps.

---

## 5. Recommendations for A

### Option (a): Accept strategy as regime-conditional (RECOMMENDED)

The current canonical core (SMC+WaveTrend) is regime-conditional. Bear markets produce strong results; sideways is weak. Traditional regime filters do not work on crypto 1H data. **Accept this as a known characteristic** and manage risk through position sizing rather than signal filtering.

### Option (b): Research alternative regime indicators

If A wants to continue regime filter research, candidates that might work for crypto:
1. **Realized volatility percentile** (instead of ATR ratio)
2. **Range compression** (high/low range as % of price over N bars)
3. **Directional correlation** (rolling correlation of returns with lagged returns)
4. **Market microstructure** indicators (order flow, if available)

These would require a separate research cycle (Track C-2).

### Option (c): Use time-based regime (calendar patterns)

Instead of indicator-based regime detection, use empirical observation:
- Avoid trading during historically low-volatility months
- Reduce exposure when B&H drawdown exceeds threshold

This is simpler but less principled.

---

## 6. Success Criteria Assessment

| Criterion | Threshold | Result | Verdict |
|-----------|-----------|--------|---------|
| Sideways Sharpe improvement | > 2.0 absolute | 0.00 (BTC Q2) | **FAIL** |
| Bear period degradation | < 10% relative | PASS (mostly 0) | **PASS** |
| Overall Sharpe with filter | > unfiltered | BTC -0.27, SOL -0.22 | **FAIL** |
| Filter stability cross-asset | Same threshold works | Both fail similarly | **N/A (both fail)** |

---

## 7. Track C Verdict

```
Track C Phase C-1/C-2: FAIL

Root Cause:
  Traditional regime indicators (ADX, BB Width, ATR ratio) do not
  discriminate between trending and sideways regimes in crypto 1H data.
  ADX remains > 30 even in sideways periods.

Consequence:
  The filter classifies only 9-13% of sideways bars correctly,
  making it unable to suppress the trades it should suppress.

Impact on Deployment:
  Regime filter is NOT a viable pre-deployment defense mechanism
  with current indicators. The strategy must be accepted as
  regime-conditional or alternative regime indicators must be
  researched.

Recommendation:
  (a) Accept regime-conditional nature (preferred)
  (b) Research alternative crypto-specific regime indicators (optional)
```

---

## Signature

```
CR-046 Track C Report
Regime Filter: Phase C-1/C-2 FAIL
Root Cause: Crypto ADX structurally high in sideways
Recommendation: Accept regime-conditional or research alternatives
Prepared by: B (Implementer)
Date: 2026-04-01
```
