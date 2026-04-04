# C-04 Minimum Implementation Scope

**evidence_id**: C04-MIN-IMPL-SCOPE-2026-03-26
**date**: 2026-03-26
**scope_type**: PRE_IMPLEMENTATION_SCOPE_DESIGN
**auto_repair_performed**: false

---

## 공식 목적

"Minimum implementation for C-04 means the smallest code-level structure necessary to express the controlled-write boundary without authorizing activation, execution, or operational use."

- C-04 최소 구현은 **실행 기능 오픈이 아니다**
- C-04 최소 구현은 controlled write boundary를 **안전하게 코드 구조로만 준비**하는 단계다
- 이번 단계의 목적은 "실행 가능하게 만드는 것"이 아니라 **"통제 규칙을 담을 최소 골격을 만드는 것"**이다
- 최소 구현은 activation 이전 단계다
- 최소 구현 완료 후에도 C-04는 기본적으로 **sealed/disabled 상태를 유지**할 수 있어야 한다

---

## 1. 이번 단계 구현 범위 (In-Scope)

| # | 허용 항목 | 설명 |
|---|----------|------|
| IS-1 | C-04 UI skeleton 보강 | sealed 카드 내부에 block-reason/status read-only 영역 추가. 여전히 disabled |
| IS-2 | Block/fail code state slot | C-04 카드가 현재 block code를 표시할 수 있는 read-only 영역 |
| IS-3 | Evidence linkage placeholder | check_id/preflight_id/gate_snapshot_id/approval_id/policy_snapshot_id 존재 여부 표시 |
| IS-4 | 9-stage chain status read-only | 9단계 각 단계의 현재 상태(pass/fail/unknown)를 read-only로 표시 |
| IS-5 | Fail-closed default rendering | 데이터 없으면 "Blocked" / "Unavailable" 표시. 낙관 표현 금지 |
| IS-6 | Disabled action handler | no-op handler 또는 handler 부재. 클릭해도 아무 일도 안 됨 |
| IS-7 | Minimal contract schema | C-04 상태 표현용 최소 read-only schema (action 실행 schema 아님) |
| IS-8 | _renderC04 read-only renderer | Safe Card처럼 상태만 표시하는 read-only 렌더 함수. action trigger 없음 |

**원칙**: in-scope는 "미래 구현을 위한 통제 골격"이다. "실제 실행 준비 완료 상태"가 되면 안 된다.

---

## 2. 이번 단계 제외 범위 (Out-of-Scope)

| # | 금지 항목 |
|---|----------|
| OS-1 | 실제 실행 로직 (dispatch, executor call, order submission) |
| OS-2 | Write endpoint (POST/PUT/PATCH/DELETE) |
| OS-3 | 버튼 enable / clickable execute |
| OS-4 | Submit / action trigger |
| OS-5 | Preview → action 실제 연결 (preview 읽기만 허용) |
| OS-6 | Runtime state mutation |
| OS-7 | Approval 변경 action |
| OS-8 | Policy override / bypass |
| OS-9 | Risk bypass |
| OS-10 | Evidence fallback 허용 (fallback-* 을 sufficient로 처리) |
| OS-11 | Operator click → 실제 action 발생 |
| OS-12 | 실제 rollback 수행 |
| OS-13 | 실제 dispatch/executor 호출 |
| OS-14 | 실제 운영 사용 허가 |
| OS-15 | receipt 생성 트리거 (읽기만 허용) |
| OS-16 | audit write trigger (읽기만 허용) |

**이번 단계는 실행을 가능하게 만드는 단계가 아니다.**

---

## 3. Minimum Implementation Unit (최소 구현 단위)

### A. UI 최소 단위

| 요소 | 설명 | 허용 |
|------|------|------|
| 카드 존재 | `id="t3sc-c04"` 유지 | ✅ |
| sealed/disabled 표현 | `t3sc-sealed` class 유지 또는 disabled 대체 | ✅ |
| block reason 영역 | 현재 block code를 read-only로 표시 | ✅ |
| 9-stage chain status 영역 | 각 단계 pass/fail/unknown 아이콘 | ✅ |
| evidence linkage 표시 | 5개 ID 존재/부재 표시 | ✅ |
| "Not enabled" 유지 가능 | 조건 미충족 시 여전히 봉인 메시지 | ✅ |
| 실행 버튼 | **비활성 또는 부재** | ⛔ enable 금지 |

### B. State 최소 단위

| 슬롯 | 용도 |
|------|------|
| `block_code` | 현재 차단 코드 표시 (12종 중 하나 또는 null) |
| `fail_code` | 직전 실패 코드 표시 (4종 중 하나 또는 null). 읽기만 |
| `chain_state` | 9단계 각 단계의 boolean/unknown 상태 |
| `preview_linkage` | linked preview id 존재 여부 |
| `evidence_linkage` | 5필드 존재 여부 |
| `audit_linkage` | 최근 audit entry 존재 여부 |
| `action_allowed` | **항상 false** (이번 단계에서) |

### C. Contract 최소 단위

