# Phase B B-3 — GO Package (Redefined)

**작성일:** 2026-04-10
**상태:** REVIEW_PENDING (사용자 GO 선언 대기)
**전제:** B-1 CLOSED_DONE, B-2 CLOSED_DONE (verdict=FAIL)

---

## 1. 범위 재정의

### 원래 B-3
> Smoke 테스트 + 준수 감사 (`scripts/phase_b_full_cycle_smoke.py`)

### 재정의 사유
B-2 실행에서 SOL/USDT:USDT 9,600 candles 전체 full-cycle이 이미 성공적으로 실행되었고,
DL-001~006 / BR-001~004 준수가 확인되었으며, 7-condition verdict가 정상 동작했다.
따라서 smoke + compliance audit는 **B-2 안에서 이미 충족**되었다.

### 새 B-3 목적
> **전략 성과 개선 실험 계층** — verdict 기준 완화가 아닌 전략 품질 개선만 허용

B-2 verdict=FAIL의 원인 3종을 해소하기 위한 **제한적 실험 단계**.

---

## 2. B-2 FAIL 원인 분해 (B-3 목표 3종)

| # | FAIL 원인 | 코드 | 실측값 | 기준 | 개선 방향 |
|---|-----------|------|--------|------|-----------|
| F-1 | Forward-2 거래 부족 | `FW2_FITNESS_LOW` | fitness=0.0 (trades=5) | >=0.25 | 신호 밀도 개선 |
| F-2 | WF efficiency 부족 | `WF_EFFICIENCY_LOW` | -0.4959 | >=0.5 | forward 지속성 개선 |
| F-3 | Regime Diversity 부족 | `RDS_LOW` | 0.274 | >=0.55 | regime 편중 완화 |

---

## 3. 실험 트랙 설계

B-3는 **단일 보정안이 아니라 3-track 실험 묶음**으로 구성한다.
각 트랙은 독립적으로 실행/평가 가능해야 하며, 무엇이 실제 개선을 만들었는지 분리할 수 있어야 한다.

### Track B-3A: Trade Scarcity 완화

**목표:** 짧은 세그먼트(FW2=960 bars)에서도 min_trades(10) 이상의 신호 생성

**원인 가설:**
- SMCWaveTrend 2/2 consensus 조건이 960 bars 기간에 너무 엄격
- 시장이 ranging 84% 상태일 때 SMC 신호 자체가 희소
- FW2 기간(40일)의 특정 시장 환경이 신호 억제

**실험 접근:**
- 진단: FW2 구간에서 SMC/WaveTrend 각각의 개별 신호 발생 빈도 분석
- 분석: consensus gap (한쪽만 활성) 빈도 확인
- 선택적: near_miss 패턴 분석 (if 학습 스키마 연결 가능)

**비허용:**
- consensus 기준을 1/2로 낮추는 것 (전략 핵심 훼손)
- min_trades 기준 하향 (fitness 판정 기준 완화)

---

### Track B-3B: Regime Diversity 개선

**목표:** RDS를 0.55 이상으로 끌어올리거나, 편중 원인을 구조적으로 이해

**원인 가설:**
- 400일 데이터의 84%가 실제로 ranging 레짐 (시장 자체 특성)
- RegimeDetector의 ranging/trending 경계가 과도하게 넓음
- SOL/USDT:USDT의 1H 타임프레임 특성

**실험 접근:**
- 진단: BTC/USDT:USDT 동일 분석으로 cross-asset RDS 비교
- 분석: RegimeDetector의 regime 분류 임계값과 실제 가격 변동성 관계
- 관찰: 레짐별 전략 성과 분포 (ranging에서의 성과 vs trending에서의 성과)

**비허용:**
- RegimeDetector 분류 기준 수정 (Phase A 봉인)
- RDS 임계값 0.55 하향

---

### Track B-3C: Forward Stability 개선

**목표:** WF efficiency ratio를 0.5 이상으로 개선하거나, degradation 구조 이해

**원인 가설:**
- Train(240일) 특성이 Forward 구간에서 유지되지 않음
- 시장 regime shift가 구간 경계에서 발생
- 전략 파라미터가 train-specific overfitting

**실험 접근:**
- 진단: train/fw1/fw2/holdout 각 구간의 regime 분포 비교
- 분석: WF 5-window 각각의 IS/OOS 성과 분해
- 관찰: regime transition points와 segment boundary의 관계

**비허용:**
- WF efficiency 임계값 0.5 하향
- WF window 수 감소 (n_windows=5 유지)
- Walk-forward 결과를 train 파라미터 재조정에 사용 (DL-002)

