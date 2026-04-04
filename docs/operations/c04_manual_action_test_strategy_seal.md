# C-04 Manual Action Test Strategy Seal

---

## 공통 원칙

1. **C-04는 테스트가 준비되기 전에는 구현될 수 없다**
2. **C-04는 테스트가 통과되기 전에는 활성화될 수 없다**
3. **unknown / missing / unverifiable는 허용이 아니라 차단 대상으로 테스트해야 한다**
4. **"실행된다"보다 "실행되면 안 된다"를 더 많이 검증해야 한다**
5. **audit / evidence / traceability는 성공 시뿐 아니라 차단/실패 시에도 검증 대상이다**
6. **rollback은 기능이 아니라 증적 보존과 함께 검증되어야 한다**
7. **테스트 전략이 확정되지 않으면 운영자 승인도 완료될 수 없다**

---

## 1. 테스트 목적

- C-04 테스트의 목적은 **실행 성공 검증이 아니라 통제 경계 유지 검증**이다
- C-04는 controlled write boundary이므로 **허용 경로보다 차단 경로를 더 엄격히 검증**해야 한다
- C-04는 **fail-open 가능성이 0**이어야 한다
- 9단계 중 하나라도 미충족이면 action 불가여야 한다
- 테스트는 "버튼이 눌린다"가 아니라 **"잘못된 경우 절대 열리지 않는다"**를 증명해야 한다

---

## 2. 테스트 계층 정의

### A. Unit Test

| 목적 | 개별 조건 판정 로직 검증 |
|------|---------------------|
| 주요 케이스 | 9단계 각 조건 pass/fail 분기, block/fail code 매핑, evidence linkage 판정, risk pass 판정 |
| 필수 통과 | 모든 단계별 정상/비정상/unknown 분기 커버 |

### B. Integration Test

| 목적 | preview → action → result → audit 흐름 연결 검증 |
|------|----------------------------------------------|
| 주요 케이스 | C-05→C-04→C-06→C-07/C-08/C-09 연계, 로그/증적 기록 연계, rollback/receipt 연계 |
| 필수 통과 | 전체 흐름에서 누락되는 기록이 0건 |

### C. UI/Render Test

| 목적 | C-04 상태별 UI 정확성 검증 |
|------|------------------------|
| 주요 케이스 | disabled / blocked / unavailable / not enabled 상태, 표시/preview/action 구분 |
| 필수 통과 | 조건 미충족 시 버튼 비활성 + 정확한 상태 문구 |

### D. Regression Test

| 목적 | C-04 변경이 기존 시스템 비손상 확인 |
|------|-------------------------------|
| 주요 케이스 | Tab 2 기준선 314+, Tab 3 Safe Cards 25+, B-14 57+ |
| 필수 통과 | 전체 테스트 기준선 339+ passed |

### E. Audit / Evidence Test

| 목적 | 모든 시도에서 증적 보존 검증 |
|------|------------------------|
| 주요 케이스 | 차단 시 audit, 실패 시 audit, preview linkage, trace linkage |
| 필수 통과 | 어떤 경로에서도 audit 0건인 경우 없음 |

---

## 3. 9단계 실행 체인 검증 전략

| # | 조건 | 정상 케이스 | 실패 케이스 | unknown/missing | 기대 block code | UI 기대 | action |
|---|------|-----------|-----------|-----------------|----------------|--------|--------|
| 1 | Pipeline Ready | check=OK → pass | check=BLOCK → blocked | check=null → blocked | `PIPELINE_NOT_READY` | "Blocked by check" | ✗ |
| 2 | Preflight Ready | pf=READY → pass | pf=NOT_READY → blocked | pf=null → blocked | `PREFLIGHT_NOT_READY` | "Preflight not ready" | ✗ |
| 3 | Gate Open | gate=OPEN → pass | gate=CLOSED → blocked | gate=null → blocked | `GATE_CLOSED` | "Gate closed" | ✗ |
| 4 | Approval OK | apr=APPROVED+valid → pass | apr=REJECTED → blocked | apr=null → blocked | `APPROVAL_REQUIRED` | "Approval required" | ✗ |
| 5 | Policy OK | pol=MATCH → pass | pol=DRIFT → blocked | pol=null → blocked | `POLICY_BLOCKED` | "Policy not matched" | ✗ |
| 6 | Risk OK | score≥0.7+auth+¬lock → pass | score<0.7 → blocked | score=null → blocked | `RISK_NOT_OK` | "Risk check failed" | ✗ |
| 7 | Auth OK | auth=true+¬lockdown → pass | auth=false → blocked | auth=null → blocked | `AUTH_NOT_OK` | "Auth not satisfied" | ✗ |
| 8 | Scope OK | exec⊆approval → pass | scope mismatch → blocked | scope=null → blocked | `SCOPE_NOT_OK` | "Scope mismatch" | ✗ |
| 9 | Evidence Present | 6 IDs non-null+non-fallback → pass | ID 누락 → blocked | fallback-* → blocked | `EVIDENCE_MISSING` | "Evidence not present" | ✗ |

