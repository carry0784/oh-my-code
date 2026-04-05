# CR-048 RI-2B-2b Implementation GO Receipt

**Receipt Type**: Implementation GO (code/config change authorization)
**Authority**: A
**Issue Date**: 2026-04-05
**Receipt Version**: v1.0
**Status**: **DRAFT — PENDING A SIGNATURE**

> **본 문서는 초안(DRAFT)이다.**
> 판정란이 BLANK 상태이며, A의 명시적 서명이 기록되기 전까지 **어떠한 구현 착수도 허용되지 않는다**.
> 본 문서의 존재만으로는 코드/설정/테스트/플래그/실행 경로를 수정할 권한이 생기지 않는다.

---

## 0. 문서 성격 선언

| 항목 | 값 |
|---|---|
| 규범 | `docs/operations/evidence/receipt_naming_convention.md` v1.0 §3.3 (I1–I6 필드 엄격 준수) |
| 선례 | `cr048_ri2b2b_scope_review_acceptance_receipt.md` v1.0 (`*_acceptance_receipt.md` 패턴 첫 적용) |
| 본 문서 위치 | 체인 2단계 — 본문 승인 완료 후, 구현 착수 승인 **대기** 단계 |
| 서명 전 상태 | **DRAFT**. 본 receipt는 즉시 효력을 발생시키지 않는다. |
| 서명 후 상태 | GO — 단, §7의 허용 변경 파일 목록과 §9의 회귀 기준 안에서만 |

---

## 1. 대상 scope

| 항목 | 값 |
|---|---|
| CR | **CR-048** |
| Stage | **RI-2B-2b** |
| 요약 | 최초 bounded business table write 활성화 |
| 대상 테이블 | `symbols` (1개) |
| 대상 필드 | `qualification_status` (1개) |
| 대상 전이 | `unchecked → pass`, `unchecked → fail` (2개) |
| 실행 방식 | **manual trigger only** (beat / schedule / periodic 호출 없음) |
| 한 줄 목표 | "`EXECUTION_ENABLED=True`로 전환하여, shadow receipt 근거의 CAS bounded write를 수동 실행 가능하게 한다. 자동화 없음, 범위 확장 없음." |

---

## 2. 판정 (BLANK / DRAFT)

| 항목 | 값 |
|---|---|
| **판정** | **✅ GO** |
| **판정 후보** | `GO` / `BLOCK` / `CONDITIONAL` |
| **판정 권한** | A (유일) |
| **판정일** | **2026-04-05** |
| **현재 상태 전환** | `A 판정 대기` (판정되지 않은 상태) |
| **서명 완료 전 효력** | **NONE** — 본 문서는 초안이며 실행 권한을 부여하지 않는다. |

> 본 receipt는 A가 판정란에 `GO` / `BLOCK` / `CONDITIONAL` 중 하나를 기입하고 서명일을 함께 기록할 때 비로소 효력이 발생한다. 그 전까지 본 문서는 **구현 조건의 서면 고정 초안** 이상의 의미를 갖지 않는다.

---

## 3. Baseline 정합

| 항목 | 값 |
|---|---|
| Stage | RI-2A-2b SEALED |
| Baseline | **v2.5** |
| Regression | **5456 / 5456 PASS** |
| Warnings | 10 (PRE-EXISTING OBS-001) |
| New warnings | 0 |
| Gate | LOCKED |
| FROZEN / RED 접촉 | 0건 |

---

## 4. 근거 문서 4-chain 정합 표

