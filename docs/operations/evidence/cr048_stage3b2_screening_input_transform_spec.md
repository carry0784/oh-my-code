# CR-048 Stage 3B-2 ScreeningInput Transformation Spec

**문서 ID:** DESIGN-STAGE3B2-003
**작성일:** 2026-04-03
**CR:** CR-048
**변경 등급:** L0 (설계 문서)

---

## 1. 목적

DataProvider 출력 (MarketDataSnapshot + FundamentalSnapshot + BacktestReadiness + SymbolMetadata)을 ScreeningInput으로 변환하는 **정확한 계약**을 정의한다.

핵심 원칙:
- **validate → build** 2단계 분리 (검증과 생성이 별개 함수)
- REJECT 계열 결정은 build 호출을 **차단** (fail-closed)
- 변환 함수는 **pure function** (no async, no I/O, no DB)

---

## 2. ScreeningInput과 ScreeningInputSource 분리

### ScreeningInput (기존 — 변경 없음)

Stage 3A `symbol_screener.py`의 ScreeningInput은 수정하지 않는다. 16개 필드 그대로 사용.

### ScreeningInputSource (신규 frozen dataclass)

```python
@dataclass(frozen=True)
class ScreeningInputSource:
    """Records WHERE each ScreeningInput field value came from.
    Audit-only. Does NOT influence screener computation."""

    symbol: str
    market_provider: str = "unknown"
    backtest_provider: str = "unknown"
    fundamental_provider: str = "unknown"
    metadata_provider: str = "unknown"
    market_timestamp: datetime | None = None
    backtest_timestamp: datetime | None = None
    fundamental_timestamp: datetime | None = None
    stale_decision: DataQualityDecision = DataQualityDecision.OK
    partial_decision: DataQualityDecision = DataQualityDecision.OK
    namespace_decision: DataQualityDecision = DataQualityDecision.OK
    build_timestamp: datetime | None = None
```

**사용 제약:**
- screener 계산에 **영향 주지 않음** (감사 전용)
- ScreeningInput과 항상 쌍으로 생성
- frozen — 생성 후 변경 불가

---

## 3. 변환 함수: build_screening_input()

```python
def build_screening_input(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    fundamental: FundamentalSnapshot | None,
    metadata: SymbolMetadata | None,
    asset_class: AssetClass,
    sector: AssetSector,
) -> ScreeningInput:
```

### 필드 매핑 표

| ScreeningInput field | Source | Mapping | None 의미 |
|---------------------|--------|---------|-----------|
| `symbol` | `market.symbol` | direct | 불가 (필수) |
| `asset_class` | parameter | direct | 불가 (필수) |
| `sector` | parameter | direct | 불가 (필수) |
| `market_cap_usd` | `market.market_cap_usd` | direct | optional (F3) |
| `listing_age_days` | `metadata.listing_age_days` if metadata else None | conditional | F6 허용 |
| `avg_daily_volume_usd` | `market.avg_daily_volume_usd` | direct | F2 mandatory |
| `spread_pct` | `market.spread_pct` | direct | optional (F3) |
| `atr_pct` | `market.atr_pct` | direct | F2 mandatory |
| `adx` | `market.adx` | direct | F2 mandatory |
| `price_vs_200ma` | `market.price_vs_200ma` | direct | optional (F3) |
| `per` | `fundamental.per` if fundamental else None | conditional | optional |
| `roe` | `fundamental.roe` if fundamental else None | conditional | optional |
| `tvl_usd` | `fundamental.tvl_usd` if fundamental else None | conditional | optional |
| `available_bars` | `backtest.available_bars` | direct | F2 mandatory |
| `sharpe_ratio` | `backtest.sharpe_ratio` | direct | optional |
| `missing_data_pct` | `backtest.missing_data_pct` | direct | optional |

**mandatory 4개:** avg_daily_volume_usd, atr_pct, adx, available_bars
- validate 단계에서 PARTIAL_REJECT → build 호출 차단
- build 내부에서 mandatory None 검사 **하지 않음** (validate가 보장)

---

## 4. 검증 함수: validate_screening_preconditions()

```python
def validate_screening_preconditions(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    metadata: SymbolMetadata | None,
    asset_class: str,
    now_utc: datetime,
) -> DataQualityDecision:
```

