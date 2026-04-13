# 통합 유동성-서사 시스템 설계서 초안

## 문서 상태: DECOMPOSED (2026-04-09)

> 본 초안은 아래 6개 문서로 분해·잠금 완료되었다. 이후 변경은 분해본에서만 수행한다.
>
> | 문서 | 파일명 | 상태 |
> |------|--------|------|
> | Document A (상위 구조) | `design_market_structure_v5.md` | LOCKED |
> | Document B (하위 진입) | `design_entry_precision_klevel.md` | LOCKED |
> | 인터페이스 명세 | `design_gate_interface_spec.md` | LOCKED |
> | 수치형 기준 | `design_numeric_criteria.md` | LOCKED |
> | 헌법 조항 검수본 | `design_constitution_review.md` | DRAFT |
> | 거버넌스·Evolution·운영 | `design_governance_operations.md` | LOCKED |
>
> **교차검증 결과:** PASS (2026-04-09, 3-axis verification)
> - Axis A 누락 6건: ALL RESOLVED
> - Axis B HIGH 불일치 2건: ALL RESOLVED
> - Axis C 타입 모순 1건: RESOLVED
> - event_blackout_state enum: HARD/SOFT 통일 완료
> - 역참조: 6개 문서 양방향 참조 완료
> - Remaining blockers: 0 / mismatches: 0 / type contradictions: 0 / new inconsistencies: 0

## 설계 기준: v5 상위 시장 구조 + K-Level 하위 진입 정밀화 + Structure Gate → Entry Gate 인터페이스 잠금

본 초안은 **v5를 상위 시장 구조 설계서**, **K-Level Alignment를 하위 진입 정밀화 설계서**로 분리한 뒤, **Structure Gate → Entry Gate 인터페이스를 통해 통합 운영**하는 것을 전제로 한다. 상위 구조는 유동성 풀·CISD·공정가치·HTF 우선 원칙을 유지하고, 하위 모듈은 higher TF key level·lower TF alignment·no-chase·level-to-level 이동 원칙을 따르되 독립 전략 엔진으로 작동하지 않는다.  

---

## 1. 문서 목적

본 문서는 다음을 하나의 운영 체계로 잠근다.

1. v5 시장 구조 판단 체계
2. K-Level 기반 진입 정밀화 체계
3. Structure Gate → Entry Gate 승인 인터페이스
4. shadow → paper → live 검증 체계
5. Learning / Evolution / Constitution 기반 자동·자율·자가진화형 운영 체계

본 문서는 코드 명세가 아니라 **운영 설계서 초안**이다.
모든 집행권은 헌법과 게이트를 통해서만 열린다.

---

## 2. 시스템 최상위 원칙

### 2.1 상위 구조 우선 원칙

* 유동성 풀은 반전 시작/청산 후보로 취급한다.
* CISD는 가격 전달 상태 변경 이벤트로 취급한다.
* 공정가치는 재축적/재분배 후보 범위로 취급한다.
* HTF 공정가치가 LTF보다 우선한다.
* HTF 미도달 상태의 LTF 강신호는 원칙적으로 약신호로 강등한다. 

### 2.2 하위 진입 종속 원칙

* K-Level 모듈은 독립 전략 엔진이 아니다.
* K-Level 모듈은 상위 구조가 승인한 구간 내부에서만 작동한다.
* Structure Gate 통과 전 Entry Gate는 열리지 않는다.
* no-chase, lower TF alignment, level-to-level target, partial/BE/trail은 실행 정밀화 규칙으로만 사용한다. 

### 2.3 fail-closed 원칙

* unknown state
* HTF/LTF 충돌
* event blackout hard
* governance lock
* portfolio heat 초과
* approval reason 누락
  중 하나라도 발생하면 신규 실행은 금지한다.

---

## 3. 전체 시스템 구성

## 3.1 상위 모듈: Market Structure Module (v5 Core)

역할:

* 유동성 풀 식별
* CISD 상태 판정
* 공정가치 후보 범위 식별
* HTF/LTF 우선순위 판정
* premature signal 강등
* structure_direction 결정
* approved_fair_value_zone 승인

## 3.2 하위 모듈: Entry Precision Module (K-Level)

역할:

* approved zone 내부 key level family 탐지
* lower TF alignment 확인
* entry/no-entry 판정
* no-chase 집행
* partial/BE/trail 관리
* counter-trend quarantine lane 집행
* execution quality 기록

## 3.3 인터페이스 모듈: Structure Gate → Entry Gate

역할:

* 상위 승인 상태를 하위 모듈로 전달
* 하위 모듈 독자 판단 차단
* 구조 충돌 시 fail-closed
* shadow/paper/live 단계별 권한 제한

## 3.4 거버넌스 모듈

역할:

