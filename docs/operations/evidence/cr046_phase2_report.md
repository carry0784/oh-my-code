# CR-046 Phase 2: OOS / Walk-Forward / Purged CV -- Results Report

Date: 2026-04-01
SMC Version: **B (pure-causal, canonical)**
Strategy D: SMC + WaveTrend + Supertrend, 2/3 consensus

---

## 1. Executive Summary

| Test | Result | Pass Criteria | Verdict |
|------|--------|---------------|---------|
| 2.1 Temporal OOS (Sharpe) | **8.34** | > 0.5 | **PASS** |
| 2.1 Temporal OOS (Return) | **+30.79%** | > 0% | **PASS** |
| 2.2 Walk-Forward Mean Sharpe | **-0.25** | > 0.3 | **FAIL** |
| 2.3 Purged CV Mean Sharpe | **2.81** | > 0.3 | **PASS** |
| 2.4 Selection Stability | **2/5** | >= 3/5 | **FAIL** |

**Phase 2 Overall: CONDITIONAL PASS (3/5)**

---

## 2. Detailed Results

### 2.1 Temporal OOS Split

```
Train: bars 0-2880 (Oct 2025 - Jan 2026, 4 months)
Test:  bars 2880-4320 (Feb - Apr 2026, 2 months)
```

| Metric | Value |
|--------|-------|
| Top 3 selected (train) | SMC, Supertrend, WaveTrend |
| OOS Sharpe | **8.34** |
| OOS Return | **+30.79%** |
| OOS Win Rate | 62.5% |
| OOS Profit Factor | 3.08 |
| OOS Max Drawdown | 2.89% |
| OOS Trades | 16 |

**Verdict: PASS** -- OOS 성능이 in-sample과 동등하게 강함. 선택 편향이 이 분할에서는 발현되지 않음.

### 2.2 Walk-Forward (3 Windows)

| Window | Train | Test | Top 3 | OOS Sharpe | OOS Return |
|--------|-------|------|-------|------------|------------|
| 1 | 0-2160 | 2160-2880 | SMC, WaveTrend, **MACD** | -1.17 | -3.27% |
| 2 | 720-2880 | 2880-3600 | SMC, **MACD**, WaveTrend | -0.95 | -2.87% |
| 3 | 1440-3600 | 3600-4320 | SMC, WaveTrend, **MACD** | **1.38** | +3.46% |

| Aggregate | Value |
|-----------|-------|
| Mean OOS Sharpe | **-0.25** |
| Pass (> 0.3) | **FAIL** |

**Verdict: FAIL** -- Walk-forward에서 Top 3가 {SMC, WaveTrend, MACD}로 변경됨 (Supertrend 탈락, MACD 진입). 더 짧은 훈련 기간에서는 Supertrend가 일관되게 Top 3에 들지 못함. Window 1,2에서 음수 Sharpe.

**핵심 관찰**: Walk-forward에서 Supertrend가 MACD로 대체됨. Strategy D의 구성 자체가 불안정할 수 있음.

### 2.3 Purged Cross-Validation

| Fold | Top 3 | OOS Sharpe | OOS Return | Trades |
|------|-------|------------|------------|--------|
| 1 | SMC, WaveTrend, **MACD** | 5.05 | +13.92% | 15 |
| 2 | SMC, WaveTrend, **SqueezeMom** | 2.65 | +5.72% | 12 |
| 3 | SMC, **Supertrend**, WaveTrend | -1.43 | -3.13% | 11 |
| 4 | SMC, **Supertrend**, WaveTrend | 4.74 | +12.99% | 15 |
| 5 | SMC, WaveTrend, **MACD** | 3.05 | +11.66% | 22 |

| Aggregate | Value |
|-----------|-------|
| Mean CV Sharpe | **2.81** |
| Std CV Sharpe | 2.32 |
| Pass (> 0.3) | **PASS** |

**Verdict: PASS** -- CV mean Sharpe 2.81은 in-sample 4.71보다 낮지만 여전히 양수이고 유의미. 단, std 2.32로 변동성이 큼 (Fold 3에서 음수).

### 2.4 Selection Stability

| Fold | Top 3 | {SMC, WaveTrend, Supertrend} Match |
|------|-------|------------------------------------|
| 1 | SMC, WaveTrend, **MACD** | DIFFER |
| 2 | SMC, WaveTrend, **SqueezeMom** | DIFFER |
| 3 | SMC, Supertrend, WaveTrend | **MATCH** |
| 4 | SMC, Supertrend, WaveTrend | **MATCH** |
| 5 | SMC, WaveTrend, **MACD** | DIFFER |

