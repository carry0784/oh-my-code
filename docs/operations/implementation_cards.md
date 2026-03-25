# Implementation Cards
## 운영 헌법 기반 카드 목록 v1.0

**Path:** `docs/operations/implementation_cards.md`
**Authority Source:** `Operating Constitution v1.0`, 하위 운영 문서 5종
**Status:** ACTIVE
**Rule:** 본 문서는 구현 카드 목록과 검수 기준을 기록하며, 본 문서 자체는 코드 구현을 수행하지 않는다.

---

## I-series 진행 상태

| 카드 | 상태 | 비고 |
|------|------|------|
| I-01 | **DONE** | 대시보드 반영 완료 (Tab 3 + ops-status 엔드포인트) |
| I-02 | **DONE** | 알림 규칙 반영 완료 (ops-alerts 엔드포인트 + 헌법 등급 어댑터) |
| I-03 | **DONE** | 자동 점검 골격 반영 완료 (ops-checks 엔드포인트 + 점검 러너 + Checks 패널) |
| I-04 | **DONE** | Recovery Preflight / Incident Playback 반영 완료 (ops-preflight + ops-playback + 패널) |
| I-05 | **DONE** | Execution Gate 4조건 통합 판정 완료 (ops-gate 엔드포인트 + Gate 패널) |
| I-06 | **DONE** | Operator Approval — 승인 영수증 계층 완료 (ops-approval + 7필드 검증 + scope + expiry) |
| I-07 | **DONE** | Execution Policy — 승인-실행 일치 검증 완료 (ops-policy + hash 검증 + MATCH/DRIFT/EXPIRED) |
| E-01 | **DESIGN DONE** | Executor — 설계 계약 완료. 실행 로직 활성화 별도 승인 전까지 금지. |
| E-02 | **DONE** | Activation Rule — 12조건 활성화 판정 + intent hash + activation approval. 실행 금지. |
| E-03 | **DONE** | Micro Executor — 1회성 소비 + dispatch guard + paper/micro 제한. live unlock 금지. |
| S-01A | **DONE** | consumed 영속성 보강 — evidence_store 기반 소비 조회 + hot cache |
| S-01B | **DONE** | dispatch window guard — 만료 시 DISPATCH_WINDOW_EXPIRED 거부 |
| S-01C | **DONE** | Hourly observability — ops-status 데이터 기반 unknown 항목 enrichment |
| S-01D | **DONE** | Tab 3 실렌더 검증 — 15패널 + 10 fetch + 24 CSS + 금지 버튼 0 확인 |
| S-02 | **DONE** | 운영 안정화 2단계 — daily/hourly Celery beat 등록 + ops 테스트 18건 |
| B-08 | **DONE** | AI Assist 데이터 소스 연결 — ops_summary + signal + position + evidence read-only 정규화 |
| B-09 | **DONE** | 실시간 호가/스프레드 피드 — 4거래소 best bid/ask/spread/trust 서비스화 + AI 통합 |
| B-10 | **DONE** | 종합 운영 강화 — ops/AI/market aggregate + ops_health + source_coverage |
| B-11 | **DONE** | Governance Summary — overall/execution/dominant_reason + governance_health |
| B-12 | **DONE** | Operator UI Health — Status Banner + Alert Strip + Health Summary |
| B-13 | **DONE** | Alert Priority Summary — P1~INFO + escalation + top_reason + alert_health |
| BL-TZ01 | **RESOLVED** | timezone aware/naive mismatch 해소 |
| BL-ENUM01 | **RESOLVED** | enum orderstatus mismatch 해소 |
| S-03 | **DONE** | 운영 안정화 3단계 — orphaned worker 해소 + controlled restart + runtime consistency 회복. WARNING (KI-1/KI-2 non-blocking). Receipt: `s03_stabilization_2026-03-25.md` |

### S-03 상태 고정

> S-03 completed with WARNING; runtime/core/ops/config layers are stable, and known issues KI-1/KI-2 are tracked separately as non-blocking follow-ups.

