# SOL S-1 V-3 — Shadow Drift Verification Design

**작성일:** 2026-04-10
**범위:** C1C2_N2 shadow 환경 drift 감시 검증
**전제:** V-2 PASS (C1C2_N2, 6/6 Primary + 2/2 Secondary 충족)
**목적:** V-2 backtest 결과가 실시간 환경에서도 안정적으로 유지되는지 확인

---

## 1. V-3 목적

V-2에서 C1C2_N2 (N=2, max_positions=2, size=1%)가 PASS를 달성했다. 그러나 이는 9600-bar 과거 데이터 기반 결과이며, ECR 마진 4.3pp / block rate 마진 4.3pp로 tight하다. V-3는 **실시간 shadow 환경에서 drift 없이 기준을 유지하는지** 검증한다.

**V-3는 수익성 검증이 아니다. drift 감시이다.**

---

## 2. Config 잠금

### 2.1 Primary Config

```
label:            C1C2_N2
consensus_window: N=2
max_positions:    2
position_size_pct: 1.0%
SL: 2% / TP: 4%
총 시장 노출:     2% max (1% × 2 slots)
```

### 2.2 Fallback Candidate

```
label:            C1C2_N1
consensus_window: N=1
max_positions:    2
position_size_pct: 1.0%
SL: 2% / TP: 4%
```

### 2.3 Fallback 사용 규칙

1. V-3의 공식 실행 config는 **N2만**
2. N1은 **fallback candidate**로만 기록 — shadow 실행 대상 아님
3. N2가 Red 판정 시 **즉시 N1 자동 전환 금지**
4. N2 실패 receipt 작성 → 별도 explicit GO로 N1 shadow 재검증 분기
5. Fallback 전환은 **거버넌스 통제 대상** — 자동 진화 아님

---

## 3. Shadow 기간 잠금 (보강 1)

### 3.1 기간 정의

| 기준 | 값 | 근거 |
|------|---|------|
| **최소 bar 수** | 96 bars | 1H cadence × 4일 (주말 포함) |
| **invalid run** | 0건 | 1건이라도 발생 시 기간 무효 |
| **min_trades** | ≥ 10 | V-2 segment 기준 계승 |

### 3.2 기간 충족 조건

아래 3개를 **모두** 충족해야 shadow 기간 완료로 인정:

1. 관측 bar ≥ 96
2. invalid_run_count = 0
3. shadow_trades ≥ 10

**기간 미충족 시**: PASS/FAIL 판정 불가, 기간 연장 또는 invalid 처리

### 3.3 기간 연장 규칙

- Yellow 상태 진입 시: 기간을 **+48 bar 연장** (관찰 연장, 즉시 실패 아님)
- Yellow 연장은 최대 1회 — 연장 후에도 Yellow 유지 시 Red 전환
- Green 복귀 시: 남은 기간 정상 소진

---

## 4. 상태 전이 수치 잠금 (보강 2)

### 4.1 V-2 Baseline 참조값

| 지표 | V-2 C1C2_N2 값 | 용도 |
|------|----------------|------|
| ECR | 64.3% | drift 기준선 |
| block_rate | 35.7% | drift 기준선 |
| same_direction_ratio | 70.9% (of all blocks) | 급증 기준선 |
| fitness | 0.4428 | 품질 기준선 |
| fire_rate | 3.55% | 참조 |
| trades/9600bars | 341 | 참조 |

### 4.2 State Transition Table

```
┌─────────┐     ECR < 60%           ┌────────┐
│  GREEN  │────or block > 40%──────→│ YELLOW │
│         │    or SD급증             │        │
└────┬────┘                         └───┬────┘
     │                                  │
     │   ECR ≥ 60%                      │  ECR < 55%
     │   block ≤ 40%                    │  or block > 45%
     │   SD정상                          │  or invalid ≥ 1
     │                                  │  or Yellow연장후 미복귀
     │         ┌────────────────────────┘
     │         ↓
     │    ┌─────────┐
     └────│   RED   │──→ 즉시 중단
          └─────────┘
```

### 4.3 Green 조건 (정상 운영)

모든 조건 동시 충족:

| 지표 | 조건 |
|------|------|
| ECR | ≥ 60% |
| block_rate | ≤ 40% |
| same_direction_ratio | ≤ 80.9% (baseline 70.9% + 10pp) |
| invalid_run | = 0 |

### 4.4 Yellow 조건 (경고 / 관찰 연장)

아래 중 **하나라도** 충족:

