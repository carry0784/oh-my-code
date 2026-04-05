# Receipt Naming Convention

**Document Type**: Governance Convention
**Authority**: A
**Issue Date**: 2026-04-05
**Version**: v1.0
**Status**: ACTIVE (applies to all subsequent receipts)

---

## 0. 목적

본 문서는 CR-048 계열 거버넌스 문서 승인 과정에서 발행되는 **3종 Receipt 파일**의
명명, 사용 시점, 필수 필드, 경계, 그리고 LOCK 원칙을 고정한다.

`cr048_ri2b2b_scope_review_acceptance_receipt.md` v1.0(2026-04-05)이
`*_acceptance_receipt.md` 패턴의 **첫 적용 사례**이며, 본 문서는 그 패턴의 규범(norm)을
이후 모든 receipt에 동일하게 적용하기 위해 작성된다.

본 문서는 **정책(policy)** 이며, 코드/테스트/워크플로/기존 evidence 본문을 수정하지 않는다.
본 문서의 개정은 A의 명시 승인 없이 허용되지 않는다.

---

## 1. Receipt 3패턴 정의

거버넌스 승인은 **3단계**로 분리되고, 각 단계마다 고유한 receipt 파일이 발행된다.

| # | 패턴 | 의미 | 승인 대상 | 권한 |
|:---:|---|---|---|:---:|
| 1 | `*_acceptance_receipt.md` | **문서 내용 승인** | 완결된 evidence / scope review / plan 문서의 본문 내용 | A |
| 2 | `*_implementation_go_receipt.md` | **구현 착수 승인** | 코드·설정·테스트 변경 착수 권한 | A |
| 3 | `*_activation_go_receipt.md` | **운영 활성화 승인** | beat / schedule / flag / 실제 write 경로 전환 권한 | A |

### 1.1 핵심 원칙

> **한 receipt = 한 승인 단계.** 한 receipt가 2개 이상의 승인(예: 본문 승인 + 구현 착수)을 겸할 수 없다.

---

## 2. 각 패턴의 사용 시점

### 2.1 `*_acceptance_receipt.md` — 문서 내용 승인

**사용 시점**:
- scope review package / completion evidence / design document / audit report 등
  **완결된 문서**가 제출되고, 그 문서의 **본문 내용**을 승인할 때.
- 문서 자체는 이미 LOCK되어 있고, 승인 흔적을 별도 파일에 기록해야 할 때.

**금지 사항**:
- 이 receipt 발행과 함께 대상 문서의 **본문을 수정해서는 안 된다** (No Write / No Edit / No Rename / No Move / No Delete).
- 이 receipt는 구현 GO 또는 활성화 GO를 **자동으로 부여하지 않는다**.

**예시**: `cr048_ri2b2b_scope_review_acceptance_receipt.md` (2026-04-05, 본 패턴 첫 적용)

---

### 2.2 `*_implementation_go_receipt.md` — 구현 착수 승인

**사용 시점**:
- 대상 scope가 이미 `*_acceptance_receipt.md`로 본문 승인 완료된 이후.
- 해당 scope의 **코드·설정·테스트 변경 착수**를 A가 허가할 때.
- 구현 범위, 허용 파일 목록, 금지 파일 목록, 회귀 기준, 롤백 조건이 명시되어야 할 때.

**전제 조건**:
1. 동일 scope의 `*_acceptance_receipt.md`가 이미 존재한다.
2. 본문 승인 이후 scope 변경이 없다 (변경되었다면 새 acceptance 필요).
3. Baseline regression이 최근 상태와 정합한다.

**금지 사항**:
- 이 receipt는 **활성화 GO를 자동으로 부여하지 않는다**.
- 실행 플래그(EXECUTION_ENABLED 등) False→True 전환, beat uncomment, DRY_SCHEDULE False 전환은
  이 receipt로 허용되지 않는다.

**예상 예시**: `cr048_ri2b2b_implementation_go_receipt.md` (향후 발행 예정)

---

### 2.3 `*_activation_go_receipt.md` — 운영 활성화 승인

**사용 시점**:
- 구현이 완료되고 회귀·안정성 검증이 끝난 이후.
- **운영 경로 전환**(실제 DB write, scheduler enable, flag 전환)을 A가 허가할 때.
- 24H dry-run clean, consecutive_failures=0, rollback_verified=true 등
  activation manifest 전체 기준이 충족된 상태에서만 발행된다.

**전제 조건**:
1. 동일 scope의 `*_acceptance_receipt.md` + `*_implementation_go_receipt.md`가 이미 존재한다.
2. Activation manifest의 모든 항목이 `true`이거나, 각 false 항목에 대한 예외 승인이 있다.
3. Rollback / kill-switch 경로가 문서화되고 검증되었다.