| B-14A | **DONE** | Operator Safety — 테스트 57건 + ops-safety-summary endpoint + safety panel. Receipt: `b14a_receipt_2026-03-25.md` |
| KI-1 | **RESOLVED** | positions.symbol_name migration 적용 (117c4dc320f5). data/v2 500→200 해소. |
| B-15 | **DONE** | Tab 1 Dead Element 활성화 — summary row + position table + stats panel JS 바인딩. Receipt: `ki1_b15_receipt_2026-03-25.md` |
| B-14B | **DONE** | Preflight item-level 표시 + Gate condition 상세화 + Approval next-steps UX 확장. Receipt: `b14b_receipt_2026-03-25.md` |
| B-16 | **DONE** | Tab 1 총계 요약 바 — 6필드 합산 (거래소/연결/포지션/매매/평가금액/PNL). Receipt: `b16_receipt_2026-03-25.md` |
| KI-2 | **RESOLVED** | readiness probe 속성명 정렬 — `_evidence_store`/`_security_ctx` → `evidence_store`/`security_ctx` (12파일 68건). /ready 503→200, /status readiness not_ready→ready. Receipt: `ki2_receipt_2026-03-25.md` |
| B-17 | **DONE** | 거래소별 환경 분석 (환경 모델) — Tab 2 하단 5거래소 프로필 카드 그리드 + 요약 바. Receipt: `b17_receipt_2026-03-25.md` |
| B-18 | **DONE** | 전략 모델 (Strategy Context) — Signal Pipeline + Exposure Overview + Execution Readiness 3섹션. Receipt: `b18_receipt_2026-03-25.md` |
| B-19 | **DONE** | 실행 모델 (Execution Pipeline) — 6단계 파이프라인 흐름도 + 차단 지점 식별. Receipt: `b19_receipt_2026-03-25.md` |
| B-20 | **DONE** | 통합 타임라인 (Unified Timeline) — 4소스 병합 + 필터 + 시간순. Receipt: `b20_receipt_2026-03-25.md` |
| B-21 | **DONE** | 리스크 모니터 (Risk Monitor) — 4-panel 상태 스냅샷 (기존 값만, 새 계산 0건). Receipt: `b21_receipt_2026-03-25.md` |
| B-22 | **DONE** | 시나리오 뷰어 (Scenario Viewer / State Comparison) — 기존 data/v2 값 기반 7조건 Gap Table + Readiness Progress. 예측/추천/AI 판단 아님. Observation Layer 마지막. Receipt: `b22_receipt_2026-03-26.md` |

### Tab 2 구조 명칭

```
Operational Context Stack (B-17/B-18/B-19)
  └── Environment → Strategy → Execution

Observation Layer (B-20/B-21/B-22)
  └── Timeline → Risk → Scenario
```

### Fallback Reason Registry (대시보드 검수 표준)

| 코드 | 의미 | UI 표시 |
|------|------|--------|
| `NULL_FROM_API` | API 응답 키 존재, 값이 null | `-` |
| `NO_DATA` | 데이터 배열이 빈 상태 | `포지션 없음` / `-` |
| `DISCONNECTED` | 거래소 연결 끊김 | `연결 안 됨` |
| `KEY_ABSENT` | 응답에 키 자체가 없음 | `-` |
| `QUERY_FAILED` | DB 집계 쿼리 실패 | `QUERY FAILED` |

> 이후 UI 검수 시 `-` 표시에는 반드시 위 이유 코드 중 하나를 대응시켜 제출한다.

### 카드 우선순위 표준

> 같은 축 연장 카드 우선 → 복구 완료 직후 UX 확장 → 인프라 KI는 blocker일 때만 선순위 승격 → 신규 카드는 연속 카드 종료 후 착수

### 다음 후보 카드

| 카드 | 범위 | 선행 조건 |
|------|------|----------|
### Observation Layer 완료

> Observation Layer (B-20 Timeline + B-21 Risk + B-22 Scenario) 전체 DONE.
> Tab 2 하단 구조: Operational Context Stack (B-17~B-19) + Observation Layer (B-20~B-22) 완성.

### B-22 설계 정의 봉인

> **공식 정의**: B-22 Scenario Viewer는 기존 data/v2 값만 사용하여, 사전 정의된 목표 상태와 현재 상태의 조건 차이를 read-only로 비교 표시하는 Observation 패널이다.

**부제**: State Comparison / Condition Comparison / Read-only comparison from existing values

**명칭 유지 이유**: "Scenario Viewer"는 카드 계보 내 위치 식별용으로 유지. 내부 구현·검수에서는 "State Comparison" 또는 "Condition Comparison"으로 참조하여 예측/추천 오해를 방지.

**B-19 / B-22 역할 경계**:

| | B-19 Execution Pipeline | B-22 Scenario Viewer |
|---|---|---|
| 질문 | 현재 실행 흐름에서 어디가 막혔는가 | 사전 정의된 목표 상태 기준으로 무엇이 부족한가 |
| 관점 | pipeline blockage 관측 | condition comparison 관측 |
| 표시 | 6단계 순차 흐름도 + 차단 지점 | 7조건 현재값 vs 필요값 테이블 |
| 예측 기능 | 없음 | 없음 |