| 지표 | 조건 | 비고 |
|------|------|------|
| ECR | 55% ≤ ECR < 60% | 마진 진입 |
| block_rate | 40% < block_rate ≤ 45% | 마진 진입 |
| same_direction_ratio | 80.9% < SD_ratio ≤ 85.9% | baseline +10~15pp |
| ECR 변화율 | 12-bar rolling ECR 하락 ≥ 10pp vs 직전 12-bar | 급락 감지 |

**Yellow 처리:**
- 즉시 실패 아님 — 관찰 연장 (+48 bar)
- Yellow 경고 receipt 작성
- 연장 후 Green 복귀 → 정상 진행
- 연장 후 Yellow 유지 또는 악화 → Red 전환

### 4.5 Red 조건 (즉시 중단)

아래 중 **하나라도** 충족:

| 지표 | 조건 | 비고 |
|------|------|------|
| ECR | < 55% | 기준선 이탈 |
| block_rate | > 45% | 상한 초과 |
| same_direction_ratio | > 85.9% | baseline +15pp 초과 |
| invalid_run | ≥ 1 | 로그 누락/계산 불능 |
| Yellow 연장 후 미복귀 | 연장 기간 내 Green 미도달 | 만성 이탈 |

**Red 처리:**
- 즉시 shadow 중단
- Red receipt 작성 (판정 근거 벡터 포함)
- V-3 = FAIL
- N1 fallback 검토는 별도 explicit GO 필요

---

## 5. Same-Direction 급증 기준 잠금 (보강 3)

### 5.1 기준선

```
V-2 C1C2_N2 same-direction block:
  count: 134 / 189 total blocks = 70.9%
  
baseline_sd_ratio = 70.9%
```

### 5.2 급증 판정 공식

```
sd_ratio_shadow = same_direction_blocks / total_blocks × 100

delta_pp = sd_ratio_shadow - baseline_sd_ratio (70.9%)
```

| delta_pp | 판정 |
|----------|------|
| ≤ +10pp (≤ 80.9%) | Green |
| +10pp < delta ≤ +15pp (80.9% < ratio ≤ 85.9%) | Yellow |
| > +15pp (> 85.9%) | Red |

### 5.3 Rolling Window 보조 판정

- 12-bar rolling window에서 same_direction_ratio 계산
- 연속 3개 rolling window 모두 Yellow 범위 → Yellow 확정
- 단일 window가 Red 범위 → 즉시 Red

---

## 6. Shadow 관측 필드

### 6.1 Bar 단위 기록 (shadow_receipt)

```json
{
  "bar_ts": "ISO8601",
  "bar_index": int,
  "consensus_dir": int,
  "consensus_generated": bool,
  "consensus_executable": bool,
  "block_code": str | null,
  "open_positions": int,
  "slots_used": int,
  "slots_available": int,
  "config_fingerprint": "C1C2_N2_v3"
}
```

### 6.2 집계 기록 (shadow_summary)

```json
{
  "shadow_id": str,
  "config_fingerprint": "C1C2_N2_v3",
  "total_bars": int,
  "total_consensus": int,
  "total_executable": int,
  "total_blocked": int,
  "ecr_pct": float,
  "block_rate_pct": float,
  "block_max_positions": int,
  "block_same_direction": int,
  "block_opposite_direction": int,
  "same_direction_ratio": float,
  "same_direction_delta_pp": float,
  "shadow_trades": int,
  "shadow_fitness": float,
  "invalid_run_count": int,
  "current_state": "GREEN" | "YELLOW" | "RED",
  "yellow_count": int,
  "yellow_extensions": int,
  "final_state": "GREEN" | "YELLOW" | "RED"
}
```

### 6.3 판정 근거 벡터 (verdict_basis)

completion receipt에 반드시 포함:

```json
{
  "ecr_value": float,
  "block_rate_value": float,
  "same_direction_delta_pp": float,
  "invalid_run_count": int,
  "segment_trade_count": int,
  "total_bars_observed": int,
  "yellow_events": int,
  "yellow_extensions_used": int,
  "final_state": str,
  "fitness_ratio": float
}
```

---

## 7. Invalid Run 정의

### 7.1 Invalid 판정 조건

아래 중 **하나라도** 해당 시 해당 bar/기간은 invalid:

| 조건 | 코드 |
|------|------|
| bar 데이터 누락 (OHLCV 불완전) | `INVALID_DATA_MISSING` |
| SMC/WT 지표 계산 실패 | `INVALID_INDICATOR_FAIL` |
| consensus 판정 불능 | `INVALID_CONSENSUS_FAIL` |
| block_code 기록 누락 | `INVALID_LOG_MISSING` |
| timestamp 역전/중복 | `INVALID_TIMESTAMP` |

