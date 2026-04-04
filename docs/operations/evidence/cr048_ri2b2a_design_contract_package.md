# CR-048 RI-2B-2a 설계/계약 패키지

**Stage**: RI-2B-2a (Real Bounded Write — Code + Contract Only, 실행 금지)
**Status**: DESIGN CONTRACT 제출
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2B-2 Scope Review v3 ACCEPT
**Baseline**: v2.3 (5397/5397 PASS)

---

## 1. 설계 목적

> 실제 business table UPDATE 코드와 계약을 구현하되, **execution_enabled=False 하드코딩으로 실행을 원천 차단**하는 단계.

RI-2B-2a는 "코드와 테스트가 존재하지만 실행할 수 없는 상태"를 만드는 단계이며,
RI-2B-2b (별도 A 승인)에서만 execution_enabled=True 전환이 허용된다.

---

## 2. 기존 코드 무수정 계약

RI-2B-1 SEALED 코드는 **1줄도 변경하지 않는다.**

| 기존 코드 | 수정 | 사유 |
|-----------|:----:|------|
| `evaluate_verdict()` | **금지** | RI-2B-1 SEALED |
| `evaluate_shadow_write()` | **금지** | RI-2B-1 SEALED |
| `compute_dedupe_key()` | **금지** | RI-2B-1 SEALED |
| `_derive_intended_value()` | **금지** | RI-2B-1 SEALED |
| `WriteVerdict` enum (3값) | **금지** | RI-2B-1 SEALED |
| `BlockReasonCode` enum (5값) | **금지** | RI-2B-1 SEALED |
| `ALLOWED_TARGETS` | **금지** | RI-2B-1 SEALED |
| `FORBIDDEN_TARGETS` | **금지** | RI-2B-1 SEALED |
| `ALLOWED_TRANSITIONS` | **금지** | RI-2B-1 SEALED |
| `ShadowWriteReceipt` 모델 | **금지** | RI-2B-1 SEALED |
| `022_shadow_write_receipt.py` | **금지** | RI-2B-1 SEALED |

---

## 3. 신규 추가 요소

### 3-1. EXECUTION_ENABLED 상수

```python
# RI-2B-2a: FORCED False. True 전환은 RI-2B-2b 별도 A 승인 후에만 허용.
# 무단 변경은 FROZEN violation으로 간주.
EXECUTION_ENABLED: bool = False
```

### 3-2. 신규 Verdict 값 (ExecutionVerdict enum)

기존 `WriteVerdict`를 수정하지 않고 **별도 enum**으로 추가:

```python
class ExecutionVerdict(str, Enum):
    EXECUTED = "executed"                    # write 성공 + 검증 통과
    EXECUTION_FAILED = "execution_failed"    # write 시도 후 실패/rollback
    ROLLED_BACK = "rolled_back"              # 성공 후 수동 rollback 완료
    BLOCKED = "blocked"                      # 전제 조건 미충족 (write 미시도)
```

### 3-3. 신규 BlockReasonCode 값

기존 enum에 **값 추가만** (기존 5개 무수정):

```python
class BlockReasonCode(str, Enum):
    # RI-2B-1 (기존 5개 — 무수정)
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    FORBIDDEN_TARGET = "FORBIDDEN_TARGET"
    INPUT_INVALID = "INPUT_INVALID"
    ALREADY_MATCHED = "ALREADY_MATCHED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    # RI-2B-2 (신규 5개)
    EXECUTION_DISABLED = "EXECUTION_DISABLED"
    NO_PRIOR_RECEIPT = "NO_PRIOR_RECEIPT"
    RECEIPT_ALREADY_CONSUMED = "RECEIPT_ALREADY_CONSUMED"
    STALE_PRECONDITION = "STALE_PRECONDITION"
    CAS_MISMATCH = "CAS_MISMATCH"
```

---

## 4. execute_bounded_write() 계약

### 시그니처

```python
async def execute_bounded_write(
    db: AsyncSession,
    receipt_id: str,                    # 이번 execution의 고유 ID (UUID)
    shadow_receipt_id: str,             # 선행 RI-2B-1 receipt의 receipt_id
    symbol: str,
    target_table: str = "symbols",
    target_field: str = "qualification_status",
) -> ShadowWriteReceipt | None:
```

### 10단계 실행 흐름

