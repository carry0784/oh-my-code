# C-04 Manual Action Operator Approval Seal

---

## 공식 선언

> **C-04 Manual Action은 기술적으로 구현 가능해도, 운영자 승인 없이는 봉인 해제될 수 없다.**

---

## 1. 승인 필요성 정의

- C-04는 Tab 3의 **유일한 controlled write entry**다
- 기술적 조건(Contract/Prereq/TestStrategy) 충족과 별도로 **운영 승인이 필수**
- 운영자 승인은 기술 검증과 별도의 **거버넌스 절차**다
- 승인 없이는 테스트 코드 작성도 금지 (Phase 1 승인 필요)
- 승인 없이는 C-04는 **계속 봉인 상태**

---

## 2. 승인 권한자 정의

| 역할 | 권한 |
|------|------|
| **시스템 운영 책임자** | 전체 승인 권한. 모든 Phase 승인 가능 |
| **아키텍처 설계 승인자** | 기술 적합성 검토. Phase 1~3 승인 참여 |
| **정책 승인자** | 정책/리스크 관점 검토. Phase 4~5 승인 참여 |

### 승인 규칙

| 규칙 | 정의 |
|------|------|
| 최소 승인자 | **1명 이상** (시스템 운영 책임자 필수) |
| 승인 주체 없음 | = 승인 **불가** |
| 승인 기록 없음 | = 승인 **무효** |
| Self-approval | **금지** (구현자 ≠ 승인자) |
| 다중 승인 | Phase 4~5는 **2인 이상 권장** |
| 조건부 승인 | **허용** (단, 조건 미충족 시 자동 봉인 복귀) |

---

## 3. 승인 기준 (Checklist)

승인 전 반드시 **전부** 확인. 1개라도 미충족 → 승인 불가.

