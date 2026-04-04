# CR-048 RI-1: Shadow Design/Contract Package

**문서 ID:** CR048-RI1-DESIGN-001
**작성일:** 2026-04-03
**전제 기준선:** v1.9 (5260/5260 PASS, Stage 4B SEALED)
**승인 범위:** RI-1 설계/계약만. 구현 아직 NO.

---

## 1. RI-1 Scope Spec

### 1.1 목적

봉인된 순수 파이프라인을 **독립 shadow 모드**로 실행하여,
기존 운영 경로에 영향 없이 **파이프라인 산출물을 관찰/기록**하는 단계.

### 1.2 핵심 제약

| 제약 | 보장 |
|------|------|
| DB write | **0** |
| 상태 전이 | **0** |
| 기존 경로 접촉 | **0** |
| FROZEN 함수 호출 | **0** (RI-1에서는 호출조차 금지) |
| Worker/Celery/Beat | **0** |
| API 엔드포인트 | **0** |
| 신규 모델/마이그레이션 | **0** |

### 1.3 신규 파일

| 파일 | 성격 | Pure Zone 후보 |
|------|------|:-------------:|
| `app/services/pipeline_shadow_runner.py` | **신규** — shadow 실행기 | **YES** (10th) |
| `tests/test_pipeline_shadow_runner.py` | **신규** — shadow 테스트 | — |
| `tests/test_purity_guard.py` | **수정** — 10th Pure Zone 등록 | — |

### 1.4 수정 불가 파일

기존 모든 파일. RI-1은 **신규 파일 생성 + purity guard 확장**만.

---

## 2. Shadow Runner Contract

### 2.1 책임

`pipeline_shadow_runner.py`는 정확히 **하나의 일**만 합니다:

> 주어진 provider 데이터로 전체 파이프라인을 실행하고,
> 결과를 `ShadowRunResult`로 반환한다.
> **DB, 네트워크, async, side-effect 없음.**

### 2.2 함수 서명

```python
@dataclass(frozen=True)
class ShadowRunResult:
    """Shadow pipeline execution result. Pure data, no side-effect."""
    symbol: str
    pipeline_output: PipelineOutput
    shadow_timestamp: datetime
    input_fingerprint: str          # hash of inputs for dedup/comparison
    comparison_verdict: str | None  # "match" | "mismatch" | None (비교 미수행)

@dataclass(frozen=True)
class ShadowComparisonInput:
    """Optional: existing screening/qualification results for comparison."""
    existing_screening_passed: bool | None = None
    existing_qualification_passed: bool | None = None
    existing_symbol_status: str | None = None


def run_shadow_pipeline(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    asset_class: AssetClass,
    sector: AssetSector,
    fundamental: FundamentalSnapshot | None = None,
    metadata: SymbolMetadata | None = None,
    strategy_id: str = "",
    timeframe: str = "1h",
    screening_thresholds: ScreeningThresholds | None = None,
    qualification_thresholds: QualificationThresholds | None = None,
    now_utc: datetime | None = None,
) -> ShadowRunResult:
    """Execute full pipeline in shadow mode. Pure function.

    1. transform_provider_to_screening(market, backtest, ...)
    2. run_screening_qualification_pipeline(transform_result, backtest, ...)
    3. Package result as ShadowRunResult
    No DB, no async, no side-effect.
    """


def compare_shadow_to_existing(
    shadow_result: ShadowRunResult,
    existing: ShadowComparisonInput,
) -> ShadowRunResult:
    """Compare shadow pipeline verdict against existing results.

    Returns new ShadowRunResult with comparison_verdict filled.
    Pure function. No mutation.
    """
```

### 2.3 호출 체인

```
run_shadow_pipeline(market, backtest, ...)
  │
  ├─ transform_provider_to_screening()     ← sealed pure (screening_transform.py)
  │    → TransformResult
  │
  ├─ run_screening_qualification_pipeline() ← sealed pure (screening_qualification_pipeline.py)
  │    → PipelineOutput
  │
  └─ ShadowRunResult(
        symbol=...,
        pipeline_output=pipeline_output,
        shadow_timestamp=now_utc,
        input_fingerprint=hash(market, backtest, ...),
        comparison_verdict=None
     )
```

