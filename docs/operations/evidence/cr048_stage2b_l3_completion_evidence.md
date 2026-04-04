# CR-048 Stage 2B L3 완료 증빙

**문서 ID:** GOV-L3-STAGE2B-EVIDENCE-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Stage 2A SEALED (2026-04-04, 4812/4812 PASS)
**승인:** GOV-L3-STAGE2B-REVIEW-001 (조건부 승인)

> Stage 2B Limited L3 배치 완료 보고서. A 검토 및 판정 대기.

---

## 1. 파일 목록 (실 변경)

| 파일 | 작업 | 유형 | GREEN/AMBER |
|------|------|:----:|:-----------:|
| `app/services/asset_service.py` | 신규 메서드 추가 + register_symbol/transition_status guard 삽입 | **수정** | GREEN |
| `tests/test_asset_service_phase2b.py` | **신규** — 서비스 통합 테스트 32건 | 신규 | GREEN |
| `tests/test_asset_registry.py` | assertion regex 정렬 (3건) + 테스트명 변경 (1건) | **정렬** | AMBER (assertion 정렬만) |

---

## 2. GREEN 파일 확인

| 파일 | Review Package §2 GREEN 목록 | 일치 |
|------|:---------------------------:|:----:|
| `app/services/asset_service.py` | YES | ✅ |
| `tests/test_asset_service_phase2b.py` | YES | ✅ |

GREEN 목록 외 파일 접촉: `tests/test_asset_registry.py` (AMBER — assertion 정렬만, 조건 충족)

---

## 3. RED/AMBER 파일 확인

### RED (금지) 파일 — 전부 미접촉

| 파일 | 접촉 여부 |
|------|:---------:|
| `app/services/symbol_screener.py` | ❌ 미접촉 |
| `app/services/backtest_qualification.py` | ❌ 미접촉 |
| `app/services/runtime_strategy_loader.py` | ❌ 미접촉 |
| `app/services/runtime_loader_service.py` | ❌ 미접촉 |
| `app/services/feature_cache.py` | ❌ 미접촉 |
| `app/services/injection_gateway.py` | ❌ 미접촉 |
| `app/services/registry_service.py` | ❌ 미접촉 |
| `app/api/routes/registry.py` | ❌ 미접촉 |
| `app/services/regime_detector.py` | ❌ 미접촉 |
| `workers/tasks/*` | ❌ 미접촉 |
| `exchanges/*` | ❌ 미접촉 |

### AMBER 파일 — 조건 준수

| 파일 | 조건 | 준수 |
|------|------|:----:|
| `tests/test_asset_registry.py` | assertion 정렬만 | ✅ regex 패턴 3건 + 테스트명 1건만 변경 |
| `app/api/routes/asset.py` | 미접촉 | ✅ |
| `app/models/asset.py` | 미접촉 | ✅ |
| `app/core/constitution.py` | 미접촉 | ✅ |

---

## 4. asset_service.py 실 라인 변경 상세

### 파일 크기 변화

| 측정 | Stage 2A 후 | Stage 2B 후 | 변화 |
|------|:-----------:|:-----------:|:----:|
| 총 라인 | 372 | 498 | **+126** |

### 변경 영역

| 영역 | 라인 | 변경 내용 | 기존 함수 수정 |
|------|------|-----------|:-------------:|
| **imports** (L1-36) | +4 lines | `SymbolStatusAudit`, `validate_broker_policy`, `validate_status_transition` import 추가 | 추가만 |
| **register_symbol()** (L89-147) | +9 lines | `validate_broker_policy()` 호출 삽입, enum→value 변환, 위반 시 raise ValueError | **수정** (guard 추가) |
| **transition_status()** (L151-218) | +42 lines (기존 완전 재작성) | `validate_status_transition()` 통합, audit 기록, triggered_by/approval_level 파라미터 | **수정** (guard + audit) |
| **_record_status_audit()** (L222-252) | +31 lines | SymbolStatusAudit row INSERT, append-only | **추가** |
| **process_expired_ttl()** (L256-300) | +45 lines | max_count=10 cap, 수동 호출, fail-closed | **추가** |
| **screen_and_update()** (L347-409) | 0 lines | **FROZEN — 미수정** | ⛔ |
| **qualify_and_record()** (L413-482) | 0 lines | **FROZEN — 미수정** | ⛔ |

### FROZEN 함수 미수정 증명

```
screen_and_update  — validate_broker_policy: False, validate_status_transition: False, SymbolStatusAudit: False
qualify_and_record — validate_broker_policy: False, validate_status_transition: False, SymbolStatusAudit: False
```

### Import 변경 확인

| Import | 변경 유형 |
|--------|:---------:|
| `from app.services.asset_validators import validate_broker_policy, validate_status_transition` | **추가** |
| `from app.models.asset import ... SymbolStatusAudit ...` | **추가** (기존 import에 추가) |
| `from app.services.symbol_screener import ...` | **미변경** ⛔ |
| `from app.services.backtest_qualification import ...` | **미변경** ⛔ |

