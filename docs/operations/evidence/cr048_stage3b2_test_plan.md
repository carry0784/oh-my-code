# CR-048 Stage 3B-2 Test Plan

**문서 ID:** DESIGN-STAGE3B2-006
**작성일:** 2026-04-03
**CR:** CR-048
**변경 등급:** L0 (설계 문서)

---

## 1. 테스트 범위 총괄

| 테스트 파일 | 대상 | 예상 테스트 수 |
|------------|------|:-------------:|
| `tests/test_screening_transform.py` | L1 Pure Transformation | ~55 |
| `tests/test_screening_stubs.py` | L2 Provider Stubs + Purity | ~35 |
| `tests/test_purity_guard.py` (확장) | screening_transform.py 추가 | ~10 |
| **합계** | | **~100** |

---

## 2. test_screening_transform.py (~55 tests)

### 2.1 TestValidateScreeningPreconditions (~15)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_valid_btc_ok` | BTC/USDT 정상 → OK |
| `test_valid_aapl_ok` | AAPL 정상 → OK |
| `test_valid_kr_stock_ok` | 005930 정상 → OK |
| `test_namespace_error_no_slash` | BTCUSDT → SYMBOL_NAMESPACE_ERROR |
| `test_namespace_error_empty` | "" → SYMBOL_NAMESPACE_ERROR |
| `test_namespace_error_kr_5digit` | 12345 → SYMBOL_NAMESPACE_ERROR |
| `test_stale_crypto_reject` | timestamp 3h old → STALE_REJECT |
| `test_stale_us_stock_reject` | timestamp 6h old → STALE_REJECT |
| `test_partial_reject_no_volume` | volume=None → PARTIAL_REJECT |
| `test_partial_reject_no_atr` | atr=None → PARTIAL_REJECT |
| `test_partial_reject_no_adx` | adx=None → PARTIAL_REJECT |
| `test_partial_reject_no_bars` | bars=None → PARTIAL_REJECT |
| `test_partial_usable_optional_missing` | mcap=None, spread=None → PARTIAL_USABLE |
| `test_fail_fast_namespace_before_stale` | bad symbol + stale → NAMESPACE (step 1 first) |
| `test_fail_fast_stale_before_partial` | stale + partial reject → STALE (step 2 first) |

### 2.2 TestBuildScreeningInput (~12)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_full_btc_mapping` | 모든 필드 매핑 정확성 |
| `test_full_aapl_with_fundamental` | fundamental 필드 (per, roe) 매핑 |
| `test_no_fundamental_none_fields` | fundamental=None → per/roe/tvl=None |
| `test_no_metadata_none_listing_age` | metadata=None → listing_age_days=None |
| `test_metadata_listing_age_copied` | metadata.listing_age_days → 정확 복사 |
| `test_asset_class_from_parameter` | asset_class 파라미터에서 복사 |
| `test_sector_from_parameter` | sector 파라미터에서 복사 |
| `test_symbol_from_market` | market.symbol에서 복사 |
| `test_optional_none_passthrough` | market_cap=None → screening_input.market_cap=None |
| `test_mandatory_present` | volume/atr/adx/bars 전부 존재 확인 |
| `test_defi_tvl_mapping` | DeFi sector → tvl_usd 매핑 |
| `test_kr_stock_no_fundamental` | KR_STOCK + fundamental=None → 정상 |

### 2.3 TestTransformProviderToScreening (~15)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_normal_btc_returns_ok` | 정상 → TransformResult(OK, input, source) |
| `test_normal_sol_returns_ok` | SOL 정상 → OK |
| `test_normal_aapl_returns_ok` | AAPL 정상 → OK |
| `test_normal_kr_returns_ok` | 005930 정상 → OK |
| `test_reject_returns_none_input` | REJECT → screening_input=None |
| `test_reject_returns_none_source` | REJECT → source=None |
| `test_namespace_error_returns_none` | bad symbol → None, None |
| `test_stale_reject_returns_none` | stale → None, None |
| `test_partial_usable_returns_input` | optional missing → input 존재 |
| `test_source_records_provider_names` | market_provider 등 기록 확인 |
| `test_source_records_timestamp` | build_timestamp 존재 |
| `test_source_records_stale_decision` | stale_decision 기록 |
| `test_f6_missing_listing_age_ok` | metadata=None → OK (F6 예외) |
| `test_f5_insufficient_bars_passes_validate` | bars=100 → OK (stage 5가 판단) |
| `test_reject_decisions_constant` | _REJECT_DECISIONS 4개 검증 |

### 2.4 TestScreeningInputSource (~5)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_frozen` | attribute 변경 시 AttributeError |
| `test_default_values` | unknown defaults |
| `test_full_construction` | 모든 필드 |
| `test_audit_only_no_screener_impact` | source 존재가 screener 결과에 영향 없음 |
| `test_paired_with_screening_input` | TransformResult에서 input과 source 쌍 확인 |

