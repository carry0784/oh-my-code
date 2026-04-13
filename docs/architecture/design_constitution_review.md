# 헌법 조항 대조 검수본

## 문서 상태: DRAFT

## 출처: design_liquidity_narrative_unified_draft.md

---

## 개요 테이블

| # | 조항 | 소속 | 집행 모듈 | 검수 상태 |
|---|------|------|-----------|-----------|
| 1 | 유동성 풀 단독 반전 진입 금지 | 상위 헌법 | Structure Gate | DRAFT |
| 2 | CISD 단일 패턴 암기형 진입 금지 | 상위 헌법 | Structure Gate | DRAFT |
| 3 | 공정가치 접촉만으로 즉시 진입 금지 | 상위 헌법 | Entry Gate | DRAFT |
| 4 | HTF 공정가치가 LTF보다 우선한다 | 상위 헌법 | Structure Gate | DRAFT |
| 5 | HTF 미도달 상태의 LTF 강진입 금지 | 상위 헌법 | Structure Gate | DRAFT |
| 6 | Structure Gate 통과 전 Entry Gate 실행 금지 | 하위 헌법 | Structure Gate / Entry Gate | DRAFT |
| 7 | 허용되지 않은 key level family 단독 승인 금지 | 하위 헌법 | Entry Gate | DRAFT |
| 8 | exhausted level 재진입 금지 | 하위 헌법 | Entry Gate | DRAFT |
| 9 | no-chase 원칙 위반 금지 | 하위 헌법 | Entry Gate | DRAFT |
| 10 | 허용되지 않은 TF pair 실행 금지 | 하위 헌법 | Entry Gate | DRAFT |
| 11 | event blackout hard 상태 실행 금지 | 거버넌스 헌법 | Governance | DRAFT |
| 12 | narrative conflict severe 상태 실행 금지 | 거버넌스 헌법 | Governance | DRAFT |
| 13 | portfolio heat 초과 시 신규 진입 금지 | 거버넌스 헌법 | Governance | DRAFT |
| 14 | approval reason / skip reason / audit 누락 시 execution 금지 | 거버넌스 헌법 | Governance | DRAFT |
| 15 | unknown state execution 금지 | 거버넌스 헌법 | Governance | DRAFT |
| 16 | shadow / paper 검증 전 live 확대 금지 | 거버넌스 헌법 | Governance / Evolution Gate | DRAFT |
| 17 | self-evolution은 제안권만 가진다 | Evolution 헌법 | Evolution Gate | DRAFT |
| 18 | shadow 재검증 없는 parameter 변경 금지 | Evolution 헌법 | Evolution Gate | DRAFT |
| 19 | live self-modification 금지 | Evolution 헌법 | Evolution Gate | DRAFT |
| 20 | interface bypass 금지 | Evolution 헌법 | Evolution Gate | DRAFT |

---

## 상위 헌법 (1-5)

### 조항 1: 유동성 풀 단독 반전 진입 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | 유동성 풀 단독 반전 진입 금지 |
| **소속** | 상위 헌법 |
| **집행 모듈** | Structure Gate |
| **집행 시점** | interpretation — CISD Integrity Score 평가 및 Structure Gate 승인 판단 단계 |
| **위반 시 조치** | fail-closed: structure_gate_pass = false, 신규 진입 금지, rule_violation_flag 기록 |
| **관련 skip_reason** | SKIP_NO_STRUCTURE_GATE, SKIP_CISD_REJECTED |
| **관련 실패 모드** | generic key level 상향 침범 (유동성 풀을 단독 key level로 오용하는 경우) |
| **검증 방법** | shadow log — structure_gate_pass = false 및 skip_reason_code = SKIP_CISD_REJECTED 기록 확인; rule_violation_flag 감사 |

---

