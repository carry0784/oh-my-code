# CR-047: 1H 시간봉 기반 CG-2B 재검증 패키지

Date: 2026-04-01
Status: **PROPOSED**
Prerequisite: CG-2A PASS sealed, CR-045 reShadow v2 7-Day complete
Scope: CG-2B (전략 생산/거버넌스 흐름) 재검증을 1H 시간봉으로 전환
Relation: CR-045 후속, CR-046과 독립

---

## 1. Background

### CR-045 reShadow v2 결론

CG-2A는 7일 무결 운영으로 PASS 확정.
CG-2B는 NOT PROVEN -- 구조 정상이나 **5m 시간봉 + Inactive Market Regime**에서 min_trades=10 미달.

### 근본 원인 분석

```
5m bars x 500 = ~41.7시간 관측 구간
  -> SMA crossover: 0~3 trades (min_trades=10 미달)
  -> RSI crossover: 0~2 trades (min_trades=10 미달)
  -> 시장 변동성이 5m 단위에서 전략 신호를 생성하기에 불충분
```

### 해결 방향

| 방향 | 판정 | 사유 |
|------|------|------|
| 시장 활성 구간 대기 | **REJECT** | "좋은 날 기다리기" = 검증 공정성 훼손 |
| min_trades 하향 | **REJECT** | 기준 완화 = 안전성/정직성 원칙 위반 |
| **1H 시간봉 전환** | **ADOPT** | 기준 유지, 관측 단위만 변경 |

---

## 2. 시간봉 전환 설계

### 안 A: 1H Signal / 1H Evaluation (순수 전환)

```
OHLCV: 1H bars, 500개 = ~20.8일 관측 구간
Signal: SMA/RSI crossover on 1H
Evaluation: 1H bar-close 기준 backtest
Min_trades: 10 유지
```

**장점**: 단순, CR-046 Strategy D 연구와 시간축 일치
**단점**: 5m 미세 관측성 상실

### 안 B: 1H Signal / 5m Execution Observation (하이브리드)

```
Signal generation: 1H bars 기준 SMA/RSI crossover
Execution observation: 5m bars로 진입/청산 관측
Evaluation: 1H signal 기준 fitness, 5m observation은 보조 메트릭
Min_trades: 10 유지 (1H 신호 기준)
```

**장점**: 후보 생성성(1H)과 운영 미세 관측성(5m) 동시 확보
**단점**: 복잡도 증가, 두 시간축 정합성 관리 필요

### A 지시: 두 안 모두 비교 평가 후 최종 선택

---

## 3. 변경 사항

### 3A. shadow_run_cycle.py 변경

| 항목 | 현재 (CR-045) | CR-047 |
|------|--------------|--------|
| OHLCV timeframe | 5m | **1h** (안 A) 또는 **1h + 5m** (안 B) |
| OHLCV limit | 500 | 500 (1H = ~20.8일) |
| lookback | 30 | 30 (유지) |
| strategy_types | [SMA, RSI] | [SMA, RSI] (유지) |
| min_trades | 10 | **10 유지** |
| islands | 5 | 5 (유지) |
| pop | 10 | 10 (유지) |
| gen | 10 | 10 (유지) |

### 3B. 추가 필드 (A 지시: CG-2B 세분화)

```json
{
  "cg2b_1_candidate_generation": "proven / not_proven",
  "cg2b_2_governance_exercisability": "proven / not_proven",
  "cg2b_opening_signal": "yes / no"
}
```

**CG-2B 세분화 (A 추가 지시)**:

| 하위 게이트 | 정의 | 판정 기준 |
|------------|------|----------|
| CG-2B-1 | Candidate generation proven | registry_size >= 1 (fitness > 0인 후보 1개 이상 생성) |
| CG-2B-2 | Governance exercisability proven | governance_decisions >= 1 (거버넌스 게이트가 1회 이상 판정) |

---

## 4. 안 A vs 안 B 비교표

