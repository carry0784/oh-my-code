# C-04 Manual Action 선행조건 해소 문서

---

## 공통 원칙

1. **unknown은 허용이 아니라 차단으로 처리한다**
2. **missing linkage는 실행 불가다**
3. **runtime 미연결은 optimistic pass 금지다**
4. **audit 없는 실행 시도는 허용되지 않는다**
5. **evidence 없는 실행은 허용되지 않는다**
6. **rollback 가능 여부와 audit 보존 여부는 별개다**
7. **구현 전 미확정 항목이 남아 있으면 C-04는 계속 봉인한다**

---

## R-1: RiskFilter Runtime 연결 기준

### A. RiskFilter의 역할

- C-04 실행 체인 9단계 중 **#6 risk ok**를 판정하는 통제점
- **예측 엔진이 아님**
- **리스크 완화 추천기가 아님**
- 실행 자격 여부만 판정: pass / blocked

### B. RiskFilter 입력값

**기존 값 기반만 허용. 없는 데이터 추정 금지.**

| 입력 | 소스 | 필수 |
|------|------|------|
| ops_score_average | `ops-safety-summary.ops_score` | ✓ |
| gate_conditions_met | `ops-safety-summary.conditions_met` | ✓ |
| trading_authorized | `ops-safety-summary.trading_authorized` | ✓ |
| lockdown_state | `ops-safety-summary.lockdown_state` | ✓ |
| governance.security_state | `data/v2.governance.security_state` | ✓ |

### C. Runtime 연결 방식

**결정: 기존 read-only 요약값 기반 판정**

| 방식 | 결정 | 이유 |
|------|------|------|
| 실제 kdexter RiskFilter runtime 연결 | 보류 | RiskFilter는 AccountState 입력 필요, 현재 실거래 미연결 |
| **기존 read-only 요약값 기반** | **채택** | ops-safety-summary의 기존 값으로 risk 통과 여부 판정 가능 |
| stub 허용 | **금지** | stub risk pass는 위험 |

**판정 규칙**:
- `ops_score >= 0.7` AND `trading_authorized == true` AND `lockdown_state ≠ LOCKDOWN` → risk ok
- 위 조건 중 하나라도 미충족 또는 null → **blocked**
- RiskFilter runtime 미연결 시 기존 값 기반 판정. 기존 값도 없으면 → **blocked**

### D. Fail-closed 규칙

| 상태 | 판정 |
|------|------|
| risk 입력값 null | **blocked** |
| risk 입력값 unknown | **blocked** |
| ops_score < 0.7 | **blocked** |
| trading_authorized ≠ true | **blocked** |
| lockdown active | **blocked** |
| partial data | **blocked** |
| runtime 오류 | **blocked** (optimistic pass 금지) |

### E. 차단 코드 연결

| 코드 | 의미 | 조건 |
|------|------|------|
| `RISK_NOT_OK` | risk 조건 미충족 | ops_score < 0.7 또는 auth 미충족 |
| `RISK_UNAVAILABLE` | risk 입력값 부재 | null 또는 unknown |
| `RISK_SOURCE_MISSING` | risk 데이터 소스 없음 | ops-safety-summary 응답 실패 |

### F. 구현 전 확인 항목

| # | 항목 | 상태 |
|---|------|------|
| 1 | risk source = ops-safety-summary | **확정** |
| 2 | risk pass 조건 = score≥0.7 + auth + ¬lockdown | **확정** |
| 3 | unknown → blocked | **확정** |
| 4 | UI 표시: "Risk check failed" / "Risk unavailable" | **확정** |

**R-1 상태: 확정**

---

## R-2: Evidence Present 판정 기준

### A. Evidence present의 의미

- 실행 자격을 뒷받침하는 **최소 증적 연결이 존재하는 상태**
- "로그가 있을 것 같음"은 evidence가 **아님**
- 추정 연결 **금지**
- **링크 가능한 근거**가 있어야 함

### B. 최소 evidence 요건

실행 시 아래 **전부** 존재해야 evidence present:

