# CR-048 Stage 4A: Pipeline Composition Contract

**문서 ID:** STAGE4A-CONTRACT-001
**작성일:** 2026-04-03
**전제:** Stage 3B SEALED, 모든 조합 대상은 FROZEN

---

## 1. Pipeline 흐름

```
TransformResult
    │
    ├─ decision ∈ _REJECT_DECISIONS → HALT (PipelineVerdict.DATA_REJECTED)
    │
    ▼
ScreeningInput (from TransformResult.screening_input)
    │
    ▼
SymbolScreener.screen(ScreeningInput) → ScreeningOutput
    │
    ├─ all_passed == False → HALT (PipelineVerdict.SCREEN_FAILED)
    │
    ▼
map_to_qualification_input(ScreeningInput, BacktestReadiness) → QualificationInput
    │
    ▼
BacktestQualifier.qualify(QualificationInput) → QualificationOutput
    │
    ├─ all_passed == False → HALT (PipelineVerdict.QUALIFY_FAILED)
    │
    ▼
PipelineVerdict.QUALIFIED
```

---

## 2. 핵심 타입

### 2.1 PipelineVerdict (enum)

```python
class PipelineVerdict(str, Enum):
    QUALIFIED = "qualified"           # 전 단계 PASS
    DATA_REJECTED = "data_rejected"   # TransformResult reject
    SCREEN_FAILED = "screen_failed"   # Screening 미통과
    QUALIFY_FAILED = "qualify_failed"  # Qualification 미통과
```

### 2.2 PipelineResult (frozen dataclass)

```python
@dataclass(frozen=True)
class PipelineResult:
    symbol: str
    verdict: PipelineVerdict
    screening_output: ScreeningOutput | None = None    # screen 도달 시
    qualification_output: QualificationOutput | None = None  # qualify 도달 시
```

**Invariants:**
- `DATA_REJECTED` → screening_output=None, qualification_output=None
- `SCREEN_FAILED` → screening_output is not None, qualification_output=None
- `QUALIFY_FAILED` → 둘 다 not None
- `QUALIFIED` → 둘 다 not None, 둘 다 all_passed=True

### 2.3 PipelineEvidence (frozen dataclass)

```python
@dataclass(frozen=True)
class PipelineEvidence:
    symbol: str
    transform_decision: DataQualityDecision
    transform_source: ScreeningInputSource | None = None
    screening_score: float | None = None
    screening_stage_count: int = 0
    qualification_status: str | None = None
    qualification_check_count: int = 0
    pipeline_timestamp: datetime | None = None
```

**PipelineEvidence는 audit-only. PipelineResult의 verdict 계산에 영향을 주지 않음.**

### 2.4 PipelineOutput (frozen dataclass, top-level return)

```python
@dataclass(frozen=True)
class PipelineOutput:
    result: PipelineResult
    evidence: PipelineEvidence
```

---

## 3. 함수 서명

### 3.1 Main pipeline function

```python
def run_screening_qualification_pipeline(
    transform_result: TransformResult,
    backtest: BacktestReadiness,
    strategy_id: str = "",
    timeframe: str = "1h",
    screening_thresholds: ScreeningThresholds | None = None,
    qualification_thresholds: QualificationThresholds | None = None,
    now_utc: datetime | None = None,
) -> PipelineOutput:
    """Compose screening transform → screen → qualify in a single pure call.

    Pure function.  No async, no I/O, no DB.
    Caller supplies TransformResult (from screening_transform) and
    BacktestReadiness (from data provider).

    Fail-closed: each stage failure halts subsequent stages.
    """
```

### 3.2 Mapping helper (internal)

```python
def _map_to_qualification_input(
    screening_input: ScreeningInput,
    backtest: BacktestReadiness,
    strategy_id: str,
    timeframe: str,
) -> QualificationInput:
    """Map ScreeningInput + BacktestReadiness → QualificationInput.

    Deterministic field copy.  No interpretation, no branching.
    """
```

---

