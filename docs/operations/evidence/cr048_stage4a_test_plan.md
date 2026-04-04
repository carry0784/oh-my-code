# CR-048 Stage 4A: Test Plan

**문서 ID:** STAGE4A-TESTPLAN-001
**작성일:** 2026-04-03
**예상 테스트 합계:** ~65 tests (3 files)

---

## 1. 테스트 파일 구조

| 파일 | 목적 | 예상 테스트 수 |
|------|------|:-------------:|
| `tests/test_screening_qualification_pipeline.py` | Pipeline composition 계약 | ~45 |
| `tests/fixtures/qualification_fixtures.py` | Qualification golden set fixtures | (테스트 아님) |
| `tests/test_purity_guard.py` (확장) | 8th Pure Zone 등록 | ~12 |
| **합계** | | **~57** |

---

## 2. test_screening_qualification_pipeline.py (~45 tests)

### 2.1 TestPipelineVerdictEnum (~4 tests)

| Test | 검증 |
|------|------|
| `test_verdict_values` | 4개 verdict: QUALIFIED, DATA_REJECTED, SCREEN_FAILED, QUALIFY_FAILED |
| `test_verdict_is_string_enum` | str Enum 확인 |
| `test_verdict_exhaustive` | 4개뿐인지 확인 |
| `test_verdict_ordering` | reject → screen → qualify → qualified 순서 |

### 2.2 TestPipelineResult (~5 tests)

| Test | 검증 |
|------|------|
| `test_frozen` | frozen dataclass 확인 |
| `test_reject_invariant` | DATA_REJECTED → screening=None, qualification=None |
| `test_screen_failed_invariant` | SCREEN_FAILED → screening present, qualification=None |
| `test_qualify_failed_invariant` | 둘 다 present |
| `test_qualified_invariant` | 둘 다 present, 둘 다 all_passed=True |

### 2.3 TestPipelineEvidence (~4 tests)

| Test | 검증 |
|------|------|
| `test_frozen` | frozen dataclass 확인 |
| `test_defaults` | 기본값 확인 |
| `test_full_construction` | 전체 필드 생성 |
| `test_audit_only` | evidence 변경이 result에 영향 없음 |

### 2.4 TestMapToQualificationInput (~6 tests)

| Test | 검증 |
|------|------|
| `test_symbol_copied` | symbol 복사 |
| `test_asset_class_to_string` | AssetClass enum → string 변환 |
| `test_total_bars_from_backtest` | available_bars 매핑 |
| `test_none_bars_to_zero` | None → 0 |
| `test_missing_data_mapped` | missing_data_pct 매핑 |
| `test_sharpe_passthrough` | sharpe_ratio 직접 복사 |

### 2.5 TestRunPipelineNormal (~4 tests, golden set)

| Test | 검증 |
|------|------|
| `test_btc_full_pipeline_qualified` | BTC/USDT 정상 → QUALIFIED |
| `test_sol_full_pipeline` | SOL/USDT 정상 |
| `test_aapl_full_pipeline` | AAPL + fundamental |
| `test_kr_005930_full_pipeline` | 005930 KR_STOCK |

### 2.6 TestRunPipelineReject (~6 tests, FC-1/FC-2)

| Test | 검증 |
|------|------|
| `test_f1_empty_data_rejected` | F1 → DATA_REJECTED |
| `test_f2_partial_mandatory_rejected` | F2 → DATA_REJECTED |
| `test_f4_stale_data_rejected` | F4 → DATA_REJECTED |
| `test_f7_namespace_data_rejected` | F7 → DATA_REJECTED |
| `test_f8_timeout_data_rejected` | F8 → DATA_REJECTED |
| `test_none_input_data_rejected` | screening_input=None → DATA_REJECTED |

### 2.7 TestRunPipelineScreenFailed (~4 tests, FC-3)

| Test | 검증 |
|------|------|
| `test_low_volume_screen_failed` | volume threshold 미달 |
| `test_low_adx_screen_failed` | ADX < 15 |
| `test_f5_insufficient_bars_screen_failed` | bars < 500 |
| `test_screen_failed_has_screening_output` | ScreeningOutput present 확인 |

### 2.8 TestRunPipelineQualifyFailed (~4 tests, FC-4)

