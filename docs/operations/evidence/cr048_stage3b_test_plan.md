# CR-048 Stage 3B Test Plan

**문서 ID:** GOV-L3-STAGE3B-TESTPLAN-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Purity Guard Spec (GOV-L3-STAGE3B-PURITY-001)
**목적:** Stage 3B-1 테스트 계획 — 계약 강화 검증

> 이 문서는 테스트 계획만 포함한다. 테스트 코드 없음.

---

## 1. 테스트 범위 (Stage 3B-1만)

### 1-1. 범위 내 (IN SCOPE)

| # | 테스트 대상 | 유형 | 신규/확장 |
|:-:|------------|------|:---------:|
| 1 | Purity Guard 통합 검증 (6 파일) | 정적 분석 | 신규 |
| 2 | DataQualityDecision enum 계약 | 단위 | 신규 |
| 3 | ProviderCapability dataclass 계약 | 단위 | 신규 |
| 4 | SymbolMetadata dataclass 계약 | 단위 | 신규 |
| 5 | Stale 판정 pure 함수 | 단위 | 신규 |
| 6 | Partial 판정 pure 함수 | 단위 | 신규 |
| 7 | Failure Mode F1-F9 계약 | 계약 | 신규 |
| 8 | RotationReasonCode enum 계약 | 단위 | 신규 |
| 9 | SectorWeight.reason 하위호환 | 회귀 | 확장 |
| 10 | Symbol namespace 정규화 | 단위 | 신규 |
| 11 | listing_age 계산 pure 함수 | 단위 | 신규 |
| 12 | Capability 충족성 판정 | 단위 | 신규 |
| 13 | 기존 4927 tests 회귀 | 회귀 | 유지 |

### 1-2. 범위 외 (OUT OF SCOPE)

| # | 제외 대상 | 이유 |
|:-:|-----------|------|
| 1 | DataProvider 구현체 테스트 | Stage 3B-2 |
| 2 | 외부 API 호출 테스트 | Stage 3B-2 |
| 3 | DB write 테스트 | Stage 3B 범위 외 |
| 4 | Celery task 테스트 | Stage 3B 범위 외 |
| 5 | screen_and_update() 관련 | FROZEN |
| 6 | qualify_and_record() 관련 | FROZEN |
| 7 | asset_service.py 관련 | AMBER, 접촉 금지 |

---

## 2. 테스트 파일 구조

### 2-1. 신규 테스트 파일

| # | 파일 | 테스트 수 (예상) | 대상 |
|:-:|------|:----------------:|------|
| 1 | `tests/test_purity_guard.py` | ~70 | Pure Zone 6파일 오염 검증 |
| 2 | `tests/test_failure_modes.py` | ~25 | F1-F9 + DataQualityDecision + Stale/Partial 정책 |
| 3 | `tests/test_provider_capability.py` | ~20 | ProviderCapability + SymbolMetadata + namespace + listing_age |

### 2-2. 확장 테스트 파일

| # | 파일 | 추가 테스트 수 (예상) | 추가 내용 |
|:-:|------|:--------------------:|-----------|
| 4 | `tests/test_sector_rotator.py` | ~8 | RotationReasonCode + SectorWeight.reason 하위호환 |
| 5 | `tests/test_data_provider.py` | ~5 | ProviderCapability 추가분 purity 검증 |

### 2-3. 테스트 총괄

| 구분 | 파일 수 | 테스트 수 (예상) |
|------|:-------:|:----------------:|
| 신규 | 3 | ~115 |
| 확장 | 2 | ~13 |
| **Stage 3B-1 전용 합계** | **5** | **~128** |
| 기존 유지 | 184 | 4927 |
| **전체 회귀 목표** | **187** | **~5055** |

---

## 3. 테스트 상세 설계

### 3-1. test_purity_guard.py (~70 tests)

