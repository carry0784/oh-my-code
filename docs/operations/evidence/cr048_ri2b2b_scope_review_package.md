# CR-048 RI-2B-2b 범위 심사 패키지

**Stage**: RI-2B-2b (Execution Enable — First Bounded Business Write)
**Status**: SCOPE REVIEW 제출 (v1)
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2B-2a SEALED (v2.4, EXECUTION_ENABLED=False), RI-2A-2b SEALED (v2.5, DRY_SCHEDULE=True)
**현재 기준선**: v2.5 (5456/5456 PASS)

---

## 1. 해석 및 요약

### 1.1 목적 정의

RI-2B-2b는 **CR-048 최초의 bounded business table write를 활성화**하는 범위 심사입니다.

> RI-2B-2b = "`EXECUTION_ENABLED=False` → `True` 전환을 허용하여,
> RI-2B-2a에서 봉인된 `execute_bounded_write()` / `rollback_bounded_write()` 코드의
> **실제 실행 권한을 부여**한다."

### 1.2 왜 "최초 business write"인가

| 단계 | DB write 유형 | 대상 | 성격 |
|------|-------------|------|------|
| RI-1 | 없음 | — | pure shadow |
| RI-2A-1 | SELECT only | screening/qualification | read-through |
| RI-2A-2a | INSERT | shadow_observation_log | 관측 전용, business 아님 |
| RI-2A-2b | INSERT (dry-schedule) | shadow_observation_log | 자동화 기반, business 아님 |
| RI-2B-1 | INSERT | shadow_write_receipt | 증거 전용, business 아님 |
| RI-2B-2a | 코드만 존재 | symbols.qualification_status | 실행 불가 |
| **RI-2B-2b** | **UPDATE (CAS)** | **symbols.qualification_status** | **최초 business write** |

> 이전 모든 단계는 INSERT-only 또는 코드만 존재했다.
> RI-2B-2b에서 처음으로 **기존 business table의 기존 row 값을 변경**한다.

### 1.3 경계 선언

| 속성 | RI-2B-2a (SEALED) | RI-2B-2b (본 심사) |
|------|:------------------:|:------------------:|
| EXECUTION_ENABLED | False | **True** |
| symbols UPDATE | 불가 | **CAS bounded** |
| execution path | 없음 | **manual trigger only** |
| gate state change | 없음 | **없음** |
| beat/schedule | 없음 | **없음** |
| scope 확장 | 없음 | **없음** |
| 대상 필드 | — | `qualification_status` 1개만 |
| 대상 전이 | — | `unchecked→pass`, `unchecked→fail` 2개만 |
| rollback | 코드만 | **수동 1회성** |

### 1.4 한 문장 목표

> **RI-2B-2b = "`EXECUTION_ENABLED=True`로 전환하여, shadow receipt 근거의 CAS bounded write를 수동 실행 가능하게 한다. 자동화 없음, 범위 확장 없음."**

---

## 2. 장점 / 단점

### 2.1 장점

| # | 장점 | 설명 |
|---|------|------|
| 1 | **shadow evidence 기반 write** | blind write 아님. RI-2B-1 shadow receipt(WOULD_WRITE) 존재가 전제 |
| 2 | **CAS bounded** | `WHERE qualification_status='unchecked'` — 현재값 일치 시에만 변경 |
| 3 | **1:1 receipt binding** | 하나의 shadow receipt으로 최대 1회만 실행 가능 (consumed 마킹) |
| 4 | **TOCTOU 방어** | `SELECT ... FOR UPDATE` + receipt.current_value 일치 검증 |
| 5 | **post-write verification** | 5개 기준 검증, 실패 시 자동 rollback |
| 6 | **수동 trigger only** | beat/schedule 없음, script/pytest에서만 호출 |
| 7 | **코드 변경 최소** | `EXECUTION_ENABLED` 상수 1줄만 False→True |
| 8 | **rollback 구비** | 수동 1회성, 협소 범위, 감사 receipt 포함 |

### 2.2 단점