**Gap 계산 규칙**:
- gap은 예측 거리나 확률이 **아니다**
- gap은 조건 충족 여부를 보여주는 **비교 상태**다
- 상태형(enum): 일치/불일치
- 불리언형(bool): 충족/미충족
- 임계형(threshold): 기준 미달/충족 (Ops Score만 현재값/기준값 표기 허용)
- 정책형(policy): 일치/불일치
- 새 계산 추가 금지. "충족 수 / 전체 수" 단순 집계만 허용

**Readiness Progress 의미 제한**:
> Readiness Progress는 전체 비교 조건 수 대비 현재 충족 조건 수의 단순 비율 표시이다.
- 이 값은 확률이 아니다
- 이 값은 예측이 아니다
- 이 값은 승인 가능성을 의미하지 않는다
- 이 값은 거래 가능성을 의미하지 않는다
- 이 값은 단지 조건 충족 개수의 비율 표시이다

**금지 범위**:
추천, 예측, AI 판단, 신규 점수 생성, 신규 파생 지표, 성공 가능성 추정, 승인 가능성 추정, next-step 자동 제안, 우선순위 재계산, 리스크 재해석, 미래 상태 시뮬레이션

| B-23 | **DONE** | Ops Summary Panel — Tab 2 상단 8-cell 상태 요약 바 + ops-safety-summary 확장. 테스트 14건. |

### Tab 2 전체 구조 최종 정리본

> 참조: `docs/operations/tab2_structure_seal.md`
> Tab 2 = read-only 운영 가시화 계층.
> Operational Context Stack (B-17~B-19) + Observation Layer (B-20~B-22) + B-23 Ops Summary = **COMPLETE + FROZEN**
> 테스트 기준선: **314 passed** (Dashboard 243 + B-14 57 + B-23 14)

### Tab 3 구조 기준선