| # | 근거 문서 | 상태 | 정합 상태어 |
|:---:|---|:---:|---|
| 1 | `docs/operations/current_governance_baseline.md` | ✅ | `RI-2A-2b SEALED · v2.5 · 5456/5456 PASS` |
| 2 | `docs/operations/evidence/exception_register.md` | ✅ | `RI-2A-2b 예외 0건 · RI-2B-2a 예외 0건 (EXECUTION_ENABLED=False 하드코딩)` |
| 3 | `docs/operations/evidence/cr048_ri2b2b_scope_review_package.md` **v1.0** (481 lines) | ✅ | LOCK 유지, 본문 무접촉 |
| 4 | `docs/operations/evidence/cr048_ri2b2b_scope_review_acceptance_receipt.md` **v1.0** | ✅ | `ACCEPT · 2026-04-05 · A 권한 · body ZERO modification` |
| 5 | `docs/operations/evidence/receipt_naming_convention.md` **v1.0** | ✅ | 본 receipt의 구조 규범. I1–I6 필드 엄격 준수 |

**충돌 건수**: 0
**상태어 일치**: 5/5

---

## 5. I1 — 선행 acceptance receipt 참조

| 항목 | 값 |
|---|---|
| 파일 경로 | `docs/operations/evidence/cr048_ri2b2b_scope_review_acceptance_receipt.md` |
| 버전 | v1.0 |
| 판정 | ACCEPT |
| 판정 권한 | A |
| 판정일 | 2026-04-05 |
| 대상 | `cr048_ri2b2b_scope_review_package.md` v1.0 (481 lines) |
| 본문 무접촉 증명 | `git status --porcelain docs/operations/evidence/cr048_ri2b2b_scope_review_package.md` → empty |

### 5.1 본 implementation GO 초안이 성립하는 이유

- 선행 `*_acceptance_receipt.md`가 존재한다 (convention §2.2 전제 조건 1 충족).
- 본문 승인 이후 scope가 변경되지 않았다 (convention §2.2 전제 조건 2 충족).
- Baseline regression(v2.5, 5456/5456 PASS)이 최근 상태와 정합한다 (convention §2.2 전제 조건 3 충족).

---

## 6. 구현 scope 요약 (scope review package §4·§8 직접 참조)

| 항목 | 값 |
|---|---|
| 코드 변경 라인 총합 | **1줄** (운영 코드) + 약 3줄 (테스트) |
| 신규 파일 | **0** |
| 모델 / 마이그레이션 변경 | **0** |
| 신규 함수 | **0** |
| SEALED 함수 body 수정 | **0** (execute_bounded_write, rollback_bounded_write 전부 read-only) |
| 기존 상수 수정 | **0** (ALLOWED_TRANSITIONS, FORBIDDEN_TARGETS, BlockReasonCode, ExecutionVerdict 전부 불변) |
| 자동화 활성화 | **0** (beat 변경 없음, schedule 변경 없음) |
| gate 변경 | **0** (gate 변경 코드 라인 0줄) |

---

## 7. I2 — 허용 변경 파일 목록

A가 본 receipt에 GO 서명 시, **오직 아래 2개 파일**만 변경이 허용된다.

| # | 파일 | 허용 변경 | 허용 범위 |
|:---:|---|---|---|
| 1 | `app/services/shadow_write_service.py` | **수정 1줄** | `EXECUTION_ENABLED: bool = False` → `EXECUTION_ENABLED: bool = True` 단일 리터럴 변경. 함수/클래스/임포트/다른 상수 수정 금지. |
| 2 | `tests/test_shadow_write_receipt.py` | **수정 약 3줄** | 기존 `test_execution_enabled_is_false` → `test_execution_enabled_is_true` 변환. 테스트 이름, assertion 값, docstring 3개 라인에 한정. 신규 테스트 추가 금지, 기존 테스트 삭제 금지. |

### 7.1 허용 변경의 경계

- 총 변경 라인: 운영 코드 1줄 + 테스트 약 3줄 = **최대 4줄**
- 4줄 초과 시 본 receipt의 허용 범위를 벗어난 것으로 간주한다.
- 린트/포매터가 추가로 건드리는 공백/줄바꿈은 예외로 허용하되, 동일 PR 내에 포함되어야 한다.

---

## 8. I3 — 금지 파일 목록 (FROZEN / RED / SEALED)