### 7.2 Invalid 처리

- invalid bar 1건 → **전체 shadow run = invalid**
- invalid run은 PASS/FAIL 판정 불가 → 재실행 필요
- invalid 원인을 receipt에 기록

---

## 8. PASS/FAIL 판정 구조

### 8.1 V-3 PASS 조건 (모두 충족)

| # | 조건 | 기준 |
|---|------|------|
| 1 | 기간 충족 | ≥ 96 bars, invalid=0, trades≥10 |
| 2 | 최종 상태 | Green |
| 3 | ECR | ≥ 60% (전체 기간) |
| 4 | block_rate | ≤ 40% (전체 기간) |
| 5 | same_direction_delta | ≤ +10pp |
| 6 | fitness_ratio | ≥ 0.80 (vs V-2 baseline 0.4428) |
| 7 | Yellow 연장 | ≤ 1회, 복귀 완료 |

### 8.2 INFORMATIVE_FAIL

- 기간 충족 + ECR/block 기준 달성, but Yellow 다회 발생
- 또는 same_direction 편중 증가 (Yellow 범위)
- 해석 가치 있으나 안정성 미확인

### 8.3 FAIL

- Red 진입 (즉시)
- 기간 미충족 + 재실행 불가
- invalid run

---

## 9. V-4 해제 조건 (V-3 PASS와 분리)

V-3 PASS ≠ V-4 자동 해제. V-4 해제에는 추가 요건:

| # | V-3 PASS 조건 | V-4 Unlock 추가 요건 |
|---|--------------|---------------------|
| 1 | Green 최종 상태 | Green 최종 상태 |
| 2 | ECR ≥ 60% | ECR ≥ 60% |
| 3 | block ≤ 40% | block ≤ 40% |
| 4 | invalid = 0 | invalid = 0 |
| 5 | — | **receipt completeness 100%** (모든 필드 존재) |
| 6 | — | **Yellow 연장 0회** (1회도 없어야) |
| 7 | — | **explicit GO** (auto_advance 금지) |

---

## 10. 금지 규칙

### 10.1 전략 변경 금지

| 금지 항목 | 근거 |
|----------|------|
| N=3 확장 | V-2에서 FAIL 확인 |
| same-direction 허용 변경 | 별도 검증 체인 필요 |
| SL/TP 최적화 | 수익성 트랙 분리 |
| 수익성 판정 | V-3는 drift 감시 전용 |

### 10.2 운영 변경 금지

| 금지 항목 | 근거 |
|----------|------|
| Fallback 자동 전환 | 거버넌스 통제 대상 |
| 기준선 동적 변경 | shadow 중간에 ECR/block baseline 재계산 금지 |
| 판정 기준 완화 | PASS를 위한 기준 느슨화 금지 |
| shadow 중 config 교체 | fingerprint 고정 |

---

## 11. Shadow 실행 방식

### 11.1 데이터 소스

- 실시간 bar 수신 (SOL/USDT:USDT, 1H)
- 기존 paper trading 인프라 활용
- shadow 전용 플래그로 실제 주문 미전송

### 11.2 Bar Cadence

- 1H bar 완성 시마다 shadow receipt 1건 생성
- consensus 판정 → block 판정 → position 시뮬레이션 → 기록
- 집계는 전체 기간 완료 후 1회

### 11.3 산출물

1. `sol_s1_v3_design.md` — 본 문서
2. Shadow 실행 스크립트/모듈
3. `sol_s1_v3_shadow_log.json` — bar 단위 + 집계 데이터
4. `sol_s1_v3_completion_receipt.md` — 판정 근거 벡터 포함

---

## 봉인

- V-3는 C1C2_N2 config의 shadow drift 감시 검증이다
- 수익성 검증이 아니라 ECR/block/same-direction 안정성 검증이다
- Shadow 기간: 최소 96 bars, invalid=0, trades≥10
- Green/Yellow/Red 상태 전이를 수치 기반으로 판정한다
- Same-direction 급증 기준: baseline 70.9% + 10pp = Yellow, +15pp = Red
- Yellow는 관찰 연장(+48 bar, 최대 1회), Red는 즉시 중단
- Fallback N1은 candidate 기록만, 자동 전환 금지
- 기준선 동적 변경 금지, 판정 기준 완화 금지
- V-3 PASS와 V-4 Unlock 조건은 분리된다
- auto_advance는 금지이다