## 4. 필드 매핑 규칙

### 4.1 TransformResult → ScreeningInput

**이미 Stage 3B-2에서 완료.** `TransformResult.screening_input`을 그대로 사용.
추가 매핑 없음. 변환 없음.

### 4.2 ScreeningInput + BacktestReadiness → QualificationInput

| QualificationInput field | Source | Rule |
|--------------------------|--------|------|
| `strategy_id` | parameter | 그대로 전달 |
| `symbol` | `screening_input.symbol` | 복사 |
| `timeframe` | parameter | 그대로 전달 |
| `symbol_asset_class` | `screening_input.asset_class.value` | enum→string |
| `total_bars` | `backtest.available_bars or 0` | None→0 |
| `warmup_bars_available` | `backtest.available_bars or 0` | None→0 |
| `missing_data_pct` | `backtest.missing_data_pct or 0.0` | None→0.0 |
| `sharpe_ratio` | `backtest.sharpe_ratio` | 직접 복사 (None 허용) |
| `has_future_data_leak` | `False` | 기본값 (real check는 Phase 4B+) |
| `has_lookahead_bias` | `False` | 기본값 (real check는 Phase 4B+) |
| `has_timestamp_disorder` | `False` | 기본값 |
| `duplicate_bar_count` | `0` | 기본값 |

**규칙: 매핑은 deterministic field copy. provider별 특례 분기 없음.**

### 4.3 매핑에서 제외되는 QualificationInput 필드

| Field | Default | 이유 |
|-------|---------|------|
| `strategy_asset_classes` | None | 전략 메타 필요 (Stage 4A 범위 밖) |
| `strategy_timeframes` | None | 전략 메타 필요 |
| `dataset_fingerprint` | None | 데이터셋 해시 필요 |
| `warmup_bars_required` | 200 | 전략별 다름 |
| `date_range_start/end` | None | 날짜 범위 필요 |
| `max_drawdown_pct` | None | 백테스트 결과 필요 |
| `total_return_pct` | None | 백테스트 결과 필요 |
| `sharpe_after_costs` | None | 비용 반영 결과 필요 |
| `return_after_costs_pct` | None | 비용 반영 결과 필요 |
| `turnover_annual` | None | 거래 빈도 필요 |

**이 필드들은 default로 남음. Phase 4 이후 단계에서 전략 메타와 연결 시 채워짐.**

---

## 5. Fail-closed 규칙 (5-point chain)

| # | 조건 | Verdict | screening_output | qualification_output |
|---|------|---------|:----------------:|:--------------------:|
| 1 | `TransformResult.decision ∈ _REJECT_DECISIONS` | `DATA_REJECTED` | None | None |
| 2 | `TransformResult.screening_input is None` (방어) | `DATA_REJECTED` | None | None |
| 3 | `ScreeningOutput.all_passed == False` | `SCREEN_FAILED` | present | None |
| 4 | `QualificationOutput.all_passed == False` | `QUALIFY_FAILED` | present | present |
| 5 | All pass | `QUALIFIED` | present | present |

**Unknown decision type → raise ValueError (예외 차단)**

---

## 6. Evidence 기록 규칙

| 시점 | evidence 필드 | 값 |
|------|---------------|-----|
| 항상 | `transform_decision` | `TransformResult.decision` |
| 항상 | `transform_source` | `TransformResult.source` |
| screen 도달 시 | `screening_score` | `ScreeningOutput.score` |
| screen 도달 시 | `screening_stage_count` | `len(ScreeningOutput.stages)` |
| qualify 도달 시 | `qualification_status` | `QualificationOutput.qualification_status.value` |
| qualify 도달 시 | `qualification_check_count` | `len(QualificationOutput.checks)` |
| 항상 | `pipeline_timestamp` | `now_utc` parameter |

**PipelineEvidence는 PipelineResult 계산에 영향 없음 (audit-only).**

---

```
Pipeline Contract v1.0
Pure composition only
No orchestration, no side-effects
```
