# 수치형 기준 잠금표

## 문서 상태: LOCKED (초안 수치 - shadow 검증 전)

## 출처: design_liquidity_narrative_unified_draft.md

---

## 1. CISD Integrity Score

CISD Integrity Score는 0-100점 체계로 정의한다. 각 구성 요소는 독립적으로 계산되며, 패널티 항목은 총점에서 차감한다.

| 구성 요소 | 가중치 | 설명 |
|-----------|--------|------|
| opposite_external_liquidity_sweep | 20 | 반대측 외부 유동성 실행 확인 |
| structure_shift_confirmation | 20 | 구조 전환/이탈 확인 (BOS/CHOCH) |
| pd_array_hold | 15 | PD Array hold/reject 판정 |
| htf_bias_alignment | 15 | HTF bias 일치 여부 |
| follow_through | 15 | 전환 후 추세 지속 확인 |
| reverse_return_penalty | -10 | 역방향 복귀 시 감점 |
| htf_unreached_penalty | -15 | HTF 미도달 시 감점 |

**기준점 계산식:** 양의 항목 합산 후 패널티 차감. 최대 가능 점수 = 85점 (패널티 없을 때).

### 판정 임계값

| 등급 | 점수 범위 | 의미 |
|------|----------|------|
| CONFIRMED | >= 70 | 구조 전환 확인됨, Structure Gate 통과 가능 |
| PROBATION | 40 - 69 | 조건부 관찰, 추가 확인 필요 |
| REJECTED | < 40 | 구조 전환 불인정, Structure Gate 차단 |

---

## 2. Fair Value Completion Gauge

FV 범위 내 가격이 채워진 비율(%)을 기준으로 상태를 판정한다.

| 상태 | 범위 | 설명 |
|------|------|------|
| TOUCH_ONLY | 0 - 10% fill | 경계 접촉만, 진입 금지 |
| SHALLOW_FILL | 10 - 33% fill | 진입 주의, premature 가능 |
| MID_FILL | 33 - 66% fill | 정상 진입 후보 |
| FULL_FILL | 66 - 100% fill | 강한 진입 후보 |
| HTF_EXTREME_REACHED | 100%+ | HTF 극단 도달, 반전 최우선 후보 |

**운영 규칙:**
- TOUCH_ONLY 상태에서는 Entry Gate가 열리지 않는다.
- SHALLOW_FILL 상태에서는 premature_flag가 자동으로 상향 적용된다.
- HTF_EXTREME_REACHED 상태는 반전 진입 우선 후보로 별도 기록한다.

---

## 3. Alignment Score

Alignment Score는 Entry Gate 통과 조건으로 사용된다. 각 항목은 독립 확인 후 합산한다.

| 구성 요소 | 점수 | 설명 |
|-----------|------|------|
| lower_tf_bos_choch | +25 | LTF BOS/CHOCH 확인 |
| rejection_wick | +15 | 거부 심지 확인 |
| displacement | +20 | 변위 확인 |
| retest_hold | +15 | 리테스트 지지 확인 |
| delta_volume_confirm | +10 | 델타/볼륨 확인 |
| micro_trend_sync | +10 | 마이크로 추세 동기화 |
| entry_tf_noise_penalty | -15 | 진입 TF 노이즈 감점 |

**기준점 계산식:** 양의 항목 합산 후 패널티 차감. 최대 가능 점수 = 95점 (패널티 없을 때).

### 판정 임계값

| 등급 | 점수 범위 | 의미 |
|------|----------|------|
| STRONG | >= 75 | 강한 진입 정렬, Entry Gate 통과 가능 |
| VALID | 50 - 74 | 유효 진입 정렬, Entry Gate 통과 가능 |
| WEAK | 25 - 49 | 약한 정렬, Entry Gate 차단 |
| REJECTED | < 25 | 정렬 불인정, Entry Gate 차단 |

---

## 4. TF 허용표

허용되지 않은 TF pair는 헌법 조항 10항에 의해 실행이 금지된다.

### 암호화폐

