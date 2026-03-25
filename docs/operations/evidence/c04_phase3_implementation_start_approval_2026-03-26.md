# C-04 Phase 3 Implementation Start Approval — 2026-03-26

**evidence_id**: C04-PHASE3-IMPL-START-2026-03-26
**date**: 2026-03-26
**approval_type**: IMPLEMENTATION_START_APPROVAL
**auto_repair_performed**: false

---

## Approval Purpose

"This approval authorizes implementation start only for the minimum sealed boundary of C-04. This approval does NOT authorize activation, execution, mutation, or handler enable."

- C-04는 Controlled Write Card이므로 최소 구현도 일반 UI처럼 바로 시작할 수 없다
- 최소 구현은 실행 오픈이 아니라 통제 경계의 최소 코드화다
- 최소 구현 착수 승인 없이는 production code 수정조차 허용되지 않는다
- 최소 구현 착수 승인 이후에도 activation과 execution은 여전히 별도 승인 대상이다

Implementation Start Approval ≠ Activation Approval
Implementation Start Approval ≠ Execution Approval
Implementation Start Approval ≠ Operational Approval

---

## Approval Scope (IS-1 ~ IS-8 Only)

| # | 허용 항목 | 설명 |
|---|----------|------|
| IS-1 | Read-only skeleton | sealed 카드 내부에 block-reason/status read-only 영역 추가 |
| IS-2 | Block / fail slots | block code를 표시할 수 있는 read-only 영역 |
| IS-3 | Evidence linkage | 5필드 존재 여부 표시 |
| IS-4 | 9-stage chain display | 각 단계 pass/fail/unknown read-only 표시 |
| IS-5 | Fail-closed default | 데이터 없으면 Blocked / Unavailable 표시 |
| IS-6 | Disabled handler | no-op handler. 클릭해도 무반응 |
| IS-7 | Minimal schema | read-only state schema만 |
| IS-8 | _renderC04 read-only renderer | Safe Card 패턴 동일. action trigger 없음 |

이번 승인은 **구현 착수 허가**이지 **기능 허가**가 아니다.

---

## Prohibition Scope

| # | 금지 항목 |
|---|----------|
| P-1 | Write endpoint (POST/PUT/PATCH/DELETE) |
| P-2 | Action trigger |
| P-3 | Execute button (enabled) |
| P-4 | Dispatch wiring |
| P-5 | Rollback execution |
| P-6 | Background action (celery/worker) |
| P-7 | Mutation (approval/policy/risk/state) |
| P-8 | Optimistic enable |
| P-9 | Scheduler/cron trigger |
| P-10 | Engine/executor call |
| P-11 | Transport/store write |
| P-12 | API write route |
| P-13 | UI enable |
| P-14 | State change |
| P-15 | Hidden handler |
| P-16 | Agent-triggered action |

이 중 하나라도 열리면 승인 위반이다.

---

## Approval Checklist (16/16 PASS Required)

| # | 항목 | 상태 | 근거 |
|---|------|------|------|
| 1 | Contract Seal 완료 | **PASS** | c04_manual_action_contract_seal.md |
| 2 | Prereq Resolution 완료 | **PASS** | c04_manual_action_prereq_resolution.md |
| 3 | Test Strategy Seal 완료 | **PASS** | c04_manual_action_test_strategy_seal.md |
| 4 | Phase 1 test wall 완료 (119 tests) | **PASS** | c04_phase1_testcode_receipt_2026-03-26.md |
| 5 | Phase 2 Review GO | **PASS** | c04_phase2_review_2026-03-26.md |
| 6 | Minimum Implementation Scope GO | **PASS** | c04_minimum_implementation_scope.md |
| 7 | Phase 3 Review GO | **PASS** | c04_phase3_review_2026-03-26.md |
| 8 | Production code 0 baseline | **PASS** | git status 확인 |
| 9 | Write path 0 baseline | **PASS** | 현재 endpoint 0 |
| 10 | Sealed/disabled baseline | **PASS** | t3sc-sealed + "Not enabled" |
| 11 | Fail-closed default 유지 가능 | **PASS** | IS-5 명시 |
| 12 | Visible ≠ executable 유지 가능 | **PASS** | IS-6 no-op handler |
| 13 | Preview ≠ action allowed 유지 가능 | **PASS** | out-of-scope OS-5 |
| 14 | Out-of-scope exclusion 강도 | **PASS** | 16 prohibitions |
| 15 | Test wall preservation 가능 | **PASS** | 119 tests, _renderC04 전환만 |
| 16 | Regression 영향 비차단 | **PASS** | 기존 12 failures isolated |

**16/16 PASS — 승인 조건 충족**

---

## Test Wall Maintenance