| 요건 | 소스 | 필수 |
|------|------|------|
| linked_preview_id | C-05 Action Preview | ✓ |
| approval_id | ops-safety-summary | ✓ |
| gate_evidence_id | ops-safety-summary | ✓ |
| preflight_evidence_id | ops-safety-summary | ✓ |
| policy_snapshot_id (policy_decision ≠ UNKNOWN) | I-07 | ✓ |
| trace_id (실행 시 생성) | 시스템 | ✓ |

### C. Sufficient vs Insufficient 구분

| 등급 | 조건 | action 허용 |
|------|------|-----------|
| **Sufficient** | 위 6개 요건 전부 존재 + 값이 non-null | ✓ |
| **Insufficient** | 1~5개 존재, 일부 누락 | ✗ blocked |
| **Missing** | 0개 또는 핵심 ID 부재 | ✗ blocked |
| **Unverifiable** | 값 존재하나 유효성 불확인 (fallback ID 등) | ✗ blocked |

**fallback-* 형태 ID는 unverifiable로 분류. evidence present 아님.**

### D. Fail-closed 규칙

| 상태 | 판정 |
|------|------|
| preview_id 없음 | **blocked** |
| trace linkage 없음 | **blocked** |
| approval/policy linkage 불완전 | **blocked** |
| evidence를 UI 문구로 대체 | **금지** |
| "추후 기록 예정" 상태로 실행 허용 | **금지** |
| fallback-* ID를 evidence로 인정 | **금지** |

### E. 차단 코드 연결

| 코드 | 의미 | 조건 |
|------|------|------|
| `EVIDENCE_MISSING` | 필수 evidence 0건 | 핵심 ID 전부 부재 |
| `EVIDENCE_INSUFFICIENT` | 일부 존재, 전부 아님 | 1~5개만 존재 |
| `TRACE_INCOMPLETE` | trace/preview linkage 불완전 | linked_preview_id 또는 trace_id 부재 |
| `LINKAGE_MISSING` | approval/policy/gate linkage 부재 | 해당 ID null |

### F. 구현 전 확인 항목

| # | 항목 | 상태 |
|---|------|------|
| 1 | preview linkage = C-05 preview_id | **확정** |
| 2 | trace_id = 실행 시 UUID 생성 | **확정** |
| 3 | evidence 최소 필드 = 6개 ID | **확정** |
| 4 | fallback-* ID = unverifiable = blocked | **확정** |
| 5 | UI 표시: "Evidence not present" / "Evidence insufficient" | **확정** |

**R-2 상태: 확정**

---

## R-3: 실행 실패 Rollback / Receipt 범위

### A. Rollback의 의미

- 실행 실패 시 **무엇을 되돌리고, 무엇은 반드시 남기는가**
- write 결과를 되돌릴 수 있어도 **audit 흔적은 남겨야 함**
- **"실패했으니 아무 흔적도 없음" 금지**

### B. 반드시 남아야 하는 기록

| 기록 | 실패 시에도 필수 |
|------|----------------|
| action attempt | ✓ |
| actor | ✓ |
| timestamp | ✓ |
| preview linkage | ✓ |
| block/fail code | ✓ |
| error message | ✓ |
| **audit entry** | **✓ (mandatory)** |
| receipt/evidence linkage | ✓ (가능한 범위) |

### C. Rollback 범위 구분

| 대상 | rollback 가능 | 비고 |
|------|-------------|------|
| UI 상태 | ✓ | 실행 전 상태로 복원 |
| 실행 결과 state | ✓ | 실패 시 state = FAILED |
| **action log** | ✗ (rollback 불가) | 시도 기록은 보존 |
| **audit log** | ✗ (rollback 불가) | 감사 증적 보존 필수 |
| **error log** | ✗ (rollback 불가) | 오류 기록 보존 필수 |
| evidence linkage | 조건부 | 실패해도 linkage 기록은 보존, 결과 evidence만 미생성 가능 |

### D. Failure Class 구분