> 참조: `docs/operations/tab3_structure_seal.md`
> Tab 3 = control / action / execution 계층.
> 구조: Control Context + Action Console + Execution Log
> 상태: **SEALED (구현 대기)**
> 카드 후보: C-01 ~ C-09 (봉인 후 순차 발행)
> 자동 실행 금지 / 승인 없이 실행 금지 / AI 단독 결정 금지
> 카드 설계 봉인: `docs/operations/tab3_cards_seal.md`
> Safe Card 8개 (C-01~C-03, C-05~C-09) + Controlled Write 1개 (C-04)
> 구현 순서: Safe Card 1순위 → C-04 최후
> **Safe Card 8개 구현 완료**: Receipt `tab3_safe_cards_receipt_2026-03-26.md`
> C-04 Manual Action: **미구현 (봉인 유지)**
> Contract Seal: `c04_manual_action_contract_seal.md`
> Prereq Resolution: `c04_manual_action_prereq_resolution.md` (R-1/R-2/R-3 확정)
> 테스트 기준선: **339 passed** (Dashboard 243 + B-14 57 + B-23 14 + Tab 3 25)
> C-04 Test Strategy Seal: `c04_manual_action_test_strategy_seal.md`
> C-04 Operator Approval Seal: `c04_manual_action_operator_approval.md`
> C-04 **Phase 1 승인 완료** (테스트 코드 작성 허가만). Receipt: `evidence/c04_phase1_approval_2026-03-26.md`
> C-04 **Phase 1 테스트 코드 작성 완료**: 119 tests across 6 files. Receipt: `evidence/c04_phase1_testcode_receipt_2026-03-26.md`
> 테스트 범위: 9-stage chain (23) + fail-closed (18) + block/fail codes (16) + evidence/audit (22) + receipts (22) + never-happen (18)
> negative-path > 70%. production code 수정 0건. C-04 여전히 봉인.
> 테스트 기준선 갱신: **458 passed** (기존 339 + C-04 119)
> C-04 **Phase 2 Review 완료**: GO. 테스트 벽 충분성 확인. Receipt: `evidence/c04_phase2_review_2026-03-26.md`
> Phase 2 허용 범위: 최소 구현 범위 설계 문서만. 구현/활성화/실행 여전히 금지.
> C-04 **최소 구현 범위 설계 완료**: `c04_minimum_implementation_scope.md`. IS-1~IS-8 허용, OS-1~OS-16 금지, write path 0개 유지.
> C-04 **Phase 3 Review GO**: 최소 구현 범위 충분히 좁고 fail-closed. Receipt: `evidence/c04_phase3_review_2026-03-26.md`
> Phase 3 허용: IS-1~IS-8 범위 내 최소 구현 착수. write path 0개. sealed/disabled 유지.
> 주의: _renderC04 추가 시 Phase 1 테스트 1건 목적 전환 필요 (삭제 금지).
> C-04 **Phase 3 Implementation Start Approved** (sealed only). IS-1~IS-8 범위 내 최소 구현 착수 허가. Receipt: `evidence/c04_phase3_implementation_start_approval_2026-03-26.md`
> C-04 **Phase 4 Activation Scope Review GO**: 10 items review-possible, 14 items forbidden/deferred. Receipt: `evidence/c04_phase4_activation_scope_review_2026-03-26.md`
> C-04 **Phase 4 Complete / SEALED**: Activation presentation implemented (A-1~A-10). Still disabled/sealed/fail-closed. Receipt: `evidence/c04_phase4_activation_completion_review_2026-03-26.md`
> C-04 **Phase 5 Execution Scope Review GO**: 19 reviewable, 9 permanently forbidden. Receipt: `evidence/c04_phase5_execution_scope_review_2026-03-26.md`
> C-04 **Phase 5 Execution Approved** (bounded only). 19 items. 9-stage chain gating. Receipt: `evidence/c04_phase5_execution_approval_2026-03-26.md`
> C-04 **Phase 5 SEALED**: Execution implemented (bounded). 30/30 PASS. Receipt: `evidence/c04_phase5_execution_completion_review_2026-03-26.md`
> C-04 **Phase 6 Scope Review GO**: 20 reviewable (text/display/schema), 17 deferred (Phase 7+), 3 permanently forbidden. Receipt: `evidence/c04_phase6_scope_review_2026-03-26.md`
> C-04 **Phase 6 Approved** (descriptive/display/schema only). A-1~A-20. Receipt: `evidence/c04_phase6_approval_2026-03-26.md`
> C-04 **Phase 6 SEALED**: Display-only (rollback/retry/polling/dryrun/preview text). 20/20 prohibitions absent. Receipt: `evidence/c04_phase6_completion_review_2026-03-26.md`
> C-04 **Phase 7 Scope Review GO**: 16 reviewable (manual rollback/retry + simulation + preview). 12 permanently forbidden. Receipt: `evidence/c04_phase7_scope_review_2026-03-26.md`
> C-04 **Phase 7 Approved** (bounded recovery). A-1~A-16: manual rollback/retry + simulation + preview. Receipt: `evidence/c04_phase7_approval_2026-03-26.md`
> C-04 **Phase 7 SEALED**: Manual rollback/retry/simulation/preview (bounded). 16/16 PASS. Receipt: `evidence/c04_phase7_completion_review_2026-03-26.md`
> C-04 **Phase 8 Scope Review GO**: 12 reviewable (text/display/guard), 17 permanently forbidden. Receipt: `evidence/c04_phase8_scope_review_2026-03-26.md`
> C-04 **Phase 8 Approved** (text/display/guard/manual-refresh). A-1~A-12. Receipt: `evidence/c04_phase8_approval_2026-03-26.md`
> C-04 **Phase 8 SEALED**: Guard/display (A-1~A-12). Write path = 5 POST unchanged. Receipt: `evidence/c04_phase8_completion_review_2026-03-26.md`
> C-04 **Phase 9 Scope Review GO**: 13 reviewable (display/guard/text). Boundary refinement only. Receipt: `evidence/c04_phase9_scope_review_2026-03-26.md`
> C-04 **Phase 9 Approved** (informational/guard/display). 13 items. Receipt: `evidence/c04_phase9_approval_2026-03-26.md`
> C-04 **Phase 9 SEALED**: Boundary refinement (13 items). Receipt: `evidence/c04_phase9_completion_review_2026-03-26.md`
> Phase 10+: engine enhancements deferred. 14 permanently forbidden. 다음: Phase 10 Scope Review.

---

## I-06 / I-07 / E-01 카드 정의

### 계층 구조

```
I-01~I-05  관찰·표시·기록 계층     (완료)
    ↓
I-06       승인 영수증 계층         (approval receipt)
    ↓
I-07       승인-실행 상태 일치 검증  (pre-execution validation)
    ↓
E-01       제한적 실행 계층         (constrained executor)
```

### 서두 제약 (I-06 / I-07 / E-01 공통)

