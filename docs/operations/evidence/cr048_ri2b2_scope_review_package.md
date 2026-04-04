# CR-048 RI-2B-2 범위 심사 패키지

**Stage**: RI-2B-2 (Real Bounded Write)
**Status**: SCOPE REVIEW 제출 (v3 — v2 피드백 4건 보강: 플래그 변경 권한, consumed 시점, rollback audit, 상태 분리)
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2B-1 SEALED (v2.3, 5397/5397 PASS)

---

## 1. 범위 심사 목적

RI-2B-1(shadow evidence)이 봉인된 상태에서, **shadow receipt의 WOULD_WRITE 판정을 근거로 실제 business table 1필드를 최초 변경**하기 위한 범위 심사.

> RI-2B-2는 CR-048 최초의 business table write이다.
> RI-2B-1과 질적으로 다른 계층이며, 통제 강도가 한 계층 올라간다.

---

## 2. 2단 분리: RI-2B-2a / RI-2B-2b

A 권고에 따라 RI-2B-2를 다시 분리합니다:

| 단계 | 명칭 | 성격 | 상태 |
|------|------|------|------|
| **RI-2B-2a** | Code + Contract (실행 금지) | write 함수 추가 + 테스트 + 계약 검증. **실행 불가 상태** | **본 심사 대상** |
| **RI-2B-2b** | Execution Enable (A 승인 후 수동 실행) | A 승인 후 수동 실행 허용 | **DEFERRED** |

### 분리 이유

> 코드 존재와 실행 권한 부여를 분리하면, 최초 real write 리스크를 더 낮출 수 있다.

| 항목 | RI-2B-2a | RI-2B-2b |
|------|:--------:|:--------:|
| write 함수 코드 존재 | **예** | 예 |
| 테스트 실행 (mock DB) | **예** | 예 |
| 실제 DB write 실행 | **금지** | **허용 (수동)** |
| execution_enabled 플래그 | **False (강제)** | True (A 승인 후) |
| 진입 조건 | RI-2B-1 SEALED | **RI-2B-2a SEALED** |

**RI-2B-2a는 "코드와 계약이 있지만, 실행할 수 없는 상태".**
**RI-2B-2b는 "A 승인 후 실행 가능한 상태".**

---

## 3. RI-2B-1 → RI-2B-2 관계

| 항목 | RI-2B-1 (SEALED) | RI-2B-2a (본 심사) | RI-2B-2b (DEFERRED) |
|------|:-----------------:|:------------------:|:-------------------:|
| shadow_write_receipt INSERT | 허용 | 허용 | 허용 |
| Business table write | **금지** | **금지 (코드만)** | **허용 (bounded)** |
| dry_run | 항상 True | True (테스트에서만) | True/False 선택 |
| executed | 항상 False | False (강제) | True/False 선택 |
| business_write_count | 항상 0 | 0 (강제) | 0 또는 1 |
| execution_enabled 플래그 | 해당 없음 | **False (강제)** | **True (A 승인)** |
| 실제 상태 전이 실행 | 금지 | **금지** | 허용 (whitelist만) |
| Rollback 계약 | 불필요 | 코드 존재 (미실행) | **필수** |

---

## 4. Write Target (확정 — RI-2B-1과 동일)

| target_table | target_field | 허용 전이 | 비고 |
|-------------|-------------|-----------|------|
| `symbols` | `qualification_status` | `unchecked → pass`, `unchecked → fail` | shadow qualification 결과 기반 |

**1개 테이블 × 1개 필드 × 2개 전이. 이 범위 밖의 write는 RI-2B-2에서도 금지.**

### 금지 Write Target (RI-2B-1과 동일)

| target_table | target_field | 금지 사유 |
|-------------|-------------|-----------|
| `symbols` | `status` (CORE/WATCH/EXCLUDED) | 3상태 전이는 screening pipeline 전용 |
| `symbols` | `promotion_eligibility_status` | 승격 경로는 Phase 4+ |
| `symbols` | `paper_evaluation_status` | paper 경로는 CR-046 frozen |
| `strategies` | `status` | 전략 승격은 Phase 4+ |
| `screening_results` | * | screening pipeline 전용 |
| `qualification_results` | * | qualification pipeline 전용 |
| `promotion_events` | * | promotion gate 전용 |