| 기준 | 안 A (1H/1H) | 안 B (1H signal/5m obs) |
|------|-------------|----------------------|
| 구현 복잡도 | 낮음 | 중간 |
| 후보 생성 가능성 | 높음 (1H 변동성 충분) | 높음 |
| 운영 미세 관측성 | 없음 (1H 단위만) | 있음 (5m 보조) |
| CR-046 Strategy D 정합성 | **완전 일치** (동일 1H 축) | 부분 일치 |
| min_trades 충족 가능성 | 높음 (20일 관측) | 높음 |
| 두 시간축 정합성 관리 | 불필요 | 필요 |
| 권장 | **1차 시행** | 2차 확장 |

**B 권고**: 안 A를 1차로 시행하고, 결과에 따라 안 B 확장 검토.

---

## 5. 금지 사항

| 금지 | 준수 방법 |
|------|----------|
| min_trades 하향 | min_trades=10 유지 |
| 시장 활성 구간 대기를 shadow 시작 gate로 사용 | 금지 -- 1H 전환으로 구조적 해결 |
| dry_run=True 해제 | HARDCODED 유지 |
| PENDING_OPERATOR 우회 | 유지 |
| live write path | 금지 |
| CR-045 baseline 변경 | CR-047은 독립 CR |
| CR-046과 혼합 | 두 트랙 분리 유지 |

---

## 6. 상태 전이 영향

| 전이 | 영향 |
|------|------|
| CG-2A | SEALED -- 영향 없음 |
| CG-2B -> CG-2B-1 + CG-2B-2 | 세분화 -- 기존 CG-2B 판정 체계를 대체 |
| CR-045 -> CR-047 | 후속 관계 -- CR-045 reShadow 결과를 기반으로 시간축 전환 |

---

## 7. 로그 / Audit 영향

| 항목 | 영향 |
|------|------|
| day_NN.json | timeframe 필드 추가: "1h" |
| config_fingerprint | timeframe 추가 |
| strategy_breakdown | 유지 |
| 신규 필드 | cg2b_1_candidate_generation, cg2b_2_governance_exercisability |

---

## 8. 미해결 리스크

| # | 리스크 | 심각도 | 대응 |
|---|--------|--------|------|
| 1 | 1H에서도 min_trades=10 미달 가능 | Medium | 500바 = 20일이면 SMA/RSI 충분한 교차 기대 |
| 2 | 1H와 5m 결과 비교 불가 | Low | 다른 관측 설계이므로 비교 자체가 부적절 |
| 3 | CR-047이 CR-046과 시간축 공유로 혼동 | Medium | CR-047 = 운영 검증, CR-046 = 전략 검증, 목적 분리 |
| 4 | 안 B 구현 시 두 시간축 정합성 | Low | 안 A 우선 시행으로 지연 |

---

## 9. 수락 기준

| # | 기준 | 임계값 |
|---|------|--------|
| AC-1 | 1H OHLCV 수집 정상 | 500바 수집 확인 |
| AC-2 | CG-2B-1: candidate generation | registry_size >= 1 in 7 days |
| AC-3 | CG-2B-2: governance exercisability | governance_decisions >= 1 in 7 days |
| AC-4 | CG-2A 불변 | 0 crashes, 0 STOP, reconciliation PASS |
| AC-5 | min_trades | 10 유지 (하향 금지) |
| AC-6 | dry_run | True 유지 |

---

## 10. 구현 파일 목록

| # | 파일 | 유형 | 내용 |
|---|------|------|------|
| 1 | `scripts/shadow_run_cycle.py` | EDIT | timeframe 5m -> 1h, CG-2B-1/2 필드 추가 |
| 2 | `docs/operations/evidence/cr047_1h_cg2b_reverification_package.md` | THIS FILE | 패키지 문서 |

---

## Signature

```
CR-047: 1H 시간봉 기반 CG-2B 재검증 패키지
Status: PROPOSED
Purpose: CG-2B 재검증을 1H 시간봉으로 전환
Safety: min_trades=10 유지, dry_run=True, PENDING_OPERATOR 유지
Prepared by: B (Implementer)
Approval required: A (Decision Authority)
Date: 2026-04-01
```