### 2.4 의존성

| 의존 대상 | 방식 | 변경 |
|----------|------|:----:|
| `screening_transform.py` | import + call | 0줄 |
| `screening_qualification_pipeline.py` | import + call | 0줄 |
| `data_provider.py` | import (types) | 0줄 |
| `symbol_screener.py` | import (types) | 0줄 |
| `backtest_qualification.py` | import (types) | 0줄 |
| `asset.py` | import (AssetClass, AssetSector) | 0줄 |

**금지 의존:**
- `asset_service.py` (RED)
- `cycle_state_service.py` (async, DB)
- `multi_symbol_runner.py` (runtime)
- `workers/*` (Celery)
- 모든 DB/async/network 모듈

---

## 3. Read-Only Guarantee Spec

### 3.1 보장 방식

| 보장 | 검증 방식 |
|------|----------|
| No DB import | purity guard: sqlalchemy import 금지 |
| No async | purity guard: async def 0개, await 0개 |
| No network | purity guard: httpx/requests/aiohttp/socket 금지 |
| No file I/O | purity guard: open() 금지 |
| No side-effect | purity guard: os.environ, dotenv 금지 |
| No session ops | purity guard: .add(), .commit(), .execute() 금지 |
| No Celery | purity guard: celery, @app.task 금지 |
| No state mutation | frozen dataclass only (ShadowRunResult) |

### 3.2 Pure Zone 등록

`pipeline_shadow_runner.py`는 **10th Pure Zone file**로 등록.
기존 12-test 패턴 동일 적용.

### 3.3 write-path 0 증명

| 검증 항목 | 테스트 |
|----------|--------|
| DB session 미사용 | purity guard 12 tests |
| return type frozen | `test_shadow_run_result_frozen` |
| 입력 불변 | `test_inputs_not_mutated` |
| 기존 경로 미호출 | `test_no_asset_service_import` (AST check) |

---

## 4. Shadow Evidence Schema

### 4.1 ShadowRunResult (computation — verdict 결정)

| 필드 | 타입 | 설명 |
|------|------|------|
| `symbol` | str | 대상 종목 |
| `pipeline_output` | PipelineOutput | 전체 파이프라인 결과 (verdict + evidence) |
| `shadow_timestamp` | datetime | shadow 실행 시각 |
| `input_fingerprint` | str | 입력 데이터 해시 (재현성) |
| `comparison_verdict` | str \| None | "match" / "mismatch" / None |

### 4.2 ShadowComparisonInput (기존 결과 비교용 — 외부 제공)

| 필드 | 타입 | 설명 |
|------|------|------|
| `existing_screening_passed` | bool \| None | 기존 screen_and_update 결과 |
| `existing_qualification_passed` | bool \| None | 기존 qualify_and_record 결과 |
| `existing_symbol_status` | str \| None | 현재 Symbol 상태 |

### 4.3 2층 분리 원칙

| 층 | 객체 | 역할 |
|----|------|------|
| Computation | `PipelineResult` (inside PipelineOutput) | verdict 결정 |
| Audit | `PipelineEvidence` (inside PipelineOutput) + `ShadowRunResult` 메타 | 추적/비교 |

**Evidence는 verdict에 영향 없음.** 이 원칙은 Stage 4A에서 봉인된 것과 동일.

---

## 5. Comparison / Drift Rule

### 5.1 비교 대상

| Shadow Verdict | 기존 결과 | 비교 |
|---------------|----------|------|
| `QUALIFIED` | screening_passed=True, qualification_passed=True | **MATCH** |
| `SCREEN_FAILED` | screening_passed=False | **MATCH** |
| `QUALIFY_FAILED` | screening_passed=True, qualification_passed=False | **MATCH** |
| `DATA_REJECTED` | (비교 불가 — 기존에 해당 개념 없음) | **N/A** |
| 그 외 조합 | | **MISMATCH** |

### 5.2 정량 기준 (RI-2 진입 조건용)

