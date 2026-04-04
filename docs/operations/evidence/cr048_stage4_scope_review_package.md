# CR-048 차기 확장 범위 심사 패키지

**문서 ID:** GOV-STAGE4-SCOPE-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**전제:** Stage 3B COMPLETED/SEALED, Gate LOCKED 유지
**기준선:** v1.7 / 5186/5186 PASS

> 본 문서는 심사 패키지입니다. A 승인 전까지 어떤 구현도 실행되지 않습니다.

---

## 1. 현재 기준선 요약

| 항목 | 값 |
|------|-----|
| Gate | LOCKED |
| 봉인 범위 | Stage 1 ~ Stage 3B (전체 SEALED) |
| 회귀 기준선 | 5186/5186 PASS |
| 경고 | 10 (PRE-EXISTING, OBS-001) |
| 예외 | 0 신규 (EX-001, EX-002 종결) |
| Pure Zone | 7 files (81 purity guard tests) |
| 신규 테스트 누적 | 742 |

---

## 2. Stage 3B 봉인 자산 재사용표

| 자산 | 위치 | 재사용 가능 여부 | 조건 |
|------|------|:---------------:|------|
| `ScreeningInput` | symbol_screener.py | **YES** (import only) | FROZEN — 구조 변경 금지 |
| `SymbolScreener.screen()` | symbol_screener.py | **YES** (call only) | FROZEN — 5-stage pipeline 무변경 |
| `BacktestQualifier.qualify()` | backtest_qualification.py | **YES** (call only) | FROZEN — 7-check pipeline 무변경 |
| `SectorRotator` | sector_rotator.py | **YES** (call only) | FROZEN — regime→sector weight 무변경 |
| `DataQualityDecision` | data_provider.py | **YES** (import only) | FROZEN — 9 enum values 무변경 |
| `ProviderCapability` | data_provider.py | **YES** (import only) | FROZEN — 20-field dataclass 무변경 |
| `check_stale/check_partial/normalize_symbol` | data_provider.py | **YES** (call only) | FROZEN — pure function 무변경 |
| `TransformResult` | screening_transform.py | **YES** (import only) | FROZEN — decision + input + source 구조 |
| `validate_screening_preconditions` | screening_transform.py | **YES** (call only) | FROZEN — fail-fast 3단계 순서 |
| `build_screening_input` | screening_transform.py | **YES** (call only) | FROZEN — field mapping |
| Provider Stubs | tests/stubs/ | **YES** (test only) | 테스트 계층 전용 — app/ import 금지 |
| Golden Set Fixtures | tests/fixtures/ | **YES** (test only) | 테스트 계층 전용 |

---

## 3. 2안 비교

### 안 A: Screening-Qualification Pipeline Composition (Pure / Safe)

#### 목적

Stage 3B-2에서 봉인한 `TransformResult`와 기존 `BacktestQualifier.qualify()`를 **순수 함수로 연결**하는 파이프라인.
screening → transform → qualify 흐름을 단일 pure orchestrator로 닫음.

#### 목표 기능

- `TransformResult` → `QualificationInput` 매핑 (deterministic field-copy)
- `ScreeningInput` → `SymbolScreener.screen()` → `ScreeningOutput` 연결
- `ScreeningOutput` + `QualificationInput` → `BacktestQualifier.qualify()` → `QualificationOutput` 연결
- Combined `ScreeningQualificationResult` 반환 (screening + qualification verdict 통합)
- reject/fail-closed: TransformResult가 REJECT이면 qualification 미진입

#### 왜 지금 열어야 하는가

- Phase 4 (Paper Shadow)의 선행 조건: **combined verdict** 없이는 Paper Shadow가 무엇을 비교할지 모름
- `screening_transform`과 `backtest_qualification`은 모두 sealed, stateless → 조합 비용 최소
- 지금 연결하지 않으면 Phase 5에서 runtime과 동시에 연결해야 해서 blast radius 증가

#### 파일

| 파일 | 작업 | 계층 |
|------|------|:----:|
| `app/services/screening_qualification_pipeline.py` | **신규** | L1 Pure |
| `tests/fixtures/qualification_fixtures.py` | **신규** | Test |
| `tests/test_screening_qualification_pipeline.py` | **신규** | Test |
| `tests/test_purity_guard.py` | **수정** (+1 Pure Zone) | Test |

#### 허용 접촉면