| # | 단점 | 완화 방안 |
|---|------|-----------|
| 1 | **최초 business write 리스크** | CAS + TOCTOU + post-write 3중 방어 |
| 2 | **qualification_status 변경은 downstream 영향 가능** | 현재 downstream 경로 미활성 (promotion/paper frozen) |
| 3 | **concurrent write 가능성** | SELECT FOR UPDATE row lock + CAS atomic |
| 4 | **rollback 실패 시 수동 복구 필요** | rollback receipt + manual SQL 문서화 |
| 5 | **consumed 상태 복구 불가** | 설계상 의도적 (1:1 binding 보장) |

---

## 3. 이유 / 근거

### 3.1 왜 지금 write가 필요한가

| 이유 | 설명 |
|------|------|
| **shadow 관측 완료** | RI-2A-2a/2b로 shadow observation 자동화 + retention 기반 완성 |
| **shadow evidence 축적** | RI-2B-1로 WOULD_WRITE receipt이 생성 가능 |
| **코드/계약 검증 완료** | RI-2B-2a로 execute/rollback 코드 + 33 테스트 봉인 |
| **실행만 남음** | 코드는 있으나 `EXECUTION_ENABLED=False`로 막혀 있음 |

### 3.2 왜 이 write가 bounded인가

| 제약 | 설명 |
|------|------|
| **1 테이블** | `symbols`만 |
| **1 필드** | `qualification_status`만 |
| **2 전이** | `unchecked→pass`, `unchecked→fail`만 |
| **1:1 binding** | shadow receipt 1건당 최대 1회 실행 |
| **CAS** | `WHERE qualification_status='unchecked'` 필수 |
| **FORBIDDEN_TARGETS** | 4개 금지 target 명시 |
| **ALLOWED_TRANSITIONS** | whitelist 방식 (허용 목록 외 전이 불가) |

### 3.3 왜 fail-closed인가

| 실패 시나리오 | 행동 | write |
|-------------|------|:-----:|
| EXECUTION_ENABLED=False | BLOCKED | **0** |
| 선행 receipt 없음 | BLOCKED | **0** |
| receipt 이미 consumed | BLOCKED | **0** |
| DB값 ≠ receipt.current_value (TOCTOU) | BLOCKED | **0** |
| CAS 0 row affected | BLOCKED | **0** |
| CAS 2+ row affected | rollback + EXECUTION_FAILED | **0 (reverted)** |
| post-write verification 실패 | rollback + EXECUTION_FAILED | **0 (reverted)** |
| DB exception | EXECUTION_FAILED | **0** |
| 모든 조건 통과 | EXECUTED | **1** |

> **9가지 실패 경로 모두 write=0 또는 reverted. 성공 경로만 write=1.**

### 3.4 왜 idempotency가 보존되는가

| 장치 | 설명 |
|------|------|
| **1:1 consumed** | 동일 shadow receipt으로 2번째 execute → BLOCKED (RECEIPT_ALREADY_CONSUMED) |
| **CAS** | 이미 `pass`/`fail`로 변경된 row에 대해 → 0 row affected → BLOCKED (CAS_MISMATCH) |
| **dedupe_key** | RI-2B-1 SEALED dedupe_key로 동일 입력 중복 receipt 방지 |

### 3.5 왜 audit trail이 완전한가

| 이벤트 | receipt | 필드 |
|--------|---------|------|
| shadow verdict 산출 | RI-2B-1 receipt | verdict, intended_value, current_value |
| execution 성공 | execution receipt | `transition_reason="exec_of:{id}"`, verdict=EXECUTED, business_write_count=1 |
| execution 차단 | blocked receipt | verdict=BLOCKED, block_reason_code |
| execution 실패 | failed receipt | verdict=EXECUTION_FAILED |
| rollback | rollback receipt | `transition_reason="rollback_of:{id}"`, verdict=ROLLED_BACK, business_write_count=-1 |

> **모든 경로(성공/차단/실패/rollback)에 receipt이 남는다.**

### 3.6 왜 execution open으로 번지지 않는가

| 경계 | 설명 |
|------|------|
| **manual only** | beat/schedule/periodic 호출 없음 |
| **1 필드 whitelist** | ALLOWED_TRANSITIONS에 없는 전이 불가 |
| **FORBIDDEN_TARGETS** | symbols.status, promotion, paper 등 명시 차단 |
| **gate LOCKED** | gate 변경 코드 0줄 |
| **promotion 경로** | CR-046 frozen, Phase 4+ blocked |
| **scope 확장 금지** | ALLOWED_TRANSITIONS 추가는 별도 A 승인 |

