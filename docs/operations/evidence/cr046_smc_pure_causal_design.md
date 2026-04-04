# CR-046: SMC Pure-Causal Reimplementation Design

Date: 2026-04-01
Status: **PROPOSED**
Prerequisite: CR-046 Phase 1 Audit (CONDITIONAL PASS)
Scope: SMC swing detection을 순수 과거 데이터 전용으로 재구현
Authority: A 결정 -- "pure-causal 재구현 후 Phase 2 본판 진행"

---

## 1. 문제 정의

### 현 구현 (Version A: delay-compensated)

```python
# indicator_backtest.py L409-417
for i in range(internal_length, n - internal_length):
    window_h = highs[max(0, i - internal_length):i + internal_length + 1]
    #                                            ^^^^^^^^^^^^^^^^^^^^
    #                                            i+1 ~ i+L 미래 바 접근
    if highs[i] == np.max(window_h):
        swing_highs[i] = highs[i]
```

**문제**: swing 감지에 `internal_length`개의 미래 바를 사용.
지연 보정(`swing_highs[i - internal_length]`)으로 신호 타이밍은 보정되지만,
**swing point 분류 품질 자체가 미래 데이터로 과대평가**됨.

### 영향

- SMC가 "더 좋은 swing"을 골라냄 -> backtest에서 더 높은 WinR/Sharpe
- Strategy D (SMC+WaveTrend+Supertrend) Sharpe 4.71 중 SMC 기여분 과대평가 가능
- Phase 2 OOS 검증 결과도 오염될 수 있음

---

## 2. Pure-Causal 재구현 (Version B)

### 설계 원칙

1. Swing point 감지에 **오직 과거 + 현재 바만 사용**
2. 미래 바 접근 0건
3. 지연 보정 불필요 (애초에 미래를 보지 않으므로)
4. 실시간 트레이딩에서 동일하게 작동

### 구현

```python
def calc_smc_pure_causal(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    swing_length: int = 50, internal_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Pure-causal SMC: swing detection using only past data.

    Swing high at bar i: confirmed when the next internal_length bars
    all have lower highs. Detection happens at bar i + internal_length,
    NOT at bar i.

    This means:
    - At bar j, we check if bar j-L was a swing high
    - By checking highs[j-2L : j-L+1] (past-only window)
    - If highs[j-L] == max(window), it's a confirmed swing
    - No future data needed at any point
    """
    n = len(closes)
    L = internal_length
    trend = np.zeros(n, dtype=int)
    signals = np.zeros(n, dtype=int)

    last_swing_high = np.nan
    last_swing_low = np.nan
    current_trend = 0

    for i in range(2 * L, n):
        # Check if bar (i - L) is a swing high using only past data
        # Window: [i - 2L, ..., i - L, ..., i]
        # All bars in this window are at index <= i (current bar)
        candidate_idx = i - L
        window_start = max(0, candidate_idx - L)
        window_end = i + 1  # up to current bar (inclusive)

        window_h = highs[window_start:window_end]
        if highs[candidate_idx] == np.max(window_h):
            last_swing_high = highs[candidate_idx]

        window_l = lows[window_start:window_end]
        if lows[candidate_idx] == np.min(window_l):
            last_swing_low = lows[candidate_idx]

        # BOS/CHoCH detection (same logic, no delay needed)
        if not np.isnan(last_swing_high) and closes[i] > last_swing_high:
            if current_trend == -1:
                signals[i] = 1  # CHoCH (bullish)
            elif current_trend == 1:
                signals[i] = 1  # BOS (bullish continuation)
            current_trend = 1
            last_swing_high = np.nan

        if not np.isnan(last_swing_low) and closes[i] < last_swing_low:
            if current_trend == 1:
                signals[i] = -1  # CHoCH (bearish)
            elif current_trend == -1:
                signals[i] = -1  # BOS (bearish continuation)
            current_trend = -1
            last_swing_low = np.nan

        trend[i] = current_trend

    return trend, signals
```

### Version A vs Version B 차이

