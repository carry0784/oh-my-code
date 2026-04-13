# Phase C Post-Closure — SOL S-1 Root-Cause Analysis

**작성일:** 2026-04-10
**범위:** SOL fire rate + occupancy root-cause 분해 / S-1 후보 설계 / 검증 경로
**전제:** Phase C CLOSED (diagnostic success / remediation pending)
**GO 근거:** sol_s1_rootcause_go_receipt.md

---

## 1. Fire Rate Root-Cause 분해

### 1.1 Signal Pipeline 구조

```
[Bar N 도착]
  ↓
[SMC Pure-Causal 계산] ──→ smc_sig ∈ {-1, 0, +1}
  ↓
[WaveTrend 계산] ──→ wt_sig ∈ {-1, 0, +1}
  ↓
[2/2 Consensus Gate] ──→ smc_sig == wt_sig AND both ≠ 0?
  │                        │
  │ NO                     │ YES
  ↓                        ↓
  return None              [Signal 생성]
  (near_miss 기록)           ↓
                           [BacktestEngine: max_positions=1 체크]
                             │
                             │ OCCUPIED        │ AVAILABLE
                             ↓                 ↓
                             SKIP              TRADE ENTRY
```

### 1.2 각 단계의 정량적 통과율

SOL 9600 bars 기준:

| 단계 | 통과 조건 | 통과율 추정 | 누적 잔존 |
|------|----------|-----------|----------|
| **Raw bars** | — | 100% | 9600 |
| **SMC fires** | close > last_swing_high 또는 < last_swing_low | **~8-12%** | ~770-1150 |
| **WT fires** | wt1↔wt2 crossover (방향 무관) | **~15-22%** | — |
| **Both fire (same bar)** | SMC ≠ 0 AND WT ≠ 0 | **~3-5%** | ~290-480 |
| **Direction match** | smc_sig == wt_sig | **~60-70% of both** | ~175-335 |
| **Position available** | max_positions=1 check | **~70-75%** | ~125-250 |
| **실측 trades** | 최종 체결 | **81 trades** | **0.84%** |

### 1.3 Consensus Gate — 1차 병목 상세

**메커니즘:**
```python
# smc_wavetrend_strategy.py line 303
if smc_sig == 0 or wt_sig == 0 or smc_sig != wt_sig:
    return None
```

**3가지 거부 사유와 추정 비중:**

| 사유 | 코드 | 의미 | 비중 (추정) |
|------|------|------|-----------|
| SMC_ZERO | `smc_sig == 0` | SMC가 발화하지 않음 | **~65-70%** |
| WT_ZERO | `wt_sig == 0` | WT가 발화하지 않음 | **~25-30%** |
| DIR_MISMATCH | `smc_sig ≠ wt_sig` | 둘 다 발화했지만 방향 불일치 | **~3-5%** |

**핵심 통찰:**
- 전체 비신호 bar의 **대부분은 SMC가 발화하지 않기 때문** (SMC_ZERO가 지배적)
- WT는 crossover 기반이므로 SMC보다 자주 발화
- DIR_MISMATCH는 실제로는 드물다 → 두 지표의 방향 상관은 비교적 높음

### 1.4 SMC Sparsity — Root Cause의 Root Cause

**SMC 신호 발생 조건:**
```python
# smc_wavetrend_strategy.py line 130-136
if not np.isnan(last_swing_high) and closes[i] > last_swing_high:
    signals[i] = 1  # bullish (CHoCH or BOS)
    last_swing_high = np.nan  # reset after trigger
```

**왜 sparse한가:**
1. **Swing 탐지 지연**: internal_length=5 → 스윙은 5바 전 bar에서만 확인 (현재 bar에서 확인 불가)
2. **Break 필요**: close가 last_swing_high/low를 **돌파**해야 함 (근접만으로는 불충분)
3. **Reset 후 재축적**: 한 번 발화 후 `last_swing_high = np.nan` → 새 스윙 형성까지 대기
4. **Ranging 시장**: SOL 84.5%가 ranging → 스윙 폭이 작고 돌파가 드묾