| 클래스 | 정의 | receipt 수준 | audit |
|--------|------|-------------|-------|
| **사전 차단** (pre-execution block) | 9단계 체인 미통과로 실행 진입 전 차단 | blocked receipt | ✓ |
| **실행 진입 실패** (execution rejected) | 실행 시작 직후 내부 거부 | failed receipt | ✓ |
| **실행 중 실패** (execution failed) | 실행 진행 중 오류 | failed receipt + error detail | ✓ |
| **부분 실패** (partial failure) | 일부 성공 일부 실패 | partial receipt + rollback 시도 | ✓ |
| **결과 미확정** (result unknown) | 실행 후 결과 확인 불가 | unknown receipt + investigation flag | ✓ |

### E. Receipt 범위

| 실패 유형 | receipt 필수 필드 |
|----------|-----------------|
| **blocked receipt** | attempt_id, actor, timestamp, block_codes, preview_linkage |
| **failed receipt** | attempt_id, actor, timestamp, fail_codes, error_message, preview_linkage |
| **partial receipt** | attempt_id, actor, timestamp, success_items, failed_items, rollback_status |
| **unknown receipt** | attempt_id, actor, timestamp, last_known_state, investigation_required=true |

### F. Fail-closed 규칙

| 상태 | 판정 |
|------|------|
| rollback 범위 미확정 | **구현 금지** |
| partial failure + unknown | **blocked 우선** |
| receipt 전략 미정 | **action open 금지** |
| result unknown 시 | investigation flag 필수, 자동 재실행 금지 |
| 모든 실패 | audit entry mandatory |

### G. 구현 전 확인 항목

| # | 항목 | 상태 |
|---|------|------|
| 1 | 실패 클래스 5개 정의 | **확정** |
| 2 | receipt 필드 클래스별 정의 | **확정** |
| 3 | rollback 가능/불가 구분 | **확정** (UI/state 가능, log/audit 불가) |
| 4 | audit = 모든 실패에서 필수 | **확정** |
| 5 | result unknown → investigation flag | **확정** |
| 6 | UI 표시: 클래스별 상태 문구 | **확정** |

**R-3 상태: 확정**

---

## 항목별 결정 요약표

| 항목 | 결정 | 상태 |
|------|------|------|
| R-1 RiskFilter 연결 | 기존 ops-safety-summary 값 기반 판정 | **확정** |
| R-1 risk pass 조건 | score≥0.7 + auth=true + ¬lockdown | **확정** |
| R-1 미연결/unknown | blocked | **확정** |
| R-2 evidence 최소 요건 | 6개 ID 전부 non-null + non-fallback | **확정** |
| R-2 fallback-* ID | unverifiable → blocked | **확정** |
| R-2 insufficient | blocked | **확정** |
| R-3 failure class | 5단계 분류 | **확정** |
| R-3 receipt 범위 | 클래스별 필수 필드 정의 | **확정** |
| R-3 rollback | UI/state 가능, log/audit 불가 | **확정** |
| R-3 audit | 모든 실패에서 mandatory | **확정** |

---

## C-04 봉인 해제 조건 갱신

| # | 조건 | c04_contract 기준 | 현재 |
|---|------|------------------|------|
| 1 | Safe Card 8개 기준선 유지 (339+) | ✓ | ✓ |
| 2 | 9단계 체인 데이터 소스 전부 확정 | 미완 → **확정** | ✓ (R-1 해소) |
| 3 | Block/Fail code 체계 확정 | ✓ | ✓ |
| 4 | Audit/Evidence linkage 방식 확정 | 미완 → **확정** | ✓ (R-2 해소) |
| 5 | Preview/Result/Log 카드 연계 검증 | 부분 → **확정** | ✓ (Safe Card 구현 완료) |
| 6 | 테스트 전략 정의 완료 | **미완** | 미완 |
| 7 | 운영자 승인 (별도 카드 발행) | **미완** | 미완 |

**잔여 미완: 2건 (#6 테스트 전략, #7 운영자 승인)**

---

*문서 확정 시각: 2026-03-26*
*코드 수정: 없음*
*C-04 상태: 봉인 유지 (잔여 미완 2건)*
