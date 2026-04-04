# CR-048 Stage 4A: Pipeline Composition Scope Spec

**문서 ID:** STAGE4A-SCOPE-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**전제:** Stage 3B SEALED, Gate LOCKED 유지
**기준선:** v1.7 / 5186/5186 PASS

---

## 1. 목적

Stage 3B에서 봉인한 `screening_transform` (validate→build)과 기존 sealed 엔진
(`SymbolScreener.screen()`, `BacktestQualifier.qualify()`)을 **단일 pure composition 함수**로 연결.

screening → transform → screen → qualify 흐름을 정적 파이프로 닫음.

---

## 2. 범위 정의

### 2.1 목표

| 항목 | 설명 |
|------|------|
| Pure composition 함수 1개 | `run_screening_qualification_pipeline()` |
| Combined result dataclass 1개 | `PipelineResult` (frozen) |
| Evidence/audit dataclass 1개 | `PipelineEvidence` (frozen) |
| Fail-closed 5-point chain | reject → screen_fail → qualify_fail 각 차단 |

### 2.2 Composition Layer의 위치

```
app/services/screening_qualification_pipeline.py   (L1 Pure)
```

Pure Zone 8번째 파일로 등록. purity guard 적용 대상.

### 2.3 Composition의 성격: "정적 파이프 연결"

| 허용 | 금지 |
|------|------|
| 입력 검증 (TransformResult 판정 확인) | provider별 특례 분기 |
| 타입 매핑 (TransformResult → ScreeningInput → QualificationInput) | runtime status 해석 |
| 단계별 fail-closed 차단 | side-effect (logging, DB, network) |
| 결과 조합 (screening + qualification → combined) | orchestration 로직 (retry, fallback, timeout) |
| 감사 정보 기록 (PipelineEvidence) | 조건부 threshold 변경 |

---

## 3. 3-Layer Architecture

| Layer | 파일 | 역할 |
|:-----:|------|------|
| L1 | `app/services/screening_qualification_pipeline.py` | Pure composition (production path) |
| L2 | `tests/fixtures/qualification_fixtures.py` | Qualification golden set |
| L2 | `tests/test_screening_qualification_pipeline.py` | Contract tests |
| BLOCKED | Runtime/service integration | Stage 4A에서 금지 |

---

## 4. 허용 접촉면

| 대상 파일 | 접촉 유형 | import 대상 |
|-----------|-----------|-------------|
| `screening_transform.py` | import only | `TransformResult`, `ScreeningInputSource`, `_REJECT_DECISIONS` |
| `symbol_screener.py` | import only | `ScreeningInput`, `ScreeningOutput`, `SymbolScreener`, `ScreeningThresholds` |
| `backtest_qualification.py` | import only | `QualificationInput`, `QualificationOutput`, `BacktestQualifier`, `QualificationThresholds` |
| `data_provider.py` | import only | `DataQualityDecision`, `BacktestReadiness` |
| `asset.py` | import only | `AssetClass`, `AssetSector` |

---

## 5. 금지 접촉면

| 대상 | 금지 사유 |
|------|-----------|
| `regime_detector` | RED — CR-046 |
| `asset_service.py` | RED — runtime path |
| `registry_service.py` | RED — runtime path |
| `injection_gateway.py` | RED — runtime (validate만 sealed) |
| `runtime_strategy_loader.py` | RED — runtime |
| `universe_manager.py` | Stage 4B 후보 — 본 단계 무접촉 |
| `multi_symbol_runner.py` | 무접촉 |
| `feature_cache.py` | 무접촉 |
| `strategy_router.py` | 무접촉 |
| beat_schedule / exchange_mode | L4 무접촉 |
| DB session / SQLAlchemy | 금지 |
| async / await | 금지 |
| os / network / file I/O | 금지 |

---

## 6. FROZEN 유지 대상

| 함수/타입 | 변경 허용 |
|-----------|:---------:|
| `ScreeningInput` | **0줄** |
| `SymbolScreener.screen()` | **0줄** |
| `BacktestQualifier.qualify()` | **0줄** |
| `validate_screening_preconditions` | **0줄** |
| `build_screening_input` | **0줄** |
| `transform_provider_to_screening` | **0줄** |
| `check_stale` / `check_partial` / `normalize_symbol` | **0줄** |
| `screen_and_update()` | **0줄** |
| `qualify_and_record()` | **0줄** |
| `_REJECT_DECISIONS` | **0줄** |
| `TransformResult` / `ScreeningInputSource` | **0줄** |

---

## 7. 안 B 요소 혼입 금지 선언

본 Stage 4A는 아래를 명시적으로 금지합니다:

- `universe_manager.py` 수정 또는 import
- universe selection 로직 추출
- DB query layer 분리
- un-sealed 파일 수정
- 안 B(Universe Extraction) 성격의 책임 재분배

---

## 8. 완료 기준 (10항목)

| # | 기준 |
|---|------|
| 1 | `screening_qualification_pipeline.py`는 pure import만 사용 |
| 2 | TransformResult→ScreeningInput→QualificationInput 매핑이 테스트로 봉인됨 |
| 3 | reject 상태는 qualification 미호출이 테스트로 증명됨 |
| 4 | screen_failed 상태는 qualification 미호출이 테스트로 증명됨 |
| 5 | golden set 4종이 전체 파이프라인 통과로 검증됨 |
| 6 | failure mode (F1-F9)가 combined result로 전파됨이 검증됨 |
| 7 | FROZEN 함수 0줄 변경 |
| 8 | RED 파일 접촉 0건 |
| 9 | 전체 회귀 PASS |
| 10 | purity guard 회귀 PASS (8 Pure Zone files) |

---

```
Stage 4A Scope Spec v1.0
Status: DESIGN/CONTRACT GO
Implementation: PENDING A approval
```
