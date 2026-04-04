# CR-048 RI-2B-1 구현 완료 보고

**Stage**: RI-2B-1 (Receipt-only Shadow Write)
**Status**: SEALED (A 승인: 2026-04-04)
**Date**: 2026-04-04
**Authority**: A
**선행 조건**: RI-2B-1 설계/계약 ACCEPT + GO
**Baseline**: v2.2 (5354) → v2.3 candidate (5397)

---

## 1. 수정/생성 파일 목록

| 파일 | 작업 | LOC | FROZEN 접촉 | RED 접촉 |
|------|------|-----|:-----------:|:--------:|
| `app/models/shadow_write_receipt.py` | **신규** | 70 | 0 | 0 |
| `app/services/shadow_write_service.py` | **신규** | 250 | 0 | 0 |
| `alembic/versions/022_shadow_write_receipt.py` | **신규** | 69 | 0 | 0 |
| `tests/test_shadow_write_receipt.py` | **신규** | ~600 | 0 | 0 |
| `app/models/__init__.py` | **수정** (2줄 추가: import + __all__) | +2 | 0 | 0 |

**총 신규 파일: 4. 수정 파일: 1 (import 등록만). 기존 파일 로직 변경: 0.**

---

## 2. DDL / 스키마 요약

### shadow_write_receipt 테이블 (18필드)

| 필드 | 타입 | nullable | UNIQUE |
|------|------|:--------:|:------:|
| id | Integer (PK, auto) | N | - |
| receipt_id | String(64) | N | **Y** |
| dedupe_key | String(128) | N | **Y** |
| symbol | String(32) | N | - |
| target_table | String(48) | N | - |
| target_field | String(48) | N | - |
| current_value | String(128) | **Y** | - |
| intended_value | String(128) | N | - |
| would_change_summary | String(256) | N | - |
| transition_reason | String(128) | N | - |
| block_reason_code | String(64) | **Y** | - |
| shadow_observation_id | Integer | **Y** | - |
| input_fingerprint | String(64) | N | - |
| dry_run | Boolean | N | - |
| executed | Boolean | N | - |
| business_write_count | Integer | N | - |
| verdict | String(32) | N | - |
| created_at | DateTime(tz) | N (server_default) | - |

- **FK: 0. UNIQUE: 2 (receipt_id, dedupe_key). CASCADE: 0.**
- **Index: 4** (PK + ix_swr_symbol + ix_swr_created_at + 2 unique)
- **Revision chain**: 021_shadow_observation_log → 022_shadow_write_receipt

---

## 3. Append-only 검증표

| DML 유형 | 서비스 메서드 존재 | 테스트 |
|----------|:-----------------:|--------|
| INSERT | `db.add(row)` + `db.flush()` | `test_only_add_called` PASS |
| UPDATE | **없음** | `test_service_has_no_update_delete_methods` PASS |
| DELETE | **없음** | `test_no_delete_called` PASS |
| MERGE | **없음** | `test_no_merge_called` PASS |

**shadow_write_service.py에 UPDATE/DELETE/MERGE 문은 존재하지 않는다.**

---

## 4. Verdict 결정표 검증표

| Step | 설명 | 기대 verdict | 테스트 | 결과 |
|------|------|-------------|--------|------|
| 1 | FORBIDDEN_TARGETS hit | BLOCKED (FORBIDDEN_TARGET) | `test_step2_forbidden_target_symbols_status` | PASS |
| 2 | NOT IN ALLOWED_TARGETS | BLOCKED (OUT_OF_SCOPE) | `test_step1_out_of_scope` | PASS |
| 3a | shadow_result is None | BLOCKED (INPUT_INVALID) | `test_step3_null_shadow_result` | PASS |
| 3b | readthrough_result is None | BLOCKED (INPUT_INVALID) | `test_step3_null_readthrough_result` | PASS |
| 4 | current == intended | WOULD_SKIP | `test_step4_already_matched` | PASS |
| 5 | transition not allowed | BLOCKED (PRECONDITION_FAILED) | `test_step5_precondition_failed` | PASS |
| 6 | intended_value is None | WOULD_SKIP | `test_step6_would_skip_screen_failed` | PASS |
| 7 | all checks passed | WOULD_WRITE | `test_step7_would_write_qualified` | PASS |

**금지선 우선 차단 검증**: `test_forbidden_before_business_logic` — `symbols.status`가 FORBIDDEN_TARGETS에 있으므로 ALLOWED_TARGETS 검사보다 먼저 FORBIDDEN_TARGET으로 차단됨. PASS.

---