| # | 기준 | 참조 문서 | 상태 |
|---|------|----------|------|
| 1 | Contract Seal 완료 | `c04_manual_action_contract_seal.md` | ✓ |
| 2 | Prereq Resolution 완료 (R-1/R-2/R-3) | `c04_manual_action_prereq_resolution.md` | ✓ |
| 3 | Test Strategy Seal 완료 | `c04_manual_action_test_strategy_seal.md` | ✓ |
| 4 | 미확정 항목 없음 (#1~#9 전부 확정) | contract_seal §11 | ✓ |
| 5 | Fail-closed 규칙 정의 완료 | contract_seal §7 | ✓ |
| 6 | Block/Fail code 정의 완료 | contract_seal §8 | ✓ |
| 7 | Evidence 기준 확정 | prereq_resolution R-2 | ✓ |
| 8 | Rollback 기준 확정 | prereq_resolution R-3 | ✓ |
| 9 | Trace/Audit 기준 확정 | contract_seal §9 | ✓ |
| 10 | Safe Card 8개 기준선 안정 (339+) | tab3_safe_cards_receipt | ✓ |

---

## 4. 단계 승인 구조

C-04는 **한 번에 열지 않는다**. 5단계 승인으로 진행.

### Phase 1 — 승인 A: 테스트 코드 작성 허가

| 항목 | 정의 |
|------|------|
| 허용 | C-04 전용 테스트 코드 작성 |
| 금지 | C-04 구현 코드, endpoint, UI 활성화 |
| 필요 조건 | Checklist 10개 전부 ✓ |
| 승인 기록 | evidence 문서에 Phase 1 승인 기록 |

### Phase 2 — 승인 B: 테스트 실행 허가

| 항목 | 정의 |
|------|------|
| 허용 | C-04 테스트 실행 + 결과 검토 |
| 금지 | C-04 구현 코드, endpoint, UI 활성화 |
| 필요 조건 | Phase 1 완료 + 테스트 코드 작성 완료 |
| 승인 기록 | evidence 문서에 Phase 2 승인 기록 |

### Phase 3 — 승인 C: 구현 허가

| 항목 | 정의 |
|------|------|
| 허용 | C-04 최소 구현 (endpoint + 로직) |
| 금지 | UI 활성화, 운영 사용 |
| 필요 조건 | Phase 2 완료 + 핵심 테스트 전부 통과 |
| 승인 기록 | evidence 문서에 Phase 3 승인 기록 |

### Phase 4 — 승인 D: UI 활성화 검토

| 항목 | 정의 |
|------|------|
| 허용 | C-04 UI 활성화 (비운영 환경에서) |
| 금지 | 운영 환경 실사용 |
| 필요 조건 | Phase 3 완료 + 구현 검증 + 회귀 통과 |
| 승인 기록 | evidence 문서에 Phase 4 승인 기록 (2인 이상 권장) |

### Phase 5 — 승인 E: 실제 사용 허가

| 항목 | 정의 |
|------|------|
| 허용 | C-04 운영 환경 활성화 |
| 금지 | 자동 실행, 정책 우회, evidence 없는 실행 |
| 필요 조건 | Phase 4 완료 + 전체 테스트 통과 + 운영 환경 검증 |
| 승인 기록 | evidence 문서에 Phase 5 승인 기록 (2인 이상 권장) |

**다음 단계로 자동 진행 금지. 각 단계마다 별도 승인 필요.**

---

## 5. 승인 없이 금지되는 행위

| 행위 | 승인 전 |
|------|--------|
| C-04 구현 코드 작성 | **금지** |
| Write endpoint 생성 | **금지** |
| 실행 버튼 활성화 | **금지** |
| Preview → Action 연결 | **금지** |
| 테스트 코드 작성 | **금지** (Phase 1 전) |
| 실행 경로 생성 | **금지** |
| Runtime 연결 | **금지** |
| UI enable | **금지** |
| C-04 봉인 해제 | **금지** |

---

## 6. 승인 후에도 바로 허용되지 않는 범위

**승인 = 구현 허용. 승인 ≠ 실행 허용.**

| 행위 | 승인 후에도 금지 |
|------|----------------|
| 자동 실행 | **영구 금지** |
| 정책 우회 | **영구 금지** |
| Evidence 없는 실행 | **영구 금지** |
| Audit 없는 실행 | **영구 금지** |
| Rollback 불명확 상태 실행 | **금지** (확정 전) |
| Partial failure 미정 상태 실행 | **금지** (확정 전) |

---

## 7. 순서 고정

| # | 단계 | 순서 변경 |
|---|------|----------|
| 1 | Contract Seal | **금지** |
| 2 | Prereq Resolution | **금지** |
| 3 | Test Strategy Seal | **금지** |
| 4 | **Operator Approval** | **금지** |
| 5 | Test Code 작성 | **금지** |
| 6 | Test 통과 | **금지** |
| 7 | 최소 구현 | **금지** |
| 8 | 검증 | **금지** |
| 9 | UI 활성화 검토 | **금지** |
| 10 | 운영 허가 | **금지** |

**순서 변경 금지. 이전 단계 미완료 시 다음 단계 진입 불가.**

---

## 8. 승인 기록 방식

| 항목 | 규칙 |
|------|------|
| 문서 위치 | `docs/operations/evidence/c04_operator_approval_YYYY-MM-DD.md` |
| 필수 필드 | 승인 날짜, 승인자, 승인 단계(Phase), 승인 범위, 승인 조건, 체크리스트 결과 |
| 형식 | 헌법 조항 대조 검수본 형식 |

**문서 없는 승인 = 승인 아님.**

---

## 9. 승인 취소 / 재봉인 규칙

| 조건 | 결과 |
|------|------|
| 핵심 테스트 실패 | **봉인 복귀** |
| 조건 변경 (contract/prereq 수정) | **봉인 복귀** |
| 정책 변경 (risk/audit 기준) | **봉인 복귀** |
| Risk 기준 변경 | **봉인 복귀** |
| Audit 기준 변경 | **봉인 복귀** |
| should-never-happen 1건 발생 | **즉시 봉인 복귀 + REJECT** |
| 운영 사고 발생 시 | **즉시 봉인 복귀 + 조사** |

> **승인은 영구 허가가 아니라 조건부 상태다.**

---

## 10. 봉인 해제 조건 (최종)

| # | 조건 | 상태 |
|---|------|------|
| 1 | Contract Seal 완료 | ✓ |
| 2 | Prereq Resolution 완료 | ✓ |
| 3 | Test Strategy Seal 완료 | ✓ |
| 4 | Test 통과 | 미완 (코드 미작성) |
| 5 | **Operator Approval 완료** | **미완 (본 문서로 절차 확정)** |
| 6 | Audit/Evidence 규칙 확정 | ✓ |
| 7 | Rollback 규칙 확정 | ✓ |

**모든 조건 AND. 1개라도 미완 → 봉인 유지.**

---

*문서 확정 시각: 2026-03-26*
*코드 수정: 없음*
*C-04 상태: COMPLETE / FROZEN. Phase 1-10 all sealed. Verification complete.*
*Write path = 5 POST. Fail-closed confirmed. Re-close verified. Evidence consistent.*
*Production execution requires separate operational authorization.*
*Final receipt: `evidence/c04_final_completion_freeze_2026-03-26.md`*
*Phase 1 승인 기록: `evidence/c04_phase1_approval_2026-03-26.md`*
