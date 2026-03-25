# Tab 3 카드 설계 봉인 — C-01~C-09 권한 경계 정의

---

## 공통 원칙 (전 카드 적용)

1. Tab 3는 자동 실행 계층이 아니다
2. AI 단독 결정 금지
3. 승인 없는 실행 금지
4. 정책 위반 실행 금지
5. Pipeline 우회 금지
6. Ledger 우회 금지
7. Evidence 없는 실행 금지
8. 기존 값 기반 확인 우선
9. Write는 controlled write만 허용
10. 모든 write는 preview → approval → evidence → result → audit 흐름을 따라야 함

---

## Tab 3 카드 분류표

| 카드 | 소속 계층 | 분류 | 구현 우선순위 | 위험도 |
|------|----------|------|-------------|--------|
| C-01 Execution Status | Control Context | **Safe Card** | 1순위 | LOW |
| C-02 Approval State | Control Context | **Safe Card** | 1순위 | LOW |
| C-03 Policy Gate | Control Context | **Safe Card** | 1순위 | LOW |
| C-04 Manual Action | Action Console | **Controlled Write** | 3순위 (최후) | **CRITICAL** |
| C-05 Action Preview | Action Console | **Safe Card** | 2순위 | LOW |
| C-06 Action Result | Action Console | **Safe Card** | 2순위 | LOW |
| C-07 Action Log | Execution Log | **Safe Card** | 1순위 | LOW |
| C-08 Error Log | Execution Log | **Safe Card** | 1순위 | LOW |
| C-09 Audit Log | Execution Log | **Safe Card** | 1순위 | LOW |

> Safe Card: 8개 / Controlled Write Card: 1개 (C-04만)

---

## C-01 Execution Status

| 항목 | 정의 |
|------|------|
| **목적** | 현재 실행 체인(I-03~E-03)의 통과 상태를 요약 표시 |
| **답하는 질문** | 지금 실행 체인이 통과 가능한가? |
| **소속 계층** | Control Context |
| **입력 데이터** | ops-executor, ops-activation, ops-dispatch, ops-gate, ops-preflight, ops-safety-summary |
| **출력 표시** | E-01 state, E-02 activation decision, E-03 dispatch decision, executor_activated, pipeline 차단 지점 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 |
| **실행 전제 조건** | 없음 (표시 전용) |
| **로그/Audit** | 표시 행위에 대한 로그 불필요 |
| **금지** | 상태 변경, executor 활성화, 실행 트리거 |
| **분류** | **Safe Card** |
| **초기 구현** | 권장 (1순위) |
| **이유** | 순수 상태 표시. 기존 Tab 3 패널과 유사하나 통합 요약 관점 |

---

## C-02 Approval State

| 항목 | 정의 |
|------|------|
| **목적** | I-06 승인 영수증 상태 + 만료 여부 + 차단 사유 표시 |
| **답하는 질문** | 현재 승인이 유효한가? 승인이 필요한가? 왜 거부되었는가? |
| **소속 계층** | Control Context |
| **입력 데이터** | ops-approval (기존 endpoint) |
| **출력 표시** | approval_decision, scope, approved_by, expiry, rejection_reasons, 7필드 상태 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 (승인 상태를 보여주는 카드이지, 승인을 수행하는 카드가 아님) |
| **실행 전제 조건** | 없음 (표시 전용) |
| **로그/Audit** | 표시 행위 로그 불필요 |
| **금지** | 승인 발행, 승인 취소, 만료 연장, scope 변경 |
| **분류** | **Safe Card** |
| **초기 구현** | 권장 (1순위) |
| **이유** | 승인 상태 확인은 실행 전 필수 단계. 읽기만 수행 |

---

## C-03 Policy Gate

| 항목 | 정의 |
|------|------|
| **목적** | I-07 정책 일치 여부 + 조건 상세 + 허용 범위 표시 |
| **답하는 질문** | 현재 정책이 승인과 일치하는가? 정책 차단 코드는? |
| **소속 계층** | Control Context |
| **입력 데이터** | ops-policy (기존 endpoint) |
| **출력 표시** | policy_decision (MATCH/DRIFT), drift_reasons, approval_hash 비교, scope 일치 여부 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 |
| **실행 전제 조건** | 없음 (표시 전용) |
| **로그/Audit** | 표시 행위 로그 불필요 |
| **금지** | 정책 수정, 정책 우회, drift 무시 처리 |
| **분류** | **Safe Card** |
| **초기 구현** | 권장 (1순위) |
| **이유** | 정책 확인은 실행 전 필수 게이트. 읽기만 수행 |