### 3.7 왜 scope가 qualification_status CAS로 한정되는가

> qualification_status는 symbols 테이블의 부속 상태 필드이며,
> 현재 downstream 소비자가 없다 (promotion frozen, paper frozen, runtime disabled).
> 따라서 이 필드를 변경해도 다른 시스템에 cascading effect가 없다.
>
> 반면 symbols.status (CORE/WATCH/EXCLUDED)는 screening pipeline 전체에 영향하므로 금지.

---

## 4. 실현 / 구현 대책

### 4.1 코드 변경 (최소)

| 파일 | 변경 | 설명 |
|------|------|------|
| `app/services/shadow_write_service.py` | **1줄** | `EXECUTION_ENABLED: bool = False` → `True` |

> **코드 변경 1줄. 신규 파일 0. 모델/마이그레이션 0. 테스트 추가 0 (RI-2B-2a에서 이미 33건 봉인).**

### 4.2 테스트 변경

| 파일 | 변경 | 설명 |
|------|------|------|
| `tests/test_shadow_write_receipt.py` | **수정** | `TestExecutionEnabledFlag.test_execution_enabled_is_false` → `test_execution_enabled_is_true` 전환 |

> RI-2B-2a에서 `EXECUTION_ENABLED=False` 검증 테스트가 있다.
> RI-2B-2b에서는 이 테스트를 `True` 검증으로 전환해야 한다.

### 4.3 미수정 파일 (SEALED 보호)

| 파일 | 상태 |
|------|------|
| execute_bounded_write() 함수 | 수정 0줄 (RI-2B-2a SEALED) |
| rollback_bounded_write() 함수 | 수정 0줄 (RI-2B-2a SEALED) |
| evaluate_verdict() | 수정 0줄 (RI-2B-1 SEALED) |
| evaluate_shadow_write() | 수정 0줄 (RI-2B-1 SEALED) |
| ALLOWED_TRANSITIONS | 수정 0줄 |
| FORBIDDEN_TARGETS | 수정 0줄 |
| BlockReasonCode | 수정 0줄 |
| ExecutionVerdict | 수정 0줄 |
| FROZEN/RED 파일 전체 | 접촉 0건 |

---

## 5. Write Intent Ledger

> A 추가 제안 반영: write가 일어났다면 어떤 intent였는가를 문서상 정의.

### 5.1 Intent 정의

| # | Intent | 조건 | 결과 |
|---|--------|------|------|
| I-1 | `qualify_pass` | shadow verdict=WOULD_WRITE, intended=pass, current=unchecked | `qualification_status: unchecked → pass` |
| I-2 | `qualify_fail` | shadow verdict=WOULD_WRITE, intended=fail, current=unchecked | `qualification_status: unchecked → fail` |
| I-3 | `rollback_pass` | execution receipt exists, current=pass | `qualification_status: pass → unchecked` |
| I-4 | `rollback_fail` | execution receipt exists, current=fail | `qualification_status: fail → unchecked` |

### 5.2 Intent 제약

| 제약 | 설명 |
|------|------|
| I-1, I-2만 자동 판정 | shadow evidence 기반 |
| I-3, I-4는 수동만 | rollback은 자동 chain 금지 |
| Intent 당 최대 1회 | consumed 마킹으로 재실행 차단 |
| Intent 범위 | qualification_status 1필드만 |

---

## 6. CAS Failure Taxonomy

> A 추가 제안 반영: CAS 실패를 세분화.

| Code | 명칭 | 원인 | 검출 시점 | receipt verdict |
|------|------|------|-----------|:---------------:|
| `STALE_READ` | receipt 생성 시점과 DB 현재값 불일치 | receipt.current_value ≠ SELECT 결과 | Step 6 | BLOCKED |
| `CONCURRENT_CHANGE` | SELECT FOR UPDATE와 CAS UPDATE 사이 변경 | CAS 0 row affected (이론상 불가 — row lock 유지 중) | Step 8 | BLOCKED |
| `INVARIANT_VIOLATION` | CAS 2+ row affected | 예상 외 (symbol unique constraint 위반 시에만) | Step 8 | EXECUTION_FAILED |
| `POLICY_BLOCKED` | 전이가 ALLOWED_TRANSITIONS에 없음 | (current, intended) ∉ whitelist | Step 7 | BLOCKED |
| `ALREADY_TRANSITIONED` | 현재값이 이미 intended값 | current == intended | RI-2B-1 평가 시 | BLOCKED (ALREADY_MATCHED) |

