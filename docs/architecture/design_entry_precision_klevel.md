# 문서 B: K-Level 진입 정밀화 설계서

## 문서 상태: LOCKED (초안 분해본)

## 출처: design_liquidity_narrative_unified_draft.md

## 전제 조건: Structure Gate 통과 필수 (문서 A 참조)

---

## 1. 문서 목적

본 문서의 범위는 **하위 진입 정밀화**만이다. K-Level 모듈은 독립 전략 엔진으로 작동하지 않는다.

본 문서는 다음을 다룬다.

1. K-Level 기반 진입 정밀화 체계
2. Structure Gate → Entry Gate 승인 인터페이스 (Entry Gate 측)
3. shadow → paper → live 검증 체계 중 Entry 관련 항목
4. Learning / Evolution 중 Entry 관련 항목

본 문서는 코드 명세가 아니라 **운영 설계서 초안**이다.
모든 집행권은 헌법과 게이트를 통해서만 열린다.

---

## 2. 하위 진입 종속 원칙

* K-Level 모듈은 독립 전략 엔진이 아니다.
* K-Level 모듈은 상위 구조가 승인한 구간 내부에서만 작동한다.
* Structure Gate 통과 전 Entry Gate는 열리지 않는다.
* no-chase, lower TF alignment, level-to-level target, partial/BE/trail은 실행 정밀화 규칙으로만 사용한다.

---

## 3. Entry Precision Module 역할

역할:

* approved zone 내부 key level family 탐지
* lower TF alignment 확인
* entry/no-entry 판정
* no-chase 집행
* partial/BE/trail 관리
* counter-trend quarantine lane 집행
* execution quality 기록

---

## 4. 하위 진입 흐름

1. Structure Gate 승인 수신
2. approved_fair_value_zone 내부 key level family 탐지
3. level freshness 판정
4. lower TF alignment 판정
5. event / heat / spread / liquidity 검사
6. Entry Gate 승인 또는 차단
7. bounce/retest 기반 실행
8. partial / BE / trail 관리
9. exit / review / learn 기록

---

## 5. Entry Precision Module 관측 규칙

허용 key level family:

* approved zone 내부 OB
* approved zone 내부 FVG / imbalance
* approved zone 내부 liquidity sweep anchor
* prior session high/low
* approved fair value 경계
* 구조 승인 구간과 결부된 SNR

비허용 또는 강등 family:

* 구조 승인과 무관한 임의 trend line
* 구조 승인과 무관한 generic SNR
* HTF 공정가치와 무관한 독립 key level

---

## 6. Level Freshness Ledger

상태:

* fresh
* retested
* exhausted

규칙:

* fresh: 정상 평가
* retested: 감점
* exhausted: 실행 금지

---

## 7. Alignment Score

입력:

* lower TF BOS / CHOCH
* rejection wick
* displacement
* retest hold
* delta / volume confirmation
* micro trend sync
* entry timeframe noise penalty

출력:

* STRONG
* VALID
* WEAK
* REJECTED

---

## 8. Entry Gate

### 전제

* Structure Gate 통과

### 승인 필수 조건

* 허용 key level family만 사용
* level_freshness_state != exhausted
* alignment_score >= 기준
* event_blackout_state != HARD
* spread_state = normal
* portfolio_heat_state <= limit
* governance_lock_flag = false
* 현재 분석 TF pair가 allowed_tf_pair와 일치 (헌법 조항 10)

### 출력

* entry_gate_pass
* entry_level_id
* entry_side
* invalidation_anchor
* target_ladder
* execution_mode

---

## 9. Counter-Trend Quarantine Lane

허용 조건:

* Structure Gate 통과
* A-class fresh level
* event risk low
* reduced size
* faster partial
* stricter invalidation
* 별도 평가 장부 사용

일반 lane과 절대 혼합하지 않는다.

---

## 10. Skip Reason 사전

* SKIP_NO_STRUCTURE_GATE
* SKIP_NO_FAIR_VALUE_ZONE
* SKIP_CISD_REJECTED
* SKIP_PREMATURE_SIGNAL
* SKIP_WEAK_LEVEL
* SKIP_LEVEL_EXHAUSTED
* SKIP_NO_ALIGNMENT
* SKIP_TF_MISMATCH
* SKIP_EVENT_RISK
* SKIP_SPREAD_ABNORMAL
* SKIP_PORTFOLIO_HEAT
* SKIP_GOVERNANCE_LOCK
* SKIP_NARRATIVE_CONFLICT

---

## 11. Execution

### 11.1 집행 원칙

* market chase 금지
* level 미도달 선진입 금지
* touch-only 즉시 진입 금지
* bounce / retest 기반 실행
* target = next approved ladder step
* partial / BE / trail은 사전 정의 규칙만 사용
* Structure Gate와 Entry Gate 중 하나라도 닫히면 신규 진입 금지

### 11.2 partial / BE / trail

* partial zone = next ladder node
* BE activation = 첫 목표 도달 또는 구조 회복 확인 후
* trail = structure_direction 유지 시만
* counter-trend lane은 faster partial / shorter hold 적용

### 11.3 주문 권한

* shadow: 주문 없음
* paper: 가상 주문만
* micro live: 최소 규모
* scaled live: 승격 후만 허용

---

## 12. Entry Learning

* key_level_reaction_rate
* alignment_false_positive_rate
* no_chase_savings
* partial_success_rate
* be_exit_quality
* trail_efficiency
* counter_trend_quarantine_outcome

---

## 13. Near-Miss Learning Ledger

기록 항목:

* reacted_but_target_missed
* partial_success_be_exit
* event_interference
* spread_interference
* structure_correct_entry_quality_poor
* entry_correct_structure_failed

---

## 인터페이스 참조

Structure Gate → Entry Gate 전달 필드 및 Entry Gate 권한 한계는 다음 문서를 참조한다.

`design_gate_interface_spec.md`

---

## 수치형 기준 참조

alignment_score 기준값, level freshness 감점 수치, portfolio heat limit, spread 정상 기준 등 수치형 파라미터는 다음 문서를 참조한다.

`design_numeric_criteria.md`

---

## 거버넌스·Evolution·운영 참조

거버넌스 모듈 역할, Evolution 원칙·제안·금지, 필수 로그/Audit 필드, 통합 승격 조건, 실패 모드, 운영 기본 상태는 다음 문서를 참조한다.

`design_governance_operations.md`