## 5. Idempotency 2계층 검증표

| 계층 | 메커니즘 | 테스트 | 결과 |
|------|----------|--------|------|
| L1 (Row identity) | receipt_id UNIQUE | `test_unique_constraints` | PASS |
| L2 (Semantic dedupe) | dedupe_key UNIQUE (SHA-256 of 7 inputs) | `test_duplicate_dedupe_key_returns_existing` | PASS |

**Dedupe Key 입력 7개**: symbol, target_table, target_field, current_value, intended_value, input_fingerprint, dry_run.

| Dedupe 속성 | 테스트 | 결과 |
|-------------|--------|------|
| 결정론적 | `test_deterministic` | PASS |
| symbol 다르면 key 다름 | `test_different_symbol_different_key` | PASS |
| intended 다르면 key 다름 | `test_different_intended_different_key` | PASS |
| None → "NULL" 치환 | `test_none_current_value_uses_null` | PASS |
| SHA-256 hex 64자 | `test_sha256_hex_length` | PASS |

---

## 6. Failure Isolation 검증표

| 실패 유형 | 기대 동작 | 테스트 | 결과 |
|-----------|----------|--------|------|
| db.flush() 예외 | return None, 예외 미전파 | `test_flush_failure_returns_none` | PASS |
| db.add() 예외 | return None, 예외 미전파 | `test_add_failure_returns_none` | PASS |
| IntegrityError (중복) | rollback → SELECT existing → return existing | `test_duplicate_dedupe_key_returns_existing` | PASS |
| 일반 예외 | logger.exception → return None | `test_failure_does_not_raise` | PASS |

**INSERT 실패가 호출자에 전파되지 않음을 보장.**

---

## 7. FROZEN / RED 무접촉 증빙

### FROZEN 파일 (변경 0줄)

| 파일 | 변경 | 검증 |
|------|:----:|------|
| `app/services/pipeline_shadow_runner.py` | 0 | import만 (service에서 type ref) |
| `app/services/screening_qualification_pipeline.py` | 0 | import만 (service에서 type ref) |
| `app/services/shadow_readthrough.py` | 0 | import만 (service에서 type ref) |
| `app/models/shadow_observation.py` | 0 | 비접촉 |

### RED 파일 (접촉 0건)

| 영역 | 접촉 | 검증 |
|------|:----:|------|
| 실행 경로 (OrderExecutor, PositionManager) | 0 | shadow_write_service.py에 실행 import 없음 |
| 전략 코드 (strategies/) | 0 | 비접촉 |
| 거래소 어댑터 (exchanges/) | 0 | 비접촉 |
| 주문/포지션 모델 (Order, Position) | 0 | 비접촉 |

---

## 8. Business Table Write 0 증빙

| 검증 항목 | 테스트 | 결과 |
|-----------|--------|------|
| Symbol 모델 미import | `test_no_symbol_model_import_in_service` | PASS |
| symbols 테이블 무변경 | `test_symbols_table_not_touched` | PASS |
| ALLOWED_TARGETS readonly | `test_allowed_targets_is_readonly` (frozenset) | PASS |
| FORBIDDEN_TARGETS readonly | `test_forbidden_targets_is_readonly` (frozenset) | PASS |

**shadow_write_service.py는 Symbol/Strategy 모델을 import하지 않으며, business table에 대한 어떠한 DML도 수행하지 않는다.**

---

## 9. 전체 회귀 결과

```
pytest --tb=short -q
5397 passed, 10 warnings in 179.61s
```

| 항목 | 값 |
|------|-----|
| 이전 baseline | 5354 |
| 신규 테스트 | +43 (test_shadow_write_receipt.py) |
| 현재 total | 5397 |
| 실패 | 0 |
| 경고 | 10 (기존 AsyncMock coroutine 경고, 기존과 동일) |

---

## 10. 신규 경고/예외 여부

- 신규 경고: **0건**
- 신규 예외: **0건**
- 기존 경고 10건은 RI-2B-1 이전부터 존재하던 AsyncMock coroutine 미await 경고 (asset_service 테스트). RI-2B-1과 무관.

---

## 11. 완료 기준 13/13 대조표