| 지표 | 임계값 | 설명 |
|------|:------:|------|
| verdict 일치율 | ≥ 95% | shadow vs 기존 결과 일치 비율 |
| screening fail reason 일치율 | ≥ 90% | 같은 stage에서 fail하는 비율 |
| qualification fail reason 일치율 | ≥ 90% | 같은 check에서 fail하는 비율 |
| DATA_REJECTED 비율 | ≤ 20% | transform 단계에서 거부되는 비율 (비교 불가 영역) |

### 5.3 Drift 발생 시 행동

| Drift 유형 | 행동 | fail-closed |
|-----------|------|:-----------:|
| 단건 mismatch | shadow log에 기록, 운영 무영향 | YES |
| 일치율 < 95% (집계) | RI-2 진입 차단 | YES |
| Shadow 실행 오류 | 에러 로그, 운영 무영향 | YES |
| Shadow 입력 오류 | ValueError, 운영 무영향 | YES |

**모든 drift는 shadow 영역 내에서 처리. 기존 운영 경로에 영향 0.**

---

## 6. Test Plan

### 6.1 파일 구조

| 파일 | 목적 | 예상 테스트 수 |
|------|------|:------------:|
| `tests/test_pipeline_shadow_runner.py` | Shadow runner 계약/동작 | ~25 |
| `tests/test_purity_guard.py` (확장) | 10th Pure Zone 등록 | +12 |
| **합계** | | **~37** |

### 6.2 test_pipeline_shadow_runner.py (~25 tests)

#### TestShadowRunResult (~4 tests)

| Test | 검증 |
|------|------|
| `test_frozen` | frozen dataclass |
| `test_defaults` | comparison_verdict=None default |
| `test_full_construction` | 전 필드 생성 |
| `test_input_fingerprint_deterministic` | 같은 입력 → 같은 fingerprint |

#### TestRunShadowPipelineNormal (~4 tests, golden set)

| Test | 검증 |
|------|------|
| `test_btc_shadow_qualified` | BTC/USDT → QUALIFIED |
| `test_sol_shadow_qualified` | SOL/USDT → QUALIFIED |
| `test_aapl_shadow_qualified` | AAPL → QUALIFIED |
| `test_kr_005930_shadow_qualified` | 005930 → QUALIFIED |

#### TestRunShadowPipelineReject (~4 tests)

| Test | 검증 |
|------|------|
| `test_f1_empty_rejected` | DATA_REJECTED |
| `test_f7_namespace_rejected` | DATA_REJECTED |
| `test_negative_sharpe_qualify_failed` | QUALIFY_FAILED |
| `test_low_adx_screen_failed` | SCREEN_FAILED |

#### TestRunShadowPipelineFailClosed (~3 tests)

| Test | 검증 |
|------|------|
| `test_reject_no_screening` | DATA_REJECTED → screening=None |
| `test_screen_fail_no_qualification` | SCREEN_FAILED → qualification=None |
| `test_unknown_decision_valueerror` | ValueError raised |

#### TestShadowComparison (~5 tests)

| Test | 검증 |
|------|------|
| `test_qualified_match` | QUALIFIED + both passed → "match" |
| `test_screen_failed_match` | SCREEN_FAILED + screen not passed → "match" |
| `test_qualify_failed_match` | QUALIFY_FAILED + screen passed, qual not passed → "match" |
| `test_mismatch_detected` | QUALIFIED + qualification_passed=False → "mismatch" |
| `test_data_rejected_no_comparison` | DATA_REJECTED → comparison=None (비교 불가) |

#### TestShadowPurity (~3 tests)

| Test | 검증 |
|------|------|
| `test_no_asset_service_import` | AST check: asset_service import 없음 |
| `test_no_db_import` | AST check: sqlalchemy import 없음 |
| `test_inputs_not_mutated` | 입력 객체 불변 확인 |

#### TestShadowEvidence (~2 tests)

| Test | 검증 |
|------|------|
| `test_shadow_timestamp_recorded` | shadow_timestamp 기록 |
| `test_pipeline_evidence_passthrough` | PipelineEvidence 그대로 전달 |

### 6.3 Purity Guard 확장 (+12 tests)

`TestPipelineShadowRunnerPurity` — 기존 패턴 동일:
no_forbidden_imports, no_async, no_await, no_side_effects,
no_session, no_decorators, no_network, no_sqlalchemy,
no_celery, all_sync, no_file_ops, no_subprocess