---

## 5. 실행 전제 조건 (6개 — 모두 충족해야 실행)

| # | 전제 조건 | 검증 방법 | A 피드백 대응 |
|---|-----------|-----------|:------------:|
| 1 | execution_enabled == True | 플래그 검사 (RI-2B-2a에서는 항상 False) | 2a/2b 분리 |
| 2 | 동일 symbol + target에 대한 RI-2B-1 receipt 존재 | receipt SELECT by symbol + target | 선행 receipt |
| 3 | 해당 receipt의 verdict == `WOULD_WRITE` | receipt.verdict 검증 | 선행 receipt |
| 4 | 해당 receipt가 **미소비 상태** (consumed == False) | receipt 소비 플래그 검증 | **1:1 결합** |
| 5 | 현재 symbols.qualification_status == `unchecked` **(실행 직전 실시간 조회)** | `SELECT ... FOR UPDATE` | **TOCTOU 방어** |
| 6 | 전이가 ALLOWED_TRANSITIONS에 포함 | whitelist 검증 | whitelist |

**전제 조건 6개 중 하나라도 실패 → write 금지 → BLOCKED receipt 기록.**

---

## 6. A 피드백 6건 보강 사항

### 6-1. 실행 직전 재검증 (TOCTOU 방어)

> receipt만 믿고 쓰지 말고, write 직전 row 상태를 다시 확인해야 한다.

| 항목 | 계약 |
|------|------|
| 방식 | `SELECT qualification_status FROM symbols WHERE symbol = :symbol FOR UPDATE` |
| 검증 | 반환값 == `unchecked` 인 경우에만 진행 |
| 불일치 시 | 즉시 BLOCKED receipt (block_reason = `STALE_PRECONDITION`) |
| receipt 당시 값과 비교 | receipt.current_value == 현재 DB값이어야 함 |

**blind write 금지. compare-and-set 성격의 조건부 write만 허용.**

### 6-2. Receipt 1:1 결합 (재사용 금지)

> 하나의 WOULD_WRITE receipt는 최대 1회의 real write에만 연결 가능.

| 항목 | 계약 |
|------|------|
| 메커니즘 | receipt에 `consumed` 플래그 추가 (default=False) |
| **consumed 전환 시점** | **post-write 검증 완료 후** (Step 9 통과 후 Step 10에서 마킹) |
| consumed 전환 시점 이유 | write 직전이면 실패 시에도 consumed=True가 됨, write 직후면 검증 전 소비 표시됨 |
| 이미 consumed된 receipt | 즉시 BLOCKED (block_reason = `RECEIPT_ALREADY_CONSUMED`) |
| 1:1 보장 | execution receipt의 `shadow_receipt_id`로 연결, UNIQUE 아님 but consumed check |
| write 실패 시 consumed | **False 유지** (재시도 가능) |
| post-write 검증 실패 시 consumed | **False 유지** (rollback 후 재시도 가능) |

**receipt는 실행 토큰이 아니라 1회용 근거 문서. 재사용 금지.**
**consumed=True 전환은 post-write 검증까지 완료된 경우에만 발생한다.**

### 6-3. Compare-and-Set 조건부 Write

> blind write 금지.

```sql
UPDATE symbols
SET qualification_status = :intended_value
WHERE symbol = :symbol
  AND qualification_status = :expected_current_value
```

| 항목 | 계약 |
|------|------|
| UPDATE 조건 | `WHERE qualification_status = 'unchecked'` 포함 필수 |
| 영향 row 수 | 정확히 1 (0이면 stale → BLOCKED, 2+이면 오류 → rollback) |
| blind UPDATE 금지 | `WHERE symbol = :symbol`만으로 UPDATE 금지 |

### 6-4. 협소 Rollback 범위

> rollback도 무제한이 아니라 계약상 허용된 복귀 범위 안에 있어야 한다.