---

## 5. TTL 실행 결과

| 항목 | 기대 | 실제 |
|------|------|------|
| 호출 방식 | 수동만 | ✅ `process_expired_ttl()` 직접 호출만 |
| max_count 기본값 | 10 | ✅ `max_count=10` |
| max_count > 10 거부 | ValueError | ✅ `test_max_count_capped_at_10` PASS |
| Celery task 등록 | 없음 | ✅ `test_manual_only_no_celery` PASS |
| 실패 시 CORE 유지 | fail-closed | ✅ `test_fail_closed_on_transition_error` PASS |
| 부분 실패 시 계속 | 나머지 처리 | ✅ `test_partial_failure_continues` PASS |
| TTL 만료 후 강등 | CORE→WATCH | ✅ `test_demotes_expired_core_to_watch` PASS |

---

## 6. Symbol.status 영향표 (Read Path)

| Read Path | 파일 | 쿼리 | 2B 영향 |
|-----------|------|------|:-------:|
| `list_core_symbols()` | asset_service.py L80-85 | `WHERE status=CORE` | **직접** — pool 축소 가능 |
| runtime_loader CORE 필터 | runtime_loader_service.py | `WHERE status='core'` | **간접** — 미수정, 다음 cycle 반영 |
| screen_and_update 결과 | asset_service.py L347-409 | status 업데이트 | **미영향** — FROZEN |
| universe_manager | 미구현 | — | 미영향 |
| multi_symbol_runner | 미구현 | — | 미영향 |

**활성 read path 영향: 1개 (list_core_symbols)**

---

## 7. Fail-Closed 검증

| 시나리오 | 테스트 | 결과 |
|----------|--------|:----:|
| register_symbol: broker 검증 실패 → 등록 거부 | `test_broker_validation_blocks_before_db` | ✅ PASS |
| transition_status: 전이 규칙 위반 → 전이 거부 | `test_transition_denied_no_db_change` | ✅ PASS |
| transition_status: excluded→core → 항상 금지 | `test_excluded_to_core_forbidden` | ✅ PASS |
| transition_status: audit 실패 → 전이 자체 완료 | `test_audit_failure_does_not_block_transition` | ✅ PASS |
| process_expired_ttl: DB 오류 → CORE 유지 | `test_fail_closed_on_transition_error` | ✅ PASS |
| process_expired_ttl: max_count > 10 → ValueError | `test_max_count_capped_at_10` | ✅ PASS |

---

## 8. Rollback 확인

| # | 트리거 | 롤백 행동 | 확인 |
|:--:|--------|----------|:----:|
| 1 | 회귀 테스트 실패 | Stage 2B 코드 전체 revert | ✅ 회귀 PASS (미발동) |
| 2 | TTL 대량 강등 (CORE 50%↓) | process_expired_ttl disable | ✅ max 10 제한 구현 |
| 3 | Symbol.status 오류 전이 | SymbolStatusAudit 기반 복원 | ✅ audit 기록 검증 |
| 4 | register_symbol 오류 등록 | 해당 symbol soft-delete/재등록 | ✅ broker 차단 구현 |
| 5 | symbol_screener/backtest_qual import 변경 | 즉시 중단 + revert | ✅ import 미변경 확인 |
| 6 | A 중단 지시 | 즉시 중단 + revert | ✅ 준비됨 |

---

## 9. 테스트 결과

### Stage 2B 전용 테스트 (test_asset_service_phase2b.py)

| 테스트 클래스 | 테스트 수 | 결과 |
|--------------|:---------:|:----:|
| TestRegisterSymbolBrokerValidation | 7 | ✅ 7/7 PASS |
| TestTransitionStatusWithAudit | 9 | ✅ 9/9 PASS |
| TestProcessExpiredTTL | 7 | ✅ 7/7 PASS |
| TestRecordStatusAudit | 2 | ✅ 2/2 PASS |
| TestFrozenFunctions | 4 | ✅ 4/4 PASS |
| TestFailClosed | 3 | ✅ 3/3 PASS |
| **합계** | **32** | **32/32 PASS** |

### 기존 테스트 유지

| 테스트 파일 | 기존 수 | 현재 | 상태 |
|------------|:-------:|:----:|:----:|
| test_cr048_design_contracts.py | 57 | 57 | ✅ 유지 |
| test_cr048_phase2_3a_contracts.py | 30 | 30 | ✅ 유지 |
| test_asset_validators.py | 75 | 75 | ✅ 유지 |
| test_asset_model_stage2a.py | 28 | 28 | ✅ 유지 |
| test_asset_registry.py | 49 | 49 | ✅ 유지 (assertion 정렬 3건) |

---

## 10. 전체 회귀 결과