| 대상 | 접촉 유형 |
|------|-----------|
| screening_transform.py | import only (TransformResult, ScreeningInputSource) |
| symbol_screener.py | import only (ScreeningInput, ScreeningOutput, SymbolScreener) |
| backtest_qualification.py | import only (QualificationInput, QualificationOutput, BacktestQualifier) |
| data_provider.py | import only (DataQualityDecision) |
| asset.py | import only (AssetClass, AssetSector) |

#### 금지 접촉면

| 대상 | 금지 사유 |
|------|-----------|
| regime_detector | RED — CR-046 |
| asset_service.py | RED — runtime path |
| registry_service.py | RED — runtime path |
| injection_gateway.py | RED — runtime path (validate만 sealed) |
| runtime_strategy_loader.py | RED — runtime |
| universe_manager.py | 본 안에서 무접촉 |
| multi_symbol_runner.py | 무접촉 |
| beat_schedule / exchange_mode | L4 무접촉 |

#### FROZEN 유지 대상

| 함수/타입 | 변경 허용 |
|-----------|:---------:|
| ScreeningInput | **0줄** |
| SymbolScreener.screen() | **0줄** |
| BacktestQualifier.qualify() | **0줄** |
| validate_screening_preconditions | **0줄** |
| build_screening_input | **0줄** |
| check_stale / check_partial / normalize_symbol | **0줄** |
| screen_and_update() | **0줄** |
| qualify_and_record() | **0줄** |

#### 테스트 증가 예상

| 범주 | 예상 테스트 수 |
|------|:-------------:|
| Pipeline orchestrator tests | ~30-40 |
| Qualification fixture tests | ~15-20 |
| Purity guard extension | ~12 |
| **예상 합계** | **~55-70** |

#### 회귀/오염 방지 계획

- 신규 파일은 **Pure Zone으로 등록** → purity guard 32 패턴 적용
- TransformResult→QualificationInput 매핑은 **테스트로 봉인** (golden set 4종 + failure 모드)
- reject → qualification 미진입 invariant를 **테스트로 증명**
- 전체 회귀 PASS 필수 (예상 ~5250+)

#### 실패 시 fail-closed 방식

- TransformResult.decision ∈ REJECT → qualification 미호출, combined result = REJECTED
- ScreeningOutput.passed == False → qualification 미호출, combined result = SCREEN_FAILED
- QualificationOutput.passed == False → combined result = QUALIFY_FAILED
- 모든 실패 경로에서 **downstream 전파 차단**

#### 리스크 평가

| 항목 | 등급 |
|------|:----:|
| FROZEN 경계 침범 | **ZERO** |
| RED 파일 접촉 | **ZERO** |
| Runtime 접촉 | **ZERO** |
| DB/async 접촉 | **ZERO** |
| 롤백 비용 | **TRIVIAL** (신규 파일 삭제) |

---

### 안 B: Universe Selection Pure Core Extraction (Bolder / Runtime-Adjacent)

#### 목적

`universe_manager.py`의 7-조건 선별 로직을 **stateless pure function**으로 추출.
DB query layer와 decision logic을 분리하여, Phase 6 multi-symbol 실행의 기초를 만듦.

#### 목표 기능

- `SymbolEligibilityRecord` (plain dataclass) → `evaluate_eligibility()` → `SelectionOutcome`
- 7개 조건: status==CORE, qualification_passed, TTL_valid, broker_available, exposure_under_limit, no_forbidden_sector, regime_compatible
- DB/SQLAlchemy 의존성 0 (plain dataclass input only)

#### 왜 지금 열어야 하는가

- Phase 6의 선행 조건: multi-symbol runner가 universe selection을 호출해야 함
- `universe_manager.py`가 현재 1개 consumer (beat task) → 추출 비용 최소
- Phase 5에서 strategy_router가 두 번째 consumer가 되면 추출이 훨씬 어려워짐

#### 파일

| 파일 | 작업 | 계층 |
|------|------|:----:|
| `app/services/universe_selection_logic.py` | **신규** | L1 Pure |
| `app/services/universe_manager.py` | **수정** (inline→delegation) | Service |
| `tests/test_universe_selection_logic.py` | **신규** | Test |
| `tests/test_purity_guard.py` | **수정** (+1 Pure Zone) | Test |

#### 허용 접촉면

| 대상 | 접촉 유형 |
|------|-----------|
| universe_manager.py | 수정 (로직 추출, DB layer 유지) |
| data_provider.py | import only (DataQualityDecision) |
| asset.py | import only (AssetClass, AssetSector) |

#### 금지 접촉면

| 대상 | 금지 사유 |
|------|-----------|
| regime_detector | RED |
| asset_service.py | RED |
| runtime_strategy_loader.py | RED |
| multi_symbol_runner.py | 본 안에서 무접촉 |
| SQLAlchemy/DB session | 신규 pure file에 금지 |

