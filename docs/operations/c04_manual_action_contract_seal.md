# C-04 Manual Action Contract Seal

---

## 공식 정의

> **C-04 Manual Action은 Tab 3의 유일한 controlled write 진입점이며, 사전 정의된 실행 체인과 승인/정책/증적 조건을 모두 충족한 경우에만 제한적으로 활성화될 수 있는 수동 실행 카드이다.**

### 절대 금지 (9항목)

| # | 금지 |
|---|------|
| 1 | 자동 실행 금지 |
| 2 | 승인 없이 실행 금지 |
| 3 | 정책 위반 실행 금지 |
| 4 | 리스크 미확인 실행 금지 |
| 5 | auth 미충족 실행 금지 |
| 6 | evidence 없는 실행 금지 |
| 7 | scope 불명확 실행 금지 |
| 8 | pipeline/preflight/gate 미통과 실행 금지 |
| 9 | AI 단독 판단 실행 금지 |

---

## 1. C-04 목적 정의

- C-04는 **"실행 버튼"이 아니라 "제한적 수동 실행 통제점"**이다
- C-04는 사용자의 의도를 그대로 통과시키는 도구가 **아니다**
- C-04는 오직 **이미 검증된 preview를 기반으로만** action을 수행할 수 있다
- C-04는 preview 없는 임의 action을 **생성할 수 없다**
- C-04는 **controlled write boundary**다

---

## 2. C-04가 답하는 질문

| 질문 |
|------|
| 지금 수동 실행이 허용되는가 |
| 어떤 조건 때문에 아직 막혀 있는가 |
| 현재 preview가 action 가능한 수준인가 |
| 실행 시 어떤 evidence와 audit가 남는가 |
| 실행 후 결과는 어디에 기록되는가 |

---

## 3. 표시 가능 / Preview 가능 / Action 가능 분리

| 단계 | 조건 | 의미 |
|------|------|------|
| **A. 표시 가능** | 항상 | 카드 자체는 항상 보임. 단, 비활성/봉인 상태 가능 |
| **B. Preview 가능** | 9단계 중 1~5번 통과 | 실행 대상 미리보기 가능. **preview 존재 ≠ action 허용** |
| **C. Action 가능** | 9단계 **전체** 통과 | 실제 실행 가능. **가장 엄격한 조건** |

> **"보이는 것" ≠ "실행 가능한 것"**
> **"preview 존재" ≠ "action 허용"**

---

## 4. 9단계 실행 체인

**단 하나라도 실패 → action 금지. Fail-closed.**

| # | 조건 | 의미 | 데이터 출처 | 실패 차단 코드 | UI 표시 | Fail-closed |
|---|------|------|-----------|--------------|--------|------------|
| 1 | Pipeline Ready | I-03 check ≠ BLOCK | `ops_summary.latest_check_grade` | `PIPELINE_NOT_READY` | "Blocked by check" | 버튼 비활성 |
| 2 | Preflight Ready | I-04 decision = READY | `ops_summary.preflight_decision` | `PREFLIGHT_NOT_READY` | "Preflight not ready" | 버튼 비활성 |
| 3 | Gate Open | I-05 decision = OPEN | `ops_summary.gate_decision` | `GATE_CLOSED` | "Gate closed" | 버튼 비활성 |
| 4 | Approval OK | I-06 APPROVED + 미만료 | `ops_summary.approval_decision` | `APPROVAL_REQUIRED` | "Approval required" | 버튼 비활성 |
| 5 | Policy OK | I-07 decision = MATCH | `ops_summary.policy_decision` | `POLICY_BLOCKED` | "Policy not matched" | 버튼 비활성 |
| 6 | Risk OK | RiskFilter 통과 | RiskFilter runtime | `RISK_NOT_OK` | "Risk check failed" | 버튼 비활성 |
| 7 | Auth OK | trading_authorized + lockdown inactive | `ops_summary.trading_authorized` | `AUTH_NOT_OK` | "Auth not satisfied" | 버튼 비활성 |
| 8 | Scope OK | execution_scope ⊆ approval_scope | scope 비교 로직 | `SCOPE_NOT_OK` | "Scope mismatch" | 버튼 비활성 |
| 9 | Evidence Present | I-03~I-07 증거 체인 완전 | evidence_store | `EVIDENCE_MISSING` | "Evidence not present" | 버튼 비활성 |

---

## 5. Input Contract

### 상태 입력