---

## C-04 Manual Action

| 항목 | 정의 |
|------|------|
| **목적** | 운영자가 수동으로 실행을 트리거하는 유일한 카드 |
| **답하는 질문** | 모든 조건이 충족되었을 때, 운영자가 실행을 시작할 수 있는가? |
| **소속 계층** | Action Console |
| **입력 데이터** | ops-safety-summary (전체 조건 집계) |
| **출력 표시** | 실행 트리거 버튼 (조건 미충족 시 비활성) + 실행 대상 요약 |
| **Write 가능** | **가능** (Controlled Write) |
| **승인 필요** | **필수** (I-06 APPROVED + 미만료) |
| **실행 전제 조건** | **9단계 전체 통과 필수**: |

### C-04 실행 전제 조건 (9단계 체인)

| # | 조건 | 확인 소스 | 실패 시 |
|---|------|----------|--------|
| 1 | Pipeline Ready | I-03 check ≠ BLOCK | 버튼 비활성 |
| 2 | Preflight Ready | I-04 decision = READY | 버튼 비활성 |
| 3 | Gate Open | I-05 decision = OPEN | 버튼 비활성 |
| 4 | Approval OK | I-06 decision = APPROVED + 미만료 | 버튼 비활성 |
| 5 | Policy OK | I-07 decision = MATCH | 버튼 비활성 |
| 6 | Risk OK | RiskFilter 통과 | 버튼 비활성 |
| 7 | Auth OK | trading_authorized = true + lockdown inactive | 버튼 비활성 |
| 8 | Scope OK | execution_scope ⊆ approval_scope | 버튼 비활성 |
| 9 | Evidence Present | evidence chain I-03~I-07 완전 | 버튼 비활성 |

**9개 중 1개라도 실패 → 실행 완전 금지. Fail-closed.**

### C-04 가시성/실행 분리

| 단계 | 조건 |
|------|------|
| **표시 가능** | 항상 (카드 자체는 항상 보임) |
| **Preview 가능** | 1~5번 통과 시 (실행 대상 미리보기) |
| **Action 가능** | 9단계 **전체** 통과 시에만 |

| 항목 | 정의 |
|------|------|
| **로그/Audit** | **필수** — 모든 실행 시도는 evidence bundle로 기록. 성공/실패/취소 모두 기록. |
| **금지** | 자동 트리거, 승인 우회, 정책 우회, pipeline 건너뛰기, scope 초과, evidence 없는 실행, 버튼 강제 활성화 |
| **분류** | **Controlled Write Card** |
| **초기 구현** | **비권장** (3순위 — 최후 구현) |
| **이유** | Tab 3에서 유일한 write 카드. 가장 높은 위험도. Safe Card 전부 구현 + 검증 완료 후에만 착수. |

---

## C-05 Action Preview

| 항목 | 정의 |
|------|------|
| **목적** | 실행 전에 어떤 action이 준비되었는지 read-only로 미리보기 |
| **답하는 질문** | 지금 실행하면 무엇이 발생하는가? (영향 범위, 대상, scope) |
| **소속 계층** | Action Console |
| **입력 데이터** | ops-executor, ops-activation, approval scope/target |
| **출력 표시** | 실행 대상 (exchange, symbol, scope), 예상 action type, evidence chain 요약 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 (미리보기 전용) |
| **실행 전제 조건** | 없음 (표시 전용, 단 C-04 전제 1~5 통과 시 상세 preview 활성) |
| **로그/Audit** | Preview 조회 자체는 로그 불필요 |
| **금지** | 실행 트리거, 대상 변경, scope 수정, preview를 실행 승인으로 간주 |
| **분류** | **Safe Card** |
| **초기 구현** | 2순위 |
| **이유** | C-04 실행 전 필수 확인 단계. 실행 자체는 수행하지 않음 |

---

## C-06 Action Result