아래 파일은 본 receipt의 서명 여부와 무관하게 **절대 수정 금지**이다.

### 8.1 SEALED 함수·상수 (RI-2B-1 / RI-2B-2a 봉인)

| # | 대상 | 봉인 단계 |
|:---:|---|---|
| 1 | `shadow_write_service.py::execute_bounded_write()` 함수 body | RI-2B-2a SEALED |
| 2 | `shadow_write_service.py::rollback_bounded_write()` 함수 body | RI-2B-2a SEALED |
| 3 | `shadow_write_service.py::evaluate_verdict()` | RI-2B-1 SEALED |
| 4 | `shadow_write_service.py::evaluate_shadow_write()` | RI-2B-1 SEALED |
| 5 | `ALLOWED_TRANSITIONS` 상수 | 불변 |
| 6 | `FORBIDDEN_TARGETS` 상수 | 불변 |
| 7 | `BlockReasonCode` enum (10값) | 추가/제거 0 |
| 8 | `ExecutionVerdict` enum (4값) | 추가/제거 0 |
| 9 | 10-step execution flow 구조 | RI-2B-2a 계약, 변경 0 |

### 8.2 FROZEN / RED 파일 (전체)

| # | 카테고리 | 예시 |
|:---:|---|---|
| 1 | Gate 관련 파일 | gate LOCKED 유지, 변경 0 |
| 2 | 모델 / 마이그레이션 | `app/models/symbol.py`, `alembic/versions/*` |
| 3 | exchanges / router / 외부 IO 경계 | 접촉 0건 |
| 4 | promotion / paper 경로 | CR-046 frozen, Phase 4+ blocked |
| 5 | runtime_strategy_loader 계열 | EX-002로 일회성 예외만 있었음, 재접촉 금지 |
| 6 | Celery beat schedule | 주석 상태 유지, uncomment 금지 |
| 7 | DRY_SCHEDULE 플래그 | True 유지, False 전환 금지 |
| 8 | Purge / retention 활성화 | 미구현 유지 |

### 8.3 금지 동작 (scope review package §12.3 계승)

| # | 금지 | 사유 |
|:---:|---|---|
| 1 | `ALLOWED_TRANSITIONS` 확장 | 별도 A 승인 필수 |
| 2 | `FORBIDDEN_TARGETS` 축소 | 절대 금지 |
| 3 | `beat` / `schedule`에서 execute 호출 | 자동 실행 금지 |
| 4 | `qualification_status` 외 필드 write | scope 밖 |
| 5 | `symbols.status` UPDATE | FORBIDDEN_TARGET |
| 6 | `promotion` / `paper` 경로 활성화 | CR-046 frozen |
| 7 | `execute_bounded_write` 함수 body 수정 | RI-2B-2a SEALED |
| 8 | `rollback_bounded_write` 함수 body 수정 | RI-2B-2a SEALED |
| 9 | 자동 chain rollback | 수동만 허용 |
| 10 | gate unlock | A 전용, 별도 receipt 필요 |

---

## 9. I4 — 회귀 기준

| 항목 | 기준 |
|---|---|
| **Regression 테스트 수** | **5456 / 5456 PASS** 이상 |
| **허용 테스트 수 증감** | 0 또는 +N (신규 테스트 추가는 본 receipt 범위 밖이므로 기본 0) |
| **테스트 전환 카운트** | test_execution_enabled_is_false → test_execution_enabled_is_true 1건 (이름 변경, 수 증감 0) |
| **경고 상한** | 10 (PRE-EXISTING OBS-001 유지) |
| **신규 경고 허용** | **0건** (단 1건이라도 신규 경고 발생 시 BLOCK) |
| **CI 체크** | `lint` / `test` / `build` 전부 green |
| **Purity Guard** | 117 tests PASS 유지 |
| **Pure Zone** | 10 files UNTOUCHED |
| **회귀 증빙 위치** | 구현 PR 본문 + 후속 `cr048_ri2b2b_completion_evidence.md` |