| Aggregate | Value |
|-----------|-------|
| Stable folds | **2/5** |
| Pass (>= 3/5) | **FAIL** |

**Verdict: FAIL** -- Top 3 구성이 불안정. SMC와 WaveTrend는 5/5 안정적이지만, **3번째 자리가 Supertrend/MACD/SqueezeMom 사이에서 변동**.

---

## 3. Three-Tier Judgment

### Research Validity: CONDITIONAL

| Check | Result | Note |
|-------|--------|------|
| OOS Sharpe > 0.5 | **PASS** (8.34) | 매우 강함 |
| OOS Return > 0% | **PASS** (+30.79%) | 양호 |
| WF mean Sharpe > 0.3 | **FAIL** (-0.25) | Window 1,2 음수 |
| CV mean Sharpe > 0.3 | **PASS** (2.81) | 양호, std 높음 |
| Selection stability >= 3/5 | **FAIL** (2/5) | 3rd indicator 불안정 |

### Execution Realism: PENDING (Phase 4)

### Operational Fit: PROVEN (CR-047)

---

## 4. Key Findings

### 4A. SMC + WaveTrend = 안정적 핵심 쌍

5/5 fold에서 SMC와 WaveTrend가 모두 Top 2에 포함.
이 두 지표는 Strategy D의 안정적 기반.

### 4B. 3번째 지표 불안정

| 3rd Indicator | 출현 횟수 (5 folds) |
|---------------|-------------------|
| MACD | 3/5 |
| Supertrend | 2/5 |
| SqueezeMom | 1/5 |

Supertrend는 원래 Strategy D의 구성원이지만, fold별로 MACD에 밀리는 경우가 더 많음.

### 4C. Walk-Forward 실패의 의미

Walk-forward에서 3/3 window 모두 Top 3가 {SMC, WaveTrend, MACD}로 선택됨.
그런데 이 조합의 평균 Sharpe는 -0.25.
이것은 **짧은 훈련 기간(3개월)에서는 최적 구성 자체가 OOS에서 음수를 기록**할 수 있다는 의미.

### 4D. In-Sample vs OOS Comparison

| Metric | In-Sample (full) | Temporal OOS | WF Mean | CV Mean |
|--------|-----------------|--------------|---------|---------|
| Sharpe | 4.71 | 8.34 | -0.25 | 2.81 |
| Return | +64.32% | +30.79% | -0.89% | +8.23% |

Temporal OOS가 in-sample보다 높은 Sharpe를 기록한 것은 주의 필요.
이것은 테스트 기간(Feb-Apr 2026)이 특히 Strategy D에 유리했을 수 있음을 시사.

---

## 5. Phase 2 Acceptance Criteria

| AC | Check | Threshold | Result | Verdict |
|----|-------|-----------|--------|---------|
| AC-3 | OOS Sharpe (temporal) | > 0.5 | 8.34 | **PASS** |
| AC-4 | Walk-forward mean Sharpe | > 0.3 | -0.25 | **FAIL** |
| AC-5 | Selection stability | >= 3/5 | 2/5 | **FAIL** |

---

## 6. Phase 2 Verdict

```
Phase 2 Overall: CONDITIONAL PASS

Passed: 3/5 (OOS Sharpe, OOS Return, CV mean Sharpe)
Failed: 2/5 (Walk-forward mean Sharpe, Selection stability)

Interpretation:
  Strategy D는 충분한 훈련 데이터(4개월)로 선택하면 OOS에서 강한 성능을 보임.
  그러나 짧은 훈련 기간(3개월) walk-forward에서는 실패.
  3번째 지표(Supertrend)가 불안정하여 구성 자체가 흔들림.

  핵심 안정 쌍: SMC + WaveTrend (5/5 안정)
  불안정 요소: 3rd indicator (Supertrend vs MACD vs SqueezeMom)

Recommendation:
  1. Strategy D를 고정 구성(SMC+WaveTrend+Supertrend)으로 배포하는 것은 위험
  2. 대안: SMC+WaveTrend 2-indicator core에 adaptive 3rd 선택 검토
  3. 또는: min_consensus를 2/3 대신 2/2 (SMC+WaveTrend only)로 축소 검토
  4. Phase 3 (multi-asset) 진행 전 3rd indicator 안정화 필요

  A 결정 필요:
  - Strategy D 고정 구성 유지 vs adaptive 3rd indicator 전환
  - Phase 3 착수 조건
```

---

## Signature

```
CR-046 Phase 2 Report
SMC Version: B (pure-causal, canonical)
Result: CONDITIONAL PASS (3/5)
Key Finding: SMC+WaveTrend stable, 3rd indicator unstable
Prepared by: B (Implementer)
Date: 2026-04-01
```