| 항목 | 설명 |
|------|------|
| Input contract 연결 | 9-stage chain state를 읽는 인터페이스. read-only |
| Output contract 연결 | block_code + chain_state를 UI에 전달하는 구조. read-only |
| No-op handler | action 요청 시 무조건 MANUAL_ACTION_DISABLED 반환 |
| Fail-closed default | 모든 미확정 상태 → blocked |

### D. Log 최소 단위

| 항목 | 설명 |
|------|------|
| Action log 참조 | C-07 Action Log에서 과거 기록 읽기 (있으면). write 없음 |
| Error log 참조 | C-08 Error Log에서 과거 기록 읽기 (있으면). write 없음 |
| Audit log 참조 | C-09 Audit Log에서 과거 기록 읽기 (있으면). write 없음 |
| 신규 write | **없음** |

**정의 원칙**: 최소 구현 단위는 "실행을 못 하더라도 구조가 성립하는 상태"여야 한다.

---

## 4. 허용 파일 범위

| 파일 | 허용 범위 | 금지 |
|------|----------|------|
| `app/templates/dashboard.html` | C-04 카드 내부 read-only skeleton 보강. block reason + chain status + evidence linkage 영역 추가 | 버튼 enable, form, onclick, submit |
| `app/static/css/dashboard.css` | `.t3sc-c04-*` disabled/blocked 스타일 추가 | active/enabled 스타일 |
| `app/api/routes/dashboard.py` | C-04 상태를 기존 ops-safety-summary에서 읽어 표시하는 read-only 로직 | POST/PUT/PATCH/DELETE route |
| `app/schemas/` | C-04 read-only state schema (ManualActionState 또는 동등) | execution request/response schema |
| `tests/test_c04_*.py` | Phase 1 테스트와 정합성 맞추기. 구조 반영 후 필요 시 보강 | 테스트 완화/삭제 |

**원칙**:
- write endpoint 신규 생성 **금지**
- executor/dispatch/writer 로직 추가 **금지**
- controlled write activation **금지**

---

## 5. 허용 UI 범위

### 허용

| 항목 | 설명 |
|------|------|
| Sealed/disabled 카드 유지 | opacity 또는 disabled class |
| 상태/차단 사유 read-only 표시 | "GATE_CLOSED", "APPROVAL_REQUIRED" 등 |
| 9-stage chain indicator | pass/fail/unknown 아이콘 (read-only) |
| Evidence availability 표시 | 5개 linkage 존재/부재 |
| Why-blocked 설명 | 현재 차단 이유 텍스트 |
| Contract slots / placeholders | 향후 확장 영역 표시 |

### 금지

| 항목 | 이유 |
|------|------|
| Clickable execute | activation 전 |
| Active submit button | write path 생성 |
| Enabled action controls | execution trigger |
| "Ready to execute" 류 문구 | 낙관 오해 유발 |
| 추천/예측/AI 해석 문구 | Tab 3 규칙 위반 |
| Progress를 실행 가능성처럼 표현 | 오해 유발 |

**UI는 더 구체화될 수 있어도, 실행 가능해 보이면 안 된다.**

---

## 6. 허용 로직 범위

### 허용

| 항목 | 설명 |
|------|------|
| Read-only 상태 조합 | 9-stage chain 값 읽기 + block code 결정 |
| Disabled/sealed 판정 | action_allowed = false 고정 또는 조건부 |
| Block/fail code 표시 매핑 | code → UI 문구 매핑 |
| Evidence linkage 존재 여부 노출 | 5필드 non-null 여부 read-only |
| Fail-closed default resolution | unknown → blocked |

### 금지

| 항목 | 이유 |
|------|------|
| 실제 action dispatch | execution path |
| Approval mutation | state change |
| Policy mutation | state change |
| Runtime write | state change |
| Recovery/rollback 실행 | write action |
| Hidden auto-execute | bypass |
| Optimistic enable | fail-open 위험 |

**계산이 있더라도 "실행 자격을 최종 확정하는 계산"이어서는 안 된다. 이번 단계는 eligibility engine이 아니라 sealed boundary skeleton 단계다.**

---

## 7. 금지 Write 범위

| # | 금지 항목 |
|---|----------|
| W-1 | POST/PUT/PATCH/DELETE 기반 action route |
| W-2 | 버튼 클릭 → 서버 요청 |
| W-3 | Background action (celery/agent) |
| W-4 | Agent-triggered action |
| W-5 | Auto retry |
| W-6 | Manual override |
| W-7 | Emergency bypass |
| W-8 | Direct executor call |
| W-9 | Receipt 생성 트리거 |
| W-10 | Audit write 트리거 |
| W-11 | Rollback 트리거 |

**이번 단계는 write를 담는 코드 구조 일부가 생길 수는 있어도, write가 실제로 발생하는 경로는 여전히 0개여야 한다.**

---

## 8. 최소 구현 vs 활성화 비교