* event blackout ladder
* portfolio heat governance
* narrative-structure conflict resolver
* self-evolution proposal gate
* audit/log completeness 검사
* shadow/paper/live 승격 통제

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

### 4.2 하위 진입 흐름

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

## 5. Observation

## 5.1 공통 입력 데이터

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

## 5.2 Market Structure Module 관측 규칙

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

## 5.3 Entry Precision Module 관측 규칙

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

## 5.4 Level Freshness Ledger

상태:

* fresh
* retested
* exhausted

규칙:

* fresh: 정상 평가
* retested: 감점
* exhausted: 실행 금지

## 5.5 Event Blackout Ladder

상태:

* BLACKOUT_HARD
* BLACKOUT_SOFT
* REDUCED_SIZE
* NORMAL

기본 적용 예:

* FOMC/CPI/NFP/실적 직전 = HARD
* 중요 거시 발표 근접 = SOFT
* 테마 과열 / 뉴스 폭발 직후 = REDUCED_SIZE

## 5.6 자산군별 Observation 확장

### 암호화폐

* funding
* OI
* liquidation cluster
* perp basis
* 거래소별 spread
* 24/7 유동성 약화 시간대

### 미국주식

* earnings schedule
* premarket / regular / afterhours
* sector rotation
* options gamma zone
* macro calendar

### 한국주식

* 외인/기관 수급
* 장초반/장마감 구조
* 테마 뉴스 강도
* VI / 급등락 상태
* 동시호가 상태

---

## 6. Interpretation

## 6.1 Market Structure 해석 규칙

* 유동성 풀 = 반전 시작 또는 청산 후보
* CISD = 전달 상태 변경 이벤트
* 공정가치 = 재축적/재분배 후보 범위
* HTF 공정가치 우선
* HTF 미도달 상태의 LTF 강신호는 약신호
* liquidity void는 공정가치 접근/이탈의 속도 흔적으로 해석
* Fair Value Completion Gauge가 낮으면 premature 가능성 상향

## 6.2 CISD Integrity Score

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

## 6.3 Fair Value Ladder

우선순위 예:

1. HTF OB
2. HTF FVG
3. HTF Breaker
4. MTF FVG
5. LTF OB

상위 사다리 우선, 하위 사다리는 세부 정밀화 전용으로 사용한다.

## 6.4 Fair Value Completion Gauge

상태:

* TOUCH_ONLY
* SHALLOW_FILL
* MID_FILL
* FULL_FILL
* HTF_EXTREME_REACHED

## 6.5 Narrative-Structure Conflict Resolver

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

## 6.6 Alignment Score

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

## 7. Decision

## 7.1 Structure Gate

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

## 7.2 Entry Gate

전제:

* Structure Gate 통과

승인 필수 조건:

* 허용 key level family만 사용
* level_freshness_state != exhausted
* alignment_score >= 기준
* event_blackout_state != HARD
* spread_state = normal
* portfolio_heat_state <= limit
* governance_lock_flag = false

출력:

* entry_gate_pass
* entry_level_id
* entry_side
* invalidation_anchor
* target_ladder
* execution_mode

## 7.3 Counter-Trend Quarantine Lane

허용 조건:

* Structure Gate 통과
* A-class fresh level
* event risk low
* reduced size
* faster partial
* stricter invalidation
* 별도 평가 장부 사용

일반 lane과 절대 혼합하지 않는다.

## 7.4 Skip Reason 사전

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

## 8. Execution

## 8.1 집행 원칙

* market chase 금지
* level 미도달 선진입 금지
* touch-only 즉시 진입 금지
* bounce / retest 기반 실행
* target = next approved ladder step
* partial / BE / trail은 사전 정의 규칙만 사용
* Structure Gate와 Entry Gate 중 하나라도 닫히면 신규 진입 금지

## 8.2 partial / BE / trail

* partial zone = next ladder node
* BE activation = 첫 목표 도달 또는 구조 회복 확인 후
* trail = structure_direction 유지 시만
* counter-trend lane은 faster partial / shorter hold 적용

## 8.3 주문 권한

* shadow: 주문 없음
* paper: 가상 주문만
* micro live: 최소 규모
* scaled live: 승격 후만 허용

---

## 9. Learning

## 9.1 Structure Learning

* htf_fair_value_hit_rate
* cisd_followthrough_rate
* premature_failure_rate
* fv_completion_success_rate
* void_revisit_acceleration_rate
* fair_value_ladder_step_success_rate

## 9.2 Entry Learning

* key_level_reaction_rate
* alignment_false_positive_rate
* no_chase_savings
* partial_success_rate
* be_exit_quality
* trail_efficiency
* counter_trend_quarantine_outcome

## 9.3 Premature Signal Ledger

기록 항목:

* signal_before_htf
* ignored_flag
* later_validation
* failure_mode
* salvage_case

