# 문서 A: v5 시장 구조 설계서

## 문서 상태: LOCKED (초안 분해본)

## 출처: design_liquidity_narrative_unified_draft.md

---

## 1. 문서 목적

본 문서의 scope는 **상위 시장 구조 판단**만이다.

본 문서는 다음을 운영 체계로 잠근다.

1. v5 시장 구조 판단 체계
2. Structure Gate → Entry Gate 승인 인터페이스 중 Structure Gate 출력 필드
3. shadow → paper → live 검증 체계 중 구조 판단 관련 부분
4. Structure Learning / Premature Signal Ledger 기반 구조 학습 체계

본 문서는 코드 명세가 아니라 **운영 설계서**이다.
모든 집행권은 헌법과 게이트를 통해서만 열린다.

Entry Gate, K-Level, 실행 정밀화(partial/BE/trail) 규칙은 문서 B에 속한다.

---

## 2. 시스템 최상위 원칙

### 2.1 상위 구조 우선 원칙

* 유동성 풀은 반전 시작/청산 후보로 취급한다.
* CISD는 가격 전달 상태 변경 이벤트로 취급한다.
* 공정가치는 재축적/재분배 후보 범위로 취급한다.
* HTF 공정가치가 LTF보다 우선한다.
* HTF 미도달 상태의 LTF 강신호는 원칙적으로 약신호로 강등한다.

---

## 3. 전체 시스템 구성

### 3.1 상위 모듈: Market Structure Module (v5 Core)

역할:

* 유동성 풀 식별
* CISD 상태 판정
* 공정가치 후보 범위 식별
* HTF/LTF 우선순위 판정
* premature signal 강등
* structure_direction 결정
* approved_fair_value_zone 승인

---

## 4. 운영 흐름

### 4.1 상위 구조 흐름

1. 유동성 풀 탐지
2. sweep 여부 확인
3. CISD 후보 확인
4. HTF 공정가치 후보 식별
5. HTF 도달 여부 판정
6. premature signal 여부 판정
7. Structure Gate 승인 또는 차단

---

## 5. Observation

### 5.1 공통 입력 데이터 (상위 구조 관련)

* symbol
* asset_class
* session_type
* higher_tf
* lower_tf
* price / volume / spread / slippage estimate
* liquidity pool candidates
* PD Array candidates
* news_event_state
* narrative_theme_state
* macro_event_state
* portfolio_heat_state
* governance_lock_flag

### 5.2 Market Structure Module 관측 규칙

* 주요 외부/내부 유동성 풀 탐지
* sweep 발생 여부 기록
* CISD 후보 위치 기록
* HTF/MTF/LTF 공정가치 후보 범위 식별
* Fair Value Ladder 구성
* Fair Value Completion Gauge 계산
* Premature Signal Ledger 기록
* HTF 미도달 상태의 LTF 신호 태깅
* liquidity void / imbalance / gap 관측
* structure bias candidate 기록

### 5.6 자산군별 Observation 확장 (상위 구조 관련)

#### 암호화폐

* funding
* OI
* liquidation cluster
* perp basis
* 거래소별 spread
* 24/7 유동성 약화 시간대

#### 미국주식

* earnings schedule
* premarket / regular / afterhours
* sector rotation
* options gamma zone
* macro calendar

#### 한국주식

* 외인/기관 수급
* 장초반/장마감 구조
* 테마 뉴스 강도
* VI / 급등락 상태
* 동시호가 상태

---

## 6. Interpretation

### 6.1 Market Structure 해석 규칙

* 유동성 풀 = 반전 시작 또는 청산 후보
* CISD = 전달 상태 변경 이벤트
* 공정가치 = 재축적/재분배 후보 범위
* HTF 공정가치 우선
* HTF 미도달 상태의 LTF 강신호는 약신호
* liquidity void는 공정가치 접근/이탈의 속도 흔적으로 해석
* Fair Value Completion Gauge가 낮으면 premature 가능성 상향

### 6.2 CISD Integrity Score

구성 예:

* 반대측 외부 유동성 실행
* 구조 전환/이탈 확인
* PD Array hold/reject
* HTF bias 일치
* follow-through
* 역방향 복귀 패널티
* HTF 미도달 패널티

판정:

* CONFIRMED
* PROBATION
* REJECTED

### 6.3 Fair Value Ladder

우선순위 예:

1. HTF OB
2. HTF FVG
3. HTF Breaker
4. MTF FVG
5. LTF OB

상위 사다리 우선, 하위 사다리는 세부 정밀화 전용으로 사용한다.

### 6.4 Fair Value Completion Gauge

상태:

* TOUCH_ONLY
* SHALLOW_FILL
* MID_FILL
* FULL_FILL
* HTF_EXTREME_REACHED

### 6.5 Narrative-Structure Conflict Resolver

입력:

* technical_score
* narrative_score
* event proximity
* session structure
* liquidity condition

출력:

* PASS
* REDUCE
* FAIL_CLOSED

규칙:

* 기술 구조가 강해도 narrative conflict severe면 fail-closed
* event blackout hard면 구조 승인 무효
* narrative conflict severe면 counter-trend lane도 금지

---

## 7. Decision

### 7.1 Structure Gate

승인 필수 조건:

* approved_fair_value_zone 존재
* CISD Integrity Score >= 기준
* HTF 공정가치 접근 또는 도달 조건 충족
* premature_flag != severe
* structure conflict 없음
* governance_lock_flag = false

출력 필드:

* structure_gate_pass
* approved_fair_value_zone_id
* structure_direction
* structure_state
* premature_flag
* entry_module_allowed_flag

---

## 9. Learning

### 9.1 Structure Learning

* htf_fair_value_hit_rate
* cisd_followthrough_rate
* premature_failure_rate
* fv_completion_success_rate
* void_revisit_acceleration_rate
* fair_value_ladder_step_success_rate

### 9.3 Premature Signal Ledger

기록 항목:

* signal_before_htf
* ignored_flag
* later_validation
* failure_mode
* salvage_case

---

## 인터페이스 참조

Structure Gate → Entry Gate 전달 필드 및 Entry Gate 권한 한계, 충돌 처리 규칙의 전체 명세는 다음 문서를 참조한다.

`design_gate_interface_spec.md`

---

## 수치형 기준 참조

CISD Integrity Score 임계값, Fair Value Completion Gauge 임계값, HTF 도달 판정 기준, premature_flag 판정 기준 등 수치형 기준 일체는 다음 문서를 참조한다.

`design_numeric_criteria.md`

---

## 거버넌스·Evolution·운영 참조

거버넌스 모듈 역할, Evolution 원칙·제안·금지, 필수 로그/Audit 필드, 통합 승격 조건, 실패 모드, 운영 기본 상태는 다음 문서를 참조한다.

`design_governance_operations.md`