| 항목 | Version A (현재) | Version B (pure-causal) |
|------|-----------------|----------------------|
| Swing detection window | `[i-L : i+L+1]` | `[i-2L : i+1]` |
| 미래 바 접근 | L개 | **0개** |
| Swing 확인 시점 | bar i (미래 L바 포함) | bar i+L (과거 데이터만) |
| 지연 보정 | 필요 (signal uses `[i-L]`) | **불필요** |
| 동일 시간 윈도우 크기 | 2L+1 | 2L+1 |
| Live trading 동작 | 불일치 가능 | **완전 일치** |
| Swing 분류 품질 | 과대평가 가능 | **실시간과 동일** |

### 핵심 차이 시각화

```
Version A (delay-compensated):
  At time i, detect swing at bar i using bars [i-L .. i+L]
  Use swing at time i+L (delay)
  Problem: swing QUALITY benefits from future knowledge

Version B (pure-causal):
  At time i, check if bar (i-L) was swing using bars [i-2L .. i]
  All data is past/current. No delay needed.
  Swing quality = exactly what live trading would see
```

---

## 3. 검증 계획

### 3A. Functional Equivalence Test

Version A와 B의 차이를 정량화:

| 메트릭 | 측정 방법 |
|--------|----------|
| Signal divergence rate | A와 B에서 동일 구간 신호 비교, 불일치율 계산 |
| Swing point overlap | A와 B의 swing point 집합 교집합 비율 |
| Strategy D Sharpe (A) | 현 구현 기준 |
| Strategy D Sharpe (B) | pure-causal 기준 |
| Sharpe delta | A - B (양수 = A가 과대평가된 정도) |

### 3B. Phase 2 적용 규칙

| 규칙 | 내용 |
|------|------|
| 본판 판정 | **Version B (pure-causal) 기준으로만** |
| Version A | 비교 레퍼런스 전용 -- 판정에 사용 금지 |
| 보고서 | 두 버전 병렬 결과 제시, 단 결론은 B 기준 |

---

## 4. 구현 파일

| # | 파일 | 유형 | 내용 |
|---|------|------|------|
| 1 | `scripts/indicator_backtest.py` | EDIT | `calc_smc_pure_causal()` 추가, composite에서 Version B 사용 |
| 2 | `docs/operations/evidence/cr046_smc_pure_causal_design.md` | THIS FILE | 설계서 |

---

## 5. 금지 사항

| 금지 | 준수 |
|------|------|
| 현 SMC 구현으로 Phase 2 본판 진행 | 금지 -- pure-causal 기준 |
| Version A 결과로 최종 판정 | 금지 -- 비교 레퍼런스만 |
| min_trades 하향 | 유지 |
| Strategy D 파라미터 변경 | Phase 2에서는 동일 파라미터 |

---

## 6. 상태 전이 영향

| 전이 | 영향 |
|------|------|
| CR-046 Phase 1 -> Phase 2 | SMC remediation이 선행 조건으로 추가 |
| Phase 2 판정 기준 | pure-causal SMC 결과 기준 |

---

## 7. 미해결 리스크

| # | 리스크 | 심각도 | 대응 |
|---|--------|--------|------|
| 1 | Pure-causal SMC가 유의미하게 약해질 수 있음 | Medium | 이것이 실제 성능이므로 수용. Strategy D의 진짜 가치를 보여줌 |
| 2 | Strategy D 전체 Sharpe가 크게 하락할 수 있음 | Medium | 하락 자체가 중요한 정보. Selection bias 감사의 핵심 |
| 3 | Version A/B 비교에서 큰 차이가 없을 수 있음 | Low | 차이가 없으면 좋은 소식 -- SMC 분류 품질이 미래 데이터에 비의존적 |

---

## Signature

```
CR-046 SMC Pure-Causal Reimplementation Design
Status: PROPOSED
Purpose: SMC swing detection을 순수 인과형으로 재구현
Constraint: Phase 2 본판은 반드시 pure-causal 기준
Prepared by: B (Implementer)
Approval required: A (Decision Authority)
Date: 2026-04-01
```
