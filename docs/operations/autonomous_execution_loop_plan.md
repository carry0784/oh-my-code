# Autonomous Execution Loop Plan (AELP) v1

**Created**: 2026-04-05
**Status**: ACTIVE
**Authority**: A explicit instruction granting autonomous execution
**Supersedes**: `continuous_progress_plan_v1.md` P2 (blocked → session end) for autonomous mode only
**Preserves**: Track A HOLD, receipt chain integrity, evidence body preservation (all v1 principles except P2)
**Purpose**: Execute all remaining unblocked low-risk work in a continuous loop without per-item user interaction, then verify, then stop.

---

## 0. Scope of Authority Grant

A의 명시 지시 (2026-04-05):
> "내 지시를 기다리지 말고 플랜 A,B,C를 만들고 프로젝트가 완료될 때까지 루프를 돌려 완성된 후 다시 검증을 하고 실행하는 플랜을 세워. 플랜을 세운 다음 실행해."

### Grant 해석

본 지시는 다음을 **부여**한다:
- ✅ 세션 중 복수 항목 연속 실행 (기존 P1 "한 세션 한 작업" 완화)
- ✅ 항목 blocked 시 PASS 후 다음 항목 자동 이동 (기존 P2 "blocked → 세션 종료" 완화)
- ✅ Plan A / B / C 문서 작성 권한
- ✅ Plan A 5개 + Plan B 3개 + Plan C 1개 PR 연속 생성/merge 권한
- ✅ 검증 단계(Plan C) 자동 실행 및 완료 receipt 작성 권한