```
Step  1: EXECUTION_ENABLED == True 검증
         → False: BLOCKED (EXECUTION_DISABLED) receipt 기록 + return
Step  2: 선행 receipt SELECT by shadow_receipt_id
         → 미존재: BLOCKED (NO_PRIOR_RECEIPT)
Step  3: 선행 receipt.verdict == "would_write" 검증
         → 불일치: BLOCKED (NO_PRIOR_RECEIPT)
Step  4: 선행 receipt.consumed == False 검증 (1:1 결합)
         → True: BLOCKED (RECEIPT_ALREADY_CONSUMED)
Step  5: FORBIDDEN_TARGETS / ALLOWED_TARGETS 검사
         → 금지/비허용: BLOCKED
Step  6: 현재 DB 실시간 조회 (SELECT ... FOR UPDATE)
         → current != receipt.current_value: BLOCKED (STALE_PRECONDITION)
         → current != "unchecked": BLOCKED (STALE_PRECONDITION)
Step  7: ALLOWED_TRANSITIONS 검증
         → (current, intended) not in whitelist: BLOCKED (PRECONDITION_FAILED)
Step  8: Compare-and-Set UPDATE
         UPDATE symbols SET qualification_status = :intended
         WHERE symbol = :symbol AND qualification_status = 'unchecked'
         → affected 0: BLOCKED (CAS_MISMATCH) + rollback
         → affected 2+: rollback + EXECUTION_FAILED
Step  9: Post-write 검증 (5개 기준)
         1. SELECT qualification_status == intended_value
         2. affected rows == 1
         3. 대상 외 필드 변경 0
         4. 후속 side effect 0
         5. execution receipt 기록 가능
         → 검증 실패: rollback + EXECUTION_FAILED receipt
Step 10: consumed 마킹 + EXECUTED receipt 기록
         → 선행 receipt consumed=True (post-write 검증 완료 후에만)
         → execution receipt: dry_run=False, executed=True, business_write_count=1
```

### consumed 전환 시점 계약

| 시점 | consumed 값 | 이유 |
|------|:-----------:|------|
| Step 8 (write) 직전 | False | write 실패 시 재시도 가능해야 함 |
| Step 8 (write) 직후 | False | 아직 post-write 검증 미완료 |
| Step 9 (검증) 실패 | False | rollback 후 재시도 가능 |
| **Step 10 (모두 성공)** | **True** | post-write 검증까지 완료된 경우에만 |

### Proof Fields

| 결과 | dry_run | executed | business_write_count |
|------|:-------:|:--------:|:--------------------:|
| EXECUTED | False | True | **1** |
| EXECUTION_FAILED | False | False | **0** |
| BLOCKED | True | False | **0** |

### 반환값

| 결과 | 반환 | verdict |
|------|------|---------|
| 성공 | ShadowWriteReceipt | EXECUTED |
| 전제 미충족 | ShadowWriteReceipt | BLOCKED |
| write 실패 | ShadowWriteReceipt | EXECUTION_FAILED |
| 내부 오류 | None | — |

---

## 5. rollback_bounded_write() 계약

### 시그니처

```python
async def rollback_bounded_write(
    db: AsyncSession,
    receipt_id: str,                    # rollback receipt의 고유 ID
    execution_receipt_id: str,          # rollback 대상 execution receipt_id
    symbol: str,
) -> ShadowWriteReceipt | None:
```

### 실행 흐름

```
Step 1: EXECUTION_ENABLED == True 검증 → False: BLOCKED
Step 2: execution receipt SELECT → 미존재: BLOCKED
Step 3: execution receipt.verdict == "executed" 검증 → 불일치: BLOCKED
Step 4: 기존 ROLLED_BACK receipt 존재 여부 → 있음: BLOCKED (재rollback 금지)
Step 5: 현재 DB값 == execution receipt.intended_value 검증 → 불일치: BLOCKED
Step 6: Compare-and-Set UPDATE
        UPDATE symbols SET qualification_status = :original_value
        WHERE symbol = :symbol AND qualification_status = :intended_value
Step 7: Post-rollback 검증 (SELECT == original_value)
Step 8: ROLLED_BACK receipt 기록
        → dry_run=False, executed=False, business_write_count=-1
```

### 협소 Rollback 범위 계약

| 항목 | 계약 |
|------|------|
| 대상 | 해당 실행이 직전에 바꾼 값에 대해서만 |
| 트리거 | 수동으로만 (자동 rollback chain 금지) |
| 횟수 | 1회성 (동일 execution에 대해 rollback은 1회) |
| 전제 | 현재 DB값 == intended_value (변경이 살아있어야 함) |
| 범위 | qualification_status 1필드만 |
| rollback receipt | verdict=ROLLED_BACK, business_write_count=-1 |
| 원 execution 연결 | shadow_receipt_id = execution_receipt_id |
| 실패 | logger.critical + return None |