---

## 4. 변경 범위

### 4.1 신규 파일 (허용)

| 파일 | 유형 | 내용 |
|------|------|------|
| `scripts/phase_b_full_cycle_smoke.py` | NEW | Full-cycle smoke + 진단 스크립트 (원래 B-3 + 실험 진단 통합) |

### 4.2 변경 파일

**없음.** B-3는 진단/분석 스크립트만 추가한다.

### 4.3 금지 파일 (수정 절대 금지)

| 파일 | 이유 |
|------|------|
| `app/services/full_cycle_backtester.py` | B-1/B-2 core 봉인 |
| `app/services/backtesting_engine.py` | Phase A 봉인 |
| `app/services/fitness_function.py` | 가중치/공식 불변 |
| `app/services/walk_forward_validator.py` | WF 검증 불변 |
| `app/services/regime_detector.py` | 레짐 감지 불변 |
| `app/services/history_data_manager.py` | Phase A 봉인 |
| `strategies/smc_wavetrend_strategy.py` | 전략 불변 (B-3는 관찰/진단만) |
| `app/models/ohlcv_history.py` | 스키마 봉인 |
| verdict thresholds (B-2 constants) | 기준 완화 금지 |

---

## 5. 핵심 원칙

### 5.1 B-3의 성격

```
B-3 = 진단 + 관찰 + 원인 분해 계층
B-3 ≠ 전략 수정 + threshold 완화 + 억지 PASS 계층
```

### 5.2 FAIL 유지가 합법적 종료조건

B-3 실험 후에도 근본 원인이 시장 구조(ranging 편중)이거나
전략의 구조적 한계라면, **FAIL 유지가 정당한 종료**이다.

억지로 PASS를 만드는 것은 금지한다.

### 5.3 평가 지표

| 지표 | B-2 실측 | B-3 목표 | 기준 |
|------|----------|----------|------|
| FW2 trades | 5 | >= 10 | min_trades 충족 |
| FW2 fitness | 0.0000 | >= 0.25 | 판정 기준 유지 |
| WF efficiency | -0.4959 | >= 0.5 | 판정 기준 유지 |
| RDS | 0.274 | >= 0.55 | 판정 기준 유지 |
| Overall fitness | 0.2865 | improvement | 방향성 확인 |

### 5.4 B-3 종료 조건 (3가지 중 하나)

| 종료 유형 | 조건 | 결과 |
|-----------|------|------|
| **IMPROVED** | 3 FAIL 원인 중 1개 이상 해소, 나머지 악화 없음 | B-3 PASS (제한적 성공) |
| **RESOLVED** | 3 FAIL 원인 전체 해소, verdict=PASS 달성 | B-3 FULL PASS |
| **MAINTAINED_FAIL** | 개선 불가 확인, 구조적 한계 문서화 | B-3 CLOSED (합법적 FAIL 유지) |

---

## 6. 실패/중단 조건

| 코드 | 조건 | 조치 |
|------|------|------|
| `ABORT_CORE_MODIFIED` | B-1/B-2 core 변경 감지 | 즉시 중단 |
| `ABORT_THRESHOLD_LOWERED` | verdict 임계값 하향 시도 | 즉시 중단 |
| `ABORT_STRATEGY_MODIFIED` | smc_wavetrend_strategy.py 수정 | 즉시 중단 |
| `ABORT_REGRESSION` | B-1 회귀 기준선 위반 | 즉시 중단 |

---

## 7. Receipt 체계

| Receipt | 시점 | 내용 |
|---------|------|------|
| `phase_b_b3_go_receipt.md` | GO 선언 시 | B-3 착수 승인 증거 |
| `phase_b_b3_diagnosis_report.md` | 진단 완료 시 | 3-track 진단 결과 |
| `phase_b_b3_completion_receipt.md` | 종료 시 | IMPROVED/RESOLVED/MAINTAINED_FAIL 판정 |

---

## 8. BTC 병행 실행

B-3 진단은 SOL 단독이 아니라 **BTC/USDT:USDT 병행 실행**으로 cross-asset 비교를 포함한다.
이를 통해 FAIL 원인이 전략 구조적 문제인지 특정 자산 특성인지 분리할 수 있다.

---

## 9. 봉인

- 본 패키지는 B-3 범위 정의이며, 사용자 GO 없이 착수 금지
- B-3의 목적은 전략 진단/관찰이며, 기존 코드 수정이 아님
- FAIL 유지가 합법적 종료조건임을 명시
- B-1/B-2 core 및 verdict thresholds 수정은 어떤 경우에도 금지