## 9.4 Near-Miss Learning Ledger

기록 항목:

* reacted_but_target_missed
* partial_success_be_exit
* event_interference
* spread_interference
* structure_correct_entry_quality_poor
* entry_correct_structure_failed

---

## 10. Evolution

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

## 11. Constitution

## 11.1 상위 헌법

1. 유동성 풀 단독 반전 진입 금지
2. CISD 단일 패턴 암기형 진입 금지
3. 공정가치 접촉만으로 즉시 진입 금지
4. HTF 공정가치가 LTF보다 우선한다
5. HTF 미도달 상태의 LTF 강진입 금지

## 11.2 하위 헌법

6. Structure Gate 통과 전 Entry Gate 실행 금지
7. 허용되지 않은 key level family 단독 승인 금지
8. exhausted level 재진입 금지
9. no-chase 원칙 위반 금지
10. 허용되지 않은 TF pair 실행 금지

## 11.3 거버넌스 헌법

11. event blackout hard 상태 실행 금지
12. narrative conflict severe 상태 실행 금지
13. portfolio heat 초과 시 신규 진입 금지
14. approval reason / skip reason / audit 누락 시 execution 금지
15. unknown state execution 금지
16. shadow / paper 검증 전 live 확대 금지

## 11.4 Evolution 헌법

17. self-evolution은 제안권만 가진다
18. shadow 재검증 없는 parameter 변경 금지
19. live self-modification 금지
20. interface bypass 금지

---

## 12. 인터페이스 명세

## 12.1 Structure Gate → Entry Gate 전달 필드

* structure_gate_pass
* approved_fair_value_zone_id
* structure_direction
* structure_state
* premature_flag
* entry_module_allowed_flag
* event_blackout_state
* portfolio_heat_state
* asset_class
* allowed_tf_pair
* governance_lock_flag

## 12.2 Entry Gate 권한 한계

Entry Gate는 아래를 단독 결정할 수 없다.

* structure_direction 변경
* approved zone 외 확장
* premature override
* governance unlock
* event blackout hard 해제
* portfolio heat override

## 12.3 충돌 처리

* Structure와 Entry 충돌 시 fail-closed
* approved zone 외부 key level은 실행 금지
* event blackout hard가 열리면 Entry 승인 무효
* narrative conflict severe면 Entry 승인 무효

---

## 13. 자산군별 허용 TF 예시 초안

## 13.1 암호화폐

허용 예:

* 4H -> 15M
* 1H -> 5M

금지 예:

* 1D -> 1M 직접 진입
* weekly -> 1M 직접 진입

## 13.2 미국주식

허용 예:

* 1D -> 30M
* 4H -> 15M

금지 예:

* earnings 직전 단기 TF 추격
* afterhours 저유동성 무리한 진입

## 13.3 한국주식

허용 예:

* 1D -> 1H
* 4H -> 15M

금지 예:

* 장초반 테마 과열 구간 무리한 하위 TF chase
* VI/급등 상태에서 lower TF alignment 단독 승인

---

## 14. 로그 / Audit 필드

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

## 15. shadow / paper / live 승격

## 15.1 Shadow

허용:

* 구조 탐지
* 승인/차단 로직 기록
* simulated entry 기록
* no order

목표:

* Structure Gate precision
* Entry Gate precision
* skip precision
* rule violation count = 0

## 15.2 Paper

허용:

* 가상 주문
* partial / BE / trail 검증
* counter-trend quarantine 분리 검증

목표:

* structure vs entry 분리 성능 확인
* event blackout 효과 검증
* portfolio heat 차단 효과 검증

## 15.3 Micro Live

전제:

* Shadow / Paper 검증 통과
* interface locked
* governance stable
* logs complete

## 15.4 Scaled Live

전제:

* CISD Integrity Score 잠금
* Fair Value Completion Gauge 잠금
* key level 허용 family 잠금
* TF 허용표 잠금
* heat / conflict / blackout 규칙 잠금

---

## 16. 통합 승격 조건

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

## 17. 실패 모드

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

## 18. 운영 기본 상태

기본 상태는 다음과 같다.

* 문서 분리 유지
* 상위 구조 우선
* 하위 진입 종속
* 인터페이스 잠금
* fail-closed
* shadow -> paper -> micro live -> scaled live
* 제안형 진화만 허용

---

**설계서 초안 작성 완료**

## 다음 단계 체크리스트

* [ ] 본 초안을 기준으로 문서 A/v5 상위 설계서와 문서 B/K-Level 하위 설계서로 분해
* [ ] Structure Gate -> Entry Gate 인터페이스 표를 별도 문서로 고정
* [ ] CISD Integrity Score / Completion Gauge / TF 허용표를 수치형으로 잠금
* [ ] 헌법 조항 대조 검수본 형식으로 재작성