| Test | 검증 |
|------|------|
| `test_negative_sharpe_qualify_failed` | Sharpe < 0 |
| `test_high_drawdown_qualify_failed` | DD > 50% |
| `test_qualify_failed_has_both_outputs` | 둘 다 present |
| `test_qualify_failed_screening_passed` | screening.all_passed=True |

### 2.9 TestRunPipelineFailClosed (~5 tests, 차단 증명)

| Test | 검증 |
|------|------|
| `test_reject_never_calls_screen` | DATA_REJECTED 시 ScreeningOutput=None 확인 |
| `test_screen_fail_never_calls_qualify` | SCREEN_FAILED 시 QualificationOutput=None 확인 |
| `test_f3_partial_usable_continues` | PARTIAL_USABLE는 screen 계속 |
| `test_f9_degraded_continues` | degraded도 screen 계속 |
| `test_symbol_consistency` | result.symbol == evidence.symbol 항상 |

### 2.10 TestRunPipelineEvidence (~3 tests)

| Test | 검증 |
|------|------|
| `test_evidence_records_transform_decision` | evidence.transform_decision 기록 확인 |
| `test_evidence_records_screening_score` | score 기록 확인 (screen 도달 시) |
| `test_evidence_records_timestamp` | pipeline_timestamp 기록 |

### 2.11 TestPipelineCustomThresholds (~3 tests)

| Test | 검증 |
|------|------|
| `test_custom_screening_thresholds` | 커스텀 threshold 전달 |
| `test_custom_qualification_thresholds` | 커스텀 threshold 전달 |
| `test_default_thresholds_used` | None → default 사용 |

---

## 3. test_purity_guard.py 확장 (~12 tests)

### TestScreeningQualificationPipelinePurity

기존 purity guard 패턴과 동일한 12개 검증:

| Test | 패턴 |
|------|------|
| `test_no_forbidden_imports` | _FORBIDDEN_MODULES + _FORBIDDEN_SERVICE_IMPORTS |
| `test_no_async_functions` | async def 없음 |
| `test_no_await_keyword` | await 없음 |
| `test_no_side_effects` | open(), os.environ 등 없음 |
| `test_no_session_operations` | .add(), .flush(), .commit(), .execute() 없음 |
| `test_no_forbidden_decorators` | @app.task, @shared_task 없음 |
| `test_no_network_imports` | httpx, requests, aiohttp, socket, urllib 없음 |
| `test_no_sqlalchemy` | sqlalchemy 없음 |
| `test_no_celery` | celery 없음 |
| `test_all_functions_are_sync` | async function 없음 |
| `test_no_file_operations` | open() 없음 |
| `test_no_subprocess` | subprocess 없음 |

---

## 4. Qualification Fixtures 계획

### tests/fixtures/qualification_fixtures.py

| Fixture | 용도 | Source |
|---------|------|--------|
| `QUAL_FIXTURE_BTC_PASS` | BTC/USDT 정상 qualify | golden set 기반 |
| `QUAL_FIXTURE_SOL_PASS` | SOL/USDT 정상 qualify | golden set 기반 |
| `QUAL_FIXTURE_AAPL_PASS` | AAPL 정상 qualify | golden set 기반 |
| `QUAL_FIXTURE_KR_PASS` | 005930 정상 qualify | golden set 기반 |
| `QUAL_FIXTURE_NEGATIVE_SHARPE` | Sharpe < 0 실패 | 커스텀 |
| `QUAL_FIXTURE_HIGH_DD` | DD > 50% 실패 | 커스텀 |
| `QUAL_FIXTURE_LOW_BARS` | bars < 500 실패 | 커스텀 |

---

## 5. 회귀 보호 전략

| 항목 | 방법 |
|------|------|
| FROZEN 무변경 | git diff로 0줄 확인 |
| RED 무접촉 | purity guard forbidden import 확인 |
| 기존 테스트 무파괴 | 전체 회귀 PASS (예상 ~5250+) |
| 신규 pure zone | purity guard 8th file (12 tests) |
| Fixture 무변경 | 기존 screening_fixtures.py 수정 0줄 |

---

```
Test Plan v1.0
Expected: ~57 new tests
Purity guard: 8 Pure Zone files
Regression target: ~5250+ PASS
```