| 항목 | 계약 |
|------|------|
| rollback 대상 | **해당 실행이 바로 직전에 바꾼 값**에 대해서만 |
| rollback 트리거 | 수동으로만 (자동 rollback chain 금지) |
| rollback 횟수 | 1회성 (동일 execution에 대해 rollback은 1회) |
| rollback 전제 | 사전 보존값(receipt.current_value)과 현재 DB값의 intended_value 일치 확인 |
| rollback 범위 | `qualification_status` 1필드만 (다른 필드 rollback 금지) |
| rollback receipt | verdict=`ROLLED_BACK`, business_write_count=-1 |
| rollback 자체 실패 | logger.critical + 수동 개입 필요 플래그 + return None |

### Rollback Receipt/Audit 귀속 (v3 추가)

> rollback이 별도 비가시 write가 되면 안 된다. rollback도 receipt/audit에 귀속되어야 한다.

| 항목 | 계약 |
|------|------|
| 원 실행 연결 | rollback receipt의 `shadow_receipt_id` = 원 execution receipt의 `receipt_id` |
| 1회성 기록 | rollback receipt에 `rollback_of` 필드로 원 execution 명시 |
| rollback 후 검증 | post-rollback SELECT로 값이 원래 current_value로 복원됐는지 확인 |
| 검증 실패 시 | logger.critical + return None (수동 개입 필요) |
| 재rollback 방지 | 동일 execution receipt에 대해 ROLLED_BACK receipt가 이미 존재하면 BLOCKED |

**rollback은 기능이 아니라 계약. 허용 복귀 범위를 넘는 rollback은 금지.**
**모든 rollback은 receipt로 기록되며 비가시 write가 되지 않는다.**

### 6-5. Post-Write 검증 수락 기준

> "write 성공"만 보면 안 되고, 예상 전이와 실제 DB 상태가 일치하는지 검증해야 한다.

| # | 검증 항목 | 기대값 | 실패 시 |
|---|-----------|--------|---------|
| 1 | 예상 target state와 실제 DB state 일치 | `SELECT qualification_status` == intended_value | rollback |
| 2 | 변경 row 수 | 정확히 1 | rollback |
| 3 | 대상 외 필드 변경 | 0 (qualification_status 외 필드 불변) | rollback |
| 4 | 후속 side effect | 0 (trigger, cascade, listener 없음) | rollback |
| 5 | execution receipt 기록 | EXECUTED verdict + business_write_count=1 | — |

**5개 검증 중 #1~#4 실패 시 rollback + EXECUTION_FAILED receipt.**

### 6-6. RI-2A-2b 방화벽 재선언

> **RI-2B-2 승인은 manual bounded write 범위에 한정되며, beat/schedule/retention/purge/automatic execution 권한을 생성하지 않는다.**
>
> **RI-2B-2a 승인은 코드·계약·테스트 범위에 한정되며, 실제 DB 실행 권한을 생성하지 않는다.**

---

## 7. 실행 흐름 (10단계, 순서 고정)

```
Step  1: execution_enabled == True 검증 (RI-2B-2a에서는 항상 False → 즉시 중단)
Step  2: 선행 receipt 존재 + verdict == WOULD_WRITE 검증
Step  3: 선행 receipt consumed == False 검증 (1:1 결합)
Step  4: FORBIDDEN_TARGETS 검사 (금지 대상 즉시 차단)
Step  5: ALLOWED_TARGETS 검사 (허용 대상 확인)
Step  6: 현재 DB 값 실시간 조회 (SELECT ... FOR UPDATE) + receipt.current_value 일치 검증
Step  7: ALLOWED_TRANSITIONS 검증 (unchecked → pass/fail만)
Step  8: Compare-and-Set UPDATE 실행 (1 row, 1 field, WHERE qualification_status = 'unchecked')
Step  9: Post-write 검증 (5개 수락 기준)
Step 10: Execution receipt 기록 + 선행 receipt consumed 마킹
```

**Step 1~7은 모두 차단 조건. Step 8은 모든 차단을 통과한 경우에만 도달.**
**Step 8 실패 또는 Step 9 검증 실패 → rollback + EXECUTION_FAILED receipt.**

---

## 8. Execution Receipt 계약

기존 `shadow_write_receipt` 테이블을 그대로 사용하되, proof field 값이 달라집니다.

### Verdict 값 (RI-2B-2 전용 추가분)