### 2.5 TestTransformResult (~5)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_frozen` | attribute 변경 시 AttributeError |
| `test_reject_invariant` | REJECT → input=None, source=None |
| `test_ok_invariant` | OK → input is not None, source is not None |
| `test_partial_usable_has_input` | PARTIAL_USABLE → input 존재 |
| `test_decision_preserved` | decision 값 정확 |

### 2.6 TestFailureModeIntegration (~3)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_f1_empty_to_reject` | F1 (빈 snapshot) → PARTIAL_REJECT |
| `test_f7_namespace_to_reject` | F7 (BTCUSDT) → NAMESPACE_ERROR |
| `test_f4_stale_to_reject` | F4 (3시간 전) → STALE_REJECT |

---

## 3. test_screening_stubs.py (~35 tests)

### 3.1 TestStubMarketDataProvider (~8)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_known_symbol_returns_fixture` | BTC/USDT → fixture data |
| `test_unknown_symbol_returns_empty` | UNKNOWN → 빈 snapshot |
| `test_empty_snapshot_quality_unavailable` | 빈 snapshot.quality == UNAVAILABLE |
| `test_batch_returns_list` | batch → list of snapshots |
| `test_batch_unknown_returns_empty` | unknown in batch → 빈 snapshot |
| `test_health_check_available` | health → is_available=True |
| `test_no_mutation` | fixture 변경 시 stub 영향 없음 (frozen) |
| `test_empty_fixture_map` | 빈 map → 모든 symbol 빈 snapshot |

### 3.2 TestStubBacktestDataProvider (~5)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_known_symbol` | fixture 반환 |
| `test_unknown_symbol_empty` | 빈 BacktestReadiness |
| `test_health_check` | available |
| `test_timeframe_parameter_accepted` | timeframe 파라미터 수용 |
| `test_min_bars_parameter_accepted` | min_bars 파라미터 수용 |

### 3.3 TestStubFundamentalDataProvider (~4)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_known_symbol` | fixture 반환 |
| `test_unknown_symbol_empty` | 빈 FundamentalSnapshot |
| `test_health_check` | available |
| `test_stock_fundamental_fields` | per, roe 존재 |

### 3.4 TestStubScreeningDataProvider (~4)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_provider_statuses_list` | 3개 status 반환 |
| `test_all_stubs_available` | is_available=True |
| `test_composition` | market+backtest+fundamental 조합 |
| `test_stub_name_in_status` | provider_name 확인 |

### 3.5 TestStubPurity (~8)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_no_httpx_import` | httpx 없음 |
| `test_no_requests_import` | requests 없음 |
| `test_no_aiohttp_import` | aiohttp 없음 |
| `test_no_sqlalchemy_import` | sqlalchemy 없음 |
| `test_no_async_functions` | AsyncFunctionDef 없음 |
| `test_no_os_environ` | os.environ 없음 |
| `test_no_open_call` | open() 없음 |
| `test_no_ccxt_import` | ccxt 없음 |

### 3.6 TestCapabilityProfiles (~6)

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_full_crypto_capable` | is_screening_capable → True |
| `test_full_us_stock_capable` | → True |
| `test_full_kr_stock_capable` | → True |
| `test_minimal_crypto_capable` | → True (4 mandatory OK) |
| `test_degraded_crypto_not_capable` | → False (adx missing) |
| `test_empty_not_capable` | → False |

---

## 4. test_purity_guard.py 확장 (~10 tests)

기존 6개 Pure Zone 파일에 `screening_transform.py`를 추가:

| 테스트 | 검증 내용 |
|--------|-----------|
| `test_screening_transform_no_forbidden_imports` | P1-P16 |
| `test_screening_transform_no_async` | A1-A3 |
| `test_screening_transform_no_side_effects` | S1-S9 |
| `test_screening_transform_no_runtime_deps` | R1-R4 |
| + 기존 32 패턴 × 7 파일 (6→7) | |

---

## 5. 회귀 보호

| 항목 | 검증 |
|------|------|
| Stage 3A 기존 테스트 | 변경 없음, PASS 유지 |
| Stage 3B-1 기존 테스트 | 변경 없음, PASS 유지 |
| Stage 2B 기존 테스트 | 변경 없음 (10 warnings 유지) |
| 전체 회귀 | 5075 + ~100 = ~5175 예상 |

---

## 6. 봉인 조건

| 조건 | 기준 |
|------|------|
| test_screening_transform.py | ALL PASS |
| test_screening_stubs.py | ALL PASS |
| test_purity_guard.py (확장) | ALL PASS |
| F1-F9 failure mode 커버리지 | 9/9 |
| Golden set (4 시장) 커버리지 | 4/4 |
| Capability profile 커버리지 | ≥ 3 profiles |
| L1→L2 의존 없음 | import graph 검증 |
| 전체 회귀 | ALL PASS |
| A 판정 | ACCEPT |

---

```
CR-048 Stage 3B-2 Test Plan v1.0
Document ID: DESIGN-STAGE3B2-006
Date: 2026-04-03
Status: SUBMITTED
```