- I-06은 승인 영수증 계층이다. 실행 권한을 부여하지 않는다.
- I-07은 승인-실행 상태 일치 검증 계층이다. 실행을 수행하지 않는다.
- E-01은 제한적 실행 계층이다. I-06/I-07 완료 전 설계만 가능하고 실행 로직 활성화는 금지한다.
- 승인은 영구 권한이 아니다. 반드시 유효시간(approval_expiry_at)이 있어야 한다.
- No Evidence, No Power 원칙은 모든 계층에 적용된다.

---

### I-06 Operator Approval — 승인 영수증 계층

**역참조:** 제43조, 제45조
**선행 조건:** I-05 완료
**우선순위:** I-series 확장 1순위

#### 목적
운영자가 실행을 승인할 때, 승인 시점의 시스템 상태를 증거로 기록하는 영수증 계층을 제공한다.
승인 영수증은 실행 허가가 아니라 "승인 시점에 조건이 충족되어 있었다"는 증거 기록이다.

#### 승인 영수증 필수 필드 (7필드)

| 필드 | 출처 | 검증 |
|------|------|------|
| gate_snapshot_id | I-05 | gate.decision == OPEN 필수 |
| preflight_id | I-04 | preflight.decision == READY 필수 |
| check_id | I-03 | check.result != BLOCK 필수 |
| ops_score | I-01 | >= threshold 필수 |
| security_state | I-01 | != LOCKDOWN 필수 |
| timestamp | 승인 시점 | ISO 8601 |
| approval_expiry_at | 만료 시점 | ISO 8601 (승인 후 N분 이내) |

#### 수용 기준
- 7필드 모두 존재해야 승인 유효
- 하나라도 누락이면 승인 불가
- approval_expiry_at 이후에는 승인 무효
- 승인 영수증은 append-only evidence로 기록
- 승인 영수증 자체는 실행 권한을 부여하지 않음

#### 금지 범위
- 승인 영수증만으로 자동 실행 금지
- 만료된 승인으로 실행 금지
- 승인 영수증 수정/삭제 금지
- 필드 누락 상태에서 승인 발행 금지

---

### I-07 Execution Policy — 승인-실행 상태 일치 검증 계층

**역참조:** 제33조, 제39조, 제43조
**선행 조건:** I-06 완료
**우선순위:** I-series 확장 2순위

#### 목적
실행 직전에 "승인 시점의 상태"와 "현재 상태"가 일치하는지 재검증한다.
승인 후 상태가 변했으면 실행을 거부한다.

#### 검증 항목
- approval_expiry_at 미만료 확인
- gate.decision이 여전히 OPEN인지 재확인
- preflight.decision이 여전히 READY인지 재확인
- ops_score가 여전히 threshold 이상인지 재확인
- security_state가 여전히 LOCKDOWN이 아닌지 재확인
- 승인 시점 ~ 현재 시점 사이 CRITICAL 알림 발생 여부 확인

#### 판정
- MATCH: 모든 조건 일치 → 실행 진행 가능
- DRIFT: 1개 이상 불일치 → 실행 거부, 재승인 필요
- EXPIRED: approval_expiry_at 초과 → 실행 거부, 재승인 필요

#### 금지 범위
- 상태 불일치를 무시하고 실행 허용 금지
- 만료 승인을 연장하는 로직 금지
- 검증 실패를 자동 복구하는 로직 금지
- I-07 자체가 실행을 수행하지 않음

---

### E-01 Executor — 제한적 실행 계층

**역참조:** 제36조~제38조 (Micro Live ~ Evidence-Based Expansion)
**선행 조건:** I-06 + I-07 완료
**우선순위:** E-series 1순위
**상태:** BLOCKED — I-06/I-07 완료 전 설계만 가능, 실행 로직 활성화 금지

#### 목적
I-07 MATCH 판정을 받은 후, 제한된 범위에서 실제 실행(주문/포지션/거래)을 수행한다.

#### 실행 전제 조건 (모두 AND)
1. I-06 승인 영수증 존재 + 미만료
2. I-07 판정 == MATCH
3. Execution Gate == OPEN
4. Preflight == READY
5. ops_score >= threshold
6. security_state != LOCKDOWN

#### 제한 범위
- Micro Live 단계 제한 (제36조): 최소 자본, 최소 전략, 최소 포지션
- 단일 주문 단위 실행
- 실행 전후 evidence 필수 기록
- 실행 실패 시 즉시 중단 + evidence 기록