| Verdict | 의미 | dry_run | executed | business_write_count |
|---------|------|:-------:|:--------:|:--------------------:|
| `EXECUTED` | 실제 write 성공 + 검증 통과 | False | True | **1** |
| `EXECUTION_FAILED` | write 시도 후 실패/rollback | False | False | **0** |
| `ROLLED_BACK` | 성공 후 수동 rollback 완료 | False | False | **-1** |
| `BLOCKED` | 전제 조건 미충족으로 write 미시도 | True | False | **0** |

### 신규 BlockReasonCode (RI-2B-2 전용)

| 코드 | 의미 |
|------|------|
| `EXECUTION_DISABLED` | execution_enabled == False (RI-2B-2a) |
| `NO_PRIOR_RECEIPT` | 선행 WOULD_WRITE receipt 없음 |
| `RECEIPT_ALREADY_CONSUMED` | 선행 receipt 이미 소비됨 |
| `STALE_PRECONDITION` | 실행 직전 DB값 ≠ receipt 당시 값 |
| `CAS_MISMATCH` | Compare-and-Set UPDATE 영향 0 row |

**RI-2B-2 receipt도 append-only. UPDATE/DELETE 금지.**

---

## 9. 서비스 API 계약

```python
async def execute_bounded_write(
    db: AsyncSession,
    receipt_id: str,                    # 이번 execution의 고유 ID
    shadow_receipt_id: str,             # 선행 RI-2B-1 receipt의 receipt_id
    symbol: str,
    target_table: str = "symbols",
    target_field: str = "qualification_status",
) -> ShadowWriteReceipt | None:
    """RI-2B-2: 선행 shadow receipt 검증 후 실제 bounded write 실행.

    계약:
      - execution_enabled == True 필수 (RI-2B-2a에서는 항상 False)
      - 선행 receipt verdict == WOULD_WRITE + consumed == False 필수
      - 실행 직전 DB 재검증 (TOCTOU 방어)
      - Compare-and-Set UPDATE (blind write 금지)
      - Post-write 5개 검증
      - 실패 시 rollback + EXECUTION_FAILED receipt
      - 성공 시 EXECUTED receipt (business_write_count=1)
      - 예외 미전파 (return None)
    """
```

```python
async def rollback_bounded_write(
    db: AsyncSession,
    receipt_id: str,                    # rollback receipt의 고유 ID
    execution_receipt_id: str,          # rollback 대상 execution receipt
    symbol: str,
) -> ShadowWriteReceipt | None:
    """RI-2B-2: 수동 rollback. 1회성. 허용 범위만.

    계약:
      - 대상 execution receipt의 verdict == EXECUTED 필수
      - 현재 DB값 == execution receipt의 intended_value 필수
      - rollback 값 == execution receipt의 current_value
      - qualification_status 1필드만
      - 1회성 (동일 execution에 대해 재rollback 금지)
    """
```

---

## 10. execution_enabled 플래그 계약

| 항목 | 계약 |
|------|------|
| 위치 | `shadow_write_service.py` 모듈 상수 |
| RI-2B-2a 값 | `EXECUTION_ENABLED: bool = False` (하드코딩) |
| RI-2B-2b 전환 | A 승인 후 `True`로 변경 (1줄 변경) |
| 검증 | `execute_bounded_write()` Step 1에서 즉시 검사 |
| False일 때 | BLOCKED receipt (EXECUTION_DISABLED) 기록 후 return |

### execution_enabled 변경 권한 규칙 (v3 추가)

| 항목 | 규칙 |
|------|------|
| 기본값 | `False` (하드코딩) |
| **RI-2B-2a 승인으로 True 전환 권한이 생기는가** | **아니오** |
| True 전환 조건 | **RI-2B-2b 별도 scope review + 설계/계약 + A 승인 완료 후에만** |
| 변경 주체 | A 승인을 받은 후 구현자가 1줄 변경 |
| 변경 문서 | RI-2B-2b 완료 증빙에 변경 사실 기록 필수 |
| 무단 변경 | **금지** — FROZEN violation으로 간주 |

> **execution_enabled 플래그의 False→True 전환은 RI-2B-2b 별도 승인 없이는 금지된다.**

**RI-2B-2a 봉인 시 execution_enabled=False가 강제됨을 테스트로 검증.**

---