### 6.1 빈도 예측

| Code | 예상 빈도 | 사유 |
|------|:---------:|------|
| STALE_READ | **중** | receipt 생성 후 시간 경과 시 다른 경로에서 상태 변경 가능 |
| CONCURRENT_CHANGE | **극히 낮음** | SELECT FOR UPDATE row lock이 보호 |
| INVARIANT_VIOLATION | **거의 0** | symbol은 unique constraint |
| POLICY_BLOCKED | **낮음** | whitelist 외 전이는 RI-2B-1에서 이미 차단 |
| ALREADY_TRANSITIONED | **낮음** | unchecked가 아니면 RI-2B-1에서 ALREADY_MATCHED |

---

## 7. No-Write Proof Table

> A 추가 제안 반영: 각 실패 시나리오별 write 발생 여부 증명.

| # | 시나리오 | 입력 상태 | 판정 | write | audit |
|---|---------|-----------|------|:-----:|:-----:|
| 1 | EXECUTION_ENABLED=False | 어떤 입력이든 | BLOCKED (EXECUTION_DISABLED) | **0** | receipt |
| 2 | 선행 receipt 없음 | shadow_receipt_id 미존재 | BLOCKED (NO_PRIOR_RECEIPT) | **0** | receipt |
| 3 | receipt.verdict ≠ WOULD_WRITE | verdict=NO_WRITE | BLOCKED (NO_PRIOR_RECEIPT) | **0** | receipt |
| 4 | receipt 이미 consumed | exec_of receipt 존재 | BLOCKED (RECEIPT_ALREADY_CONSUMED) | **0** | receipt |
| 5 | target이 FORBIDDEN | symbols.status 등 | BLOCKED (FORBIDDEN_TARGET) | **0** | receipt |
| 6 | target이 ALLOWED 외 | 미등록 target | BLOCKED (OUT_OF_SCOPE) | **0** | receipt |
| 7 | DB값 ≠ receipt.current_value | status='pass' ≠ 'unchecked' | BLOCKED (STALE_PRECONDITION) | **0** | receipt |
| 8 | 전이가 ALLOWED_TRANSITIONS 외 | ('pass','fail') | BLOCKED (PRECONDITION_FAILED) | **0** | receipt |
| 9 | CAS 0 row | concurrent change | BLOCKED (CAS_MISMATCH) | **0** | receipt |
| 10 | CAS 2+ row | invariant violation | EXECUTION_FAILED (rollback) | **0** | receipt |
| 11 | post-write: 값 불일치 | DB ≠ intended | EXECUTION_FAILED (rollback) | **0** | receipt |
| 12 | post-write: row count ≠ 1 | 0 or 2+ | EXECUTION_FAILED (rollback) | **0** | receipt |
| 13 | post-write: 다른 필드 변경 | side effect | EXECUTION_FAILED (rollback) | **0** | receipt |
| 14 | DB exception | 연결 실패 등 | EXECUTION_FAILED | **0** | receipt |
| **15** | **모든 조건 통과** | **정상** | **EXECUTED** | **1** | **receipt** |

> **15개 시나리오 중 14개 = write 0. 1개만 write 1. 모든 시나리오에 audit receipt.**

---

## 8. Runtime Delta

### 8.1 코드 변경

| 파일 | 변경 라인 | 변경 내용 |
|------|:--------:|-----------|
| `shadow_write_service.py` | 1줄 | `EXECUTION_ENABLED: bool = False` → `True` |
| `test_shadow_write_receipt.py` | ~3줄 | flag 검증 테스트 전환 |

### 8.2 미변경 보호

| 항목 | 보호 |
|------|------|
| execute_bounded_write 함수 | RI-2B-2a SEALED, 수정 0줄 |
| rollback_bounded_write 함수 | RI-2B-2a SEALED, 수정 0줄 |
| 10-step execution flow | RI-2B-2a 계약, 변경 0 |
| BlockReasonCode 10값 | 추가/제거 0 |
| ExecutionVerdict 4값 | 추가/제거 0 |
| ALLOWED_TRANSITIONS | 추가/제거 0 |
| FORBIDDEN_TARGETS | 추가/제거 0 |
| 모델/마이그레이션 | 변경 0 |
| FROZEN/RED 파일 | 접촉 0 |

