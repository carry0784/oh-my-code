# 거버넌스·Evolution·운영 설계서

## 문서 상태: LOCKED (초안 분해본)

## 출처: design_liquidity_narrative_unified_draft.md

---

## 거버넌스 모듈 역할

역할:

* event blackout ladder
* portfolio heat governance
* narrative-structure conflict resolver
* self-evolution proposal gate
* audit/log completeness 검사
* shadow/paper/live 승격 통제

---

## Evolution 전체

## 10.1 Evolution 원칙

Evolution은 자동 실행권이 아니라 **제안권**만 가진다.
모든 변경은 shadow 재검증 전 live 반영 금지.

## 10.2 제안 가능 항목

* TF pair 조정
* level score weight 조정
* event blackout window 조정
* portfolio heat threshold 조정
* counter-trend 허용 범위 조정
* fair value completion threshold 조정

## 10.3 금지 항목

* 손절 제거
* live 직접 자가수정
* governance 우회
* Structure Gate 삭제 또는 약화
* generic key level 단독 승인 허용

## 10.4 Self-Evolution Proposal Gate

필수 제안 필드:

* change_target
* log_evidence
* expected_gain
* risk_of_failure
* blast_radius
* market_scope
* shadow_revalidation_plan

---

## 필수 로그/Audit 필드

필수 로그:

* symbol
* asset_class
* structure_state
* structure_gate_pass
* approved_fair_value_zone_id
* cisd_integrity_score
* fair_value_completion_state
* premature_flag
* key_level_type
* key_level_score
* level_freshness_state
* alignment_score
* event_blackout_state
* narrative_conflict_score
* portfolio_heat_state
* entry_gate_pass
* skip_reason_code
* approval_reason_code
* entry_side
* invalidation_anchor
* target_ladder
* trade_outcome
* MAE / MFE
* execution_quality
* slippage_actual
* rule_violation_flag

---

## 통합 승격 조건

통합본 승격은 아래가 모두 충족될 때만 가능하다.

1. CISD Integrity Score 잠금 완료
2. Fair Value Completion Gauge 잠금 완료
3. Fair Value Ladder 잠금 완료
4. key level 허용 family 잠금 완료
5. Structure Gate -> Entry Gate 인터페이스 잠금 완료
6. asset-class TF 허용표 잠금 완료
7. event blackout / narrative conflict / portfolio heat 규칙 잠금 완료
8. shadow / paper 검증 완료
9. live rule violation = 0 유지
10. generic key level이 상위 공정가치 구조를 침범하지 않음 검증 완료

그 전까지는 **분리 설계 유지**가 기본 상태다.

---

## 실패 모드

* generic key level 상향 침범
* HTF 미도달 상태의 LTF 강진입
* touch-only 진입
* no-chase 위반
* counter-trend 일반 lane 오염
* narrative conflict 무시
* blackout hard 무시
* portfolio heat 무시
* interface bypass
* self-evolution direct execute

실패 모드 발생 시:

* 신규 실행 정지
* incident audit 생성
* 원인 필드 분류
* shadow 재검증 대기

---

## 운영 기본 상태

기본 상태는 다음과 같다.

* 문서 분리 유지
* 상위 구조 우선
* 하위 진입 종속
* 인터페이스 잠금
* fail-closed
* shadow -> paper -> micro live -> scaled live
* 제안형 진화만 허용

---

## 상호 참조

* 상위 구조: design_market_structure_v5.md
* 하위 진입: design_entry_precision_klevel.md
* 인터페이스: design_gate_interface_spec.md
* 수치 기준: design_numeric_criteria.md
* 헌법 검수: design_constitution_review.md