| # | 기준 | 검증 결과 | 근거 |
|---|------|:---------:|------|
| 1 | Schema 구현 (18필드, FK 0, UNIQUE 2) | **PASS** | §2 DDL 요약 |
| 2 | Append-only (INSERT만, UPDATE/DELETE 0) | **PASS** | §3 Append-only 검증표 |
| 3 | Verdict 7단계 결정표 순서 준수 | **PASS** | §4 Verdict 검증표 (8 tests) |
| 4 | 금지선 우선 차단 (Step 1~3 선행) | **PASS** | §4 금지선 우선 차단 검증 |
| 5 | dry_run=True / executed=False / business_write_count=0 고정 | **PASS** | 3 proof field tests |
| 6 | Semantic dedupe (dedupe_key UNIQUE) | **PASS** | §5 Idempotency L2 (5 tests) |
| 7 | Idempotency (receipt_id UNIQUE + dedupe_key UNIQUE) | **PASS** | §5 Idempotency 2계층 |
| 8 | Business table write 0 | **PASS** | §8 Business Table Write 0 증빙 |
| 9 | Forbidden target 차단 | **PASS** | 4 forbidden target tests |
| 10 | Failure isolation (flush/add 실패 → None) | **PASS** | §6 Failure Isolation 검증표 |
| 11 | FROZEN 수정 0줄 | **PASS** | §7 FROZEN 무접촉 증빙 |
| 12 | RED 접촉 0건 | **PASS** | §7 RED 무접촉 증빙 |
| 13 | 전체 회귀 PASS | **PASS** | §9 5397/5397 PASS |

---

## 테스트 구조 요약 (43 tests, 11 classes)

| Class | Tests | 검증 영역 |
|-------|:-----:|-----------|
| TestShadowWriteReceiptModel | 5 | 스키마, import, unique |
| TestVerdictDecisionTable | 10 | 7단계 결정표 전수 |
| TestDedupeKey | 5 | 결정론적 해시, 길이 |
| TestEvaluateShadowWrite | 4 | 서비스 통합 (verdict별 receipt) |
| TestProofFields | 3 | dry_run/executed/business_write_count |
| TestForbiddenTargets | 4 | 금지 대상 차단 |
| TestAppendOnlyGuarantee | 4 | DML 제한 |
| TestFailureIsolation | 3 | 예외 미전파 |
| TestIdempotency | 1 | 중복 요청 → 기존 반환 |
| TestBusinessTableWriteZero | 4 | business table 무접촉 |

---

## 구현 수정 이력

| 시점 | 수정 | 사유 |
|------|------|------|
| 초기 구현 | evaluate_verdict Step 1=OUT_OF_SCOPE, Step 2=FORBIDDEN_TARGET | 설계 초안 순서 |
| 수정 1 | Step 1↔Step 2 swap: FORBIDDEN_TARGETS 우선 | 금지선 우선 차단 원칙 위반 (forbidden target이 OUT_OF_SCOPE로 잡힘) |
| 수정 2 | 테스트 fixture DataQuality.LOW → DataQuality.STALE | DataQuality enum에 LOW 없음 (HIGH/DEGRADED/STALE) |

두 수정 모두 적용 후 43/43 PASS 확인.

---

## 방화벽 선언 (재확인)

1. **RI-2B-1은 receipt INSERT만 수행하며, business table (symbols, strategies 등)에 대한 UPDATE/DELETE를 0건 보장한다.**
2. **RI-2B-1 승인은 RI-2B-2 (real bounded write) 승인을 포함하지 않는다. RI-2B-2는 별도 scope review → 설계/계약 → A 승인을 요구한다.**
3. **RI-2B-1의 INSERT 실패는 호출자에 전파되지 않으며, 기존 운영 경로에 부작용을 발생시키지 않는다.**

---

## 상태 보호 선언

> **RI-2B-1은 구현 완료 보고 제출 상태이며, A 승인 전까지는 candidate pass로만 취급하고 baseline 승격·seal 해석을 금지한다.**

| 항목 | 값 |
|------|-----|
| 현재 상태 | **SEALED** (A 승인: 2026-04-04) |
| 확정 baseline | **v2.3 (5397/5397 PASS)** |
| 이전 baseline | v2.2 (5354/5354 PASS) |
| Gate | LOCKED |
| 허용 작업 | 증빙 제시 / 질의 응답만 가능 |
| 추가 수정·구현·범위 확장 | **금지** |
| RI-2B-2 | DEFERRED |
| RI-2A-2b | DEFERRED |

---

## A 판정 요청

RI-2B-1 구현 완료 보고를 제출합니다.

- 완료 기준: **13/13 PASS**
- 회귀 테스트: **5397/5397 PASS** (baseline 5354 + 43 신규, candidate)
- FROZEN/RED 접촉: **0건**
- Business table write: **0건**

**A 판정: ACCEPT → SEALED** (2026-04-04)
- RI-2B-1 구현 봉인 확정
- Baseline v2.2 (5354) → **v2.3 (5397) 승격**
