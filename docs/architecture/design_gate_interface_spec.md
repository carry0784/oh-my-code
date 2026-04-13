# Structure Gate → Entry Gate 인터페이스 명세

## 문서 상태: LOCKED

## 출처: design_liquidity_narrative_unified_draft.md

---

## 1. 문서 목적

본 문서는 Structure Gate → Entry Gate 인터페이스를 잠근다.

상위 Market Structure Module이 생성한 승인 상태를 하위 Entry Precision Module로 전달하는 계약 필드, 권한 한계, 충돌 처리 규칙, 단계별 허용 범위를 단일 명세로 고정한다.

본 명세가 정의하는 인터페이스 경계를 우회하는 모든 실행은 헌법 위반으로 처리된다.

---

## 2. 인터페이스 모듈 역할

출처: 섹션 3.3

인터페이스 모듈의 역할은 다음 네 가지로 한정된다.

1. 상위 승인 상태를 하위 모듈로 전달한다.
2. 하위 모듈의 독자 판단을 차단한다.
3. 구조 충돌 시 fail-closed를 집행한다.
4. shadow / paper / live 단계별 권한을 제한한다.

---

## 3. Structure Gate 출력 필드

출처: 섹션 7.1 (Structure Gate 출력), 섹션 12.1 (인터페이스 전달 필드)

| 필드명 | 타입 | 생산자 | 소비자 | 설명 |
|---|---|---|---|---|
| `structure_gate_pass` | bool | Structure Module | Entry Module | Structure Gate 승인 여부. false이면 Entry Gate는 열리지 않는다. |
| `approved_fair_value_zone_id` | string | Structure Module | Entry Module | 승인된 공정가치 구간 식별자. Entry는 이 구간 내부에서만 작동한다. |
| `structure_direction` | enum: LONG / SHORT / NEUTRAL | Structure Module | Entry Module | 상위 구조가 결정한 방향. Entry Gate가 단독으로 변경할 수 없다. |
| `structure_state` | string | Structure Module | Entry Module | 현재 구조 상태 기술자. HTF/LTF 우선순위 판정 결과를 포함한다. |
| `premature_flag` | enum: NONE / MILD / SEVERE | Structure Module | Entry Module | 조기 신호 여부. SEVERE이면 Structure Gate 자체가 차단된다. |
| `entry_module_allowed_flag` | bool | Structure Module | Entry Module | Entry Module 활성화 허용 여부. false이면 Entry Gate 실행 금지. |
| `event_blackout_state` | enum: HARD / SOFT / REDUCED_SIZE / NORMAL | Governance | Both | 이벤트 블랙아웃 단계. HARD이면 Entry 승인이 무효가 된다. |
| `portfolio_heat_state` | enum: NORMAL / ELEVATED / HIGH / EXCEEDED | Governance | Both | 포트폴리오 열 상태. Governance 모듈이 원시 heat %를 이산 상태로 변환하여 전달. EXCEEDED 시 신규 진입 금지. |
| `asset_class` | enum: CRYPTO / US_STOCK / KR_STOCK | System | Both | 자산군 분류. 허용 TF 쌍 및 관측 확장 규칙 선택에 사용된다. |
| `allowed_tf_pair` | string | Structure Module | Entry Module | 허용된 상위TF→하위TF 쌍 (예: "4H->15M"). 이 쌍 외의 실행은 금지된다. |
| `governance_lock_flag` | bool | Governance | Both | 거버넌스 잠금 여부. true이면 Structure Gate와 Entry Gate 모두 차단된다. |

### Entry Module 자체 관측 필드 (인터페이스 비전달)

아래 필드는 Structure Gate에서 전달하지 않으며, Entry Module이 자체적으로 관측·판정한다.

| 필드명 | 타입 | 설명 |
|--------|------|------|
| spread_state | enum: NORMAL / WIDE / ABNORMAL | 실시간 스프레드 상태. ABNORMAL 시 Entry Gate 차단 |
| alignment_score | enum: STRONG / VALID / WEAK / REJECTED | LTF alignment 자체 판정 |
| key_level_type | string | 감지된 key level family 유형 |
| level_freshness_state | enum: FRESH / RETESTED / EXHAUSTED | 레벨 선도 상태 |

---

## 4. Entry Gate 권한 한계

출처: 섹션 12.2

Entry Gate는 아래 항목을 단독으로 결정할 수 없다.

- `structure_direction` 변경
- `approved_fair_value_zone_id` 범위 외부로의 확장
- `premature_flag` 재정의 또는 override
- `governance_lock_flag` 해제
- `event_blackout_state` HARD 상태 해제
- `portfolio_heat_state` 한도 override

Entry Gate의 역할은 Structure Gate가 승인한 구간 내부에서 진입 조건을 정밀화하는 것으로 한정된다.

---

## 5. 충돌 처리 규칙

출처: 섹션 12.3

| 충돌 유형 | 처리 결과 |
|---|---|
| Structure와 Entry 판단 충돌 | fail-closed (신규 실행 금지) |
| `approved_fair_value_zone_id` 외부 key level 사용 시도 | 실행 금지 |
| `event_blackout_state` = HARD 발생 | Entry 승인 즉시 무효 |
| narrative conflict SEVERE 발생 | Entry 승인 즉시 무효 |

---

## 6. fail-closed 조건

출처: 섹션 2.3

아래 조건 중 하나라도 발생하면 신규 실행은 즉시 금지된다.

- unknown state
- HTF/LTF 충돌
- `event_blackout_state` = HARD
- `governance_lock_flag` = true
- `portfolio_heat_state` 한도 초과
- approval reason 누락

fail-closed는 예외 없이 적용된다. 어떤 모듈도 이 조건을 해제할 수 없다.

---

## 7. shadow / paper / live 단계별 권한

출처: 섹션 8.3, 섹션 15

| 단계 | 주문 권한 | 허용 활동 | 목표 |
|---|---|---|---|
| shadow | 주문 없음 | 구조 탐지, 승인/차단 로직 기록, simulated entry 기록 | Structure Gate precision, Entry Gate precision, skip precision, rule violation count = 0 |
| paper | 가상 주문만 | 가상 주문 실행, partial / BE / trail 검증, counter-trend quarantine 분리 검증 | structure vs entry 분리 성능 확인, event blackout 효과 검증, portfolio heat 차단 효과 검증 |
| micro live | 최소 규모 실행 | shadow / paper 검증 통과 후, interface locked, governance stable, logs complete 전제 하에 허용 | 실계좌 소규모 검증 |
| scaled live | 승격 후만 허용 | CISD Integrity Score, Fair Value Completion Gauge, key level 허용 family, TF 허용표, heat / conflict / blackout 규칙 전부 잠금 완료 후 허용 | 정식 운영 규모 집행 |

shadow 또는 paper 검증 완료 전 live 확대는 거버넌스 헌법 위반이다.

---

## 참조 문서

- Document A (상위 구조 설계서): `design_market_structure_v5.md`
- Document B (하위 진입 설계서): `design_entry_precision_klevel.md`
- 거버넌스·Evolution·운영: `design_governance_operations.md`
- 수치형 기준: `design_numeric_criteria.md`
- 헌법 조항 검수: `design_constitution_review.md`
