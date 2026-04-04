# CR-048 RI-1 완료 증빙

**문서 ID:** RI1-COMPLETION-001
**작성일:** 2026-04-03
**전제 기준선:** v1.9 (5260/5260 PASS, Stage 4B SEALED)
**새 기준선:** v2.0 (5299/5299 PASS, RI-1 SEALED)
**Authority:** A

---

## 1. 배치 요약

| 항목 | 값 |
|------|-----|
| 배치명 | RI-1: Pipeline Shadow Runner (Read-Only Shadow) |
| 성격 | 런타임 통합 첫 단계 — read-only shadow 관찰 계층 |
| 운영 코드 수정 | **0줄** (FROZEN/RED 무접촉) |
| 신규 서비스 파일 | **1** (pipeline_shadow_runner.py) |
| 신규 테스트 파일 | **1** (test_pipeline_shadow_runner.py) |
| 테스트 확장 | **1** (test_purity_guard.py — 10th Pure Zone) |
| 신규 테스트 수 | **+39** (27 shadow + 12 purity) |
| 전체 회귀 | **5299/5299 PASS** |
| 신규 경고 | **0** |
| 신규 예외 | **0** |

---

## 2. 완료 기준 10항 체크

| # | 기준 | 결과 | 근거 |
|---|------|:----:|------|
| 1 | pipeline_shadow_runner.py pure (forbidden import/async/write 0) | **PASS** | 12/12 purity guard tests |
| 2 | run_shadow_pipeline pure (DB/state 0) | **PASS** | No DB, no state mutation, frozen dataclass only |
| 3 | compare_shadow_to_existing pure (fetch/import side-effect 0) | **PASS** | Pure comparison only, no external fetch |
| 4 | ShadowRunResult/Evidence separation | **PASS** | 3 dedicated evidence tests (TestShadowEvidence) |
| 5 | 기존 경로 무접촉 (FROZEN call 0, modify 0) | **PASS** | 0줄 수정, sealed assets untouched |
| 6 | asset_service 독립 (import 0) | **PASS** | No asset_service import in pipeline_shadow_runner.py |
| 7 | Purity guard PASS (10th Pure Zone) | **PASS** | 12/12 TestPipelineShadowRunnerPurity |
| 8 | 신규 테스트 PASS | **PASS** | 27/27 + 12/12 = 39/39 |
| 9 | 전체 회귀 PASS | **PASS** | 5299/5299 |
| 10 | 경고/예외 0건 | **PASS** | 기존 OBS-001만, 신규 0 |

---

## 3. 수정 파일 목록

| 파일 | 변경 | 유형 |
|------|------|:----:|
| `app/services/pipeline_shadow_runner.py` | 230줄 신규 | 신규 |
| `tests/test_pipeline_shadow_runner.py` | 27 tests, 7 classes | 신규 |
| `tests/test_purity_guard.py` | +12 tests (10th Pure Zone 등록) | 확장 |

### 접촉하지 않은 파일 (무접촉 확인)