| 입력 | 소스 | 필수 |
|------|------|------|
| pipeline_state | ops-safety-summary | ✓ |
| preflight_decision | ops-safety-summary | ✓ |
| gate_decision | ops-safety-summary | ✓ |
| approval_decision | ops-safety-summary | ✓ |
| policy_decision | ops-safety-summary | ✓ |
| trading_authorized | ops-safety-summary | ✓ |
| lockdown_state | ops-safety-summary | ✓ |
| ops_score | ops-safety-summary | ✓ |
| conditions_met | ops-safety-summary | ✓ |

### Preview 입력

| 입력 | 소스 | 필수 |
|------|------|------|
| action_type | C-05 preview | ✓ |
| target (exchange, symbol) | C-05 preview | ✓ |
| scope | C-05 preview | ✓ |
| linked_preview_id | C-05 preview | ✓ |

### 실행 컨텍스트 입력

| 입력 | 소스 | 필수 |
|------|------|------|
| actor | 운영자 식별 | ✓ |
| timestamp | 시스템 시각 | ✓ |
| trace_id | 실행 추적 ID | ✓ |

### 보호 입력

| 입력 | 소스 | 필수 |
|------|------|------|
| block_codes | 9단계 체인 결과 | ✓ |
| forbidden_conditions | ForbiddenLedger | ✓ |
| policy_version | I-07 | ✓ |
| approval_source | I-06 | ✓ |

### 입력 규칙

- 없는 값은 추정 금지
- 임시 mock 입력으로 실행 허용 금지
- preview 없이 action 허용 금지
- linked_preview_id 없는 실행 금지

---

## 6. Output Contract

### UI 출력

| 결과 | 표시 |
|------|------|
| 성공 | C-06 Action Result에 success 표시 |
| 차단 | 차단 코드 + 사유 표시 |
| 실패 | 실패 코드 + 오류 상세 표시 |
| 불가 | unavailable / not enabled |

### 로그 출력

| 결과 | C-07 Action Log | C-08 Error Log | C-09 Audit Log |
|------|----------------|----------------|----------------|
| 성공 | ✓ 기록 | - | ✓ 기록 |
| 차단 | - | ✓ 기록 | ✓ 기록 |
| 실패 | ✓ 기록 | ✓ 기록 | ✓ 기록 |

### 결과 연결

| 연결 | 필수 |
|------|------|
| action_result → evidence_id | ✓ |
| action_result → trace_id | ✓ |
| action_result → linked_preview_id | ✓ |
| action_result → approval_id | ✓ |
| action_result → policy_snapshot_id | ✓ |

### 출력 규칙

- 성공해도 audit 기록 **필수**
- 실패해도 audit 기록 **필수**
- 차단되어도 최소 error/audit 흔적 **필수**
- **"아무 기록도 남지 않는 실행 시도" 금지**

---

## 7. Fail-Closed 규칙

| 상태 | 판정 |
|------|------|
| 승인 상태 unknown | **blocked** |
| policy 상태 unknown | **blocked** |
| risk 상태 unknown | **blocked** |
| auth 상태 unknown | **blocked** |
| scope 상태 unknown | **blocked** |
| evidence missing | **blocked** |
| preview missing | **blocked** |
| linked ids 불완전 | **blocked** |
| runtime 미연결 | **unavailable 또는 blocked** |
| optimistic enable | **금지** |

### 허용 문구

- blocked by approval
- blocked by policy
- preview unavailable
- evidence not present
- not enabled
- unavailable in current phase

### 금지 문구

- probably executable
- should proceed
- looks safe
- ready to run
- recommended action

---

## 8. 차단 코드 / 실패 코드 체계

### Block Code (사전 차단)

| 코드 | 의미 | 단계 |
|------|------|------|
| `MANUAL_ACTION_DISABLED` | C-04 비활성 단계 | 봉인 |
| `PREVIEW_MISSING` | preview 없음 | 입력 |
| `PIPELINE_NOT_READY` | I-03 check BLOCK/FAIL | 1 |
| `PREFLIGHT_NOT_READY` | I-04 ≠ READY | 2 |
| `GATE_CLOSED` | I-05 ≠ OPEN | 3 |
| `APPROVAL_REQUIRED` | I-06 ≠ APPROVED 또는 만료 | 4 |
| `POLICY_BLOCKED` | I-07 ≠ MATCH | 5 |
| `RISK_NOT_OK` | RiskFilter 미통과 | 6 |
| `AUTH_NOT_OK` | trading_authorized ≠ true | 7 |
| `SCOPE_NOT_OK` | scope 불일치 | 8 |
| `EVIDENCE_MISSING` | 증거 체인 불완전 | 9 |
| `TRACE_INCOMPLETE` | trace/linked id 불완전 | 입력 |