#### TestSectorRotatorPurity (~12 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_no_asyncio_import` | P1 |
| 2 | `test_no_sqlalchemy_import` | P2, P3 |
| 3 | `test_no_network_imports` | P4, P5, P6 |
| 4 | `test_no_celery_redis_imports` | P7, P8 |
| 5 | `test_no_os_env_imports` | P9, P10 |
| 6 | `test_no_system_imports` | P11, P12, P13, P14, P15 |
| 7 | `test_no_regime_detector_import` | P16 |
| 8 | `test_no_async_functions` | A1 |
| 9 | `test_no_await_keyword` | A2 |
| 10 | `test_no_file_operations` | S1, S2, S4 |
| 11 | `test_no_session_operations` | S5, S6 |
| 12 | `test_no_runtime_service_imports` | R1, R2, R3, R4 |

#### TestDataProviderPurity (~12 tests)

동일 구조, 단 A1 예외 (ABC async def 허용).
추가: `test_abc_methods_have_no_implementation` (AST body 검사).

#### TestSymbolScreenerPurity (~12 tests)

동일 구조. 추가: `test_all_functions_are_sync`.

#### TestBacktestQualifierPurity (~12 tests)

동일 구조. 추가: `test_all_functions_are_sync`.

#### TestAssetValidatorsPurity (~12 tests)

동일 구조.

#### TestConstitutionPurity (~10 tests)

동일 구조 (상수 모듈이므로 일부 항목 해당 없음).

### 3-2. test_failure_modes.py (~25 tests)

#### TestDataQualityDecision (~5 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_all_decision_values` | 9개 값 존재 확인 |
| 2 | `test_is_str_enum` | str 기반 enum |
| 3 | `test_reject_decisions` | PARTIAL_REJECT, STALE_REJECT, PROVIDER_UNAVAILABLE, SYMBOL_NAMESPACE_ERROR 4종 |
| 4 | `test_usable_decisions` | OK, PARTIAL_USABLE, STALE_USABLE 3종 |
| 5 | `test_special_decisions` | INSUFFICIENT_BARS, MISSING_LISTING_AGE 2종 |

#### TestStalePolicy (~8 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_crypto_price_fresh` | 30분 → OK |
| 2 | `test_crypto_price_stale_usable` | 50분 → STALE_USABLE |
| 3 | `test_crypto_price_stale_reject` | 2시간 → STALE_REJECT |
| 4 | `test_us_stock_fundamental_fresh` | 3일 → OK |
| 5 | `test_us_stock_fundamental_stale_reject` | 10일 → STALE_REJECT |
| 6 | `test_none_timestamp_stale_reject` | None → STALE_REJECT |
| 7 | `test_unknown_freshness_conservative` | unknown → 최단 한도 적용 |
| 8 | `test_stale_function_is_pure` | DB/네트워크 접근 없음 확인 |

#### TestPartialPolicy (~7 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_all_mandatory_present_ok` | 4필수 모두 존재 → OK |
| 2 | `test_volume_missing_reject` | volume None → PARTIAL_REJECT |
| 3 | `test_atr_missing_reject` | atr None → PARTIAL_REJECT |
| 4 | `test_adx_missing_reject` | adx None → PARTIAL_REJECT |
| 5 | `test_bars_missing_reject` | available_bars None → PARTIAL_REJECT |
| 6 | `test_optional_missing_usable` | 선택 필드 None → PARTIAL_USABLE |
| 7 | `test_all_present_ok` | 전부 존재 → OK |

#### TestFailureModePolicies (~5 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_f1_empty_provider_unavailable` | 전 필드 None → PROVIDER_UNAVAILABLE |
| 2 | `test_f7_namespace_error` | 잘못된 심볼 형식 → SYMBOL_NAMESPACE_ERROR |
| 3 | `test_f9_pessimistic_merge` | HIGH + STALE → STALE 채택 |
| 4 | `test_reject_blocks_screening_input` | REJECT decision → ScreeningInput 미생성 |
| 5 | `test_all_failure_modes_have_decision` | F1-F9 각각에 대응 Decision 존재 |