---

## 6. Failure Isolation (RI-2B-1 패턴 계승)

| 실패 유형 | 운영 영향 | 처리 |
|-----------|:---------:|------|
| EXECUTION_ENABLED=False | 0 | BLOCKED receipt + return |
| 선행 receipt 미존재 | 0 | BLOCKED receipt + return |
| SELECT FOR UPDATE 실패 | 0 | return None, 예외 미전파 |
| UPDATE 실패 | 0 | rollback + EXECUTION_FAILED receipt |
| post-write 검증 실패 | 0 | rollback + EXECUTION_FAILED receipt |
| commit 실패 | 0 | 트랜잭션 자동 rollback |
| 일반 예외 | 0 | logger.exception + return None |

**모든 실패는 호출자에 전파되지 않는다.**

---

## 7. 파일 목록 (확정)

| 파일 | 작업 | 등급 | 변경 상세 |
|------|------|:----:|-----------|
| `app/services/shadow_write_service.py` | **수정** | L3 | EXECUTION_ENABLED 상수, ExecutionVerdict enum, BlockReasonCode 5값 추가, execute_bounded_write(), rollback_bounded_write() 추가 |
| `tests/test_shadow_write_receipt.py` | **수정** | L1 | RI-2B-2a 테스트 클래스 추가 |

**총 2개 파일 수정. 신규 파일 0. 모델/마이그레이션 변경 0.**

### 무접촉 파일

| 파일 | 사유 |
|------|------|
| `app/models/shadow_write_receipt.py` | RI-2B-1 SEALED |
| `alembic/versions/022_shadow_write_receipt.py` | RI-2B-1 SEALED |
| `app/services/pipeline_shadow_runner.py` | FROZEN (RI-1) |
| `app/services/shadow_readthrough.py` | FROZEN (RI-2A-1) |
| `app/services/shadow_observation_service.py` | FROZEN (RI-2A-2a) |
| `app/models/shadow_observation.py` | FROZEN (RI-2A-2a) |
| `app/models/asset.py` | Symbol 모델 수정 금지 |
| `exchanges/*` | RED |
| `workers/tasks/*` | task 등록 금지 |

---

## 8. consumed 필드 구현 전략

RI-2B-1 모델(SEALED)은 수정 금지. consumed 필드는 **별도 저장** 방식:

| 방식 | 설명 |
|------|------|
| **execution receipt 내 기록** | execution receipt의 `shadow_receipt_id` 존재 = 해당 shadow receipt는 consumed |
| consumed 확인 | `SELECT ... FROM shadow_write_receipt WHERE receipt_id = :shadow_receipt_id AND verdict = 'executed'` |
| 명시적 consumed 컬럼 | 모델 수정 금지이므로 **사용 불가** |

**consumed 상태는 execution receipt의 존재로 추론한다.**
- shadow_receipt_id로 execution receipt (verdict=EXECUTED)가 존재하면 → consumed
- 존재하지 않으면 → not consumed

이 방식은 shadow_write_receipt 모델을 수정하지 않으면서 1:1 결합을 보장한다.

### 구현 검증

```python
# consumed 여부 확인
stmt = select(ShadowWriteReceipt).where(
    ShadowWriteReceipt.shadow_observation_id == None,  # execution receipts use this differently
    ShadowWriteReceipt.verdict == ExecutionVerdict.EXECUTED.value,
    ShadowWriteReceipt.current_value == shadow_receipt.current_value,
    ShadowWriteReceipt.symbol == symbol,
    ShadowWriteReceipt.intended_value == shadow_receipt.intended_value,
)
```

실제로는 더 간단히: execution receipt에 `transition_reason`에 `shadow_receipt_id`를 기록하여 연결.

---

## 9. execution receipt ↔ shadow receipt 연결

| 필드 | shadow receipt (RI-2B-1) | execution receipt (RI-2B-2) |
|------|:------------------------:|:---------------------------:|
| receipt_id | UUID-A (shadow) | UUID-B (execution) |
| dedupe_key | SHA-256 (dry_run=true) | SHA-256 (dry_run=false) — 다른 key |
| dry_run | True | False |
| transition_reason | "shadow_qualified" 등 | **"exec_of:{shadow_receipt_id}"** |
| shadow_observation_id | observation ID | **shadow receipt의 shadow_observation_id 계승** |