### 조항 2: CISD 단일 패턴 암기형 진입 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | CISD 단일 패턴 암기형 진입 금지 |
| **소속** | 상위 헌법 |
| **집행 모듈** | Structure Gate |
| **집행 시점** | interpretation — CISD Integrity Score 다중 요소 평가 단계 (반대측 유동성 실행 / 구조 전환 / PD Array hold / HTF bias 일치 / follow-through 복합 검사) |
| **위반 시 조치** | fail-closed: CISD Integrity Score < 기준이면 structure_gate_pass = false, 신규 진입 금지 |
| **관련 skip_reason** | SKIP_CISD_REJECTED |
| **관련 실패 모드** | touch-only 진입 (단일 패턴 인식만으로 진입하는 경우에 동반) |
| **검증 방법** | shadow log — cisd_integrity_score 필드 기록 확인; CISD 구성 요소 개별 채점 로그 감사 |

---

### 조항 3: 공정가치 접촉만으로 즉시 진입 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | 공정가치 접촉만으로 즉시 진입 금지 |
| **소속** | 상위 헌법 |
| **집행 모듈** | Entry Gate |
| **집행 시점** | decision — Entry Gate 승인 조건 검사 단계 (bounce / retest 기반 실행 확인) |
| **위반 시 조치** | fail-closed: entry_gate_pass = false, touch-only 진입 시 rule_violation_flag 기록 |
| **관련 skip_reason** | SKIP_NO_FAIR_VALUE_ZONE, SKIP_PREMATURE_SIGNAL |
| **관련 실패 모드** | touch-only 진입 |
| **검증 방법** | shadow log / paper receipt — fair_value_completion_state = TOUCH_ONLY 상태에서 entry_gate_pass = false 기록 확인; execution_mode 필드 감사 |

---

### 조항 4: HTF 공정가치가 LTF보다 우선한다

| 항목 | 내용 |
|------|------|
| **조항 원문** | HTF 공정가치가 LTF보다 우선한다 |
| **소속** | 상위 헌법 |
| **집행 모듈** | Structure Gate |
| **집행 시점** | interpretation — Fair Value Ladder 우선순위 적용 단계 (HTF OB → HTF FVG → HTF Breaker → MTF → LTF 순서 강제) |
| **위반 시 조치** | fail-closed: LTF 공정가치가 HTF 공정가치를 침범하면 structure_gate_pass = false |
| **관련 skip_reason** | SKIP_TF_MISMATCH, SKIP_NO_FAIR_VALUE_ZONE |
| **관련 실패 모드** | HTF 미도달 상태의 LTF 강진입 |
| **검증 방법** | shadow log — approved_fair_value_zone_id의 TF 계층 확인; Fair Value Ladder 우선순위 적용 로그 감사 |

---

### 조항 5: HTF 미도달 상태의 LTF 강진입 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | HTF 미도달 상태의 LTF 강진입 금지 |
| **소속** | 상위 헌법 |
| **집행 모듈** | Structure Gate |
| **집행 시점** | interpretation — premature_flag 판정 및 Structure Gate 승인 단계 |
| **위반 시 조치** | fail-closed: premature_flag = severe이면 structure_gate_pass = false; 신규 진입 금지, Premature Signal Ledger 기록 |
| **관련 skip_reason** | SKIP_PREMATURE_SIGNAL, SKIP_TF_MISMATCH |
| **관련 실패 모드** | HTF 미도달 상태의 LTF 강진입 |
| **검증 방법** | shadow log — premature_flag 필드 기록 확인; Premature Signal Ledger (signal_before_htf, ignored_flag) 감사 |

---

## 하위 헌법 (6-10)

### 조항 6: Structure Gate 통과 전 Entry Gate 실행 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | Structure Gate 통과 전 Entry Gate 실행 금지 |
| **소속** | 하위 헌법 |
| **집행 모듈** | Structure Gate / Entry Gate |
| **집행 시점** | decision — Entry Gate 진입 전제 조건 검사 단계 (entry_module_allowed_flag 수신 확인) |
| **위반 시 조치** | execution halt: entry_module_allowed_flag = false이면 Entry Gate 비활성, 신규 실행 즉시 차단 |
| **관련 skip_reason** | SKIP_NO_STRUCTURE_GATE |
| **관련 실패 모드** | interface bypass |
| **검증 방법** | shadow log — structure_gate_pass = false 상태에서 entry_gate_pass = true 기록이 존재하면 rule_violation_flag; 인터페이스 전달 필드 순서 감사 |