---

## 9. Risk Matrix

| # | 리스크 | 확률 | 영향 | 완화 |
|---|--------|:----:|:----:|------|
| R1 | 잘못된 qualification_status 변경 | 낮 | 중 | CAS + TOCTOU + post-write 3중 방어 |
| R2 | concurrent write 충돌 | 극히 낮 | 낮 | SELECT FOR UPDATE row lock |
| R3 | downstream cascading effect | 낮 | 중 | 현재 downstream 경로 미활성 (promotion/paper frozen) |
| R4 | rollback 실패 | 낮 | 중 | rollback receipt + manual SQL 문서화 |
| R5 | consumed 복구 불가 | 중 | 낮 | 설계상 의도 (1:1 보장), 새 shadow receipt 생성 가능 |
| R6 | EXECUTION_ENABLED 무단 변경 | 극히 낮 | 높 | 테스트 검증 + A 승인 게이트 |
| R7 | scope creep (추가 필드/테이블) | 낮 | 높 | ALLOWED_TRANSITIONS whitelist + FORBIDDEN_TARGETS |

### 9.1 리스크 수준 종합

| 수준 | 판정 |
|------|------|
| 대상 필드 | **1개** (qualification_status) |
| 대상 전이 | **2개** (unchecked→pass, unchecked→fail) |
| 자동 실행 | **ZERO** (manual only) |
| gate change | **ZERO** |
| scope 확장 | **ZERO** |
| rollback 비용 | **LOW** (1필드 revert + receipt) |
| 전체 리스크 | **MEDIUM** (최초 business write이므로) |

---

## 10. Rollback / Disable Plan

### 10.1 Rollback 시나리오

| 시나리오 | 행동 | 비용 |
|---------|------|:----:|
| **write 전 차단** | BLOCKED receipt 기록, write 0 | TRIVIAL |
| **write 후 post-verify 실패** | 자동 rollback + EXECUTION_FAILED receipt | LOW |
| **write 성공 후 수동 rollback** | rollback_bounded_write() 호출 | LOW |
| **EXECUTION_ENABLED 비활성** | True → False 1줄 변경 | TRIVIAL |
| **RI-2B-2b 전체 철회** | EXECUTION_ENABLED=False 복원 | TRIVIAL |

### 10.2 단계적 disable 순서

```
1. EXECUTION_ENABLED = False (즉시 모든 실행 차단)
2. 기존 execution receipt 보존 (삭제하지 않음)
3. 잘못 변경된 qualification_status 복원 (수동 SQL or rollback_bounded_write)
4. RI-2B-2a 상태로 복귀 확인
```

### 10.3 Emergency SQL (최악의 경우)

```sql
-- 특정 symbol의 qualification_status를 unchecked로 복원
-- execution receipt에서 symbol과 원래 값 확인 후 실행
UPDATE symbols
SET qualification_status = 'unchecked'
WHERE symbol = :symbol
  AND qualification_status IN ('pass', 'fail');
-- 실행 후 반드시 rollback receipt 수동 기록
```

---

## 11. Constitutional Comparison Review

### 11.1 헌법 조항 대조

| # | 조항 | RI-2B-2b 준수 | 검증 |
|---|------|:-------------:|------|
| C-01 | business write bounded | **PASS** | 1 테이블 × 1 필드 × 2 전이, CAS, whitelist |
| C-02 | execution manual only | **PASS** | beat/schedule 없음, script/pytest에서만 |
| C-03 | gate LOCKED | **PASS** | gate 변경 코드 0줄 |
| C-04 | FROZEN 수정 0줄 | **PASS** | 기존 함수/상수 수정 없음 |
| C-05 | RED 접촉 0건 | **PASS** | exchanges, router 등 무접촉 |
| C-06 | SEALED 함수 수정 0줄 | **PASS** | execute/rollback 함수 body 변경 없음 |
| C-07 | fail-closed | **PASS** | 14/15 시나리오에서 write=0 |
| C-08 | audit trail complete | **PASS** | 모든 경로에 receipt |
| C-09 | rollback available | **PASS** | 수동 1회성 rollback 구비 |
| C-10 | 회귀 기준선 보호 | **PASS** | 5456 회귀 PASS 필수 |
| C-11 | 1:1 receipt binding | **PASS** | consumed 마킹으로 재실행 차단 |
| C-12 | TOCTOU 방어 | **PASS** | SELECT FOR UPDATE + receipt.current_value 검증 |
| C-13 | post-write verification | **PASS** | 5개 기준 검증 |