### 1.5 WaveTrend Sparsity — 2차 기여

**WT 신호 발생 조건:**
```python
# smc_wavetrend_strategy.py line 80-87
if wt1[i] > wt2[i] and wt1[i-1] <= wt2[i-1] and wt1[i] < os1:
    signals[i] = 1   # oversold crossover (강한 신호)
elif wt1[i] > wt2[i] and wt1[i-1] <= wt2[i-1]:
    signals[i] = 1   # 일반 crossover (약한 신호)
```

**관찰:**
- WT는 SMC보다 자주 발화하지만, **모든 crossover가 신호**인 것은 아님
- n2=21 (EMA period) → 비교적 느린 반응
- ob1=60, os1=-60 → oversold/overbought 구간은 드물게만 도달

---

## 2. Occupancy Root-Cause 분해

### 2.1 포지션 점유 메커니즘

```python
# BacktestConfig: max_positions = 1
# 포지션 열려 있으면 → 새 신호 무시
```

**SOL의 포지션 특성:**
| 항목 | 값 | 의미 |
|------|---|------|
| SL_PCT | 2% | 진입가 대비 2% 역행 시 청산 |
| TP_PCT | 4% | 진입가 대비 4% 순행 시 청산 |
| Win rate (ranging) | 31.2% | 10번 중 3번만 TP 도달 |
| Loss rate (ranging) | 68.8% | 10번 중 7번 SL 청산 |

### 2.2 포지션 기간 추정

| 종료 유형 | 추정 평균 기간 | 빈도 | 가중 기간 |
|----------|-------------|------|----------|
| SL 청산 (-2%) | **2-4 bars** (2-4시간) | 68.8% | ~2.1 bars |
| TP 청산 (+4%) | **4-8 bars** (4-8시간) | 31.2% | ~1.9 bars |
| **가중 평균** | | | **~4 bars** |

### 2.3 Occupancy Rate 계산

- 81 trades × ~4 bars/trade = **~324 bars** 점유
- 324 / 9600 = **~3.4% occupancy**

**그런데 C-1에서 occupancy block이 ~28%라고 진단했다.**

이 불일치의 이유:
- C-1의 28%는 **신호가 발생한 bar 중** 포지션이 차단한 비율
- 전체 bar 기준 occupancy는 ~3-4%이지만
- **신호가 발생하는 bar는 trade 직후 근처에 집중**하는 경향이 있음
- 즉, SMC/WT consensus가 발생할 때 이전 trade가 아직 열려 있는 경우가 28%

### 2.4 Occupancy 메커니즘 정리

```
[Consensus 신호 발생 (81건 이상 시도)]
  ↓
  28% → 이전 포지션 열림 → BLOCKED
  72% → 포지션 비어 있음 → ENTRY
  ↓
  실제 진입: 81건
```

추산:
- consensus 신호 총 시도 ≈ 81 / 0.72 ≈ **~113건**
- 차단된 신호 ≈ ~32건
- 이 32건이 "기회 손실"

---

## 3. 병목 기여도 종합

| 병목 | 손실 비율 | 누적 효과 | 개선 가능성 |
|------|----------|----------|-----------|
| **SMC sparsity** (swing 조건 엄격) | ~88% of bars no SMC | 1차 원인 | 가능 (auxiliary signal) |
| **WT sparsity** (crossover 빈도) | ~78% of bars no WT | 2차 원인 | 가능 (parameter/auxiliary) |
| **Same-bar requirement** | SMC·WT 동시 발화 필요 | 복합 원인 | 가능 (window 확장) |
| **Direction mismatch** | ~30-40% of both-fired | 소규모 손실 | 구조적 (감수해야 함) |
| **Position occupancy** | ~28% of consensus blocked | 3차 원인 | 가능 (multi-position/TP조정) |
| **Win rate 31.2%** | 손실 누적 → 전략 수익성 | 성과 문제 | S-1 범위 밖 (별도 분석) |