| 항목 | Minimum Implementation | Activation |
|------|----------------------|------------|
| **목적** | 통제 구조 코드화 | 기능 개방 |
| **UI 상태** | sealed/disabled | enabled |
| **버튼 상태** | 비활성 또는 부재 | 조건부 활성 |
| **Endpoint 상태** | read-only only | read-write |
| **Write 가능 여부** | **불가** | 조건부 가능 |
| **Approval 요구** | Phase 3 승인 | Phase 4~5 승인 |
| **운영 사용 가능** | **불가** | 조건부 가능 |
| **action_allowed** | 항상 false | 조건부 true |
| **C-04 sealed 해제** | 아니오 | 조건부 예 |

**Minimum implementation = 구조 준비. Activation = 기능 개방. 둘은 절대 동일하지 않다.**

---

## 9. 최소 구현 완료 기준

| # | 기준 | 위반 시 |
|---|------|--------|
| CC-1 | Phase 1 테스트 119건과 충돌 없음 | 완료 불인정 |
| CC-2 | C-04 여전히 sealed/disabled 가능 | 완료 불인정 |
| CC-3 | Write 경로 0개 유지 | 완료 불인정 |
| CC-4 | Block/fail/evidence/audit slot 구조 반영 | CONDITIONAL |
| CC-5 | UI가 실행 가능해 보이지 않음 | 완료 불인정 |
| CC-6 | Operator click이 실제 action을 발생시키지 않음 | 완료 불인정 |
| CC-7 | preview exists ≠ action allowed 유지 | 완료 불인정 |
| CC-8 | visible ≠ executable 유지 | 완료 불인정 |
| CC-9 | 기존 Tab 2 / Tab 3 Safe Card 회귀 없음 | 완료 불인정 |
| CC-10 | _renderC04가 read-only renderer만 | 완료 불인정 |

**하나라도 깨지면 완료가 아니다.**

---

## 10. 최소 구현 후에도 유지되어야 할 봉인 조건

| # | 봉인 조건 |
|---|----------|
| S-1 | C-04 기본 disabled (별도 승인 없이 활성화 금지) |
| S-2 | Activation은 Phase 4 승인 필요 |
| S-3 | Execution은 Phase 5 승인 필요 |
| S-4 | Phase 1 테스트 벽 119건 유지 |
| S-5 | Fail-closed 기본값 유지 |
| S-6 | Audit/evidence 규칙 완화 금지 |
| S-7 | Operator approval 절차 우회 금지 |
| S-8 | 9-stage chain 규칙 완화 금지 |

**최소 구현은 봉인 해제가 아니라 "봉인된 구조물의 코드화"다.**

---

## 11. 다음 승인 단계 진입 조건

최소 구현 설계 확정 후 다음 단계 진입 요건:

| # | 조건 |
|---|------|
| N-1 | 최소 구현 범위 문서 확정 (본 문서) |
| N-2 | 구현 파일 범위 확정 |
| N-3 | Write path 0개 보장 명시 |
| N-4 | UI disabled 기준 확정 |
| N-5 | 테스트 영향 범위 확정 |
| N-6 | Operator approval Phase 3 검토 준비 완료 |

**다음 단계는 "최소 구현 착수 승인 검토 (Phase 3 approval)"이다. 즉시 구현/활성화/운영 허가로 넘어가면 안 된다.**

---

## 범위 체크리스트 표

| 항목 | 허용/금지 | 이유 | 위반 시 |
|------|----------|------|--------|
| C-04 read-only skeleton | 허용 | 통제 구조 표현 | — |
| Block code 표시 | 허용 | 차단 사유 가시화 | — |
| 9-stage chain read-only | 허용 | 체인 상태 관측 | — |
| Evidence linkage 표시 | 허용 | 증거 존재 확인 | — |
| _renderC04 (read-only) | 허용 | 상태 렌더링만 | — |
| Write endpoint | **금지** | execution path 생성 | REJECT |
| 버튼 enable | **금지** | action trigger | REJECT |
| Action dispatch | **금지** | runtime mutation | REJECT |
| Approval mutation | **금지** | state change | REJECT |
| Optimistic enable | **금지** | fail-open 위험 | REJECT |
| "Ready to execute" 문구 | **금지** | 낙관 오해 | REJECT |
| Phase 1 테스트 완화 | **금지** | 테스트 벽 훼손 | REJECT |

---

## 헌법 조항 대조

| 요구 조항 | 반영 문장 |
|----------|----------|
| 최소 구현 ≠ activation | §공식 목적 + §8 비교표 명시 |
| in-scope / out-of-scope 분리 | §1, §2 각각 별도 섹션 |
| write 경로 0개 유지 | §7 금지 write 11항목 + §9 CC-3 |
| UI가 실행 가능해 보이면 안 됨 | §5 금지 UI + §9 CC-5 |
| Phase 1 테스트 벽 유지 | §10 S-4 + §9 CC-1 |
| fail-closed 기본값 유지 | §6 허용 로직 + §10 S-5 |
| 봉인 조건 유지 | §10 8개 조건 |

**금지 조항 확인**: production code 수정 0건, 구현 시작 0건, 활성화 0건
**상태 전이 영향**: 없음. C-04 여전히 sealed.
**미해결 리스크**: 없음. 문서 설계만 수행.