**금지 사항**:
- 이 receipt는 범위를 초과하는 추가 scope(예: 다른 symbol, 다른 table)로 **자동 확장되지 않는다**.
- 활성화 이후 장애 발생 시 이 receipt는 자동 철회되지 않으며, 별도 rollback receipt가 필요하다.

**예상 예시**: `cr048_ri2b2b_activation_go_receipt.md` (향후 발행 예정)

---

## 3. 각 패턴의 최소 필수 필드

세 패턴 모두 아래 **공통 필드**를 반드시 포함한다. 추가로 각 패턴별 고유 필드를 덧붙인다.

### 3.1 공통 필수 필드 (3패턴 전부)

| # | 필드명 | 설명 |
|:---:|---|---|
| 1 | **Receipt Type** | 3패턴 중 어느 것인지 명시 |
| 2 | **Authority** | 승인 권한자 (원칙상 `A`) |
| 3 | **Issue Date** | 발행일 (YYYY-MM-DD) |
| 4 | **Receipt Version** | `v1.0`부터 시작 |
| 5 | **대상 문서 / 대상 scope** | 파일 경로 + 버전 + 줄 수 + 작성일 |
| 6 | **판정** (ACCEPT / GO / BLOCK) + 판정일 |
| 7 | **Baseline 정합** (stage, version, regression 결과, 경고 수) |
| 8 | **근거 문서 4-chain 정합 표** (governance baseline / exception register / activation manifest / completion evidence) |
| 9 | **범위 경계 선언** (포함되는 것 / 포함되지 않는 것) |
| 10 | **세션 증빙** (본 receipt 발행 세션의 파일 변경 집계) |
| 11 | **승인자 서명** |
| 12 | **Receipt 무결성 선언** (checklist + code-block summary) |

### 3.2 `*_acceptance_receipt.md` 고유 필드

| # | 필드명 | 설명 |
|:---:|---|---|
| A1 | **LOCK 유지 선언** | No Write / No Edit / No Rename / No Move / No Delete 표 |
| A2 | **본문 수정 0줄 증빙** | `git status --porcelain`으로 검증 가능한 형태 |
| A3 | **구현 GO와의 분리 명시** | "본 ACCEPT는 구현 GO가 아니다" 문구 |

### 3.3 `*_implementation_go_receipt.md` 고유 필드

| # | 필드명 | 설명 |
|:---:|---|---|
| I1 | **선행 acceptance receipt 참조** | 파일 경로 + 판정일 |
| I2 | **허용 변경 파일 목록** | 절대 경로 + 변경 유형(추가/수정/삭제) |
| I3 | **금지 파일 목록** (FROZEN / RED / AMBER 파일) |
| I4 | **회귀 기준** (목표 테스트 수, 허용 경고 수, 신규 경고 상한) |
| I5 | **롤백 조건** (어떤 조건에서 즉시 revert) |
| I6 | **활성화 GO와의 분리 명시** | "본 GO는 운영 활성화가 아니다" 문구 |

### 3.4 `*_activation_go_receipt.md` 고유 필드

| # | 필드명 | 설명 |
|:---:|---|---|
| X1 | **선행 acceptance + implementation go receipt 참조** |
| X2 | **Activation manifest 상태 스냅샷** (전체 checklist 결과) |
| X3 | **운영 전환 대상** (flag, beat, schedule, table 등 구체 지정) |
| X4 | **1회성 범위 선언** (다른 scope로 자동 확장 불가) |
| X5 | **Kill-switch / rollback 경로** (수동 실행 명령 또는 함수명) |
| X6 | **모니터링 기준선** (활성화 직후 관찰할 지표와 허용 범위) |
| X7 | **철회 조건** (어떤 상황에서 본 activation go가 무효화되는지) |

---

## 4. 본문 승인 / 구현 승인 / 활성화 승인의 경계

세 승인은 **명확히 분리**되며, 한 승인이 다음 승인을 자동으로 부여하지 않는다.

### 4.1 경계 표

| 권한 | `acceptance` | `implementation_go` | `activation_go` |
|---|:---:|:---:|:---:|
| 문서 본문 내용 확정 | ✅ | (전제) | (전제) |
| 문서 본문 수정 권한 | ❌ | ❌ | ❌ |
| 코드/설정/테스트 수정 착수 | ❌ | ✅ | (전제) |
| FROZEN 파일 수정 | ❌ | ❌ | ❌ |
| ALLOWED_TRANSITIONS / FORBIDDEN_TARGETS 변경 | ❌ | ❌ | ❌ |
| EXECUTION_ENABLED False→True 전환 | ❌ | ❌ | ✅ |
| beat uncomment / DRY_SCHEDULE False | ❌ | ❌ | ✅ |
| 실제 business table write 실행 | ❌ | ❌ | ✅ |
| rollback_bounded_write() 수동 실행 | ❌ | ❌ | ✅ |
| Gate unlock | ❌ | ❌ | ❌ (별도 A 전용) |
| 범위 확장 (추가 symbol/table) | ❌ | ❌ | ❌ (별도 receipt) |