**연결 방식**: execution receipt의 `transition_reason` = `"exec_of:{shadow_receipt_id}"` 형식.
**consumed 확인**: transition_reason이 `exec_of:{shadow_receipt_id}`인 EXECUTED receipt 존재 → consumed.

---

## 10. 완료 기준 (25개)

| # | 기준 | 검증 방법 |
|---|------|-----------|
| 1 | EXECUTION_ENABLED=False 하드코딩 | 상수 검증 테스트 |
| 2 | execution_enabled=False → BLOCKED (EXECUTION_DISABLED) | Step 1 차단 테스트 |
| 3 | 선행 receipt 없음 → BLOCKED (NO_PRIOR_RECEIPT) | Step 2 차단 테스트 |
| 4 | 선행 receipt verdict != WOULD_WRITE → BLOCKED | Step 3 차단 테스트 |
| 5 | 선행 receipt consumed → BLOCKED (RECEIPT_ALREADY_CONSUMED) | Step 4 차단 테스트 |
| 6 | FORBIDDEN_TARGET → BLOCKED | Step 5 차단 테스트 |
| 7 | 현재 DB값 != unchecked → BLOCKED (STALE_PRECONDITION) | Step 6 TOCTOU 테스트 |
| 8 | receipt.current_value != 현재 DB값 → BLOCKED (STALE_PRECONDITION) | Step 6 TOCTOU 테스트 |
| 9 | Compare-and-Set 0 row → BLOCKED (CAS_MISMATCH) | Step 8 테스트 |
| 10 | 정상 경로: unchecked→pass + EXECUTED receipt (mock) | 성공 경로 |
| 11 | 정상 경로: unchecked→fail + EXECUTED receipt (mock) | 성공 경로 |
| 12 | business_write_count=1 (성공 시) | proof field |
| 13 | dry_run=False, executed=True (성공 시) | proof field |
| 14 | post-write 검증 실패 → rollback + EXECUTION_FAILED | 검증 테스트 |
| 15 | write 실패 시 consumed=False 유지 | consumed 시점 |
| 16 | post-write 검증 실패 시 consumed=False 유지 | consumed 시점 |
| 17 | rollback 정상 동작 + ROLLED_BACK receipt | rollback 계약 |
| 18 | rollback receipt이 원 execution에 연결됨 | rollback audit |
| 19 | post-rollback DB값 == original current_value | rollback 검증 |
| 20 | 동일 execution 재rollback → BLOCKED | 1회성 |
| 21 | rollback 대상 없음 → BLOCKED | 범위 제한 |
| 22 | receipt append-only (UPDATE/DELETE 없음) | RI-2B-1 패턴 |
| 23 | 기존 함수 (evaluate_verdict 등) 무수정 확인 | SEALED 보호 |
| 24 | FROZEN/RED 무접촉 | 봉인 파손 없음 |
| 25 | 전체 회귀 PASS | baseline 유지 |

---

## 11. execution_enabled 변경 권한 규칙

| 항목 | 규칙 |
|------|------|
| 기본값 | `False` (하드코딩) |
| RI-2B-2a 승인으로 True 전환 권한 생성 | **아니오** |
| True 전환 조건 | RI-2B-2b 별도 scope review + 설계/계약 + A 승인 완료 후에만 |
| 무단 변경 | FROZEN violation으로 간주 |

> **RI-2B-2a 승인 범위에는 execution_enabled 값 변경, 운영 실행, rollback 실행 권한이 포함되지 않는다.**

---

## 12. 방화벽 선언

1. **RI-2B-2a는 execute_bounded_write()와 rollback_bounded_write() 코드를 추가하되, EXECUTION_ENABLED=False가 강제되어 실제 실행은 불가능하다.**
2. **기존 RI-2B-1 코드 (evaluate_verdict, evaluate_shadow_write, compute_dedupe_key, 모델, 마이그레이션)는 1줄도 수정하지 않는다.**
3. **RI-2B-2a 승인은 실행 활성화, 운영 실행, rollback 실행 권한을 포함하지 않는다.**
4. **execution_enabled=False→True 전환은 RI-2B-2b 별도 승인 없이는 금지된다.**
5. **모든 테스트는 mock/patch로 execution_enabled=True를 시뮬레이션하되, 실제 프로덕션 상수는 False 유지.**

---

## A 판정 요청

RI-2B-2a 설계/계약 패키지를 제출합니다.

- **ACCEPT + GO** → RI-2B-2a 구현 제한 승인 (execution_enabled=False 고정 상태)
- **CONDITIONAL** → 지적 사항 반영 후 재제출
- **REJECT** → 설계 재검토
