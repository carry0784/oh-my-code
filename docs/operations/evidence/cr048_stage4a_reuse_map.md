# CR-048 Stage 4A: Sealed Asset Reuse Map

**문서 ID:** STAGE4A-REUSE-001
**작성일:** 2026-04-03

---

## 1. 재사용 자산 목록

### 1.1 Stage 3B-2 자산 (직접 조합 대상)

| 자산 | 파일 | 재사용 방식 | Stage 4A 변경 |
|------|------|------------|:------------:|
| `TransformResult` | screening_transform.py | import → pipeline 입력 | **0줄** |
| `ScreeningInputSource` | screening_transform.py | import → evidence 기록 | **0줄** |
| `_REJECT_DECISIONS` | screening_transform.py | import → reject 판정 | **0줄** |
| Golden set fixtures (20) | tests/fixtures/screening_fixtures.py | import → pipeline 테스트 입력 | **0줄** |
| Provider stubs (4) | tests/stubs/screening_stubs.py | **미사용** (Stage 4A는 stub 불요) | **0줄** |

### 1.2 Stage 3A 자산 (sealed 엔진)

| 자산 | 파일 | 재사용 방식 | Stage 4A 변경 |
|------|------|------------|:------------:|
| `SymbolScreener` | symbol_screener.py | import → screen() 호출 | **0줄** |
| `ScreeningInput` | symbol_screener.py | import → pipeline 중간 타입 | **0줄** |
| `ScreeningOutput` | symbol_screener.py | import → pipeline 중간 결과 | **0줄** |
| `ScreeningThresholds` | symbol_screener.py | import → configurable parameter | **0줄** |

### 1.3 Stage 3B-1 자산 (contracts)

| 자산 | 파일 | 재사용 방식 | Stage 4A 변경 |
|------|------|------------|:------------:|
| `DataQualityDecision` (9 enum) | data_provider.py | import → reject 판정 | **0줄** |
| `BacktestReadiness` | data_provider.py | import → qualify input 매핑 | **0줄** |
| `check_stale` / `check_partial` / `normalize_symbol` | data_provider.py | **미사용** (이미 TransformResult에 반영) | **0줄** |

### 1.4 기존 sealed 자산 (backtest qualification)

| 자산 | 파일 | 재사용 방식 | Stage 4A 변경 |
|------|------|------------|:------------:|
| `BacktestQualifier` | backtest_qualification.py | import → qualify() 호출 | **0줄** |
| `QualificationInput` | backtest_qualification.py | import → 매핑 대상 | **0줄** |
| `QualificationOutput` | backtest_qualification.py | import → pipeline 결과 | **0줄** |
| `QualificationThresholds` | backtest_qualification.py | import → configurable parameter | **0줄** |

### 1.5 기존 sealed 자산 (models)

| 자산 | 파일 | 재사용 방식 | Stage 4A 변경 |
|------|------|------------|:------------:|
| `AssetClass` | asset.py | import → type reference | **0줄** |
| `AssetSector` | asset.py | import → type reference | **0줄** |

---

## 2. 재사용 불가 자산 (Stage 4A 범위 밖)

| 자산 | 파일 | 불가 사유 |
|------|------|-----------|
| `universe_manager.py` | app/services/ | Stage 4B 후보 — 접촉 금지 |
| `strategy_router.py` | app/services/ | Phase 5 — 접촉 금지 |
| `runtime_strategy_loader.py` | app/services/ | RED — 접촉 금지 |
| `feature_cache.py` | app/services/ | Phase 5 — 접촉 금지 |
| `regime_detector` | app/services/ | RED — CR-046 |
| `asset_service.py` | app/services/ | RED — runtime path |

---

## 3. 신규 생성 자산

| 자산 | 파일 | 성격 |
|------|------|------|
| `PipelineVerdict` (enum) | screening_qualification_pipeline.py | 신규 |
| `PipelineResult` (frozen dataclass) | screening_qualification_pipeline.py | 신규 |
| `PipelineEvidence` (frozen dataclass) | screening_qualification_pipeline.py | 신규 |
| `PipelineOutput` (frozen dataclass) | screening_qualification_pipeline.py | 신규 |
| `run_screening_qualification_pipeline()` | screening_qualification_pipeline.py | 신규 |
| `_map_to_qualification_input()` | screening_qualification_pipeline.py | 신규 (internal) |
| Qualification fixtures | tests/fixtures/qualification_fixtures.py | 신규 |
| Pipeline tests | tests/test_screening_qualification_pipeline.py | 신규 |

---

## 4. 재사용 원칙

| 원칙 | 설명 |
|------|------|
| **import only** | 모든 sealed 자산은 import만. 수정 금지. |
| **call only** | screen()/qualify()는 호출만. 내부 수정 금지. |
| **type copy only** | 필드 매핑은 deterministic copy. 해석/분기 금지. |
| **fixture extend only** | 기존 golden set을 확장 사용. 기존 fixture 수정 금지. |
| **zero side-effect** | 새 함수도 pure. logging/DB/network 금지. |

---

```
Reuse Map v1.0
15 sealed assets reused (import/call only)
0 sealed assets modified
6 new assets created
```