### 4.2 승인 누락 금지 규칙

- `implementation_go_receipt` 없이 코드 변경을 착수할 수 없다.
- `activation_go_receipt` 없이 운영 경로 전환을 시행할 수 없다.
- 3패턴 중 어느 단계라도 누락되면 **거버넌스 위반**이며, 사후 예외 승인으로 구제되지 않는다.

---

## 5. Naming / Versioning / Lock 원칙

### 5.1 Naming 원칙

| 원칙 | 설명 |
|---|---|
| Prefix | 대상 scope 식별자 + 단계 식별자 (예: `cr048_ri2b2b_`) |
| Suffix | 3패턴 중 하나 정확히 일치 (`_acceptance_receipt.md` / `_implementation_go_receipt.md` / `_activation_go_receipt.md`) |
| 저장 위치 | `docs/operations/evidence/` 하위 고정 |
| 파일명 규칙 | 소문자 + 언더스코어, 공백 금지, 한글 금지, 버전 suffix 금지 (버전은 문서 내부에 명시) |
| 중복 금지 | 동일 scope + 동일 패턴의 receipt는 1개만 존재한다 |

### 5.2 Versioning 원칙

| 원칙 | 설명 |
|---|---|
| 초기 버전 | `v1.0` |
| 증분 조건 | 판정 결과 유지 + 부가 증빙만 보강되는 경우에만 minor(`v1.1`) 증분 허용 |
| Major 증분 | 판정 결과 변경 시(ACCEPT→REJECT, GO→BLOCK 등)는 새 receipt 파일로 분리 발행 권장 |
| 버전 기록 위치 | receipt 본문 상단 metadata 테이블 + 하단 무결성 선언 코드블록 |
| Update Log | 증분 시 reason / source evidence / 날짜를 본문에 기록 |

### 5.3 Lock 원칙

| 원칙 | 설명 |
|---|---|
| 발행 즉시 LOCK | receipt 파일은 발행 커밋 직후 read-only로 간주된다 |
| 수정 금지 동작 | No Write / No Edit / No Rename / No Move / No Delete |
| LOCK 해제 권한 | A의 **명시적 지시**가 있을 때만 해제 가능 |
| 대상 문서 LOCK | `acceptance_receipt`는 대상 문서의 기존 LOCK을 **유지**하며, 해제하지 않는다 |
| 예외 처리 | 오탈자/링크 깨짐 등 사소한 보강도 A 지시 없이 수정 금지. 필요 시 후속 receipt로 보강 기록 |

---

## 6. "한 세션 한 작업" 및 "별도 A 지시 필수" 연결 규칙

### 6.1 한 세션 한 작업 원칙

본 프로젝트는 **한 세션에서 한 개의 거버넌스 작업만** 수행한다.

| 세션 유형 | 허용 범위 |
|---|---|
| Acceptance 세션 | 단일 acceptance receipt 1건 발행 (또는 선행 gap 보강 1건 + 해당 receipt) |
| Implementation 세션 | 단일 implementation go receipt 발행 + 그에 따른 코드 변경 범위 한정 |
| Activation 세션 | 단일 activation go receipt 발행 + 운영 전환 1회 |
| Docs-only 세션 | 단일 docs PR 1건 (본 convention 문서 같은 정책 문서) |

세션 내 범위 혼합(예: acceptance + implementation 동시 진행)은 **금지**된다.
범위 혼합이 필요하면 세션을 분리한다.

### 6.2 별도 A 지시 필수 규칙

아래 행위는 **개별 A 승인 receipt**가 각각 필요하며, 한 receipt가 둘 이상을 자동 위임하지 않는다.

| 행위 | 요구 receipt |
|---|---|
| 완결된 문서 본문 내용 확정 | `*_acceptance_receipt.md` |
| 코드·설정·테스트 변경 착수 | `*_implementation_go_receipt.md` |
| 운영 경로 전환 (flag / beat / schedule) | `*_activation_go_receipt.md` |
| Gate LOCK / UNLOCK 전환 | 별도 `*_gate_unlock_receipt.md` (향후 패턴) |
| ALLOWED_TRANSITIONS 확장 | 별도 A 전용 receipt (본 convention 범위 외) |
| 예외 조건부 revert | 별도 `*_rollback_receipt.md` (향후 패턴) |

### 6.3 연결 체인

단일 scope의 표준 승인 체인은 아래와 같다.