---

### 조항 7: 허용되지 않은 key level family 단독 승인 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | 허용되지 않은 key level family 단독 승인 금지 |
| **소속** | 하위 헌법 |
| **집행 모듈** | Entry Gate |
| **집행 시점** | observation / decision — Entry Precision Module의 key level family 탐지 및 Entry Gate 허용 family 검사 단계 |
| **위반 시 조치** | fail-closed: 비허용 family(임의 trend line, generic SNR, HTF 공정가치 무관 독립 key level)는 entry_gate_pass = false |
| **관련 skip_reason** | SKIP_WEAK_LEVEL, SKIP_NO_STRUCTURE_GATE |
| **관련 실패 모드** | generic key level 상향 침범 |
| **검증 방법** | shadow log — key_level_type 필드가 허용 family 목록 내인지 감사; 비허용 family 탐지 시 skip_reason_code = SKIP_WEAK_LEVEL 기록 확인 |

---

### 조항 8: exhausted level 재진입 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | exhausted level 재진입 금지 |
| **소속** | 하위 헌법 |
| **집행 모듈** | Entry Gate |
| **집행 시점** | observation / decision — Level Freshness Ledger 판정 및 Entry Gate 조건 검사 단계 |
| **위반 시 조치** | execution halt: level_freshness_state = exhausted이면 entry_gate_pass = false, 실행 금지 |
| **관련 skip_reason** | SKIP_LEVEL_EXHAUSTED |
| **관련 실패 모드** | generic key level 상향 침범 (exhausted level을 재사용하는 경우에 동반) |
| **검증 방법** | shadow log / paper receipt — level_freshness_state 필드 기록 확인; exhausted 상태에서 skip_reason_code = SKIP_LEVEL_EXHAUSTED 기록 감사 |

---

### 조항 9: no-chase 원칙 위반 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | no-chase 원칙 위반 금지 |
| **소속** | 하위 헌법 |
| **집행 모듈** | Entry Gate |
| **집행 시점** | execution — 실행 모드 결정 및 주문 제출 단계 (market chase 금지, level 미도달 선진입 금지) |
| **위반 시 조치** | execution halt: market chase 또는 level 미도달 선진입 감지 시 entry_gate_pass = false, rule_violation_flag 기록 |
| **관련 skip_reason** | SKIP_PREMATURE_SIGNAL |
| **관련 실패 모드** | no-chase 위반 |
| **검증 방법** | paper receipt / audit field — execution_mode 필드 확인; no-chase 위반 시 rule_violation_flag 기록; no_chase_savings 학습 지표 감사 |

---

### 조항 10: 허용되지 않은 TF pair 실행 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | 허용되지 않은 TF pair 실행 금지 |
| **소속** | 하위 헌법 |
| **집행 모듈** | Entry Gate |
| **집행 시점** | decision — allowed_tf_pair 수신 및 Entry Gate 조건 검사 단계 |
| **위반 시 조치** | fail-closed: allowed_tf_pair 범위 외 TF 조합이면 entry_gate_pass = false |
| **관련 skip_reason** | SKIP_TF_MISMATCH |
| **관련 실패 모드** | HTF 미도달 상태의 LTF 강진입 (TF pair 위반을 동반하는 경우) |
| **검증 방법** | shadow log — allowed_tf_pair 필드와 실제 사용 TF 비교 감사; SKIP_TF_MISMATCH 기록 확인 |

---

## 거버넌스 헌법 (11-16)

### 조항 11: event blackout hard 상태 실행 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | event blackout hard 상태 실행 금지 |
| **소속** | 거버넌스 헌법 |
| **집행 모듈** | Governance |
| **집행 시점** | observation / decision — Event Blackout Ladder 상태 판정 및 Structure Gate / Entry Gate 무효화 단계 |
| **위반 시 조치** | fail-closed: event_blackout_state = HARD이면 구조 승인 무효, Entry Gate 승인 무효, 신규 실행 금지 |
| **관련 skip_reason** | SKIP_EVENT_RISK |
| **관련 실패 모드** | blackout hard 무시 |
| **검증 방법** | shadow log — event_blackout_state 필드 기록 확인; HARD 상태에서 skip_reason_code = SKIP_EVENT_RISK 기록 감사; paper receipt에서 실행 차단 확인 |