본 지시는 다음을 **부여하지 않는다**:
- ❌ Track A 분기 전진 (B3' / B3'' / first CAS write / B2-2 / CR-046 Phase 5a 실행)
- ❌ `EXECUTION_ENABLED` flag 전환
- ❌ 기존 evidence / package 본문 수정
- ❌ `ALLOWED_TRANSITIONS` / `FORBIDDEN_TARGETS` 수정
- ❌ receipt chain 스킵
- ❌ Track A에 해당하는 governance 위반

---

## 1. Plan A — Primary Execution (Track B from v1)

**Source**: `continuous_progress_plan_v1.md` §4.1 ~ §4.5
**Execution mode**: 순차, 한 항목 = 한 PR = 한 merge

| # | ID | 항목 | 산출물 |
|:---:|:---:|---|---|
| A1 | B-1 | CI coverage 기준선 수립 | `docs/operations/ci_coverage_baseline.md` |
| A2 | B-2 | CI concurrency cancel-in-progress | `.github/workflows/ci.yml` (블록 추가) |
| A3 | B-3 | SHA pinning inventory | `docs/operations/sha_pinning_inventory.md` |
| A4 | B-4 | CODEOWNERS draft 문서 | `docs/operations/codeowners_draft.md` |
| A5 | B-5 | CR-046 Phase 5a preflight | `docs/operations/evidence/cr046_phase5a_preflight.md` |

각 항목의 상세 명세는 `continuous_progress_plan_v1.md` §4.x 참조.

---

## 2. Plan B — Fallback Quality Improvements

**목적**: Plan A 완료 후 또는 Plan A 항목이 차단되어 skip된 경우 추가로 진행할 저위험 품질 작업.

| # | ID | 항목 | 산출물 | 조건 |
|:---:|:---:|---|---|---|
| B1 | Q-1 | Evidence index 문서 | `docs/operations/evidence_index.md` | 기존 evidence 본문 미수정 |
| B2 | Q-2 | Session operating runbook | `docs/operations/session_operating_runbook.md` | 운영 원칙만 기술 |
| B3 | Q-3 | Repository structure doc | `docs/operations/repository_structure.md` | 정적 구조 설명만 |

**공통 원칙**:
- 코드 변경 0건
- 기존 evidence 본문 수정 0건
- workflow 수정 0건
- 신규 문서 1건씩 생성

---

## 3. Plan C — Verification & Graduation

**목적**: Plan A + Plan B 완료 후 전체 세션의 산출물을 검증하고 최종 completion receipt 작성.

### Plan C 절차

1. **C1. Merge 이력 검증**
   - main 브랜치 최근 N개 커밋 확인
   - AELP merge 이후 커밋 수 집계
   - 각 PR의 squash merge + branch 삭제 상태 확인

2. **C2. CI 상태 검증**
   - 최신 main의 3 check (lint/test/build) 상태 확인
   - 실패 check 0건 확인

3. **C3. Track A 무결성 검증**
   - `cr048_ri2b2b_implementation_go_receipt.md` 서명 상태 (`d999aed`) 유지 확인
   - `cr048_ri2b2b_scope_review_package.md` v1.0 LOCK 유지 확인
   - `cr048_ri2a2b_activation_manifest.md` v1.1 SEALED 유지 확인
   - `EXECUTION_ENABLED` flag 값 = `False` 유지 확인

4. **C4. Evidence 본문 무결성 검증**
   - 기존 evidence 본문 수정 0건 확인 (git log로 해당 파일 변경 이력 체크)

5. **C5. Out-of-scope 위반 검증**
   - Plan A/B 실행 중 금지 항목 접촉 여부 확인
   - `shadow_write_service.py` 미수정 확인
   - `test_shadow_write_receipt.py` 미수정 확인

6. **C6. 완료 receipt 작성**
   - 신규 `docs/operations/evidence/aelp_v1_completion_receipt.md` 생성
   - Plan A/B 산출물 리스트 + 각 merge commit hash
   - Track A 무결성 검증 결과
   - 위반 0건 선언
   - STANDBY 전환 선언

---

## 4. Loop Rules (autonomous mode)

### 4.1 메인 루프

```text
AELP PR merge 완료 후 시작

for item in Plan_A:
    try execute(item)
    if blocked: record PASS reason, continue
    if ci_fail: record CI failure, continue
    if merge_success: record merge commit, continue

for item in Plan_B:
    try execute(item)
    if blocked: record PASS reason, continue
    if ci_fail: record CI failure, continue
    if merge_success: record merge commit, continue

Plan_C.execute()
  if no_issues: mark AELP COMPLETE
  if issues_found: report + halt (no Plan D auto-creation)

Final report → STANDBY
```

### 4.2 차단 감지 시 (autonomous mode 새 규칙)

| 상황 | 기존 v1 대응 | autonomous 대응 |
|---|---|---|
| 항목 시작 전 명백한 block | 세션 종료 | PASS + 다음 항목 |
| 실행 중 CI fail | 세션 종료 | CI fail 기록 + 다음 항목 |
| 로컬 도구 부재 | 세션 종료 | PASS 기록 + 다음 항목 |
| governance 위반 감지 | EMERGENCY STOP | **여전히 EMERGENCY STOP** |

> Governance 위반 감지는 autonomous mode에서도 즉시 halt 한다. 이 규칙은 완화되지 않는다.

### 4.3 절대 위반 금지 (autonomous mode에서도 불변)

- 기존 evidence 본문 수정
- `shadow_write_service.py` 비-테스트 수정
- `EXECUTION_ENABLED` flag 전환
- Track A 분기 어떤 형태의 전진
- receipt chain 스킵
- force push / rebase main
- hooks 우회

---

## 5. Stop Conditions

| 조건 | 효과 |
|---|---|
| Plan A + B + C 모두 완료 | **COMPLETE** → Final report → STANDBY |
| governance 위반 감지 | **EMERGENCY STOP** → 원인 보고 → STANDBY |
| 연속 3회 CI fail | **CIRCUIT BREAKER** → 원인 보고 → STANDBY |
| Plan A/B 모든 항목 skip (전부 blocked) | Plan C로 이동 |
| A의 interrupt 명시 지시 | 즉시 STANDBY |

---

## 6. 본 plan이 부여하는 것 / 부여하지 않는 것

### 부여 ✅
- Plan A 5개 항목 + Plan B 3개 항목 + Plan C 1개 항목에 대한 session-scoped 실행 권한
- 항목 간 자동 전환 권한 (P2 완화)
- 한 세션 내 복수 PR 생성/merge 권한 (P1 완화)
- Plan C 검증 및 완료 receipt 작성 권한
- 차단 항목 자동 skip 권한

### 부여하지 않음 ❌
- Track A 전진 (B3' / B3'' / B2-2 / 첫 write / CR-046 5a 실행)
- evidence 본문 수정
- 코드 실행 권한 (test/lint 외)
- `EXECUTION_ENABLED` / flag 전환
- 새 Plan 항목 자동 추가 (명시된 A1~A5, B1~B3, C 외)
- Plan D 자동 생성 (Plan C가 issue 발견 시 halt → 보고 → A 판단 대기)

---

## 7. References

| 문서 | 역할 |
|---|---|
| `docs/operations/continuous_progress_plan_v1.md` | Track B 원본 (Plan A source) |
| `docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` | Track A SIGNED (HOLD) |
| `docs/operations/evidence/cr048_ri2a2b_activation_manifest.md` | Activation BLOCKED |
| `docs/operations/evidence/receipt_naming_convention.md` | receipt 3 pattern |

---

## Footer

```
Autonomous Execution Loop Plan v1
Status            : ACTIVE
Created           : 2026-04-05
Authority         : A autonomous execution grant
Plan A            : 5 items (Track B from v1)
Plan B            : 3 items (quality fallbacks)
Plan C            : verification + completion receipt
Loop mode         : sequential auto-advance on block
Circuit breaker   : 3 consecutive CI fail OR governance violation
Forbidden         : Track A forward progression (unchanged)
Supersession      : Plan A+B+C complete → STANDBY
```