#### 금지 범위
- I-06/I-07 미완료 상태에서 실행 로직 활성화 금지
- 승인 없는 실행 금지
- 만료 승인 기반 실행 금지
- DRIFT 상태 실행 금지
- 자본 확대 자동 실행 금지
- 승격 자동 실행 금지

---

## 서두 제약

- 카드 문서는 구현 승인 문서가 아니다.
- 카드 문서는 자동 실행 권한을 생성하지 않는다.
- 카드 문서는 상위 헌법에 없는 권한을 추가하지 않는다.
- I-series 상세 확장은 별도 승인 전까지 금지한다.

---

# Part A. O-series 상세 정의

---

## O-01 운영 대시보드 명세 고정

**대상 문서:** `docs/operations/dashboard_spec.md`
**역참조:** 제5조~제13조, 제41조~제42조
**우선순위:** 최우선

### 목적

운영 대시보드의 4구역 구성, 표시 원칙, 상태 문구, 시간 표준, 이중 잠금 구조를 구현 가능한 명세로 고정한다.

### 수용 기준

- 전역 상태 바 / 무결성 패널 / 거래 안전 패널 / 사고·증거 패널의 4구역이 명시되어 있어야 한다.
- 각 구역별 필수 표시 항목이 누락 없이 문서화되어 있어야 한다.
- 허용 상태 문구가 `HEALTHY / DEGRADED / UNVERIFIED / BRAKE / LOCKDOWN` 으로 제한되어 있어야 한다.
- 절대시간 우선 표기 원칙이 명시되어 있어야 한다.
- `System Healthy` 와 `Trading Authorized` 분리 표기 원칙이 명시되어 있어야 한다.
- Ops Score가 보조 지표이며 단독 권한을 발생시키지 않음을 명시해야 한다.
- Read-Only 제약이 문서에 명확히 선언되어 있어야 한다.

### 금지 범위

- 대시보드에서 상태 변경 기능을 허용하는 명세 추가 금지
- 거래 재개, 자본 확대, 강등 해제, 자동 승인 기능 명세 추가 금지
- 상위 헌법에 없는 신규 상태 문구 추가 금지
- unknown / stale / unverified 상태를 정상처럼 보이게 하는 낙관 표시 허용 금지
- System Healthy 와 Trading Authorized 를 단일 배지로 합치는 명세 금지

### 검수 항목

- 4구역 구조가 제6조와 일치하는가
- 전역 상태 바 필수 필드가 제7조와 일치하는가
- 무결성 패널 필드가 제8조와 일치하는가
- 거래 안전 패널 필드가 제9조와 일치하는가
- 사고·증거 패널 필드가 제10조와 일치하는가
- 상태 문구 제한이 제12조와 일치하는가
- 시간 표준이 제13조와 일치하는가
- Ops Score / 이중 잠금이 제41조~제42조와 충돌하지 않는가
- 새 권한 추가가 없는가

---

## O-02 알림 정책 명세 고정

**대상 문서:** `docs/operations/alert_policy.md`
**역참조:** 제14조~제22조
**우선순위:** 최우선

### 목적

알림 등급, 표준 필드, 발생 기준, 억제 규칙, 운영자 조치 문구를 운영 정책으로 고정한다.

### 수용 기준

- 허용 알림 등급이 `INFO / WARNING / CRITICAL / PROMOTION` 으로 제한되어 있어야 한다.
- 모든 알림의 표준 필드가 정의되어 있어야 한다.
- INFO, WARNING, CRITICAL, PROMOTION 각각의 대표 사건과 사용 목적이 구분되어 있어야 한다.
- WARNING 묶음 처리 규칙이 명시되어 있어야 한다.
- CRITICAL 상태 변화 즉시 전송 규칙이 명시되어 있어야 한다.
- 복구 알림 필수 규칙이 명시되어 있어야 한다.
- WARNING 이상 알림에 운영자 해야 할 일 필드가 필수임이 명시되어 있어야 한다.
- 알림이 자동 실행 권한을 가지지 않음을 문서에 명시해야 한다.

### 금지 범위

- 알림만으로 거래 승인 또는 상태 해제 허용 금지
- 알림만으로 자본 확대 또는 승격 실행 허용 금지
- 단순 로그를 알림으로 무분별하게 승격하는 정책 금지
- 상위 헌법에 없는 신규 알림 등급 추가 금지
- CRITICAL 복구 알림 생략 허용 금지

### 검수 항목