"Implementation may adapt to the test wall, but the test wall must not be relaxed to accommodate unsafe implementation."

- 기존 119 tests는 유지되어야 한다
- 테스트를 느슨하게 해서 구현을 수용하면 안 된다
- 테스트 삭제 금지
- 테스트 약화 금지
- 목적 전환이 필요한 테스트는 "완화"가 아니라 "동일 통제 목적의 재정의"여야 한다
- visible ≠ executable 유지
- preview ≠ action allowed 유지
- fail-closed default 유지
- sealed-state preservation 유지
- no write path 유지
- no hidden trigger 유지

---

## _renderC04 Conditional Principle

### 현재 상태

기존 테스트 1건 (`test_no_render_c04_function_added`)은 `_renderC04`의 **부재**를 invariant로 확인한다.

### 허용 가능한 전환

`_renderC04` 부재 확인 → `_renderC04`가 존재하더라도 다음을 **모두** 만족하는지 확인:

1. disabled only
2. no action trigger
3. no execution path
4. no enabled controls
5. sealed state preserved
6. no optimistic wording
7. read-only rendering only

### 이것은 테스트 완화가 아니다

이것은 **비활성 renderer 통제 강화**다.

- 부재 확인 → 존재하되 비활성 확인으로 전환
- 통제 수준은 유지되거나 강화됨
- execution path가 열리면 테스트는 FAIL해야 함

### 금지

- `_renderC04` 도입을 이유로 실행 가능 경로 허용
- 테스트 삭제
- 테스트 약화
- renderer 존재 = implementation completion 해석

---

## Post-Approval Seal Conditions

구현이 시작되어도 아래 봉인 조건은 **그대로 유지**된다.

| # | 봉인 조건 |
|---|----------|
| S-1 | C-04 기본 disabled |
| S-2 | C-04 기본 sealed |
| S-3 | Fail-closed default |
| S-4 | Phase 4 = activation 승인 필요 |
| S-5 | Phase 5 = execution 승인 필요 |
| S-6 | No write until Phase 5 |
| S-7 | No enable until Phase 4 |
| S-8 | No handler until Phase 4 |
| S-9 | No endpoint until Phase 4 |
| S-10 | No dispatch until Phase 5 |

구현이 시작되어도 봉인은 계속된다.

---

## Cancellation Rules

"Implementation-start approval is conditional and reversible."

아래 중 하나라도 발생하면 **승인 즉시 취소**:

| # | 취소 사유 |
|---|----------|
| C-1 | Write path 추가됨 |
| C-2 | 버튼 enabled 됨 |
| C-3 | 테스트 벽 완화됨 |
| C-4 | Fail-closed 제거됨 |
| C-5 | Sealed class 제거됨 |
| C-6 | Handler enabled 됨 |
| C-7 | Endpoint 추가됨 |
| C-8 | Dispatch wiring 추가됨 |
| C-9 | Out-of-scope 침범 발생 |
| C-10 | Hidden trigger 발견됨 |

---

## Next Step

이번 승인 후 허용되는 다음 단계는 **오직 하나**:

→ **C-04 최소 구현 실행 프롬프트**

이 구현도 sealed/disabled/write-path-zero 범위 안에 있어야 한다.

명시적 금지:
- C-04 활성화 프롬프트
- C-04 실행 허가 프롬프트
- C-04 운영 허가 프롬프트
- Dispatch/rollback 연결 프롬프트

---

## Constitution Comparison

| 요구 조항 | 반영 문장 |
|----------|----------|
| Implementation start ≠ activation | §Approval Purpose 명시 |
| Approval scope = IS-1~IS-8 only | §Approval Scope 8항목 |
| Prohibition = 16 items | §Prohibition Scope P-1~P-16 |
| Checklist 16/16 PASS | §Approval Checklist |
| Test wall preserved | §Test Wall Maintenance |
| _renderC04 = control reinforcement | §_renderC04 Conditional Principle |
| Seal conditions maintained | §Post-Approval Seal S-1~S-10 |
| Approval reversible | §Cancellation Rules C-1~C-10 |

**Scope check**: PASS — IS-1~IS-8 범위 내 read-only skeleton만 허용
**Seal check**: PASS — S-1~S-10 봉인 유지
**Write path check**: PASS — 0개 유지 보장, P-1~P-16 금지
**Test wall check**: PASS — 119 tests 유지, 전환만 허용 (완화 금지)

---

## Final Judgment

**GO**

16/16 승인 조건 충족. 최소 구현 범위는 IS-1~IS-8로 충분히 좁고, write path 0개 유지가 보장되며, 봉인 조건 10항이 유지된다. Activation/execution/operational use는 여전히 금지.