---

### 조항 12: narrative conflict severe 상태 실행 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | narrative conflict severe 상태 실행 금지 |
| **소속** | 거버넌스 헌법 |
| **집행 모듈** | Governance |
| **집행 시점** | interpretation / decision — Narrative-Structure Conflict Resolver 판정 단계 (FAIL_CLOSED 출력 조건) |
| **위반 시 조치** | fail-closed: narrative_conflict_score = severe이면 Entry Gate 승인 무효, counter-trend lane도 금지, 신규 실행 금지 |
| **관련 skip_reason** | SKIP_NARRATIVE_CONFLICT |
| **관련 실패 모드** | narrative conflict 무시 |
| **검증 방법** | shadow log — narrative_conflict_score 필드 기록 확인; FAIL_CLOSED 출력 시 skip_reason_code = SKIP_NARRATIVE_CONFLICT 기록 감사 |

---

### 조항 13: portfolio heat 초과 시 신규 진입 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | portfolio heat 초과 시 신규 진입 금지 |
| **소속** | 거버넌스 헌법 |
| **집행 모듈** | Governance |
| **집행 시점** | decision — Entry Gate 조건 검사 단계 (portfolio_heat_state <= limit 확인) |
| **위반 시 조치** | fail-closed: portfolio_heat_state > limit이면 entry_gate_pass = false, 신규 진입 금지 |
| **관련 skip_reason** | SKIP_PORTFOLIO_HEAT |
| **관련 실패 모드** | portfolio heat 무시 |
| **검증 방법** | shadow log / paper receipt — portfolio_heat_state 필드 기록 확인; 한도 초과 시 skip_reason_code = SKIP_PORTFOLIO_HEAT 기록 감사 |

---

### 조항 14: approval reason / skip reason / audit 누락 시 execution 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | approval reason / skip reason / audit 누락 시 execution 금지 |
| **소속** | 거버넌스 헌법 |
| **집행 모듈** | Governance |
| **집행 시점** | execution — 주문 제출 직전 audit/log completeness 검사 단계 |
| **위반 시 조치** | execution halt: approval_reason_code 또는 skip_reason_code 또는 필수 audit 필드 누락 시 실행 금지, governance_lock_flag 활성화 |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | interface bypass (audit 우회를 동반하는 경우) |
| **검증 방법** | audit field — 필수 로그 필드(approval_reason_code, skip_reason_code, rule_violation_flag 등) 완전성 검사; 누락 필드 존재 시 governance_lock_flag 기록 확인 |

---

### 조항 15: unknown state execution 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | unknown state execution 금지 |
| **소속** | 거버넌스 헌법 |
| **집행 모듈** | Governance |
| **집행 시점** | decision — 모든 게이트 상태 판정 완료 후 최종 집행 전 상태 유효성 검사 단계 |
| **위반 시 조치** | fail-closed: structure_state, event_blackout_state, narrative_conflict_score, portfolio_heat_state 중 하나라도 unknown이면 신규 실행 금지 (2.3 fail-closed 원칙 직접 적용) |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | interface bypass (상태 불명확 상태에서 실행을 강제하는 경우) |
| **검증 방법** | shadow log — 모든 상태 필드의 known/unknown 분류 기록 확인; unknown 상태 발생 시 incident audit 생성 여부 감사 |

---

### 조항 16: shadow / paper 검증 전 live 확대 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | shadow / paper 검증 전 live 확대 금지 |
| **소속** | 거버넌스 헌법 |
| **집행 모듈** | Governance / Evolution Gate |
| **집행 시점** | evolution — shadow → paper → micro live → scaled live 승격 조건 검사 단계 |
| **위반 시 조치** | execution halt: shadow / paper 검증 미완료 상태에서 micro live 또는 scaled live 주문 권한 부여 금지 |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | self-evolution direct execute (검증 단계 생략을 동반하는 경우) |
| **검증 방법** | audit field / paper receipt — 승격 이력 기록 확인; shadow / paper 단계 완료 플래그 없이 live 주문 권한이 열린 경우 rule_violation_flag 기록 감사 |