- 알림 등급이 제15조와 일치하는가
- INFO / WARNING / CRITICAL / PROMOTION 정의가 제16조~제19조와 일치하는가
- 표준 필드가 제20조와 일치하는가
- 알림 원칙이 제21조와 일치하는가
- 억제 규칙이 제22조와 일치하는가
- 자동 실행 권한 부여 문장이 없는가
- 운영자 조치 필드가 WARNING 이상에 강제되어 있는가

---

## O-03 Daily / Hourly / Event Check 명세 고정

**대상 문서:** `docs/operations/daily_hourly_event_checks.md`
**역참조:** 제23조~제31조
**우선순위:** 최우선

### 목적

Daily / Hourly / Event Check 3종 자동 점검의 항목, 결과 등급, 산출물, 금지 규칙을 운영 명세로 고정한다.

### 수용 기준

- Daily Check, Hourly Check, Event Check 3종이 명확히 분리되어 있어야 한다.
- 각 점검의 목적과 필수 항목이 구체적으로 정의되어 있어야 한다.
- 결과 등급이 `OK / WARN / FAIL / BLOCK` 으로 제한되어 있어야 한다.
- 점검 산출물로 콘솔 요약, 파일 evidence, 필요 시 알림 전송이 명시되어 있어야 한다.
- evidence 최소 필드가 정의되어 있어야 한다.
- 점검 불능 또는 evidence 누락 시 OK 처리 금지 규칙이 있어야 한다.
- Event Check가 복구 전 / 승격 전 차단 판단 용도임이 명시되어 있어야 한다.
- 점검이 복구 권한, 승격 권한을 직접 가지지 않음을 명시해야 한다.

### 금지 범위

- 자동 점검의 상태 임의 수정 허용 금지
- 거래 재개 자동 실행 금지
- 자본 확대 자동 실행 금지
- 점검 결과만으로 자동 승격 실행 금지
- 점검 결과만으로 LOCKDOWN 해제 허용 금지
- evidence 누락 PASS 허용 금지

### 검수 항목

- 목적과 원칙이 제23조~제24조와 일치하는가
- 3종 점검 분류가 제25조와 일치하는가
- Daily Check 항목이 제26조와 일치하는가
- Hourly Check 항목이 제27조와 일치하는가
- Event Check 트리거가 제28조와 일치하는가
- 결과 등급이 제29조와 일치하는가
- 산출물이 제30조와 일치하는가
- 금지 규칙이 제31조와 일치하는가
- Recovery Preflight 연계가 권한 분리 원칙을 훼손하지 않는가

---

## O-04 실거래 안정화 계획 명세 고정

**대상 문서:** `docs/operations/live_stabilization_plan.md`
**역참조:** 제32조~제40조
**우선순위:** 높음

### 목적

4단계 실거래 안정화 절차와 승격·강등 조건을 운영 계획으로 고정한다.

### 수용 기준

- Frozen Observation / Micro Live / Controlled Live / Evidence-Based Expansion 4단계가 명시되어 있어야 한다.
- 각 단계의 목적과 운영 제한 또는 운용 의도가 문서화되어 있어야 한다.
- 승격 조건이 제39조 기준에 맞게 명시되어 있어야 한다.
- 강등 조건이 제40조 기준에 맞게 명시되어 있어야 한다.
- 승격 금지 규칙이 별도로 명시되어 있어야 한다.
- 실거래 목적이 수익 극대화가 아니라 운영 신뢰도 축적임이 명시되어 있어야 한다.
- 자본 확대가 별도 심사 없이는 허용되지 않음을 명시해야 한다.
- Promotion Review 문서와의 연계가 정의되어 있어야 한다.

### 금지 범위

- 자동 승격 허용 금지
- 자동 자본 확대 허용 금지
- 치명 결함 이후 신뢰 유지 허용 금지
- 실거래 확대를 수익 목표 중심으로 서술하는 정책 금지
- 강등 조건 완화 또는 삭제 금지
- 관찰 단계 생략 허용 금지

### 검수 항목

- 목적과 원칙이 제32조~제33조와 일치하는가
- 4단계 구조가 제34조와 일치하는가
- Frozen Observation 정의가 제35조와 일치하는가
- Micro Live 정의가 제36조와 일치하는가
- Controlled Live 정의가 제37조와 일치하는가
- Evidence-Based Expansion 정의가 제38조와 일치하는가
- 승격 조건이 제39조와 일치하는가
- 강등 조건이 제40조와 일치하는가
- 자동 확대 또는 자동 승격 권한이 추가되지 않았는가

---

## O-05 Promotion Review 템플릿 고정