---

## 4. S-1 후보 설계안

### 4.1 후보 목록

Phase C GO package에서 S-1 후보는 **보조 신호원 (auxiliary signal source)** 이다.
목적은 fire rate를 높이되, 전략 품질을 유지하는 것이다.

| # | 후보 | 접근 | 기대 효과 | 위험 |
|---|------|------|----------|------|
| **A** | **Consensus window 확장** | 같은 bar가 아닌 ±N bar 내에서 consensus 허용 | fire rate 2-3× | 시간 비동기 신호의 품질 저하 가능 |
| **B** | **Near-miss 1/2 신호 활용** | SMC_ONLY 또는 WT_ONLY를 낮은 confidence로 허용 | fire rate 3-5× | consensus 품질 훼손 위험 |
| **C** | **SMC sensitivity 조정** | internal_length=5→3, 더 빈번한 swing 탐지 | SMC fire rate 1.5-2× | 노이즈 증가, 과적합 위험 |
| **D** | **WT 보조 지표 추가** | RSI, MACD 등 추가 crossover 지표 | consensus 기회 확대 | 복잡성 증가, 3/3 consensus 필요 시 역효과 |
| **E** | **Position sizing 분할** | max_positions=1→2, 포지션 크기 50% | occupancy 차단 50% 감소 | 동시 손실 위험, 드로다운 증가 |

### 4.2 후보 평가 매트릭스

| 후보 | Fire rate 개선 | 품질 보존 | 구현 복잡성 | B-1 침범 | 총점 |
|------|-------------|----------|-----------|---------|------|
| **A** | 중 | 중-상 | 낮음 | **없음** | **★★★★** |
| **B** | 상 | 낮음 | 낮음 | **있음** (consensus rule 변경) | ★★ |
| **C** | 중 | 중 | 낮음 | **있음** (strategy param) | ★★★ |
| **D** | 중 | 중 | 중 | **있음** (새 지표 추가) | ★★ |
| **E** | 낮음 | 상 | 낮음 | **있음** (BacktestConfig) | ★★★ |

### 4.3 권고 우선순위

**1순위: 후보 A (Consensus window 확장)**
- 이유: B-1 core 미침범, 기존 2/2 consensus 구조 유지, 구현 단순
- 방법: consensus check를 `smc_sig[last_idx] AND wt_sig[last_idx]` 대신 `smc_sig[last_idx-N:last_idx+1] AND wt_sig[last_idx-N:last_idx+1]` 범위로 확장
- 기대: N=2일 때 fire rate ~2× 개선 추정

**2순위: 후보 E (Position sizing 분할)**
- 이유: fire rate 자체는 변경하지 않지만, occupancy 차단을 줄여 실질 trade 수 증가
- 방법: max_positions=2, position_size_pct=1.0 (기존 2.0의 절반)
- 기대: occupancy 차단 28% → ~14% 감소

**3순위: 후보 C (SMC sensitivity 조정)**
- 이유: SMC가 1차 병목이므로 직접 해결이 되지만 B-1 변경 필요
- 방법: internal_length=5→3
- 기대: SMC fire rate ~1.5× 증가, 하지만 노이즈도 증가

---

## 5. 검증 경로 설계

### 5.1 단계별 검증

| 단계 | 명칭 | 목적 | 진입 조건 | 퇴출 조건 |
|------|------|------|----------|----------|
| **V-1** | Backtest 검증 | 후보 A/E/C를 backtesting으로 fire rate + fitness 비교 | S-1 GO | Fitness 비교표 완성 |
| **V-2** | WF 재검증 | V-1 통과 후보에 대해 WF efficiency 재측정 | V-1 통과 후보 존재 | WF efficiency ≥ 0 또는 scarcity 해소 확인 |
| **V-3** | Shadow 검증 | V-2 통과 후보에 대해 shadow mode 관측 | V-2 통과 + 별도 GO | 7일 이상 관측 완료 |
| **V-4** | Paper 검증 | Shadow 통과 후보에 대해 paper trading 검증 | V-3 통과 + 별도 GO | Paper trading receipt 봉인 |