| 대상 | 접촉 |
|------|:----:|
| FROZEN 9 Pure Zone files | **0줄** |
| RED files (regime_detector, asset_service, runtime_strategy_loader 등) | **0줄** |
| workers/* | **0줄** |
| exchanges/* | **0줄** |
| alembic/* | **0줄** |

---

## 4. 신규 서비스: pipeline_shadow_runner.py

### 구조

| 요소 | 설명 |
|------|------|
| `ComparisonVerdict` | enum: MATCH, VERDICT_MISMATCH, REASON_MISMATCH, INSUFFICIENT_EXISTING_DATA |
| `ShadowComparisonInput` | frozen dataclass: 기존 결과를 caller가 제공 (shadow runner는 fetch 안 함) |
| `ShadowRunResult` | frozen dataclass: symbol, pipeline_output, shadow_timestamp, input_fingerprint, comparison_verdict |
| `_compute_input_fingerprint()` | SHA-256 기반 입력 해시 (16자 hex) |
| `run_shadow_pipeline()` | transform → screen → qualify 순수 실행, DB/async/side-effect 0 |
| `compare_shadow_to_existing()` | 순수 비교만, fetch/import 0 |

### Import 관계

```
pipeline_shadow_runner.py
  ← app.models.asset (AssetClass, AssetSector)
  ← app.services.data_provider (snapshots, BacktestReadiness)
  ← app.services.backtest_qualification (QualificationThresholds)
  ← app.services.screening_qualification_pipeline (PipelineOutput, run_screening_qualification_pipeline)
  ← app.services.screening_transform (transform_provider_to_screening)
  ← app.services.symbol_screener (ScreeningThresholds)
```

**전부 sealed Pure Zone 자산만 참조. runtime/RED 자산 import 0.**

### 금지선 (RI-1 봉인 후 영구 적용)

| 금지 항목 | 사유 |
|-----------|------|
| DB write (session.add, commit, flush, execute) | Read-only shadow 전용 |
| State transition (status 변경, promotion 전이) | Shadow = 관찰만 |
| 기존 runtime path 삽입 | RI-2 범위, RI-1에서 금지 |
| compare_shadow_to_existing에서 fetch | 비교만 허용, 데이터 조회 금지 |
| async def / await | Pure Zone 규칙 |
| asset_service import | Runtime 경계 침범 |
| worker/celery task 등록 | Infrastructure 계층 침범 |
| Redis/network 접근 | Side-effect 금지 |

---

## 5. 테스트 구조

### test_pipeline_shadow_runner.py (27 tests, 7 classes)

| Class | Tests | 검증 대상 |
|-------|:-----:|-----------|
| TestShadowRunResult | 3 | frozen dataclass 구조, 필드, default |
| TestRunShadowPipelineNormal | 6 | golden path QUALIFIED, fingerprint, evidence |
| TestRunShadowPipelineReject | 2 | DATA_REJECTED (unavailable, stale) |
| TestRunShadowPipelineFailClosed | 3 | fail-closed (low volume, low bars, edge data) |
| TestShadowComparison | 7 | MATCH, VERDICT_MISMATCH, INSUFFICIENT, preservation, frozen |
| TestShadowPurity | 3 | no state mutation, timestamp determinism, UTC |
| TestShadowEvidence | 3 | evidence independence, fingerprint independence, hex format |

### test_purity_guard.py 확장 (12 tests)

| Class | Tests | 검증 대상 |
|-------|:-----:|-----------|
| TestPipelineShadowRunnerPurity | 12 | 10th Pure Zone: forbidden imports, async, side-effects, decorators |

---

## 6. ComparisonVerdict 분류표

| Verdict | 의미 | 조건 |
|---------|------|------|
| `MATCH` | Shadow와 기존 결과 일치 | screening + qualification 판정 모두 동일 |
| `VERDICT_MISMATCH` | Shadow와 기존 결과 불일치 | screening 또는 qualification 판정이 다름 |
| `REASON_MISMATCH` | 판정은 같으나 사유가 다름 | (RI-2에서 활용 예정) |
| `INSUFFICIENT_EXISTING_DATA` | 비교 불가 | 기존 결과에 screening_passed가 없거나 DATA_REJECTED |

### RI-2 진입 시 활용 기준 (참고, RI-1 완료 기준 아님)

| 기준 | 임계 |
|------|------|
| verdict 일치율 | ≥95% |
| fail reason 일치율 | ≥90% |
| drift 허용 임계 | 별도 정의 필요 |
| carried exception 허용 | 별도 정의 필요 |

---

## 7. Pure Zone Registry 카드

### 10th Pure Zone: pipeline_shadow_runner.py

| 필드 | 값 |
|------|-----|
| 파일명 | `app/services/pipeline_shadow_runner.py` |
| Pure 근거 | No DB, no async, no network, no side-effect, frozen dataclass only |
| 금지 import | asyncio, sqlalchemy, httpx, requests, aiohttp, celery, redis, os, dotenv, socket, urllib, subprocess, shutil, tempfile |
| 금지 service import | regime_detector, asset_service, registry_service, injection_gateway, runtime_strategy_loader |
| 금지 side-effect | open(), os.environ, os.getenv, beat_schedule, session ops |
| 봉인 기준선 | v2.0 |
| 관련 테스트 수 | 39 (27 functional + 12 purity) |
| 재개방 조건 | A 승인 필수, 별도 CR 또는 RI-2 범위 심사 통과 |

---

## 8. 경고 분류표

| 분류 | 건수 | 출처 | RI-1 관련 |
|------|:----:|------|:---------:|
| AsyncMockMixin RuntimeWarning | 10 | test_asset_service_phase2b.py (Stage 2B 기원) | **PRE-EXISTING only** |
| RI-1 신규 경고 | **0** | — | — |

---

## 9. 기준선 갱신

| 항목 | v1.9 (이전) | v2.0 (신규) |
|------|:-----------:|:-----------:|
| 전체 테스트 | 5260 | **5299** |
| Pure Zone files | 9 | **10** |
| Purity guard tests | 105 | **117** |
| 신규 경고 | 0 | **0** |
| FROZEN/RED 접촉 | 0 | **0** |

---

## 10. RI-1 vs RI-2 경계 명시

| 항목 | RI-1 (본 배치) | RI-2 (DEFERRED) |
|------|:--------------:|:---------------:|
| DB write | **금지** | 제한적 허용 (bounded) |
| State transition | **금지** | 제한적 허용 |
| FROZEN function call | **금지** | FROZEN call-only 허용 |
| Runtime path 삽입 | **금지** | 제한적 허용 |
| Shadow comparison | **Pure only** | + fetch 가능 |
| 범위 | Read-only shadow | Bounded write-path |
| 재심사 | 완료 | **필요** |

---

```
RI-1 Completion Evidence v1.0
Baseline: v1.9 → v2.0
Tests: 5260 → 5299 (+39)
Pure Zone: 9 → 10 files
Purity Guard: 105 → 117 tests
Risk: ZERO (read-only shadow, production code 0 lines changed)
Rollback: TRIVIAL (2 test files + 1 service file 삭제)
RI-2: DEFERRED / 재심사 필요
```