| 항목 | 정의 |
|------|------|
| **목적** | 직전 실행 결과(성공/실패/부분 실행) 표시 |
| **답하는 질문** | 마지막 실행은 성공했는가? 실패 사유는? |
| **소속 계층** | Action Console |
| **입력 데이터** | 실행 결과 evidence bundle, execution receipt |
| **출력 표시** | execution_state, fail_reasons, target, scope, evidence_id, 실행 시각 |
| **Write 가능** | **불가** (read-only — 결과를 보여주는 카드) |
| **승인 필요** | 불필요 |
| **실행 전제 조건** | 없음 (표시 전용) |
| **로그/Audit** | 결과 자체가 이미 evidence로 기록됨. 조회 로그 불필요 |
| **금지** | 결과 수정, 실패 상태 덮어쓰기, 재실행 트리거 |
| **분류** | **Safe Card** |
| **초기 구현** | 2순위 |
| **이유** | C-04 실행 후 결과 확인 카드. 읽기 전용 |

---

## C-07 Action Log

| 항목 | 정의 |
|------|------|
| **목적** | 전체 실행 이력 (시간순) |
| **답하는 질문** | 지금까지 어떤 실행이 있었는가? |
| **소속 계층** | Execution Log |
| **입력 데이터** | evidence_store (actor: e01/e02/e03), execution receipts |
| **출력 표시** | 실행 ID, 시각, scope, target, decision, result 리스트 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 |
| **실행 전제 조건** | 없음 |
| **로그/Audit** | 이미 evidence store에 기록됨. 별도 로그 불필요 |
| **금지** | 로그 삭제, 로그 수정, 로그 필터링을 통한 은닉 |
| **분류** | **Safe Card** |
| **초기 구현** | 권장 (1순위) |
| **이유** | 순수 이력 조회. 감사 기반 |

---

## C-08 Error Log

| 항목 | 정의 |
|------|------|
| **목적** | 실행 오류/차단/실패 사유 이력 |
| **답하는 질문** | 어떤 실행이 왜 실패했는가? |
| **소속 계층** | Execution Log |
| **입력 데이터** | evidence_store (fail_reasons), execution receipts (PRECONDITION_FAILED, SCOPE_MISMATCH 등) |
| **출력 표시** | 실패 ID, 시각, fail_reasons, 차단 단계, 사유 코드 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 |
| **실행 전제 조건** | 없음 |
| **로그/Audit** | 이미 evidence에 기록됨 |
| **금지** | 오류 삭제, 오류 은닉, 사유 수정 |
| **분류** | **Safe Card** |
| **초기 구현** | 권장 (1순위) |
| **이유** | 오류 투명성 필수. 감사 기반 |

---

## C-09 Audit Log

| 항목 | 정의 |
|------|------|
| **목적** | 전체 감사 증적 (evidence bundle) 조회 |
| **답하는 질문** | 어떤 증거가 기록되었는가? 증거 체인이 완전한가? |
| **소속 계층** | Execution Log |
| **입력 데이터** | evidence_store 전체 (모든 actor, 모든 trigger) |
| **출력 표시** | bundle_id, actor, action, trigger, timestamp, before/after state, artifacts 요약 |
| **Write 가능** | **불가** (read-only) |
| **승인 필요** | 불필요 |
| **실행 전제 조건** | 없음 |
| **로그/Audit** | 이 카드 자체가 audit 조회 카드 |
| **금지** | evidence 삭제, evidence 수정, bundle 위조, 필터를 통한 은닉 |
| **분류** | **Safe Card** |
| **초기 구현** | 권장 (1순위) — **필수 증거 카드** |
| **이유** | "No Evidence, No Power" 원칙의 최종 검증 지점 |

---

## 계층별 구현 순서 제안

### 1순위: Safe Card (즉시 구현 가능)

| 순서 | 카드 | 이유 |
|------|------|------|
| 1 | C-01 Execution Status | 실행 상태 확인 기반 |
| 2 | C-02 Approval State | 승인 상태 확인 |
| 3 | C-03 Policy Gate | 정책 확인 |
| 4 | C-07 Action Log | 이력 조회 |
| 5 | C-08 Error Log | 오류 조회 |
| 6 | C-09 Audit Log | 감사 증적 (필수) |

### 2순위: Safe Card (C-04 연계)

| 순서 | 카드 | 이유 |
|------|------|------|
| 7 | C-05 Action Preview | C-04 전 미리보기 |
| 8 | C-06 Action Result | C-04 후 결과 확인 |

### 3순위: Controlled Write Card (최후)

| 순서 | 카드 | 이유 |
|------|------|------|
| 9 | C-04 Manual Action | **유일한 write 카드. Safe Card 8개 전부 완료 후에만 착수.** |

---

*문서 확정 시각: 2026-03-26*
*코드 수정: 없음*
*이 문서는 Tab 3 카드별 권한 경계 봉인 문서이다.*