#### FROZEN 유지 대상

안 A와 동일 + universe_manager.py의 기존 API 서명 유지

#### 테스트 증가 예상

| 범주 | 예상 테스트 수 |
|------|:-------------:|
| Selection logic tests | ~25-30 |
| Purity guard extension | ~12 |
| Manager regression tests | ~10 |
| **예상 합계** | **~45-50** |

#### 리스크 평가

| 항목 | 등급 |
|------|:----:|
| FROZEN 경계 침범 | **ZERO** |
| RED 파일 접촉 | **ZERO** |
| Runtime 접촉 | **MODERATE** (universe_manager.py 수정) |
| DB/async 접촉 | **ZERO** (신규 pure file), **READ** (기존 manager) |
| 롤백 비용 | **MODERATE** (manager revert 필요) |

---

## 4. 비교 매트릭스

| 기준 | 안 A (Pipeline Composition) | 안 B (Universe Extraction) |
|------|:--:|:--:|
| FROZEN/RED 접촉 | **Zero** | Zero FROZEN, 1 un-sealed 수정 |
| 신규 파일 | 3 | 3 + 1 수정 |
| 봉인 자산 재사용 깊이 | **High** (5개 sealed module) | Medium (3개 sealed module) |
| 다음 Phase 해제 | **Phase 4** (Paper Shadow) | Phase 6 (Multi-symbol) |
| 롤백 비용 | **Trivial** (삭제) | Moderate (revert) |
| 테스트 신뢰도 | **High** (기존 golden set 활용) | Medium (신규 fixture 필요) |
| 의존 순서 | **자연스러움** (screening→qualify) | 선취적 (Phase 6 준비) |

---

## 5. 권장 실행 순서

**안 A를 먼저 실행**하고, 안 B는 후속 sub-stage로 제안합니다.

### 근거

1. 안 A는 Stage 3B의 **직접 후속**이며 자연스러운 의존 순서를 따름
2. 안 A의 combined verdict가 존재해야 안 B의 universe selection 조건 #2 (qualification_passed)에 공급할 데이터가 생김
3. 안 A의 리스크가 극히 낮아 봉인 성공 확률이 높음
4. 안 A 봉인 후 안 B를 열면, 두 단계 모두 개별 봉인이 가능

### 제안 구조

```
Stage 4A: Screening-Qualification Pipeline Composition (Pure)
  ├─ 설계/계약 단계 (design docs)
  └─ 제한 구현 단계 (pure implementation GO)

Stage 4B: Universe Selection Pure Core (후속, 별도 심사)
  ├─ 설계/계약 단계
  └─ 제한 구현 단계
```

---

## 6. 완료 기준 (안 A 기준)

| # | 기준 |
|---|------|
| 1 | `screening_qualification_pipeline.py`는 pure import만 사용 |
| 2 | TransformResult→QualificationInput 매핑이 테스트로 봉인됨 |
| 3 | reject 상태는 qualification 미호출이 테스트로 증명됨 |
| 4 | screen_failed 상태는 qualification 미호출이 테스트로 증명됨 |
| 5 | golden set 4종이 전체 파이프라인 통과로 검증됨 |
| 6 | failure mode (F1-F9)가 combined result로 전파됨이 검증됨 |
| 7 | FROZEN 함수 0줄 변경 |
| 8 | RED 파일 접촉 0건 |
| 9 | 전체 회귀 PASS |
| 10 | purity guard 회귀 PASS (8 Pure Zone files) |

---

## 7. fail-closed 위험 분석

| 실패 지점 | fail-closed 행동 | 증빙 방법 |
|-----------|-----------------|-----------|
| TransformResult = REJECT | qualification 미호출, combined = REJECTED | 테스트 (F1/F2/F4/F7/F8) |
| TransformResult = OK but screen() fails | combined = SCREEN_FAILED | 테스트 (threshold 미달) |
| screen() passes but qualify() fails | combined = QUALIFY_FAILED | 테스트 (bars/sharpe/cost) |
| All pass | combined = QUALIFIED | 테스트 (golden set 4종) |
| Unknown decision type | **raise ValueError** (예외 차단) | 테스트 |

---

```
차기 확장 범위 심사 패키지 v1.0
Authority: A
Date: 2026-04-03
Baseline: v1.7 / 5186/5186 PASS
Recommended: 안 A (Screening-Qualification Pipeline Composition)
Structure: 설계/계약 단계 → 제한 구현 단계 (2단 분리)
```