**핵심 음성 테스트**: 9개 중 1개만 실패해도 action=false (조합 테스트 포함)

---

## 4. 표시 / Preview / Action 분리 검증

| 단계 | 테스트 | 기대 |
|------|--------|------|
| **표시** | C-04 카드가 DOM에 존재 | 항상 true (봉인/비활성 포함) |
| **표시** | visible이지만 action 불가 | 조건 미충족 시 true |
| **Preview** | 1~5번 통과 시 preview 읽기 가능 | true |
| **Preview** | preview 존재하지만 action 불가 | 6~9번 미충족 시 true |
| **Action** | 9단계 전체 통과 시에만 활성 | true |

### 필수 음성 테스트

| 테스트 | 기대 | 검증 이유 |
|--------|------|----------|
| visible == executable 혼동 | **반드시 분리** | 보이지만 실행 불가 상태 존재 확인 |
| preview exists == action allowed 혼동 | **반드시 분리** | preview 있지만 action 불가 상태 존재 확인 |

---

## 5. Fail-Closed 검증 전략

| 상태 | 테스트 유형 | 기대 상태 | 기대 문구 | 기대 코드 |
|------|-----------|----------|----------|----------|
| approval unknown | unit | blocked | "Approval required" | `APPROVAL_REQUIRED` |
| policy unknown | unit | blocked | "Policy not matched" | `POLICY_BLOCKED` |
| risk unknown | unit | blocked | "Risk unavailable" | `RISK_UNAVAILABLE` |
| auth unknown | unit | blocked | "Auth not satisfied" | `AUTH_NOT_OK` |
| scope unknown | unit | blocked | "Scope mismatch" | `SCOPE_NOT_OK` |
| preview missing | unit | blocked | "No preview available" | `PREVIEW_MISSING` |
| evidence missing | unit | blocked | "Evidence not present" | `EVIDENCE_MISSING` |
| trace incomplete | unit | blocked | "Trace incomplete" | `TRACE_INCOMPLETE` |
| runtime disconnected | unit | unavailable | "Unavailable" | `RISK_SOURCE_MISSING` |
| partial data | unit | blocked | optimistic pass **금지** | 해당 stage code |

---

## 6. Block Code / Fail Code 검증 전략

### A. Block Code 테스트 (사전 차단)

| 코드 | 테스트 | 판정 |
|------|--------|------|
| `MANUAL_ACTION_DISABLED` | C-04 비활성 단계에서 action 시도 → 차단 | blocker |
| `PREVIEW_MISSING` | preview 없이 action 시도 → 차단 | blocker |
| `PIPELINE_NOT_READY` | check=BLOCK → 차단 | blocker |
| `PREFLIGHT_NOT_READY` | pf≠READY → 차단 | blocker |
| `GATE_CLOSED` | gate≠OPEN → 차단 | blocker |
| `APPROVAL_REQUIRED` | apr≠APPROVED 또는 만료 → 차단 | blocker |
| `POLICY_BLOCKED` | pol≠MATCH → 차단 | blocker |
| `RISK_NOT_OK` | risk 미충족 → 차단 | blocker |
| `AUTH_NOT_OK` | auth 미충족 → 차단 | blocker |
| `SCOPE_NOT_OK` | scope 불일치 → 차단 | blocker |
| `EVIDENCE_MISSING` | evidence 부재 → 차단 | blocker |
| `TRACE_INCOMPLETE` | trace/linked id 부재 → 차단 | blocker |

### B. Fail Code 테스트 (실행 후 실패)

| 코드 | 테스트 | 판정 |
|------|--------|------|
| `EXECUTION_REJECTED` | 실행 진입 후 내부 거부 → 실패 기록 | blocker |
| `EXECUTION_FAILED` | 실행 중 오류 → 실패 기록 + audit | blocker |
| `EXECUTION_TIMEOUT` | 시간 초과 → 실패 기록 | blocker |
| `EXECUTION_ROLLBACK` | 롤백 발생 → 롤백 기록 + audit 보존 | blocker |

### 경계 테스트

- block code는 **실행 이전에만** 발생 → 실행 후 발생 시 **테스트 실패**
- fail code는 **실행 진입 후에만** 발생 → 실행 전 발생 시 **테스트 실패**

---

## 7. Evidence / Audit / Trace Linkage 검증

