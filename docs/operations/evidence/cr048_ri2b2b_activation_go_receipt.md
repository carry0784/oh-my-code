# CR-048 RI-2B-2b Activation GO Receipt

**Receipt Type**: Activation GO (first real bounded CAS write authorization)
**Authority**: A
**Issue Date**: 2026-04-05
**Receipt Version**: v1.0
**Status**: **DRAFT — PENDING A SIGNATURE**

> **본 문서는 초안(DRAFT)이다.**
> 판정란(P1), 판정일(P2), 실행 대상(P4), 롤백 권한(P5)이 전부 BLANK 상태이며,
> A의 명시적 서명이 기록되기 전까지 **어떠한 실제 실행도 허용되지 않는다**.
> 본 문서의 존재만으로는 `execute_bounded_write()` 호출, 실제 CAS bounded write 실행,
> `rollback_bounded_write()` 호출 권한이 생기지 않는다.

---

## 0. 문서 성격 선언

| 항목 | 값 |
|---|---|
| 규범 | `docs/operations/evidence/receipt_naming_convention.md` v1.0 §3.4 (I1–I6 필드 엄격 준수, activation 패턴) |
| 선례 (구조) | `cr048_ri2b2b_implementation_go_receipt.md` v1.0 (I1–I6 필드 구조 직접 상속) |
| 본 문서 위치 | 체인 3단계 — 구현 완료(B3') 이후, **실제 첫 bounded CAS write 실행 승인 대기** 단계 |
| 서명 전 상태 | **DRAFT**. 본 receipt는 즉시 효력을 발생시키지 않는다. |
| 서명 후 상태 | GO — 단, §7의 허용 실행 항목과 §9의 verification 기준 안에서만 **1회** |
| 첫 적용 패턴 | `*_activation_go_receipt.md` 패턴의 첫 초안 사례 |

---

## 1. 대상 scope

| 항목 | 값 |
|---|---|
| CR | **CR-048** |
| Stage | **RI-2B-2b** (activation step, post-B3') |
| 요약 | 최초 bounded business table write **수동 1회 실행** 승인 |
| 대상 테이블 | `symbols` (1개) |
| 대상 필드 | `qualification_status` (1개 column) |
| 대상 row 수 | **1** (P4.symbol로 유일 식별) |
| 대상 전이 후보 | `unchecked → pass`, `unchecked → fail` (2개 중 1개, P4.intended_value에서 확정) |
| 실행 방식 | **manual trigger only**, **1회 한정**, **batch 금지**, **재시도 금지** |
| 한 줄 목표 | "`EXECUTION_ENABLED=True` 상태(B3' merge 완료)에서, P4에 기재된 symbol 1건에 대해 shadow receipt 근거의 CAS bounded write를 수동 1회 실행한다. 자동화 없음, 범위 확장 없음." |

---

## 2. 판정 슬롯 (BLANK / DRAFT)

| 항목 | 값 |
|---|---|
| **P1 판정** | **⬜ BLANK** |
| P1 판정 후보 | `GO` / `BLOCK` / `CONDITIONAL` |
| P1 판정 권한 | A (유일) |
| **P2 판정일** | **⬜ BLANK** (예상 형식: `YYYY-MM-DD`) |
| **P4 실행 대상** | **⬜ BLANK** (§7.1 slot 구조 참조) |
| **P5 롤백 권한** | **⬜ BLANK** (`YES` / `NO`) |
| 현재 상태 전환 | `A 판정 대기` (DRAFT) |
| 서명 완료 전 효력 | **NONE** — 본 문서는 초안이며 실행 권한을 부여하지 않는다. |

> 본 receipt는 A가 §14 서명란에 P1(판정) / P2(판정일) / P4(symbol, intended_value, shadow_receipt_id) / P5(rollback 권한)를 전부 기입할 때 비로소 효력이 발생한다. 그 전까지 본 문서는 **실행 조건의 서면 고정 초안** 이상의 의미를 갖지 않는다.

---

## 3. Baseline 정합

| 항목 | 값 |
|---|---|
| Stage | RI-2B-2b B3' COMPLETE |
| Main head | `409ed2d` (B3' flag flip merge) |
| Implementation GO head | `d999aed` (A signed 2026-04-04) |
| Regression (최신 참조) | **5456 / 5456 PASS** 이상 (B3' CI green 확인) |
| Warnings | 10 이내 (PRE-EXISTING OBS-001) |
| New warnings | 0 |
| EXECUTION_ENABLED | **True** (B3' 반영 완료) |
| 실제 bounded write 수행 여부 | **0건** (B3' 단계에서 flag만 flip, 실제 실행 없음) |
| Gate | LOCKED |
| FROZEN / RED 접촉 | 0건 |

---

## 4. 근거 문서 4-chain 정합 표

| # | 근거 문서 | 상태 | 정합 상태어 |
|:---:|---|:---:|---|
| 1 | `docs/operations/current_governance_baseline.md` | ✅ | `RI-2B-2b B3' COMPLETE · EXECUTION_ENABLED=True · 실제 write 0건` |
| 2 | `docs/operations/evidence/exception_register.md` | ✅ | `RI-2B-2b 예외 0건 (B3' post-merge)` |
| 3 | `docs/operations/evidence/cr048_ri2b2b_scope_review_package.md` **v1.0** | ✅ | LOCK 유지, 본문 무접촉 |
| 4 | `docs/operations/evidence/cr048_ri2b2b_scope_review_acceptance_receipt.md` **v1.0** | ✅ | `ACCEPT · A 권한 · body ZERO modification` |
| 5 | `docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` **v1.0** | ✅ | `GO · A 서명 완료 (d999aed, 2026-04-04) · body ZERO modification` |
| 6 | `docs/operations/evidence/receipt_naming_convention.md` **v1.0** | ✅ | 본 receipt의 구조 규범. I1–I6 필드 엄격 준수 (activation 패턴) |

**충돌 건수**: 0
**상태어 일치**: 6/6

---

## 5. I1 — 선행 implementation GO receipt 참조

| 항목 | 값 |
|---|---|
| 파일 경로 | `docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` |
| 버전 | v1.0 |
| 판정 | GO (A 서명 완료) |
| 판정 권한 | A |
| 판정일 | 2026-04-04 |
| 반영 merge SHA | `d999aed` (PR #34) |
| 후속 B3' merge SHA | `409ed2d` (PR #46) |
| 본문 무접촉 증명 | `git log d999aed..HEAD -- docs/operations/evidence/cr048_ri2b2b_implementation_go_receipt.md` → empty |

### 5.1 본 activation GO 초안이 성립하는 이유

- 선행 `*_implementation_go_receipt.md`가 **A 서명 완료 상태로 존재**한다 (convention §2.3 전제 조건 1 충족).
- implementation GO가 허가한 scope(B3' 플래그 플립 + 테스트 전환)가 **완료 merge**되었다 (convention §2.3 전제 조건 2 충족).
- B3' merge(`409ed2d`) 이후 `EXECUTION_ENABLED=True`가 반영되었으나, 실제 `execute_bounded_write()` 호출은 아직 0건이다 (convention §2.3 전제 조건 3 충족).
- Baseline regression 및 CI(lint/test/build)가 B3' PR에서 전부 green을 유지했다 (convention §2.3 전제 조건 4 충족).
- 선행 receipt가 §11 및 §12에서 명시적으로 "activation GO는 별도 receipt로 분리한다"고 기록하고 있다.

---

## 6. 실행 scope 요약 (선행 receipt §11 직접 참조)

| 항목 | 값 |
|---|---|
| 실행 함수 | `shadow_write_service.py::execute_bounded_write()` (RI-2B-2a SEALED body) |
| 호출 횟수 | **정확히 1회** |
| 호출 방식 | **manual trigger** (Python shell / 관리자 CLI / 단일 request) |
| 호출 인자 | P4에 기재된 **정확한 값**만 사용 (symbol 1건, intended_value 1건, shadow_receipt_id 1건) |
| batch 호출 | **금지** |
| 자동 재시도 | **금지** (실패 시 P5 rollback 권한에 따라 처리 또는 즉시 halt) |
| 병렬 호출 | **금지** |
| 다른 symbol 동시 처리 | **금지** |
| 함수 body 수정 | **금지** (SEALED) |
| 신규 코드 추가 | **금지** (activation receipt는 코드 변경을 부여하지 않는다) |
| 신규 테스트 추가 | **금지** (본 receipt scope 밖) |

---

## 7. I2 — 허용 실행 목록

A가 본 receipt에 GO 서명 시, **오직 아래 1건 실행**만 허용된다.

### 7.1 허용 실행 slot (P4, 서명 시 기입)

| Slot 이름 | 값 (BLANK) | 제약 |
|---|---|---|
| `P4.symbol` | ⬜ | 정확히 1건. ALLOWED_TARGETS 및 `symbols` 테이블 내 실존 row여야 함. FORBIDDEN_TARGETS 금지. |
| `P4.intended_value` | ⬜ | `pass` 또는 `fail` 중 1개. 다른 값 금지. |
| `P4.shadow_receipt_id` | ⬜ | 선행 shadow observation receipt의 실존 id. null/공백 금지. |
| `P4.transition` | ⬜ (자동) | `unchecked → <intended_value>`. ALLOWED_TRANSITIONS에 반드시 포함되어야 함. |

### 7.2 허용 실행의 경계

- 실행 횟수: **1회**
- 작용 field: `symbols.qualification_status` **단일 컬럼**
- 작용 row: **1건** (P4.symbol로 유일 식별)
- 실행 operation: **UPDATE (CAS)**
- 트리거 소스: **A 세션의 수동 명령만 허용**
- 동일 세션 내 두 번째 실행: **금지**
- 서명된 receipt의 재사용: **금지** (1회 소모성, 실행 후 closed로 간주)

### 7.3 P4 기입 예시 (DRAFT, 참고용)

```
P4:
  symbol: <예: BTCUSDT | SOLUSDT | ...>  # A가 선택
  intended_value: <pass | fail>          # A가 선택
  shadow_receipt_id: <예: shadow_2026...> # A가 선택 (실존 id)
  transition: unchecked → <intended_value> (자동 파생)
```

> 위는 **형식 예시**이며, 실제 값은 §14 서명란에서만 확정된다.

---

## 8. I3 — 금지 동작 목록 (FROZEN / RED / SEALED, 강화)

본 receipt는 서명 여부와 무관하게 아래 동작을 **절대 금지**한다.

### 8.1 SEALED 함수·상수 (RI-2B-1 / RI-2B-2a 봉인, 본 단계에서도 유지)

| # | 대상 | 봉인 상태 |
|:---:|---|---|
| 1 | `execute_bounded_write()` 함수 body | SEALED, 호출만 허용, 수정 금지 |
| 2 | `rollback_bounded_write()` 함수 body | SEALED, P5=YES 시 호출만 허용, 수정 금지 |
| 3 | `evaluate_verdict()` | SEALED, 내부 호출만 |
| 4 | `evaluate_shadow_write()` | SEALED, 내부 호출만 |
| 5 | `ALLOWED_TRANSITIONS` 상수 | 불변 |
| 6 | `FORBIDDEN_TARGETS` 상수 | 불변 |
| 7 | `BlockReasonCode` enum (10값) | 불변 |
| 8 | `ExecutionVerdict` enum (4값) | 불변 |
| 9 | 10-step execution flow 구조 | 불변 |
| 10 | `EXECUTION_ENABLED` 상수 | B3' 이후 True 고정, 본 receipt가 재전환하지 않는다 |

### 8.2 FROZEN / RED 범주 (본 receipt 하에서도 유지)

| # | 카테고리 | 상태 |
|:---:|---|---|
| 1 | Gate 관련 파일 | LOCKED |
| 2 | 모델 / 마이그레이션 | 접촉 0 |
| 3 | exchanges / router / 외부 IO 경계 | 접촉 0 |
| 4 | promotion / paper 경로 | CR-046 frozen 유지 |
| 5 | Celery beat schedule | 주석 유지, uncomment 금지 |
| 6 | `DRY_SCHEDULE` 플래그 | True 유지, False 전환 금지 |
| 7 | Purge / retention 활성화 | 미구현 유지 |
| 8 | whitelist / ALLOWED_TARGETS 확장 | 금지 |

### 8.3 금지 동작 (activation 특화)

| # | 금지 | 사유 |
|:---:|---|---|
| 1 | 두 번째 `execute_bounded_write()` 호출 | 1회 한정 |
| 2 | P4에 없는 symbol에 대한 호출 | scope 밖 |
| 3 | `qualification_status` 외 필드 write | scope 밖 |
| 4 | `symbols.status` UPDATE | FORBIDDEN_TARGET |
| 5 | batch / 스크립트 / loop 호출 | 자동화 금지 |
| 6 | cron / beat / 스케줄러 경유 호출 | 자동화 금지 |
| 7 | 실패 시 자동 retry | 금지, manual만 |
| 8 | rollback을 **P5=NO 상태에서** 호출 | 금지 |
| 9 | receipt 서명 이전 실행 | 금지 |
| 10 | 서명된 receipt의 재사용 (2번째 세션) | 금지, 1회 소모성 |
| 11 | 다른 CR로의 자동 위임 | 금지 |
| 12 | `EXECUTION_ENABLED=False`로의 재전환 (본 receipt 권한 밖) | 본 receipt 권한 밖, 별도 수속 |
| 13 | 본 receipt 본문의 임의 수정 (서명란 제외) | 금지 |
| 14 | scope review package / acceptance / implementation GO 본문 수정 | 금지 (LOCK 유지) |

---

## 9. I4 — 실행 전/후 verification 기준

### 9.1 Pre-activation checklist (서명 전 필수 확인)

| # | 항목 | 기준 |
|:---:|---|---|
| 1 | 선행 implementation_go_receipt 서명 완료 | `d999aed` 존재 |
| 2 | B3' merge 완료 | `409ed2d` main 반영 |
| 3 | `EXECUTION_ENABLED` 모듈 상수 = True | 직접 import 검증 |
| 4 | B3' PR CI 3종 전부 green | lint/test/build PASS |
| 5 | 실제 write 0건 | `bounded_write_receipts` 테이블(또는 동등 기록) empty |
| 6 | 대상 symbol이 ALLOWED_TARGETS/실존 row | A 확인 |
| 7 | 대상 전이가 ALLOWED_TRANSITIONS 내 | A 확인 |
| 8 | 선행 shadow receipt 실존 | A 확인 |
| 9 | FORBIDDEN_TARGETS 위반 없음 | A 확인 |
| 10 | Gate LOCKED 상태 유지 | 확인 |
| 11 | 다른 Track A 동시 진행 없음 | 확인 |
| 12 | 본 DRAFT receipt가 main에 merge됨 | 본 PR 완료 후 충족 |

> 위 12개 항목이 **전부 green**이 아니면 서명을 보류한다.

### 9.2 Post-write verification checklist (실행 직후 필수 확인)

| # | 항목 | 기준 |
|:---:|---|---|
| 1 | `execute_bounded_write()` return value | `ExecutionVerdict` enum 내 1값 (예: `SUCCESS`) |
| 2 | 대상 row read-back | `qualification_status == P4.intended_value` |
| 3 | 다른 row 영향 | 0건 (row count delta check) |
| 4 | 다른 필드 영향 | 0건 (`symbols` 테이블 외 컬럼 변경 0) |
| 5 | receipt 기록 생성 | `bounded_write_receipts` 테이블에 1건 신규 (또는 동등 log) |
| 6 | 트랜잭션 commit 성공 | DB 연결 정상, rollback 없음 |
| 7 | 신규 경고/에러 로그 0건 | application log check |
| 8 | Gate 상태 변동 0 | LOCKED 유지 |
| 9 | 다른 symbol 상태 변동 0 | 확인 |
| 10 | CI baseline regression 무영향 | 본 세션에서는 CI 재실행 없이 증거만 수집 |

### 9.3 Verification 실패 시 행동

1. **P5 = YES 인 경우**: 즉시 `rollback_bounded_write()`를 1회 호출하여 원상 복구. 실패 상세는 별도 `cr048_ri2b2b_rollback_evidence.md`에 기록.
2. **P5 = NO 인 경우**: 즉시 halt. rollback 호출 금지. 사건을 `exception_register.md`에 EX-XXX로 등록하고 A의 추가 지시를 대기한다.
3. 어느 경우든 **두 번째 호출 금지**. 추가 실행은 새 activation GO receipt가 필요하다.

---

## 10. I5 — 롤백 조건

본 receipt 서명 이후 실행이 시작되면, 아래 조건 중 **단 하나라도** 발생 시 §9.3 절차를 따른다.

| # | 트리거 | 행동 |
|:---:|---|---|
| 1 | `execute_bounded_write()` return verdict이 성공값이 아닌 경우 | §9.3 |
| 2 | post-write read-back 결과가 `P4.intended_value`와 불일치 | §9.3 |
| 3 | 대상 row 외 다른 row에 변경 흔적 | §9.3 + 사고 보고 |
| 4 | `symbols` 테이블 외 다른 테이블 변경 흔적 | §9.3 + 사고 보고 |
| 5 | SEALED 함수 body에 수정 흔적 발견 | §9.3 + 긴급 감사 |
| 6 | ALLOWED_TRANSITIONS / FORBIDDEN_TARGETS 변경 흔적 | §9.3 + 긴급 감사 |
| 7 | beat/schedule 경로에서 자동 호출 감지 | §9.3 + 긴급 감사 |
| 8 | DB 예외 / 트랜잭션 롤백 | §9.3 |
| 9 | 동일 receipt로 2회 이상 호출 흔적 | §9.3 + 사고 보고 (치명) |
| 10 | receipt id 불일치 (shadow_receipt_id 미존재) | §9.3 |

### 10.1 롤백 수행 시 기록 의무

- 롤백이 발생하면 `exception_register.md`에 새 EX-XXX 항목을 등록한다.
- 별도 `cr048_ri2b2b_rollback_evidence.md` 발행을 고려한다.
- 롤백 이후 본 receipt는 **closed** 상태로 간주되며, **다음 실행은 새 activation GO receipt가 필요**하다.
- rollback 행위 자체는 P5 권한에 의존하며, P5=NO 상태에서는 rollback 호출도 금지된다.

---

## 11. I6 — 다음 단계와의 분리 명시

> **본 activation GO receipt는 향후 확장을 자동 승인하지 않는다.**
>
> 본 문서는 A 서명 시 **symbol 1건에 대한 bounded CAS write 1회 실행**을 허가할 뿐이며,
> 아래 항목은 **전부 별도 승인**이 필요하다.

| 구분 | 본 receipt (activation GO) | 별도 receipt 필요 항목 |
|---|:---:|:---:|
| 첫 manual `execute_bounded_write()` 1회 호출 | ✅ (서명 시) | — |
| post-write verification 1회 수행 | ✅ (서명 시) | — |
| P5=YES 일 때 `rollback_bounded_write()` 1회 호출 | ✅ (조건부) | — |
| 두 번째 symbol 실행 | ❌ | 새 activation GO |
| 동일 symbol 두 번째 write | ❌ | 새 activation GO |
| batch 실행 | ❌ | scope 확장 별도 receipt |
| beat/schedule 자동화 활성화 | ❌ | 별도 activation GO (자동화 전용) |
| `DRY_SCHEDULE=False` 전환 | ❌ | 별도 A 승인 |
| purge / retention 활성화 | ❌ | 별도 A 승인 |
| whitelist / ALLOWED_TARGETS 확장 | ❌ | 별도 A 전용 승인 |
| gate unlock | ❌ | A 전용, 별도 receipt |
| 다른 table / 다른 field write | ❌ | 별도 scope review + acceptance + implementation GO + activation GO 체인 |
| promotion / paper 경로 활성화 | ❌ | CR-046 frozen 상태 유지 |

> **EXECUTION_ENABLED=True 상태 + 서명된 activation receipt = 1회 실행**. 그 이상은 전부 별도 승인이 필요하다.

---

## 12. 이 문서가 부여하지 않는 것 (negative scope)

본 receipt는 서명 여부와 무관하게 **아래 권한을 부여하지 않는다**.

| # | 미부여 권한 | 사유 |
|:---:|---|---|
| 1 | 2회 이상의 `execute_bounded_write()` 호출 | 1회 한정, scope 밖 |
| 2 | P4에 없는 symbol에 대한 실행 | scope 밖 |
| 3 | batch / loop / 스크립트 호출 | 자동화 금지 |
| 4 | beat / cron / scheduler 경유 호출 | 자동화 금지 |
| 5 | `DRY_SCHEDULE=False` 전환 | 별도 A 승인 필요 |
| 6 | beat uncomment | 별도 activation GO |
| 7 | purge / retention 활성화 | 별도 A 승인 |
| 8 | whitelist / ALLOWED_TARGETS 확장 | 별도 A 전용 승인 |
| 9 | `FORBIDDEN_TARGETS` 축소 | 절대 금지, 예외 없음 |
| 10 | `ALLOWED_TRANSITIONS` 추가/수정 | 별도 A 전용 승인 |
| 11 | `BlockReasonCode` / `ExecutionVerdict` 변경 | 별도 A 전용 승인 |
| 12 | Gate LOCK/UNLOCK 전환 | A 전용, 별도 receipt |
| 13 | 다른 symbol / 다른 table / 다른 field 확장 | 별도 전체 체인 |
| 14 | promotion / paper 경로 활성화 | CR-046 frozen 유지 |
| 15 | scope review package 본문 수정 | LOCK 유지 |
| 16 | acceptance receipt 본문 수정 | LOCK 유지 |
| 17 | implementation GO receipt 본문 수정 | LOCK 유지 |
| 18 | 본 receipt 서명란 외 본문 수정 | LOCK 유지 (서명 이후) |
| 19 | 자동 chain rollback | 수동만 허용, P5에 따름 |
| 20 | 다른 CR로의 자동 위임 | 각 CR은 고유 체인 필요 |
| 21 | `EXECUTION_ENABLED=False` 재전환 권한 | 본 receipt 권한 밖, 별도 수속 |
| 22 | 신규 코드 라인 추가 | 본 receipt는 코드 변경을 부여하지 않는다 |
| 23 | 신규 테스트 추가 | 본 receipt는 테스트 변경을 부여하지 않는다 |
| 24 | 새로운 evidence 문서 작성 권한 | 본 receipt 밖 (증빙은 별도 세션) |

> **요약**: 본 receipt의 최대 권한은 "P4에 기재된 **symbol 1건에 대한 bounded CAS write 1회 실행** + 필요 시 1회 rollback (P5=YES 조건)" 뿐이며, 그 이상의 모든 권한은 별도 receipt가 필요하다.

---

## 13. 세션 증빙 (본 초안 발행 세션)

본 초안 발행 세션의 파일 변경 집계:

| 카테고리 | 대상 | 변경 수 |
|---|---|:---:|
| scope review 본문 | `cr048_ri2b2b_scope_review_package.md` | **0** |
| acceptance receipt 본문 | `cr048_ri2b2b_scope_review_acceptance_receipt.md` | **0** |
| implementation GO receipt 본문 | `cr048_ri2b2b_implementation_go_receipt.md` | **0** |
| activation manifest | `cr048_ri2a2b_activation_manifest.md` | **0** |
| governance baseline | `current_governance_baseline.md` | **0** |
| exception register | `exception_register.md` | **0** |
| completion evidence (RI-2A-2b) | `cr048_ri2a2b_completion_evidence.md` | **0** |
| receipt naming convention | `receipt_naming_convention.md` | **0** |
| 코드 파일 | `app/services/shadow_write_service.py` | **0** |
| 테스트 파일 | `tests/test_shadow_write_receipt.py` | **0** |
| 워크플로 / settings | `.github/workflows/*`, `.github/settings`, rulesets | **0** |
| 본 receipt (신규) | `cr048_ri2b2b_activation_go_receipt.md` | 1 Write (본 파일) |

### 13.1 본 초안 세션 전용 증빙

| 호출 유형 | 대상 `shadow_write_service.py` / `test_shadow_write_receipt.py` | 호출 수 |
|---|:---:|:---:|
| Read (read-only) | — | 0 |
| **Write** | ❌ | **0** |
| **Edit** | ❌ | **0** |

| 호출 유형 | 대상 `cr048_ri2b2b_implementation_go_receipt.md` | 호출 수 |
|---|:---:|:---:|
| Read (read-only, 구조 상속 확인 목적) | ✅ | ≥1 |
| **Write / Edit / Rename / Delete** | ❌ | **0** |

| 호출 유형 | 실제 DB write 경로 | 호출 수 |
|---|:---:|:---:|
| `execute_bounded_write()` | ❌ | **0** |
| `rollback_bounded_write()` | ❌ | **0** |
| 수동 SQL UPDATE | ❌ | **0** |

> `git status --porcelain`으로 본 receipt 외 다른 파일의 수정 0줄이 증명된다.
> 본 세션은 **문서 생성만** 수행하며, 어떠한 실제 실행도 트리거하지 않는다.

---

## 14. 승인자 서명란 (BLANK)

> 본 서명란은 A가 직접 기입하기 전까지 **BLANK 상태로 유지**되어야 한다.
> 서명 없이 기입된 내용이 발견되면 본 receipt 전체를 무효화한다.

### 14.1 기본 서명 정보

| 항목 | 값 |
|---|---|
| 승인자 | **A** |
| 권한 유형 | 최종 의사결정자 |
| 승인 형태 | Activation GO (단, 본 receipt 서명 시 한정, 1회 소모성) |
| 서명 이후 효력 발생 시각 | 서명일 기준 (세션 내 유효) |
| 효력 종료 | 실행 완료 후 즉시 closed (또는 rollback 후 closed) |
| 승인 철회 조건 | A 명시 지시 시에만 가능. 자동 철회 조건 없음. |

### 14.2 P1 — 판정 (BLANK)

```
P1:
  verdict: GO   # GO / BLOCK / CONDITIONAL 중 1
```

### 14.3 P2 — 판정일 (BLANK)

```
P2:
  signature_date: 2026-04-05   # YYYY-MM-DD
```

### 14.4 P4 — 실행 대상 (BLANK)

```
P4:
  symbol: SOL/USDT
  intended_value: pass            # pass 또는 fail
  shadow_receipt_id: prior_68d980c176d24a0c9dc6ead35307bbad
  transition: unchecked → pass                # unchecked → <intended_value> (자동 파생, 기입 시 명시)
```

### 14.5 P5 — 롤백 권한 (BLANK)

```
P5:
  rollback_authority: YES   # YES 또는 NO
  rollback_trigger_set: §10.1–§10.10   # 기본 10개 트리거 고정
```

### 14.6 서명 시 지켜야 할 규칙

- 모든 슬롯(P1/P2/P4/P5)은 **한 서명 세션에서 동시에 기입**되어야 한다. 부분 서명 금지.
- 서명은 본 receipt 파일에 대한 **단일 Edit commit**으로 기록한다.
- 서명 PR은 `track-a/activation-signature` 브랜치에서 생성한다.
- 서명 PR은 문서 본문(섹션 §1–§13, §15–§16)을 수정하지 않는다.
- 서명 이후 본 receipt의 PR body와 merge SHA가 activation 단계 권한의 단일 근거가 된다.

---

## 15. 적용 규칙 (본 건부터 고정)

| 규칙 | 설명 |
|---|---|
| 본 receipt는 `*_activation_go_receipt.md` 패턴의 **첫 초안 사례**이다 | `receipt_naming_convention.md` §2.3 / §3.4를 최초로 구체 적용 |
| DRAFT 상태에서도 LOCK 대상이다 | 본문 임의 수정 금지. A 지시 없이 Edit/Rename/Move/Delete 금지. |
| A 서명 이후 Version bump 규칙 | 서명만으로는 version이 bump되지 않는다. 서명 결과를 §14에 기입 후 새 커밋으로 반영. |
| 구조 규범 이탈 금지 | §5~§11(I1~I6)의 필드 순서·명칭은 convention §3.4를 그대로 따른다. |
| 1회 소모성 | 본 receipt는 서명 후 1회 실행(또는 1회 rollback)으로 closed. 재사용 금지. |
| 다음 activation은 별도 receipt | 두 번째 실행은 새 DRAFT → 새 서명 → 새 실행 체인이 필요하다. |
| 본 receipt는 자동화 경로를 열지 않는다 | beat/schedule/cron/purge/whitelist는 전부 본 receipt 밖. |

---

## 16. Receipt 무결성 선언

본 receipt는 다음 조건을 모두 충족한다:

- [x] receipt_naming_convention v1.0 §3.4 (I1–I6) 필드 전부 포함
- [x] 선행 implementation GO receipt 참조 포함 (§5)
- [x] 허용 실행이 1회로 한정됨 (§7)
- [x] 금지 동작이 SEALED + FROZEN + RED + activation 특화 범주로 명시됨 (§8)
- [x] Pre/post verification 기준이 §9에 12 + 10 항목으로 명시됨
- [x] 롤백 조건이 10개 트리거 + P5 의존 처리로 명시됨 (§10)
- [x] 다음 단계(두 번째 실행 / 자동화)와의 분리가 명시됨 (§11)
- [x] 본 문서가 부여하지 않는 권한이 24개로 명시됨 (§12)
- [x] P1/P2/P4/P5 슬롯이 전부 BLANK (§2, §14)
- [x] A 서명 전에는 효력 없음을 명시 (§0, §2, §14)
- [x] 본 receipt 외 다른 파일 변경 0건 (§13)
- [x] 4-chain 정합 6/6 (§4)
- [x] 실제 DB write 호출 0건 (§13.1)

```
CR-048 RI-2B-2b Activation GO Receipt v1.0
Target: 1 manual execute_bounded_write() call on 1 symbol
        + 1 post-write verification sweep
        + (conditional on P5=YES) 1 rollback call
Status: DRAFT — PENDING A SIGNATURE
Verdict P1       : ⬜ BLANK
Signature date P2: ⬜ BLANK
Execution P4     : ⬜ BLANK (symbol / intended_value / shadow_receipt_id)
Rollback P5      : ⬜ BLANK (YES / NO)
Authority        : A (pending)
Issued           : 2026-04-05
Effective        : NONE until A explicit signature
Parent chain head: d999aed (implementation GO, A signed 2026-04-04)
Current main head: 409ed2d (B3' flag flip merge)
Baseline         : 5456/5456 PASS + CI 3/3 green (B3' PR #46)
EXECUTION_ENABLED: True (B3' reflected, no real write yet)
Actual write count to date: 0
4-chain consistency: 6/6
Max permission on sign: 1 manual execute call on 1 symbol, 1 verify, (opt) 1 rollback
Second execution : NOT GRANTED (separate new receipt required)
Automation       : NOT GRANTED (beat/schedule/cron/purge all separate)
Gate unlock      : NOT GRANTED (A-only, separate receipt)
Scope expansion  : NOT GRANTED (other symbol/table/field all separate)
SEALED function body modification: FORBIDDEN (ever)
ALLOWED_TRANSITIONS change: NOT GRANTED (ever, separate A approval)
FORBIDDEN_TARGETS reduction: FORBIDDEN (no exception)
One-shot semantics: this receipt is consumed on first execution (or first rollback)
Lock status: maintained on scope review package, acceptance, implementation GO receipts
Convention compliance: receipt_naming_convention v1.0 §3.4 I1–I6 strict
Pattern inauguration: first use of *_activation_go_receipt.md pattern (DRAFT form)
```