### 9.1 회귀 실패 시 행동

1. 즉시 PR close 또는 revert
2. 회귀 실패 원인 분석 후 본 receipt 판정을 `BLOCK`으로 갱신 (새 DRAFT v1.1 또는 별도 receipt)
3. 회귀 실패 건은 `exception_register.md`에 OBS/EX로 기록

---

## 10. I5 — 롤백 조건

본 receipt의 서명 이후 구현이 시작되면, 아래 조건 중 **단 하나라도** 발생 시 **즉시 revert**한다.

| # | 트리거 | 행동 |
|:---:|---|---|
| 1 | 회귀 테스트 5456 중 1건이라도 FAIL | 즉시 revert |
| 2 | 신규 경고 1건이라도 발생 | 즉시 revert |
| 3 | 허용 변경 파일 목록(§7) 외 파일 수정 흔적 발견 | 즉시 revert |
| 4 | SEALED 함수 body에 수정 흔적 발견 | 즉시 revert + 사고 보고 |
| 5 | FORBIDDEN_TARGETS 축소 또는 ALLOWED_TRANSITIONS 확장 흔적 | 즉시 revert + 사고 보고 |
| 6 | `EXECUTION_ENABLED=True` 전환 이후 **의도치 않은 실제 write 흔적 발견** | 즉시 revert + `EXECUTION_ENABLED=False` 복원 + qualification_status 수동 SQL 복원 |
| 7 | `beat` / `schedule` 경로에서 execute 호출 감지 | 즉시 revert + 긴급 감사 |
| 8 | CI 체크 3개(lint/test/build) 중 1개라도 red | PR close, 원인 분석 후 재평가 |

### 10.1 롤백 수행 시 기록 의무

- 롤백이 발생하면 `exception_register.md`에 새 EX-XXX 항목을 등록한다.
- 롤백 이후에도 본 receipt는 자동 철회되지 않으며, A의 재평가가 필요하다.
- 필요 시 별도 `cr048_ri2b2b_rollback_receipt.md` 발행을 고려한다 (향후 패턴).

---

## 11. I6 — 활성화 GO와의 분리 명시

> **본 implementation GO receipt는 `*_activation_go_receipt.md`가 아니다.**
>
> 본 문서는 A 서명 시 **코드 변경 1줄 + 테스트 약 3줄**의 착수를 허가할 뿐이며,
> 실제 **운영 경로 전환**(manual execute_bounded_write 호출, 실제 첫 CAS bounded write 실행 등)은
> **별도의 `cr048_ri2b2b_activation_go_receipt.md`** 발행 후에만 수행할 수 있다.

| 구분 | 본 receipt (implementation GO) | 향후 receipt (activation GO) |
|---|:---:|:---:|
| `EXECUTION_ENABLED` 상수 False→True 편집 | ✅ (코드 변경) | — |
| 테스트 flag 검증 전환 | ✅ | — |
| 빌드/테스트 회귀 green 확보 | ✅ | — |
| **실제 `execute_bounded_write()` 호출 (manual)** | ❌ | ✅ |
| **첫 실제 CAS bounded write 실행** | ❌ | ✅ |
| **rollback_bounded_write() 수동 실행 권한** | ❌ | ✅ |
| beat uncomment / DRY_SCHEDULE False | ❌ | ❌ (본 scope 밖) |

> `EXECUTION_ENABLED=True` 상수 편집과 **실제 실행 행위**는 별개이다. 상수 편집이 완료되어도, 실제 함수 호출은 activation GO 없이 금지된다.

---

## 12. 이 문서가 부여하지 않는 것 (negative scope)

> A 추가 제안 반영: 본 문서와 실행 허가 문서의 경계를 명시적으로 기록한다.

본 receipt는 서명 여부와 무관하게 **아래 권한을 부여하지 않는다**.