| 테스트 | 기대 | 유형 |
|--------|------|------|
| linked_preview_id 존재 | 필수 | positive |
| trace_id 존재 | 필수 | positive |
| policy_snapshot_id linkage | 필수 | positive |
| approval_id linkage | 필수 | positive |
| 차단 시 audit entry 존재 | 필수 | positive |
| 실패 시 audit entry 존재 | 필수 | positive |
| 성공 시 audit entry 존재 | 필수 | positive |
| fallback-* ID → evidence 인정 거부 | 필수 | **negative** |
| UI 문구만 → evidence 인정 거부 | 필수 | **negative** |
| "추후 기록 예정" → evidence present 아님 | 필수 | **negative** |

---

## 8. Rollback / Receipt 검증 전략

| Failure Class | receipt 테스트 | audit 테스트 | log 테스트 | rollback 테스트 | UI 테스트 |
|---------------|--------------|------------|-----------|----------------|---------|
| Pre-execution block | blocked receipt 존재 | ✓ audit | error log | N/A (실행 전) | blocked 상태 |
| Execution rejected | failed receipt 존재 | ✓ audit | action+error log | UI 복원 | failed 상태 |
| Execution failed | failed receipt+error | ✓ audit | action+error log | state rollback | failed 상태 |
| Partial failure | partial receipt | ✓ audit | action+error log | partial rollback | partial 상태 |
| Result unknown | unknown receipt+flag | ✓ audit | action log | investigation flag | unknown 상태 |

**핵심**: 어떤 failure에서도 **audit entry 0건 = 테스트 실패**

---

## 9. Should-Never-Happen 테스트

| # | 절대 발생 금지 | 이유 | 검증 방식 | 실패 시 |
|---|--------------|------|----------|--------|
| 1 | unknown 상태에서 action 허용 | fail-open 금지 | 모든 unknown 입력 → action=false 확인 | **REJECT** |
| 2 | preview 없이 action 허용 | linked preview 필수 | preview_id=null → action=false 확인 | **REJECT** |
| 3 | evidence 없이 action 허용 | No Evidence No Power | evidence 부재 → action=false 확인 | **REJECT** |
| 4 | trace 없는 실행 허용 | traceability 필수 | trace_id=null → action=false 확인 | **REJECT** |
| 5 | audit 없이 실행 시도 통과 | 감사 무결성 | 모든 경로에서 audit≥1 확인 | **REJECT** |
| 6 | block code 없이 blocked 발생 | code 추적 필수 | blocked 상태 → block_code 존재 확인 | **BLOCKER** |
| 7 | fail code 없이 failed 발생 | code 추적 필수 | failed 상태 → fail_code 존재 확인 | **BLOCKER** |
| 8 | C-04가 Safe Card처럼 동작 | write boundary 위반 | read-only 검사에서 C-04 제외 확인 | **REJECT** |
| 9 | C-04가 자동 실행처럼 동작 | 수동 트리거 필수 | 자동 호출 경로 부재 확인 | **REJECT** |
| 10 | C-04가 Tab 2 기준선에 영향 | 격리 필수 | Tab 2 테스트 기준선 비손상 확인 | **REJECT** |

---

## 10. 오픈 전 필수 통과 기준

| # | 기준 | 필수 |
|---|------|------|
| 1 | Unit test: 9단계 정상/비정상/unknown 커버 | ✓ |
| 2 | Unit test: 모든 block code 발생 확인 | ✓ |
| 3 | Integration test: preview→action→result→audit 흐름 | ✓ |
| 4 | UI test: disabled/blocked/unavailable/not enabled | ✓ |
| 5 | Negative test: 9개 should-never-happen 전부 통과 | ✓ |
| 6 | Evidence test: 차단/실패/성공 모두 audit 존재 | ✓ |
| 7 | Rollback test: 5 failure class receipt 검증 | ✓ |
| 8 | Regression: Tab 2 기준선 314+ 유지 | ✓ |
| 9 | Regression: Tab 3 기준선 339+ 유지 | ✓ |
| 10 | 운영자 승인 완료 | ✓ |

**위 10개 중 1개라도 미통과 → C-04 계속 봉인.**
**일부 통과를 이유로 단계적 오픈 금지 (별도 승인 전까지).**

---

## 11. 테스트 미통과 시 봉인 유지 규칙

| 상태 | C-04 |
|------|------|
| 테스트 전략 미확정 | **봉인 유지** |
| 테스트 코드 미작성 | **봉인 유지** |
| 핵심 음성 테스트 미통과 | **봉인 유지** |
| audit/evidence 검증 미통과 | **봉인 유지** |
| should-never-happen 1건이라도 발생 | **봉인 유지 + REJECT** |
| 운영자 승인 미완료 | **봉인 유지** |

> 테스트는 구현 후 확인이 아니라 **봉인 해제 조건의 일부**이다.

---

*문서 확정 시각: 2026-03-26*
*코드 수정: 없음*
*C-04 상태: 봉인 유지 (테스트 전략 확정, 테스트 코드 미작성, 운영자 승인 미완)*