### 3-3. test_provider_capability.py (~20 tests)

#### TestProviderCapability (~8 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_frozen` | frozen=True 확인 |
| 2 | `test_default_values` | 모든 bool False, policy "reject" 기본값 |
| 3 | `test_all_fields_present` | 20 필드 존재 |
| 4 | `test_is_screening_capable_all_true` | 필수 4개 True → True |
| 5 | `test_is_screening_capable_missing_volume` | volume False → False |
| 6 | `test_is_screening_capable_missing_atr` | atr False → False |
| 7 | `test_is_screening_capable_missing_adx` | adx False → False |
| 8 | `test_is_screening_capable_missing_bars` | bars False → False |

#### TestSymbolMetadata (~5 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_frozen` | frozen=True 확인 |
| 2 | `test_default_none` | 선택 필드 None 기본값 |
| 3 | `test_compute_listing_age_known` | listing_date 존재 → 일수 계산 |
| 4 | `test_compute_listing_age_unknown` | listing_date None → None |
| 5 | `test_listing_age_is_pure` | 함수에 I/O 없음 확인 |

#### TestSymbolNamespace (~4 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_ccxt_format_passthrough` | "BTC/USDT" → "BTC/USDT" |
| 2 | `test_lowercase_normalization` | "btc/usdt" → "BTC/USDT" |
| 3 | `test_no_separator_error` | "BTCUSDT" → SYMBOL_NAMESPACE_ERROR |
| 4 | `test_krx_code_passthrough` | "005930" → "005930" |

#### TestCapabilityCrossModes (~3 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_missing_volume_maps_to_f2` | supports_volume=False → F2 |
| 2 | `test_missing_listing_age_maps_to_f6` | supports_listing_age=False → F6 |
| 3 | `test_all_mandatory_maps_to_ok` | 필수 4개 True → OK |

### 3-4. test_sector_rotator.py 확장 (~8 tests)

#### TestRotationReasonCode (~4 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_reason_code_enum_values` | 모든 reason code 존재 확인 |
| 2 | `test_reason_code_is_str_enum` | str 기반 enum |
| 3 | `test_get_sector_weight_returns_reason` | reason 포함 반환 (확장 시) |
| 4 | `test_reason_is_explanation_only` | reason이 판정 로직에 영향 없음 |

#### TestSectorWeightBackwardCompat (~4 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_sector_weight_without_reason` | SectorWeight(sector, weight, regime) 기존 호출 성공 |
| 2 | `test_sector_weight_with_reason` | SectorWeight(sector, weight, regime, reason=...) 신규 호출 성공 |
| 3 | `test_reason_default_is_none` | reason 미지정 시 None |
| 4 | `test_existing_tests_pass` | 기존 48 tests 무변경 PASS |

### 3-5. test_data_provider.py 확장 (~5 tests)

#### TestProviderCapabilityPurity (~5 tests)

| # | 테스트 | 검증 |
|:-:|--------|------|
| 1 | `test_capability_in_data_provider_module` | ProviderCapability import 가능 |
| 2 | `test_capability_is_frozen` | frozen=True |
| 3 | `test_capability_no_runtime_import` | ProviderCapability에 sqlalchemy 등 없음 |
| 4 | `test_symbol_metadata_in_module` | SymbolMetadata import 가능 |
| 5 | `test_data_provider_purity_maintained` | 기존 7 purity tests 무변경 PASS |

---

## 4. 회귀 보호 계획

### 4-1. 기존 테스트 보호