### 6.4 회귀 보호

| 항목 | 방법 |
|------|------|
| FROZEN 무변경 | git diff 0줄 확인 |
| RED 무접촉 | purity guard + AST import check |
| 기존 테스트 무파괴 | 전체 회귀 PASS |
| 신규 pure zone | 10th file (12 tests) |
| 기존 fixture 무변경 | screening_fixtures.py, qualification_fixtures.py 수정 0줄 |

### 6.5 예상 기준선

| 항목 | 현재 (v1.9) | RI-1 이후 |
|------|:----------:|:--------:|
| 전체 테스트 | 5260 | **~5297** (+37) |
| Pure Zone 파일 | 9 | **10** |
| Purity guard 테스트 | 105 | **117** |

---

## 7. FROZEN/RED 무접촉 계획

### FROZEN 유지 (RI-1)

| 파일 | 상태 | RI-1 접촉 |
|------|:----:|:---------:|
| screening_transform.py | FROZEN | import만 |
| screening_qualification_pipeline.py | FROZEN | import + call |
| symbol_screener.py | FROZEN | import만 (types) |
| backtest_qualification.py | FROZEN | import만 (types) |
| data_provider.py | FROZEN | import만 (types) |
| asset_validators.py | FROZEN | 없음 |
| constitution.py | FROZEN | 없음 |
| sector_rotator.py | FROZEN | 없음 |
| universe_manager.py | FROZEN | 없음 |
| asset_service.py (screen_and_update) | FROZEN | **접촉 금지** |
| asset_service.py (qualify_and_record) | FROZEN | **접촉 금지** |

### RED 유지 (RI-1)

| 파일 | 이유 | RI-1 접촉 |
|------|------|:---------:|
| asset_service.py | DB write 포함 | **금지** |
| regime_detector.py | CR-046 | **금지** |
| runtime_strategy_loader.py | runtime | **금지** |
| feature_cache.py | Phase 5 | **금지** |
| strategy_router.py | Phase 5 | **금지** |
| multi_symbol_runner.py | Phase 6 | **금지** |
| workers/* | Celery | **금지** |
| exchanges/* | broker | **금지** |

---

## 8. RI-1 → RI-2 진입 조건

RI-1 완료 후 RI-2를 열기 위한 **필수 조건**:

| # | 조건 | 검증 방법 |
|---|------|----------|
| 1 | RI-1 SEALED | 완료 증빙 + 기준선 승격 |
| 2 | Shadow 비교 기준 정의 완료 | 이 문서 §5 참조 |
| 3 | Shadow 실행 안정성 증거 | golden set 전량 PASS + 비교 일치 |
| 4 | Verdict 일치율 ≥ 95% | shadow comparison tests |
| 5 | 신규 예외 0 | 예외 레지스터 확인 |
| 6 | FROZEN 함수 호출 범위 명확화 | RI-2 범위 심사 문서 |
| 7 | A 승인 | 공식 판정 |

---

## 9. 완료 기준 10항 (RI-1)

| # | 기준 |
|---|------|
| 1 | `pipeline_shadow_runner.py` pure 유지 (purity guard 12/12 PASS) |
| 2 | DB write 0 (sqlalchemy import 0, session ops 0) |
| 3 | 상태 전이 0 (asset_service import 0) |
| 4 | FROZEN 함수 호출 0 (screen_and_update, qualify_and_record 접촉 0) |
| 5 | golden set 4종 shadow QUALIFIED |
| 6 | reject/screen-fail/qualify-fail shadow 테스트 존재 |
| 7 | shadow comparison match/mismatch 테스트 존재 |
| 8 | FROZEN/RED 무접촉 (0줄 diff) |
| 9 | 전체 회귀 PASS |
| 10 | 신규 경고/예외 0 |

---

```
RI-1 Shadow Design/Contract v1.0
Scope: Read-only shadow pipeline execution
New files: 1 service + 1 test + purity guard extension
Expected: ~37 new tests
DB write: 0 | State mutation: 0 | FROZEN contact: 0
Pure Zone: 9 → 10
```