---

## 12. Approval Gate Checklist

### 12.1 구현 전 A 승인 필요 항목

| # | 항목 | 승인 시점 |
|---|------|-----------|
| 1 | RI-2B-2b scope review (본 문서) | **지금** |
| 2 | EXECUTION_ENABLED True 전환 | 구현 GO 시 |

### 12.2 구현 후 A 승인 필요 항목

| # | 항목 | 승인 시점 |
|---|------|-----------|
| 1 | RI-2B-2b completion evidence | 봉인 시 |
| 2 | 첫 실제 execute 실행 (선택) | 운영 전환 시 |

### 12.3 금지 항목 (out-of-scope)

| # | 금지 | 사유 |
|---|------|------|
| 1 | ALLOWED_TRANSITIONS 확장 | 별도 A 승인 필요 |
| 2 | FORBIDDEN_TARGETS 축소 | 절대 금지 |
| 3 | beat/schedule에서 execute 호출 | 자동 실행 금지 |
| 4 | qualification_status 외 필드 write | scope 밖 |
| 5 | symbols.status UPDATE | FORBIDDEN_TARGET |
| 6 | promotion/paper 경로 활성화 | CR-046 frozen |
| 7 | execute_bounded_write 함수 수정 | RI-2B-2a SEALED |
| 8 | rollback_bounded_write 함수 수정 | RI-2B-2a SEALED |
| 9 | 자동 chain rollback | 수동만 허용 |
| 10 | gate unlock | A 전용 |

---

## 13. 종합

### 13.1 범위 요약

```
허용:
  ├─ EXECUTION_ENABLED: False → True (1줄)
  ├─ 테스트 flag 검증 전환 (~3줄)
  └─ manual execute_bounded_write / rollback_bounded_write 실행 가능

금지:
  ├─ execute/rollback 함수 코드 수정
  ├─ ALLOWED_TRANSITIONS / FORBIDDEN_TARGETS 수정
  ├─ BlockReasonCode / ExecutionVerdict 수정
  ├─ beat/schedule에서 execute 호출
  ├─ qualification_status 외 필드 write
  ├─ gate unlock
  ├─ FROZEN/RED 파일 수정
  ├─ 모델/마이그레이션 변경
  └─ 자동 chain rollback
```

### 13.2 기준선 보호

| 보호 대상 | 보장 |
|-----------|------|
| Baseline v2.5 (5456/5456 PASS) | 전체 회귀 PASS 필수 |
| Gate LOCKED | 변경 0 |
| SEALED 함수 | 수정 0줄 |
| FROZEN/RED 파일 | 접촉 0건 |
| 10-step flow | 변경 0 |
| CAS/TOCTOU/post-write 계약 | 변경 0 |

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| RI-2B-2b 범위 | **승인 / 수정 요청 / 거부** |
| EXECUTION_ENABLED True 전환 | 허용 여부 |
| Write Intent Ledger | 채택 여부 |
| CAS Failure Taxonomy | 채택 여부 |
| No-Write Proof Table | 채택 여부 |
| 구현 GO | 범위 승인 후 별도 GO 필요 |

---

```
CR-048 RI-2B-2b Scope Review Package v1.0
Baseline: v2.5 (5456/5456 PASS)
Gate: LOCKED (변경 없음)
Target: symbols.qualification_status CAS write only
Transitions: unchecked→pass, unchecked→fail (2개만)
Code change: 1 line (EXECUTION_ENABLED False→True)
New files: 0
Model/migration change: 0
SEALED function modification: ZERO
FROZEN/RED contact: ZERO
Manual trigger only: YES
Beat/schedule: ZERO
Fail-closed: 14/15 scenarios = write 0
Audit: all paths have receipt
Rollback: manual 1-time + receipt
Risk level: MEDIUM (first business write)
Recommendation: Scope review submission for A judgment
```