## 11. 10대 필수 원칙 준수표

| # | 원칙 | RI-2B-2 준수 방식 |
|---|------|-------------------|
| 1 | Manual trigger only | pytest / script만. beat/schedule/periodic 금지 |
| 2 | Beat/schedule/periodic/background loop 금지 | Celery task 등록 없음, beat_schedule 변경 없음 |
| 3 | Purge/retention 금지 | receipt는 append-only, 삭제/정리 없음 |
| 4 | Single bounded target only | symbols.qualification_status 1개 필드만 |
| 5 | Whitelist state transition only | unchecked→pass, unchecked→fail만 |
| 6 | Idempotency key + durable receipt 필수 | dedupe_key UNIQUE + receipt_id UNIQUE + consumed 1:1 |
| 7 | Rollback contract 필수 | §6-4 협소 Rollback 범위 참조 |
| 8 | Exchange/API/후속 자동 side-effect 금지 | 외부 호출 0, 후속 chain 0 |
| 9 | FROZEN/RED 불가침 | pipeline_shadow_runner, shadow_readthrough, exchanges/* 무접촉 |
| 10 | 관찰 계층 봉인 파손 금지 | shadow_observation_log/service 무수정, RI-2B-1 기존 함수 무수정 |

---

## 12. 파일 목록 (예상 — RI-2B-2a 범위)

| 파일 | 작업 | 등급 |
|------|------|:----:|
| `app/services/shadow_write_service.py` | **수정** — `execute_bounded_write()`, `rollback_bounded_write()` 추가, `EXECUTION_ENABLED=False` 추가, 기존 함수 무수정 | L3 |
| `tests/test_shadow_write_receipt.py` | **수정** — RI-2B-2 테스트 클래스 추가 | L1 |

**총 2개 파일 수정. 신규 파일 0. 모델/마이그레이션 변경 0.**

### 변경 없는 파일 (무접촉 필수)

| 파일 | 사유 |
|------|------|
| `app/models/shadow_write_receipt.py` | RI-2B-1 SEALED 모델 — 스키마 변경 금지 |
| `alembic/versions/022_shadow_write_receipt.py` | RI-2B-1 SEALED 마이그레이션 |
| `app/services/pipeline_shadow_runner.py` | FROZEN (RI-1 SEALED) |
| `app/services/shadow_readthrough.py` | FROZEN (RI-2A-1 SEALED) |
| `app/services/shadow_observation_service.py` | FROZEN (RI-2A-2a SEALED) |
| `app/models/shadow_observation.py` | FROZEN (RI-2A-2a SEALED) |
| `shadow_write_service.py` 기존 함수 | `evaluate_verdict()`, `evaluate_shadow_write()`, `compute_dedupe_key()` 무수정 |
| `exchanges/*` | RED |
| `workers/tasks/*` | task 등록 금지 |

### shadow_write_service.py 수정 범위 (RI-2B-2a)

| 영역 | 허용/금지 |
|------|:---------:|
| `EXECUTION_ENABLED = False` 상수 추가 | **허용** |
| `execute_bounded_write()` 신규 함수 추가 | **허용** |
| `rollback_bounded_write()` 신규 함수 추가 | **허용** |
| 신규 Verdict/BlockReasonCode enum 값 추가 | **허용** |
| `evaluate_verdict()` 기존 로직 수정 | **금지** |
| `evaluate_shadow_write()` 기존 로직 수정 | **금지** |
| `compute_dedupe_key()` 기존 로직 수정 | **금지** |
| ALLOWED_TARGETS / FORBIDDEN_TARGETS / ALLOWED_TRANSITIONS 수정 | **금지** |

---

## 13. 테스트 수락 기준 (예상 — RI-2B-2a)

| # | 테스트 항목 | 검증 대상 |
|---|-----------|-----------|
| 1 | execution_enabled=False → BLOCKED (EXECUTION_DISABLED) | 플래그 차단 |
| 2 | 선행 receipt 없음 → BLOCKED (NO_PRIOR_RECEIPT) | 전제 조건 2 |
| 3 | 선행 receipt verdict != WOULD_WRITE → BLOCKED | 전제 조건 3 |
| 4 | 선행 receipt consumed=True → BLOCKED (RECEIPT_ALREADY_CONSUMED) | 1:1 결합 |
| 5 | 현재 qualification_status != unchecked → BLOCKED (STALE_PRECONDITION) | TOCTOU 방어 |
| 6 | receipt.current_value ≠ 현재 DB값 → BLOCKED (STALE_PRECONDITION) | TOCTOU 방어 |
| 7 | FORBIDDEN_TARGET → BLOCKED | 금지 대상 차단 |
| 8 | Compare-and-Set 0 row 영향 → BLOCKED (CAS_MISMATCH) | blind write 방지 |
| 9 | 정상 경로: unchecked→pass + EXECUTED receipt (mock) | 성공 경로 |
| 10 | 정상 경로: unchecked→fail + EXECUTED receipt (mock) | 성공 경로 |
| 11 | business_write_count == 1 (성공 시) | proof field |
| 12 | dry_run=False, executed=True (성공 시) | proof field |
| 13 | post-write 검증 실패 → rollback + EXECUTION_FAILED | post-write 검증 |
| 14 | rollback 정상 동작 + ROLLED_BACK receipt | rollback 계약 |
| 15 | rollback 대상 없음 → BLOCKED | rollback 범위 제한 |
| 16 | 동일 execution 재rollback → BLOCKED | 1회성 rollback |
| 17 | receipt append-only (UPDATE/DELETE 없음) | RI-2B-1 패턴 계승 |
| 18 | 기존 함수 무수정 확인 | SEALED 보호 |
| 19 | execution_enabled=False 하드코딩 확인 | RI-2B-2a 계약 |
| 20 | write 실패 시 consumed=False 유지 | consumed 시점 계약 |
| 21 | post-write 검증 실패 시 consumed=False 유지 | consumed 시점 계약 |
| 22 | rollback receipt이 원 execution receipt에 연결됨 | rollback audit 귀속 |
| 23 | post-rollback DB값 == original current_value | rollback 검증 |
| 24 | FROZEN/RED 무접촉 | 봉인 파손 없음 |
| 25 | 전체 회귀 PASS | baseline 유지 |

---

## 14. 위험 분석

| 위험 | 등급 | 완화 |
|------|:----:|------|
| Business table 최초 write | **높음** | Compare-and-Set + post-write 검증 + rollback 계약 |
| TOCTOU (receipt↔write 시간차) | **높음** | SELECT FOR UPDATE + receipt.current_value 일치 검증 |
| Receipt 재사용으로 중복 write | **높음** | consumed 플래그 + 1:1 결합 |
| Blind write | **높음** | WHERE qualification_status = 'unchecked' 필수 |
| Rollback이 새로운 오염 경로 | **중간** | 협소 rollback (1필드, 1회, 수동, 사전값 일치 검증) |
| execution_enabled 우회 | **중간** | 하드코딩 상수 + 테스트 검증 + RI-2B-2b 별도 심사 |
| RI-2B-1 기존 코드 의도치 않은 수정 | **중간** | 기존 함수 무수정 테스트 |
| write target 확대 요청 | **중간** | ALLOWED_TARGETS 수정 금지, 확장 시 별도 심사 |

---

## 15. 방화벽 선언

1. **RI-2B-2는 symbols.qualification_status 1개 필드에 대한 Compare-and-Set bounded UPDATE만 수행하며, 그 외 business table에 대한 write를 금지한다.**
2. **RI-2B-2 실행은 반드시 RI-2B-1 선행 receipt (verdict=WOULD_WRITE, consumed=False)를 전제로 하며, 선행 receipt 없는 write는 불가능하다.**
3. **RI-2B-2a 승인은 코드·계약·테스트 범위에 한정되며, 실제 DB 실행 권한을 생성하지 않는다. execution_enabled=False가 강제된다.**
4. **RI-2B-2b (실행 권한 부여)는 RI-2B-2a 봉인 후 별도 A 승인을 요구한다.**
5. **RI-2B-2 승인은 beat/schedule/retention/purge/automatic execution 권한을 포함하지 않는다.**
6. **Rollback은 해당 실행이 직전에 바꾼 값에 대해서만, 수동으로, 1회성으로, 사전 보존값 일치 시에만 허용된다.**

---

## 16. 현재 상태 / 다음 단계

```
Guarded Release ACTIVE · Gate LOCKED
Stage 1~4B L3: SEALED
RI-1 L3: SEALED
RI-2A-1 L3: SEALED
RI-2A-2a L3: SEALED
RI-2B-1 L3: SEALED
RI-2B-2a: SCOPE REVIEW 제출 (본 문서 v3)
RI-2B-2b: DEFERRED (RI-2B-2a 봉인 후 별도 심사 필요, execution_enabled=False→True 전환 권한 미생성)
RI-2A-2b: DEFERRED
Baseline: v2.3 (5397/5397 PASS)
RI-2B-2a 승인은 real bounded write 코드의 존재와 검증 범위만 다루며, 실행 활성화·운영 권한·후속 단계 권한을 생성하지 않는다.
```

### 판정 기준 (A 원문)

> "좁고, 수동이며, 되돌릴 수 있고, 증빙 가능하며, 자동 반복되지 않는다"를 입증하지 못하면 GO 금지.

| 기준 | RI-2B-2a 대응 |
|------|-------------|
| 좁다 | 1 테이블 × 1 필드 × 2 전이 + execution_enabled=False |
| 수동이다 | manual trigger only, beat/schedule 0, 플래그 off |
| 되돌릴 수 있다 | Rollback 계약 §6-4 + 수동 rollback 함수 + 1회성 |
| 증빙 가능하다 | execution receipt + consumed 마킹 + post-write 검증 |
| 자동 반복되지 않는다 | Celery task 0, background loop 0, execution_enabled=False |

### A 피드백 6건 대응표

| # | A 피드백 | 반영 위치 | 상태 |
|---|---------|-----------|:----:|
| 1 | 실행 직전 재검증 (TOCTOU) | §6-1 | **반영** |
| 2 | Receipt 1:1 결합 (재사용 금지) | §6-2 | **반영** |
| 3 | Compare-and-Set 조건부 write | §6-3 | **반영** |
| 4 | 협소 Rollback 범위 | §6-4 | **반영** |
| 5 | Post-write 검증 수락 기준 | §6-5 | **반영** |
| 6 | RI-2A-2b 방화벽 재선언 | §6-6 | **반영** |
| + | 2a/2b 분리 | §2 | **반영** |

### v3 추가 보강 (A v2 피드백 4건)

| # | A 피드백 (v2) | 반영 위치 | 상태 |
|---|--------------|-----------|:----:|
| 7 | execution_enabled 변경 권한 규칙 고정 | §10 변경 권한 규칙 | **반영** |
| 8 | consumed 전환 시점 명문화 (post-write 검증 완료 후) | §6-2 전환 시점 | **반영** |
| 9 | rollback receipt/audit 귀속 | §6-4 Rollback Receipt/Audit 귀속 | **반영** |
| 10 | 2a/2b 분리 문구를 상태표에도 반영 | §16 상태표 | **반영** |

---

## 17. 승인 범위 한정 선언

> **본 문서의 승인 범위는 RI-2B-2a (코드+계약+테스트, 실행 금지) 설계 심사에 한정되며, 실제 DB 실행 권한·write target 확대·beat/schedule 등록·자동 반복 실행·후속 단계 권한을 생성하지 않는다.**
>
> **RI-2B-2a 승인 범위에는 execution_enabled 값 변경, 운영 실행, rollback 실행 권한이 포함되지 않는다.**

---

## A 판정 요청

RI-2B-2 범위 심사 v3를 제출합니다. v2 대비 4건 보강:

1. **execution_enabled 변경 권한 규칙** — RI-2B-2a 승인으로 True 전환 불가, RI-2B-2b 별도 승인 필수
2. **consumed 전환 시점** — post-write 검증 완료 후에만 consumed=True (write 실패/검증 실패 시 False 유지)
3. **rollback receipt/audit 귀속** — 원 execution 연결 + post-rollback 검증 + 재rollback 방지
4. **상태표 2a/2b 분리** — RI-2B-2b 권한 미생성 명시

- **ACCEPT** → RI-2B-2a 설계/계약 패키지 진행
- **CONDITIONAL** → 지적 사항 반영 후 재제출
- **REJECT** → 방향 재검토