**대상 문서:** `docs/operations/promotion_review_template.md`
**역참조:** 제39조, 제45조
**우선순위:** 높음

### 목적

승격 심사 표준 양식과 필수 포함 항목, 판정 등급, 제한 승인 규칙을 템플릿으로 고정한다.

### 수용 기준

- 승격 심사의 사용 범위가 단계 전환 및 자본 확대 판단으로 명시되어 있어야 한다.
- 필수 포함 항목이 제45조 기준과 일치해야 한다.
- 판정 등급이 `APPROVED / APPROVED_WITH_LIMITS / DEFERRED / REJECTED` 로 정의되어 있어야 한다.
- `APPROVED_WITH_LIMITS` 의 제한 항목 명시 의무가 있어야 한다.
- 심사 완료가 자동 승격을 의미하지 않음을 명시해야 한다.
- 표준 양식이 Summary / Mandatory Evidence / Capital Decision / Conclusion 구조를 가져야 한다.
- 추가 권장 항목은 있어도 필수 항목을 대체하지 못함이 유지되어야 한다.

### 금지 범위

- 심사 템플릿에 자동 승격 실행 권한 부여 금지
- 자본 확대 자동 실행 권한 부여 금지
- LOCKDOWN 자동 해제 권한 부여 금지
- 미완료 evidence를 완료로 간주하는 표현 금지
- 제한 승인에서 제한 필드 생략 허용 금지

### 검수 항목

- 필수 포함 항목이 제45조와 일치하는가
- 승격 검토 조건이 제39조와 충돌하지 않는가
- 판정 등급 체계가 명확한가
- APPROVED가 자동 실행이 아님을 명시했는가
- APPROVED_WITH_LIMITS의 제한 필드가 존재하는가
- DEFERRED / REJECTED의 후속 처리 의미가 모호하지 않은가
- 새 권한 추가가 없는가

---

# Part B. I-series 기본 골격

---

## I-01 대시보드 반영

**목적:** `dashboard_spec.md` 기준으로 대시보드 코드 반영
**역참조:** 제5조~제13조, 제41조~제42조
**선행 조건:** O-01 완료
**우선순위:** O-series 완료 후 1순위

---

## I-02 알림 규칙 반영

**목적:** `alert_policy.md` 기준으로 알림 코드 반영
**역참조:** 제14조~제22조
**선행 조건:** O-02 완료
**우선순위:** O-series 완료 후 2순위

---

## I-03 자동 점검 골격 반영

**목적:** `daily_hourly_event_checks.md` 기준으로 점검 코드 골격 반영
**역참조:** 제23조~제31조
**선행 조건:** O-03 완료
**우선순위:** O-series 완료 후 3순위

---

## I-04 Recovery Preflight / Incident Playback 반영

**목적:** Recovery Preflight 카드(제43조)와 Incident Playback 타임라인(제44조) 코드 반영
**역참조:** 제43조~제44조
**선행 조건:** O-03 완료, I-03 착수 이후
**우선순위:** O-series 완료 후 4순위

---

## I-05 Ops Score / Trading Authorized 이중 잠금 반영

**목적:** Ops Score 4축(제41조)과 이중 잠금(제42조) 코드 반영
**역참조:** 제41조~제42조
**선행 조건:** O-01 완료, I-01 착수 이후
**우선순위:** O-series 완료 후 5순위

---

# Part C. 공통 금지 규칙

- 상위 헌법과 충돌하는 새 원칙 추가 금지
- 자동 승인 / 자동 승격 / 자동 자본 확대 / 자동 해제 권한 추가 금지
- 운영 표면을 제어 표면으로 변환하는 명세 금지
- 범위 확장 금지
- 카드 문서는 구현 승인 문서가 아니다.
- 카드 문서는 자동 실행 권한을 생성하지 않는다.
- 카드 문서는 상위 헌법에 없는 권한을 추가하지 않는다.
- I-series 상세 확장은 별도 승인 전까지 금지한다.

---

# Part D. 우선순위 및 선행조건 표

| 순위 | 카드 | 선행 조건 |
|------|------|-----------|
| 1 | O-01~O-05 | 상위 헌법 고정 |
| 2 | I-01 | O-01 |
| 3 | I-02 | O-02 |
| 4 | I-03 | O-03 |
| 5 | I-04 | O-03, I-03 |
| 6 | I-05 | O-01, I-01 |

---

I-series 상세 정의는 별도 승인 전까지 확장하지 않으며, 본 문서는 기본 골격 기록에 한정한다.