| 측정 | Stage 2A | Stage 2B | 변화 |
|------|:--------:|:--------:|:----:|
| 총 테스트 | 4812 | **4844** | +32 |
| Passed | 4812 | **4844** | +32 |
| Failed | 0 | **0** | 0 |
| 테스트 파일 | 181 | **182** | +1 |

```
4844 passed, 0 failed, 10 warnings in 173.28s
```

---

## Runtime Touch Budget

| 접촉 지점 | 파일 | 접촉 유형 | 위험 수준 | Fail-Closed |
|-----------|------|-----------|:---------:|:-----------:|
| register_symbol() broker guard | asset_service.py L99-108 | 신규 guard 삽입 | LOW | ✅ 등록 거부 |
| transition_status() validator | asset_service.py L178-188 | 기존 로직 → validator 교체 | HIGH | ✅ 전이 거부 |
| transition_status() audit | asset_service.py L199-216 | 신규 audit 기록 | LOW | ✅ audit 실패 시 전이 유지 |
| process_expired_ttl() | asset_service.py L256-300 | 신규 메서드 | HIGH | ✅ 중단, CORE 유지 |
| _record_status_audit() | asset_service.py L222-252 | 신규 메서드 (private) | LOW | N/A (append-only) |

**Runtime 접촉 총 5개 지점, 전부 fail-closed 구현 완료.**

---

## 봉인 조건 체크리스트

| # | 조건 | 결과 |
|:--:|------|:----:|
| 1 | Symbol-Broker 교차 검증 테스트 PASS | ✅ 7/7 |
| 2 | TTL 만료 CORE→WATCH 강등 테스트 PASS (max 10 포함) | ✅ 7/7 |
| 3 | EXCLUDED→CORE 직행 금지 테스트 PASS | ✅ PASS |
| 4 | EXCLUDED→WATCH manual_override 필수 테스트 PASS | ✅ PASS |
| 5 | SymbolStatusAudit 기록 테스트 PASS | ✅ 2/2 |
| 6 | Fail-closed 동작 테스트 PASS | ✅ 3/3 |
| 7 | screen_and_update **미수정** 확인 | ✅ Stage 2B 함수 미포함 |
| 8 | qualify_and_record **미수정** 확인 | ✅ Stage 2B 함수 미포함 |
| 9 | symbol_screener/backtest_qualification import **미변경** | ✅ |
| 10 | 기존 계약 테스트 유지 (57+30건) | ✅ 87/87 |
| 11 | Stage 2A 테스트 유지 (103건) | ✅ 103/103 |
| 12 | 전체 회귀 PASS (4812+32) | ✅ 4844/4844 |
| 13 | **A 판정** | ✅ **ACCEPTED** (2026-04-04) |

---

## test_asset_registry.py 정렬 상세

Stage 2B에서 `transition_status()`의 에러 메시지 형식이 변경됨에 따라 기존 테스트 3건의 regex 패턴을 정렬:

| 변경 | 기존 regex | 신규 regex | 사유 |
|------|-----------|-----------|------|
| test_excluded_sector_cannot_leave_excluded | `"excluded sector"` | `"exclusion baseline"` | 에러 메시지 형식 변경 |
| test_excluded_to_core_requires_manual_override | `"manual_override"` | `"forbidden"` | EXCLUDED→CORE는 항상 forbidden |
| test_excluded_to_core_with_manual_override | 전이 성공 기대 | `pytest.raises(ValueError, match="forbidden")` | EXCLUDED→CORE 직행 금지 규칙 적용 |

**test_excluded_to_core_with_manual_override** → **test_excluded_to_core_with_manual_override_still_forbidden** 으로 이름 변경. Stage 2A에서 확립한 STATUS_TRANSITION_RULES `("excluded", "core"): "forbidden"` 규칙에 맞춰 기대값 수정.

---

## 중단 조건 7개 상태

| # | 조건 | 상태 |
|:--:|------|:----:|
| 1 | screen_and_update/qualify_and_record 수정 시도 | ❌ 미발생 |
| 2 | symbol_screener/backtest_qualification import 변경 | ❌ 미발생 |
| 3 | Celery task/beat 등록 시도 | ❌ 미발생 |
| 4 | process_expired_ttl max_count > 10 실제 실행 | ❌ 미발생 (guard 구현) |
| 5 | RED 파일 접촉 | ❌ 미발생 |
| 6 | 기존 테스트 실패 (회귀) | ❌ 미발생 |
| 7 | A 중단 지시 | ❌ 미발생 |

---

**A 판정: ACCEPTED (2026-04-04)**

---

```
CR-048 Stage 2B L3 Completion Evidence v1.0
Document ID: GOV-L3-STAGE2B-EVIDENCE-001
Date: 2026-04-04
Authority: A
Status: SEALED (A ACCEPTED 2026-04-04)
Tests: 32/32 PASS (Stage 2B) + 4844/4844 PASS (전체 회귀)
FROZEN: screen_and_update ✅, qualify_and_record ✅
RED files: 0 contacted
Runtime Touch: 5 points, all fail-closed
```