| HTF | LTF | 허용 | 비고 |
|-----|-----|------|------|
| 4H | 15M | O | 표준 |
| 1H | 5M | O | 단기 |
| 1D | 1H | O | 스윙 |
| 1D | 1M | X | 금지: TF 격차 과대 |
| W | 1M | X | 금지: TF 격차 과대 |

### 미국주식

| HTF | LTF | 허용 | 비고 |
|-----|-----|------|------|
| 1D | 30M | O | 표준 |
| 4H | 15M | O | 단기 |
| 1D | 5M | X | 금지: TF 격차 과대 |

### 한국주식

| HTF | LTF | 허용 | 비고 |
|-----|-----|------|------|
| 1D | 1H | O | 표준 |
| 4H | 15M | O | 단기 |
| 1D | 5M | X | 금지: TF 격차 과대 |

---

## 5. Level Freshness 감점표

Level Freshness 상태는 Entry Gate 통과 조건에 직접 영향을 준다.

| 상태 | 접촉 횟수 | score 감점 | 진입 가능 여부 |
|------|----------|-----------|--------------|
| fresh | 0회 | 0% 감점 | 가능 |
| retested | 1회 | -20% score 감점 | 조건부 가능 |
| retested | 2회 | -40% score 감점 | 조건부 가능 |
| exhausted | 3회+ | 실행 금지 | 불가 |

**운영 규칙:**
- exhausted 상태 레벨은 Entry Gate가 열리지 않는다 (헌법 조항 8항).
- 감점은 해당 레벨의 key_level_score에 비율로 적용한다.
- 카운트 기준: 가격이 레벨에 접촉 후 반응한 이력을 기준으로 한다.

---

## 6. Portfolio Heat 한계표

Portfolio Heat 상태는 신규 진입 허용 여부 및 규모를 결정한다.

| 상태 | 동시 포지션 한도 | 단일 포지션 한도 | 비고 |
|------|-----------------|-----------------|------|
| NORMAL | 3 | 2% equity | 기본 |
| ELEVATED | 2 | 1.5% equity | 경계 |
| HIGH | 1 | 1% equity | 축소 |
| EXCEEDED | 0 | 0 | 신규 금지 |

**운영 규칙:**
- EXCEEDED 상태에서는 신규 진입이 전면 금지된다 (헌법 조항 13항).
- 포지션 한도는 동시 보유 기준이며, 진입 시점에 평가한다.
- equity 기준: 당일 account equity 기준으로 계산한다.

---

## 7. Event Blackout 시간표 (초안)

Event Blackout 상태는 Structure Gate 및 Entry Gate 모두에 영향을 준다.

| 이벤트 | 상태 | 사전 시간 | 사후 시간 |
|--------|------|-----------|-----------|
| FOMC | HARD | 2H 전 | 1H 후 |
| CPI/NFP | HARD | 1H 전 | 30M 후 |
| Earnings | HARD | 30M 전 | 15M 후 |
| 중요 거시 | SOFT | 1H 전 | 15M 후 |
| 테마 과열 | REDUCED_SIZE | 즉시 | 판단 시 |

**상태별 집행 규칙:**

| 상태 | 신규 진입 | 기존 포지션 |
|------|----------|-----------|
| HARD | 금지 (헌법 조항 11항) | 유지 또는 청산 선택 |
| SOFT | 조건부 허용 (size 50% 이하) | 유지 |
| REDUCED_SIZE | 허용 (size 50% 이하) | 유지 |
| NORMAL | 정상 | 정상 |

---

> 본 수치는 shadow 검증 결과에 따라 Evolution Proposal을 통해서만 변경 가능하다.

---

## 참조 문서

- Document A (상위 구조 설계서): `design_market_structure_v5.md`
- Document B (하위 진입 설계서): `design_entry_precision_klevel.md`
- 인터페이스 명세: `design_gate_interface_spec.md`
- 거버넌스·Evolution·운영: `design_governance_operations.md`
- 헌법 조항 검수: `design_constitution_review.md`
