# CR-048 Stage 2A L3 완료 증빙

**문서 ID:** EVIDENCE-STAGE2A-001
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048
**변경 등급:** L3 (Stage 2A Limited — static metadata / pure validators)
**판정:** **ACCEPTED**

---

## 1. 배치 개요

| 항목 | 값 |
|------|-----|
| 대상 | Phase 2 Asset 정적 계층 (model/schema/validators/constants) |
| Stage | Stage 2A (runtime 비연결) |
| 승인 범위 | GREEN 7개 파일만 |
| 모델/DB 변경 | 1건 (symbol_status_audits 테이블 추가 — DDL only) |
| 예외 발생 | 0건 |

---

## 2. 수정/생성 파일 목록

| 파일 | 작업 | 등급 | GREEN |
|------|------|:----:|:-----:|
| `app/services/asset_validators.py` | **신규** — 순수 검증 함수 7개 | L3 | **O** |
| `app/models/asset.py` | 확장 — SymbolStatusAudit 모델 추가 | L3 | **O** |
| `app/core/constitution.py` | 확장 — 상수 3종 추가 | L0 | **O** |
| `app/schemas/asset_schema.py` | 확장 — 응답 스키마 6종 추가 | L2 | **O** |
| `alembic/versions/020_stage2a_asset_metadata.py` | **신규** — DDL migration | L3 | **O** |
| `tests/test_asset_validators.py` | **신규** — 순수 함수 테스트 | L1 | **O** |
| `tests/test_asset_model_stage2a.py` | **신규** — model/enum/schema 테스트 | L1 | **O** |

**합계: GREEN 7/7. AMBER 0. RED 접촉 0.**

---

## 3. GREEN 범위만 변경 확인표

| 파일 | GREEN 등록 | 변경됨 | 준수 |
|------|:----------:|:------:|:----:|
| `app/services/asset_validators.py` | O | O (신규) | **O** |
| `app/models/asset.py` | O | O (확장) | **O** |
| `app/core/constitution.py` | O | O (확장) | **O** |
| `app/schemas/asset_schema.py` | O | O (확장) | **O** |
| `alembic/versions/020_stage2a_asset_metadata.py` | O | O (신규) | **O** |
| `tests/test_asset_validators.py` | O | O (신규) | **O** |
| `tests/test_asset_model_stage2a.py` | O | O (신규) | **O** |

---

## 4. RED 미침범 확인표

| RED 파일 | 변경 여부 |
|----------|:---------:|
| `app/services/asset_service.py` | **미변경** |
| `app/services/symbol_screener.py` | **미변경** |
| `app/services/backtest_qualification.py` | **미변경** |
| `app/services/runtime_strategy_loader.py` | **미변경** |
| `app/services/runtime_loader_service.py` | **미변경** |
| `app/services/feature_cache.py` | **미변경** |
| `app/services/paper_shadow_service.py` | **미변경** |
| `app/services/injection_gateway.py` | **미변경** |
| `app/services/registry_service.py` | **미변경** |
| `app/api/routes/registry.py` | **미변경** |
| `app/services/regime_detector.py` | **미변경** |
| `workers/tasks/*` | **미변경** |
| `exchanges/*` | **미변경** |

---

## 5. constitution.py 상수 정의만 변경 확인표

| 추가 항목 | 유형 | 런타임 스위치 | Side-effect | 기존 값 변경 |
|-----------|------|:------------:|:-----------:|:------------:|
| `BROKER_POLICY_RULES` | `dict[str, dict]` (frozenset 값) | **NO** | **NO** | **NO** |
| `TTL_DEFAULTS` | `dict[str, int]` | **NO** | **NO** | **NO** |
| `TTL_MIN_HOURS` | `int` (12) | **NO** | **NO** | **N/A (신규)** |
| `TTL_MAX_HOURS` | `int` (168) | **NO** | **NO** | **N/A (신규)** |
| `STATUS_TRANSITION_RULES` | `dict[tuple, str]` | **NO** | **NO** | **NO** |

기존 상수 (FORBIDDEN_BROKERS, ALLOWED_BROKERS, FORBIDDEN_SECTOR_VALUES, EXPOSURE_LIMITS) **미변경**.

---

## 6. Migration 범위 요약

| Migration | 작업 | DDL/DML |
|-----------|------|:-------:|
| `020_stage2a_asset_metadata.py` | CREATE TABLE `symbol_status_audits` (11 columns) | **DDL only** |

- 기존 테이블 수정: **0건**
- 기존 column 변경: **0건**
- 데이터 backfill: **0건**
- runtime hooking: **0건**
- Task dispatch: **0건**

---

## 7. asset_validators.py 순수 함수성 확인표