### Fail Code (실행 후 실패)

| 코드 | 의미 |
|------|------|
| `EXECUTION_REJECTED` | 실행 체인 내부 거부 |
| `EXECUTION_FAILED` | 실행 중 오류 |
| `EXECUTION_TIMEOUT` | 실행 시간 초과 |
| `EXECUTION_ROLLBACK` | 실행 롤백 |

### 규칙

- Block code = 사전 차단 (action 전)
- Fail code = 실행 실패 (action 후)
- UI 문구와 로그 코드 매핑 가능

---

## 9. 로그 / Evidence / Audit 의무

| 의무 | 필수 |
|------|------|
| action log 기록 | ✓ (모든 성공/실패) |
| error log 기록 | ✓ (모든 차단/실패) |
| audit log 기록 | ✓ (**모든 시도**) |
| linked_preview_id 기록 | ✓ |
| actor 기록 | ✓ |
| timestamp 기록 | ✓ |
| policy/approval/scope linkage 기록 | ✓ |
| evidence bundle 생성 | ✓ |

### 절대 규칙

- evidence 없이 실행 금지
- audit 없는 실행 금지
- traceability 없는 실행 금지

---

## 10. 연계 카드

| 카드 | C-04와의 관계 |
|------|-------------|
| C-05 Action Preview | 실행 전 원본 preview. C-04는 C-05의 preview_id를 참조해야만 action 가능 |
| C-06 Action Result | 실행 후 결과 표시. C-04 action의 결과가 C-06에 반영 |
| C-07 Action Log | action history. C-04 모든 실행이 C-07에 기록 |
| C-08 Error Log | 차단/실패 내역. C-04 차단/실패가 C-08에 기록 |
| C-09 Audit Log | 감사 증적. C-04 **모든 시도**가 C-09에 기록 |

> C-04는 고립된 버튼이 아니라, **Tab 3 Safe Card 체인 위에서만 열릴 수 있는 카드**이다.

---

## 11. 구현 선행조건

C-04 구현 전 반드시 결정/확정되어야 할 사항:

| # | 선행조건 | 상태 |
|---|---------|------|
| 1 | RiskFilter runtime 연결 여부 | **확정** (R-1: ops-safety-summary 값 기반) |
| 2 | approval source 확정 | **확정** (ops-safety-summary.approval_id) |
| 3 | policy source 확정 | **확정** (ops-safety-summary.policy_decision) |
| 4 | evidence present 판정 기준 | **확정** (R-2: 6개 ID non-null + non-fallback) |
| 5 | scope ok 판정 기준 | **확정** (execution_scope ⊆ approval_scope) |
| 6 | trace_id / preview_id linkage 기준 | **확정** (R-2: linked_preview_id + trace_id UUID) |
| 7 | 실행 실패 시 rollback/receipt 처리 범위 | **확정** (R-3: 5-class + receipt 필드 정의) |
| 8 | disable 상태 UI 표준 (봉인 vs 비활성 vs 숨김) | 확정 (t3sc-sealed) |
| 9 | action 결과 저장 최소 필드 | **미확정** |
| 10 | Safe Card 8개 기준선 안정 | **확정 (339 passed)** |

**위 미확정 항목이 모두 확정되기 전에는 C-04 구현 금지.**

---

## 12. 봉인 해제 조건

C-04를 구현 단계로 넘기기 위한 조건:

| # | 조건 | 현재 |
|---|------|------|
| 1 | Safe Card 8개 기준선 유지 (339+ passed) | ✓ |
| 2 | 9단계 체인 데이터 소스 전부 확정 | **확정** (prereq_resolution R-1) |
| 3 | Block/Fail code 체계 확정 | ✓ (본 문서) |
| 4 | Audit/Evidence linkage 방식 확정 | **확정** (prereq_resolution R-2) |
| 5 | Preview/Result/Log 카드 연계 검증 완료 | **확정** (Safe Card 8개 구현 완료) |
| 6 | 테스트 전략 정의 완료 | **확정** (test_strategy_seal.md) |
| 7 | 운영자 승인 (별도 카드 발행) | **절차 확정** (operator_approval.md). 승인 미실행. |

**모든 조건 충족 후에만 C-04 봉인 해제 가능.**

---

*문서 확정 시각: 2026-03-26*
*코드 수정: 없음*
*C-04 상태: 봉인 유지 (Not enabled in this phase)*
*이 문서는 C-04 Manual Action의 권한/계약/경계 봉인 문서이다.*