| 기존 테스트 파일 | 테스트 수 | Stage 3B-1 영향 | 조치 |
|----------------|:---------:|:---------------:|------|
| test_sector_rotator.py | 48 | ⚠️ SectorWeight 확장 | 하위호환 보장 (reason=None 기본값) |
| test_data_provider.py | 35 | ⚠️ 신규 타입 추가 | 기존 import 무변경, 신규 추가만 |
| test_asset_validators.py | 75 | ❌ 미접촉 | 무변경 |
| test_asset_model_stage2a.py | 28 | ❌ 미접촉 | 무변경 |
| test_asset_service_phase2b.py | 32 | ❌ 미접촉 | 무변경 |
| test_asset_registry.py | 28+ | ❌ 미접촉 | 무변경 |
| test_cr048_design_contracts.py | 57 | ❌ 미접촉 | 무변경 |
| test_cr048_phase2_3a_contracts.py | 30 | ❌ 미접촉 | 무변경 |
| test_cr048_model_skeletons.py | 44 | ❌ 미접촉 | 무변경 |
| test_cr048_observatory.py | 48 | ❌ 미접촉 | 무변경 |
| 기타 모든 테스트 (4502) | 4502 | ❌ 미접촉 | 무변경 |

### 4-2. 회귀 실패 시 행동

| 실패 유형 | 행동 |
|-----------|------|
| 기존 테스트 FAIL | **즉시 중단 + 원인 분석 + 롤백** |
| 신규 테스트 FAIL | 설계 재검토 후 수정 |
| Purity Guard FAIL | **즉시 중단 + 오염원 제거** |

### 4-3. 성공 기준

| # | 기준 | 값 |
|:-:|------|-----|
| 1 | 기존 테스트 전부 PASS | 4927/4927 |
| 2 | 신규 테스트 전부 PASS | ~128/~128 |
| 3 | 전체 회귀 PASS | ~5055/~5055 |
| 4 | FROZEN 함수 미접촉 | 0줄 변경 |
| 5 | RED 파일 미접촉 | 0건 |
| 6 | AMBER 파일 미접촉 | 0건 |
| 7 | Purity Guard 전체 PASS | ~70/~70 |

---

## 5. Stage 3B-1 산출물 예상

| # | 파일 | 유형 | GREEN |
|:-:|------|:----:|:-----:|
| 1 | `app/services/data_provider.py` | 확장 (ProviderCapability, SymbolMetadata, DataQualityDecision, stale/partial 함수) | ✅ |
| 2 | `app/services/sector_rotator.py` | 확장 (RotationReasonCode, SectorWeight.reason) | ✅ |
| 3 | `tests/test_purity_guard.py` | 신규 (~70 tests) | ✅ |
| 4 | `tests/test_failure_modes.py` | 신규 (~25 tests) | ✅ |
| 5 | `tests/test_provider_capability.py` | 신규 (~20 tests) | ✅ |
| 6 | `tests/test_sector_rotator.py` | 확장 (~8 tests 추가) | ✅ |
| 7 | `tests/test_data_provider.py` | 확장 (~5 tests 추가) | ✅ |

**전부 GREEN. RED/AMBER 접촉 0건.**

---

## 6. 봉인 조건 체크리스트 (예상)

| # | 조건 |
|:-:|------|
| 1 | Purity Guard 통합 테스트 PASS (~70) |
| 2 | Failure Mode 계약 테스트 PASS (~25) |
| 3 | ProviderCapability 계약 테스트 PASS (~20) |
| 4 | RotationReasonCode + 하위호환 테스트 PASS (~8) |
| 5 | data_provider.py 확장 purity 유지 PASS (~5) |
| 6 | RED 파일 미접촉 확인 |
| 7 | FROZEN 함수 미접촉 확인 |
| 8 | 기존 테스트 유지 (4927건) |
| 9 | 전체 회귀 PASS (~5055) |
| 10 | A 판정 |

---

```
CR-048 Stage 3B Test Plan v1.0
Document ID: GOV-L3-STAGE3B-TESTPLAN-001
Date: 2026-04-03
Authority: A
Status: SUBMITTED
Test Files: 5 (3 new + 2 extended)
New Tests: ~128
Regression Base: 4927
Regression Target: ~5055
FROZEN Contact: 0
RED Contact: 0
AMBER Contact: 0
Success Criteria: 7 items
```