| 함수 | DB 접근 | Network 접근 | Cache 접근 | Exchange 접근 | Task 접근 | AsyncSession | Side-effect |
|------|:-------:|:----------:|:---------:|:------------:|:---------:|:------------:|:-----------:|
| `check_forbidden_brokers` | NO | NO | NO | NO | NO | NO | **NO** |
| `validate_broker_policy` | NO | NO | NO | NO | NO | NO | **NO** |
| `is_excluded_sector` | NO | NO | NO | NO | NO | NO | **NO** |
| `validate_status_transition` | NO | NO | NO | NO | NO | NO | **NO** |
| `compute_candidate_ttl` | NO | NO | NO | NO | NO | NO | **NO** |
| `validate_symbol_data` | NO | NO | NO | NO | NO | NO | **NO** |
| `validate_constitution_consistency` | NO | NO | NO | NO | NO | NO | **NO** |

**Import 안전성 검증:** 테스트 `TestImportSafety` 2건 — asset_validators.py 소스 코드에 `asset_service`, `symbol_screener`, `backtest_qualification` 문자열 없음 확인 PASS.

---

## 8. 전용 테스트 결과

| 테스트 파일 | 테스트 수 | 결과 |
|-------------|:---------:|:----:|
| `test_asset_validators.py` | 75 | **75/75 PASS** |
| `test_asset_model_stage2a.py` | 28 | **28/28 PASS** |
| **합계** | **103** | **103/103 PASS** |

### 테스트 분류

| 범주 | 테스트 수 |
|------|:---------:|
| Broker Policy (forbidden + allowed) | 20 |
| Sector Validation (excluded) | 9 |
| Status Transition Matrix (3x3) | 15 |
| TTL Computation | 9 |
| Symbol Data Validation | 8 |
| Constitution Consistency | 7 |
| SymbolStatusAudit Model | 5 |
| Constitution New Constants | 8 |
| Enum Cross-Consistency | 5 |
| Schema Response Models | 8 |
| Existing Schema Unchanged | 1 |
| Import Safety | 2 |
| **빠짐없이 검증** | 6 *(parametrized over all excluded sectors, asset classes, brokers)* |

---

## 9. 전체 회귀 결과

| 항목 | 이전 | 현재 |
|------|:----:|:----:|
| 총 테스트 | 4709 | **4812** |
| PASS | 4709 | **4812** |
| FAIL | 0 | **0** |
| 신규 추가 | — | +103 |

---

## 10. Runtime 도달 경로 확인표 (Static vs Runtime Boundary Proof)

| 변경 항목 | 정적 정의인가 | 런타임 호출 가능성 | 현재 도달 경로 | Fail-Closed |
|-----------|:------------:|:-----------------:|:-------------:|:-----------:|
| `BROKER_POLICY_RULES` 상수 | **YES** | 없음 (import only) | **NO** | N/A |
| `TTL_DEFAULTS` / `TTL_MIN/MAX` 상수 | **YES** | 없음 (import only) | **NO** | N/A |
| `STATUS_TRANSITION_RULES` 상수 | **YES** | 없음 (import only) | **NO** | N/A |
| `SymbolStatusAudit` 모델 | **YES** (DDL) | 없음 (write는 2B) | **NO** | N/A |
| `asset_validators.py` 순수 함수 | **YES** | 없음 (어디서도 호출 안 함) | **NO** | N/A |
| Schema 응답 모델 6종 | **YES** | 없음 (API 연결 안 함) | **NO** | N/A |
| Migration 020 | **YES** (DDL) | 없음 | **NO** | N/A |

**전 항목 Runtime 도달: NO**

---

## 11. 봉인 조건 충족 확인

| # | 조건 | 충족 |
|:--:|------|:----:|
| 1 | asset_validators.py 전 함수 테스트 PASS | **O** (75/75) |
| 2 | constitution 상수 일관성 테스트 PASS | **O** (7/7) |
| 3 | migration 020 작성 완료 (DDL only) | **O** |
| 4 | schema validator 테스트 PASS | **O** (8/8) |
| 5 | `asset_service.py` **미변경** 확인 | **O** |
| 6 | `symbol_screener` / `backtest_qualification` **미접촉** 확인 | **O** |
| 7 | 기존 계약 테스트 유지 (57+30건) | **O** |
| 8 | 전체 회귀 PASS (4812/4812) | **O** |
| 9 | **A 판정** | **ACCEPTED** |

---

```
CR-048 Stage 2A L3 Completion Evidence v1.0
Document ID: EVIDENCE-STAGE2A-001
Date: 2026-04-04
Authority: A
Decision: ACCEPTED
Regression: 4812/4812 PASS
Gate: LOCKED
Runtime Reach: ALL NO
asset_service.py: UNTOUCHED
symbol_screener: UNTOUCHED
backtest_qualification: UNTOUCHED
EX-003: NOT REQUIRED
```