---

## Evolution 헌법 (17-20)

### 조항 17: self-evolution은 제안권만 가진다

| 항목 | 내용 |
|------|------|
| **조항 원문** | self-evolution은 제안권만 가진다 |
| **소속** | Evolution 헌법 |
| **집행 모듈** | Evolution Gate |
| **집행 시점** | evolution — Self-Evolution Proposal Gate 제출 및 검토 단계 |
| **위반 시 조치** | execution halt: Evolution 모듈이 직접 실행권을 행사하는 경우 즉시 차단, incident audit 생성 |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | self-evolution direct execute |
| **검증 방법** | audit field — Self-Evolution Proposal Gate 필수 필드(change_target, log_evidence, shadow_revalidation_plan 등) 완전성 확인; 제안 이후 인간 승인 없이 변경 적용된 기록 감사 |

---

### 조항 18: shadow 재검증 없는 parameter 변경 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | shadow 재검증 없는 parameter 변경 금지 |
| **소속** | Evolution 헌법 |
| **집행 모듈** | Evolution Gate |
| **집행 시점** | evolution — parameter 변경 제안 수락 후 shadow 재검증 완료 전 적용 차단 단계 |
| **위반 시 조치** | execution halt: shadow_revalidation_plan 미완료 상태에서 parameter 변경 적용 금지; 위반 시 incident audit 생성, 원상태 복구 |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | self-evolution direct execute |
| **검증 방법** | shadow log — parameter 변경 이력과 shadow 재검증 완료 플래그 대조; 재검증 없이 변경이 적용된 기록 존재 시 rule_violation_flag 감사 |

---

### 조항 19: live self-modification 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | live self-modification 금지 |
| **소속** | Evolution 헌법 |
| **집행 모듈** | Evolution Gate |
| **집행 시점** | execution / evolution — live 운영 중 런타임 자가 수정 감지 및 차단 단계 |
| **위반 시 조치** | execution halt: live 상태에서의 직접 자가 수정 시도 즉시 차단, 신규 실행 정지, incident audit 생성 |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | self-evolution direct execute, interface bypass |
| **검증 방법** | audit field — live 운영 기간 중 parameter / 로직 변경 이력 감사; 런타임 수정 시도 발생 시 rule_violation_flag 및 incident audit 기록 확인 |

---

### 조항 20: interface bypass 금지

| 항목 | 내용 |
|------|------|
| **조항 원문** | interface bypass 금지 |
| **소속** | Evolution 헌법 |
| **집행 모듈** | Evolution Gate |
| **집행 시점** | decision / execution — Structure Gate → Entry Gate 인터페이스 경유 여부 및 governance 우회 감지 단계 |
| **위반 시 조치** | execution halt: Structure Gate / Entry Gate / Governance 인터페이스를 우회한 실행 즉시 차단, incident audit 생성, shadow 재검증 대기 |
| **관련 skip_reason** | SKIP_GOVERNANCE_LOCK |
| **관련 실패 모드** | interface bypass |
| **검증 방법** | audit field — entry_module_allowed_flag 없이 실행된 기록, governance_lock_flag 없이 governance 조건 생략된 기록 감사; rule_violation_flag 발생 이력 전수 확인 |

---

## 참조 문서

- Document A (상위 구조 설계서): `design_market_structure_v5.md`
- Document B (하위 진입 설계서): `design_entry_precision_klevel.md`
- 인터페이스 명세: `design_gate_interface_spec.md`
- 수치형 기준: `design_numeric_criteria.md`
- 거버넌스·Evolution·운영: `design_governance_operations.md`

---

## 검수 완료 조건: 전 조항 검수 상태 = PASS일 때만 운영 투입 가능