| # | 미부여 권한 | 사유 |
|:---:|---|---|
| 1 | `EXECUTION_ENABLED=True` 이후 **실제 실행 허가** | activation GO 별도 필요 |
| 2 | 첫 실제 CAS bounded write 1건 실행 권한 | activation GO 별도 필요 |
| 3 | `rollback_bounded_write()` 수동 실행 권한 | activation GO 별도 필요 |
| 4 | `ALLOWED_TRANSITIONS` 추가/수정 권한 | 별도 A 전용 승인 |
| 5 | `FORBIDDEN_TARGETS` 축소 권한 | 절대 금지, 예외 없음 |
| 6 | `BlockReasonCode` / `ExecutionVerdict` 변경 권한 | 별도 A 전용 승인 |
| 7 | Celery beat schedule uncomment 권한 | 별도 activation go |
| 8 | `DRY_SCHEDULE=False` 전환 권한 | 별도 A 승인 |
| 9 | purge / retention 활성화 권한 | 별도 A 승인 |
| 10 | Gate LOCK/UNLOCK 전환 권한 | A 전용, 별도 receipt |
| 11 | 다른 symbol / 다른 table 확장 권한 | scope 확장 별도 receipt |
| 12 | `promotion` / `paper` 경로 활성화 | CR-046 frozen 상태 유지 |
| 13 | 자동 chain rollback | 수동만 허용 |
| 14 | 본 scope 외 CR로의 자동 위임 | 각 CR은 고유 receipt 체인 필요 |
| 15 | scope review package 본문 수정 권한 | LOCK 유지 |
| 16 | acceptance receipt 본문 수정 권한 | LOCK 유지 |

> **요약**: 본 receipt의 최대 권한은 "코드 1줄 + 테스트 약 3줄 변경"이며, 그 이상의 모든 권한은 별도 receipt가 필요하다.

---

## 13. 세션 증빙 (본 초안 발행 세션)

본 초안 발행 세션의 파일 변경 집계:

| 카테고리 | 대상 | 변경 수 |
|---|---|:---:|
| scope review 본문 | `cr048_ri2b2b_scope_review_package.md` | **0** |
| acceptance receipt 본문 | `cr048_ri2b2b_scope_review_acceptance_receipt.md` | **0** |
| activation manifest | `cr048_ri2a2b_activation_manifest.md` | **0** |
| governance baseline | `current_governance_baseline.md` | **0** |
| exception register | `exception_register.md` | **0** |
| completion evidence | `cr048_ri2a2b_completion_evidence.md` | **0** |
| receipt naming convention | `receipt_naming_convention.md` | **0** |
| 코드 파일 | `app/services/shadow_write_service.py` | **0** |
| 테스트 파일 | `tests/test_shadow_write_receipt.py` | **0** |
| 워크플로 / settings | `.github/workflows/*`, `.github/settings`, rulesets | **0** |
| 본 receipt (신규) | `cr048_ri2b2b_implementation_go_receipt.md` | 1 Write (본 파일) |

### 13.1 본 초안 세션 전용 증빙

| 호출 유형 | 대상 `shadow_write_service.py` / `test_shadow_write_receipt.py` | 호출 수 |
|---|:---:|:---:|
| Read (read-only) | — | 0 |
| **Write** | ❌ | **0** |
| **Edit** | ❌ | **0** |

| 호출 유형 | 대상 `cr048_ri2b2b_scope_review_package.md` | 호출 수 |
|---|:---:|:---:|
| Read (read-only, 구현 scope 확인 목적) | ✅ | ≥1 |
| **Write / Edit / Rename / Delete** | ❌ | **0** |

> `git status --porcelain`으로 본 receipt 외 다른 파일의 수정 0줄이 증명된다.

---

## 14. 승인자 서명란 (BLANK)

> 본 서명란은 A가 직접 기입하기 전까지 **BLANK 상태로 유지**되어야 한다.
> 서명 없이 기입된 내용이 발견되면 본 receipt 전체를 무효화한다.