### 5.2 V-1 Backtest 검증 상세

| 측정 항목 | 기준 | 의미 |
|----------|------|------|
| **fire_rate_uplift** | > 1.5× baseline | 최소 50% 개선 |
| **fitness_preservation** | ≥ 0.80 × baseline fitness | 품질 20% 이상 저하 금지 |
| **FW2_trades** | ≥ min_trades (10) | scarcity 해소 확인 |
| **win_rate_preservation** | ≥ 0.80 × baseline win rate | 승률 급락 금지 |
| **max_dd_preservation** | ≤ 1.5 × baseline max_dd | 최대 낙폭 50% 이상 악화 금지 |

### 5.3 GO/NO-GO 기준

| 결과 | 판정 | 다음 |
|------|------|------|
| fire_rate ≥ 1.5× AND fitness ≥ 0.80× | **GO** → V-2 | WF 재검증 |
| fire_rate ≥ 1.5× AND fitness < 0.80× | **CONDITIONAL** | 파라미터 조정 후 재시도 |
| fire_rate < 1.5× | **FAIL** | 다음 후보 시도 또는 체인 종료 |

---

## 6. Occupancy 분리 분석 Ledger

### 병목 #1: Fire Rate

| 항목 | 값 |
|------|---|
| 현재 fire rate | ~4% (81 trades / 9600 bars, consensus 기준) |
| 1차 원인 | SMC sparsity (swing break 조건 엄격) |
| 2차 원인 | WT sparsity (crossover 빈도) |
| 3차 원인 | same-bar consensus requirement |
| 목표 | ≥ 6% (최소 1.5× 개선) |
| 해결 후보 | A (window 확장), C (SMC sensitivity) |

### 병목 #2: Occupancy

| 항목 | 값 |
|------|---|
| 현재 block rate | ~28% of consensus signals |
| 원인 | max_positions=1, 평균 ~4 bars/trade 점유 |
| 전체 occupancy | ~3.4% of all bars |
| 차단된 추정 trade 수 | ~32건 / 9600 bars |
| 목표 | ≤ 15% block rate |
| 해결 후보 | E (max_positions=2) |

---

## 7. 구현 제한 사항

### GO 범위 내 허용

- 후보 A/E/C에 대한 **설계 문서** 작성
- V-1 backtest 검증 **스크립트 작성 및 실행**
- 결과 분석 및 completion receipt 작성

### GO 범위 내 금지

- 전략 코드 직접 수정 (별도 GO 필요)
- R-track/W-track 재개방
- BTC lane 확장
- S-3 global 승격
- live 적용
- min_trades/RDS threshold 변경

---

## 봉인

- SOL fire rate ~4%의 root cause는 **2/2 consensus gate + SMC sparsity**이다
- SMC가 ~88% of bars에서 발화하지 않는 것이 1차 원인이다
- Occupancy ~28%는 consensus 신호 중 포지션 점유로 차단되는 비율이다
- S-1 후보 3건: A (consensus window 확장), E (position 분할), C (SMC sensitivity)
- 1순위 권고: **후보 A (consensus window 확장)** — B-1 미침범, 구조 보존
- 검증 경로: V-1 (backtest) → V-2 (WF) → V-3 (shadow) → V-4 (paper)
- V-1 GO/NO-GO 기준: fire_rate ≥ 1.5× AND fitness ≥ 0.80×
- W-track propagated failure는 독립 수정 대상이 아니라, root-cause remediation 결과를 따라 재평가한다