### 검증 순서 (fail-fast, 순서 고정)

| Step | 검증 | 실패 시 반환 | 중단 |
|:----:|------|:----------:|:----:|
| 1 | `normalize_symbol(market.symbol, asset_class)` → None? | `SYMBOL_NAMESPACE_ERROR` | **YES** |
| 2 | `check_stale(market.timestamp, asset_class, "price", now_utc)` | `STALE_REJECT` | **YES** |
| 3 | `check_partial(market, backtest)` | `PARTIAL_REJECT` | **YES** |
| 4 | 모든 검증 통과 | `check_partial` 결과 (OK 또는 PARTIAL_USABLE) | NO |

---

## 5. DataQualityDecision → build 허용/차단 규칙

| DataQualityDecision | build 호출 | 비고 |
|--------------------:|:----------:|------|
| `OK` | **YES** | 정상 경로 |
| `PARTIAL_USABLE` | **YES** | F3: optional 누락, 일부 None |
| `STALE_USABLE` | **YES** | 경고 기록 |
| `PARTIAL_REJECT` | **NO** | F2: mandatory 누락 |
| `STALE_REJECT` | **NO** | 데이터 너무 오래됨 |
| `SYMBOL_NAMESPACE_ERROR` | **NO** | F7 |
| `PROVIDER_UNAVAILABLE` | **NO** | F1/F8 |
| `INSUFFICIENT_BARS` | **YES** | Stage 5가 판단 |
| `MISSING_LISTING_AGE` | **YES** | F6 예외, listing_age=None |

**_REJECT_DECISIONS 상수:**
```python
_REJECT_DECISIONS: frozenset[DataQualityDecision] = frozenset({
    DataQualityDecision.PARTIAL_REJECT,
    DataQualityDecision.STALE_REJECT,
    DataQualityDecision.SYMBOL_NAMESPACE_ERROR,
    DataQualityDecision.PROVIDER_UNAVAILABLE,
})
```

---

## 6. TransformResult (변환 결과 타입)

```python
@dataclass(frozen=True)
class TransformResult:
    """Result of the validate+build pipeline."""
    decision: DataQualityDecision
    screening_input: ScreeningInput | None   # None if REJECT
    source: ScreeningInputSource | None      # None if REJECT
```

**규칙:**
- decision이 REJECT → screening_input = None, source = None
- decision이 OK/USABLE → screening_input과 source 모두 반드시 존재

---

## 7. 통합 변환 함수: transform_provider_to_screening()

```python
def transform_provider_to_screening(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    fundamental: FundamentalSnapshot | None,
    metadata: SymbolMetadata | None,
    asset_class: AssetClass,
    sector: AssetSector,
    now_utc: datetime,
    market_provider: str = "unknown",
    backtest_provider: str = "unknown",
    fundamental_provider: str = "unknown",
    metadata_provider: str = "unknown",
) -> TransformResult:
    """Full transformation pipeline: validate → build.
    Pure function. No async, no I/O, no DB."""
```

### 내부 흐름

```
1. validate_screening_preconditions(market, backtest, metadata, asset_class, now_utc)
     │
     ├─ REJECT → return TransformResult(decision, None, None)
     │
     └─ OK/USABLE → continue
          │
2. build_screening_input(market, backtest, fundamental, metadata, asset_class, sector)
     │
3. build ScreeningInputSource (감사 메타데이터)
     │
4. return TransformResult(decision, screening_input, source)
```

---

## 8. Pure Function 보장

| 함수 | async | I/O | DB | Side-effect | 위치 |
|------|:-----:|:---:|:--:|:-----------:|------|
| `validate_screening_preconditions` | NO | NO | NO | NO | screening_transform.py |
| `build_screening_input` | NO | NO | NO | NO | screening_transform.py |
| `transform_provider_to_screening` | NO | NO | NO | NO | screening_transform.py |

Purity guard (32 forbidden patterns) 대상에 `screening_transform.py` 추가.

---

```
CR-048 Stage 3B-2 ScreeningInput Transformation Spec v1.0
Document ID: DESIGN-STAGE3B2-003
Date: 2026-04-03
Status: SUBMITTED
```