| 항목 | 값 |
|---|---|
| 승인자 | **A** |
| 권한 유형 | 최종 의사결정자 |
| 승인 형태 | Implementation GO (단, 본 receipt 서명 시 한정) |
| 승인일 | **2026-04-05** |
| 판정 | **✅ GO** |
| 서명 이후 효력 발생 시각 | 서명일 00:00 KST (서명일 기준) |
| 효력 종료 | GO 서명 후 구현 PR이 merge되거나 revert된 시점 |
| 승인 철회 조건 | A 명시 지시 시에만 가능. 자동 철회 조건 없음. |

---

## 15. 적용 규칙 (본 건부터 고정)

| 규칙 | 설명 |
|---|---|
| 본 receipt는 `*_implementation_go_receipt.md` 패턴의 **첫 초안 사례**이다 | `receipt_naming_convention.md` §2.2를 최초로 구체 적용 |
| DRAFT 상태에서도 LOCK 대상이다 | 본문 임의 수정 금지. A 지시 없이 Edit/Rename/Move/Delete 금지. |
| A 서명 이후 Version bump 규칙 | 서명만으로는 version이 bump되지 않는다. 서명 결과를 §14와 §2에 기입 후 새 커밋으로 반영. |
| 구조 규범 이탈 금지 | §5~§11(I1~I6)의 필드 순서·명칭은 convention §3.3을 그대로 따른다. |
| 선례 사용 가능 여부 | 본 receipt 자체는 선례로 사용 가능하나, scope는 자동 승계되지 않는다. |

---

## 16. Receipt 무결성 선언

본 receipt는 다음 조건을 모두 충족한다:

- [x] receipt_naming_convention v1.0 §3.3 (I1–I6) 필드 전부 포함
- [x] 선행 acceptance receipt 참조 포함 (§5)
- [x] 허용 변경 파일 목록이 2개 이하로 한정됨 (§7)
- [x] 금지 파일 목록이 SEALED + FROZEN + RED 범주로 명시됨 (§8)
- [x] 회귀 기준이 v2.5 (5456/5456 PASS)와 정합 (§9)
- [x] 롤백 조건이 8개 트리거로 명시됨 (§10)
- [x] activation GO와의 분리가 명시됨 (§11)
- [x] 본 문서가 부여하지 않는 권한이 16개로 명시됨 (§12)
- [x] 판정란이 BLANK 상태 (§2, §14)
- [x] A 서명 전에는 효력 없음을 명시 (§0, §2, §14)
- [x] 본 receipt 외 다른 파일 변경 0건 (§13)
- [x] 4-chain 정합 5/5 (§4)

```
CR-048 RI-2B-2b Implementation GO Receipt v1.0
Target: code change 1 line (EXECUTION_ENABLED False→True)
        + test change ~3 lines (flag verification transition)
Status: DRAFT — PENDING A SIGNATURE
Verdict: BLANK (⬜)
Authority: A (pending)
Issued: 2026-04-05
Effective: NONE until A explicit signature
Baseline: v2.5 (5456/5456 PASS)
4-chain consistency: 5/5
Max permission on sign: 1 line operational code + ~3 lines test = 4 lines total
Activation GO: NOT INCLUDED (separate receipt required)
Actual execution of execute_bounded_write(): NOT GRANTED (activation go required)
First CAS bounded write: NOT GRANTED (activation go required)
Gate unlock: NOT GRANTED (A-only, separate receipt)
ALLOWED_TRANSITIONS change: NOT GRANTED (ever, separate A approval)
FORBIDDEN_TARGETS reduction: FORBIDDEN (no exception)
Rollback triggers: 8 conditions, immediate revert
Lock status: maintained on scope review package and acceptance receipt
Convention compliance: receipt_naming_convention v1.0 §3.3 I1–I6 strict
Pattern inauguration: first use of *_implementation_go_receipt.md pattern (DRAFT form)
```