```
[문서 작성]
    ↓
*_scope_review_package.md (v1.0)
    ↓
*_acceptance_receipt.md (A 판정 ACCEPT)
    ↓
*_implementation_go_receipt.md (A 구현 착수 GO)
    ↓
[코드 변경 + 테스트 + 회귀 검증]
    ↓
*_completion_evidence.md
    ↓
*_activation_go_receipt.md (A 운영 활성화 GO)
    ↓
[실제 운영 전환 1회]
    ↓
[관찰 기간 + 안정성 확인]
    ↓
SEALED
```

중간 단계를 건너뛰면 거버넌스 위반이다.

---

## 7. Decision Matrix (승인 유형 결정 표)

다음 표는 **"지금 필요한 receipt는 무엇인가"** 를 판정할 때 사용한다.

| 질문 | 답변 Yes → | 답변 No → |
|---|---|---|
| Q1. 대상이 **완결된 문서의 내용 승인**인가? | `*_acceptance_receipt.md` 발행 → 종료 | Q2로 |
| Q2. 대상이 **코드·설정·테스트 변경 착수 허가**인가? | 선행 acceptance 존재 확인 → `*_implementation_go_receipt.md` 발행 → 종료 | Q3로 |
| Q3. 대상이 **운영 경로 전환 허가**(flag / beat / schedule / 실제 write)인가? | 선행 acceptance + implementation go 존재 확인 + activation manifest 전체 충족 확인 → `*_activation_go_receipt.md` 발행 → 종료 | Q4로 |
| Q4. 대상이 Gate / ALLOWED_TRANSITIONS / FORBIDDEN_TARGETS 변경인가? | 본 convention 범위 외. 별도 A 전용 승인 절차 필요 | Q5로 |
| Q5. 대상이 사후 예외 승인인가? | `exception_register.md`에 EX-XXX 등록 (receipt 아님) | 재검토 필요. A에 문의 |

### 7.1 승인 유형별 축약

| 승인 유형 | Receipt 파일 패턴 | Receipt 내 판정어 |
|---|---|---|
| 문서 내용 승인 | `*_acceptance_receipt.md` | `ACCEPT` / `REJECT` |
| 구현 착수 승인 | `*_implementation_go_receipt.md` | `GO` / `BLOCK` |
| 활성화(운영 전환) 승인 | `*_activation_go_receipt.md` | `GO` / `HOLD` |

### 7.2 승인 거부 / 보류 시 처리

| 판정 | 처리 |
|---|---|
| `REJECT` | receipt는 발행하되 판정란에 REJECT 명시 + 원인 기록. 대상 문서 수정 후 새 acceptance로 재도전 |
| `BLOCK` | implementation go 발행 자체 보류. 선행 조건 충족 후 재평가 |
| `HOLD` | activation 보류. manifest gap 해소 후 재평가 |
| `CONDITIONAL` | 조건부 승인 — receipt에 해제 조건을 명시하고 조건 충족 시 자동 GO는 **금지**. 새 receipt로 확정 |

---

## 8. 본 Convention 문서의 자기 구속 선언

본 convention 문서는 다음을 스스로에 대해 선언한다.

- [x] 본 문서는 정책(policy) 문서이며 실행 권한을 부여하지 않는다.
- [x] 본 문서의 발행은 `*_acceptance_receipt.md` 패턴 대상이 아니다 (정책 자체는 receipt 체인 밖에 있다).
- [x] 본 문서의 개정은 A의 명시적 지시가 있을 때만 수행된다.
- [x] 본 문서는 CR-048 계열 뿐 아니라 이후 모든 CR에도 기본 적용된다.
- [x] 본 문서의 내용과 기존 `cr048_ri2b2b_scope_review_acceptance_receipt.md` v1.0 간 충돌이 발견되면,
      receipt 본문을 수정하지 않고 본 convention 문서에 각주/보강으로 기록한다.

---

## 9. 적용 범위

| 대상 | 적용 여부 |
|---|:---:|
| CR-048 RI 하위 모든 승인 절차 | ✅ |
| CR-049 이후 신규 CR | ✅ |
| CR-046 Phase 5a 이후 승인 절차 | ✅ (준용) |
| 과거 SEALED 문서의 사후 receipt 발행 | ✅ (소급 가능, 단 본문 수정 금지) |
| 단순 docs PR (본 문서 유형) | ❌ (receipt 대상 아님, 일반 PR로 처리) |

---

## 10. 무결성 선언

```
Receipt Naming Convention v1.0
Scope: CR-048 이후 모든 거버넌스 receipt
Patterns: *_acceptance_receipt.md / *_implementation_go_receipt.md / *_activation_go_receipt.md
Authority: A
Issued: 2026-04-05
First acceptance receipt instance: cr048_ri2b2b_scope_review_acceptance_receipt.md v1.0 (2026-04-05)
Enforcement: effective immediately
Modification: A explicit instruction required
Lock: applied upon initial commit
Boundaries: body approval / implementation approval / activation approval strictly separated
Chain skip: governance violation (no retroactive exception)
```
