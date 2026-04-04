# CR-048 Stage 3B DataProvider Capability Matrix

**문서 ID:** GOV-L3-STAGE3B-CAPABILITY-001
**작성일:** 2026-04-03
**Authority:** A (Decision Authority)
**CR:** CR-048
**전제:** Failure Mode Matrix (GOV-L3-STAGE3B-FAILMODE-001)
**목적:** DataProvider 구현체가 선언해야 하는 capability 계약 정의

> 이 문서는 계약 정의만 포함한다. 구현체 설계 없음.

---

## 1. ProviderCapability Frozen Dataclass 정의

각 DataProvider 구현체는 자신의 capability를 frozen dataclass로 선언해야 한다.

### 1-1. 필드 정의

| # | 필드 | 타입 | 의미 | 기본값 |
|:-:|------|------|------|:------:|
| 1 | `provider_name` | `str` | Provider 식별자 | 필수 |
| 2 | `supported_asset_classes` | `frozenset[AssetClass]` | 지원 자산 클래스 | 필수 |
| 3 | `supports_volume` | `bool` | avg_daily_volume_usd 제공 가능 | `False` |
| 4 | `supports_spread` | `bool` | spread_pct 제공 가능 | `False` |
| 5 | `supports_atr` | `bool` | atr_pct 제공 가능 (직접 또는 OHLCV에서 계산) | `False` |
| 6 | `supports_adx` | `bool` | adx 제공 가능 (직접 또는 OHLCV에서 계산) | `False` |
| 7 | `supports_price_vs_ma` | `bool` | price_vs_200ma 제공 가능 | `False` |
| 8 | `supports_market_cap` | `bool` | market_cap_usd 제공 가능 | `False` |
| 9 | `supports_per` | `bool` | PER 제공 가능 | `False` |
| 10 | `supports_roe` | `bool` | ROE 제공 가능 | `False` |
| 11 | `supports_tvl` | `bool` | TVL (DeFi) 제공 가능 | `False` |
| 12 | `supports_available_bars` | `bool` | 히스토리 바 수 제공 가능 | `False` |
| 13 | `supports_sharpe` | `bool` | Sharpe ratio 제공 가능 | `False` |
| 14 | `supports_missing_pct` | `bool` | 결측률 제공 가능 | `False` |
| 15 | `supports_listing_age` | `bool` | listing_age_days 제공 가능 | `False` |
| 16 | `freshness_granularity` | `str` | 데이터 갱신 주기 (예: "realtime", "1m", "5m", "1h", "1d") | `"unknown"` |
| 17 | `partial_data_policy` | `str` | 부분 데이터 처리 방식 ("reject", "fill_none", "last_known") | `"reject"` |
| 18 | `stale_data_policy` | `str` | stale 데이터 처리 방식 ("reject", "warn", "use_with_flag") | `"reject"` |
| 19 | `symbol_namespace` | `str` | 심볼 형식 (예: "ccxt", "krx", "kis_us") | `"unknown"` |
| 20 | `max_batch_size` | `int` | 일괄 조회 최대 종목 수 | `1` |

### 1-2. Frozen Dataclass 구조 (계약)

```python
@dataclass(frozen=True)
class ProviderCapability:
    provider_name: str
    supported_asset_classes: frozenset[AssetClass]
    supports_volume: bool = False
    supports_spread: bool = False
    supports_atr: bool = False
    supports_adx: bool = False
    supports_price_vs_ma: bool = False
    supports_market_cap: bool = False
    supports_per: bool = False
    supports_roe: bool = False
    supports_tvl: bool = False
    supports_available_bars: bool = False
    supports_sharpe: bool = False
    supports_missing_pct: bool = False
    supports_listing_age: bool = False
    freshness_granularity: str = "unknown"
    partial_data_policy: str = "reject"
    stale_data_policy: str = "reject"
    symbol_namespace: str = "unknown"
    max_batch_size: int = 1
```

**규칙:** 이 dataclass는 Pure Zone에 배치 (data_provider.py). frozen=True, 모든 필드 immutable.

---

## 2. Mandatory Capability (필수 4개)

ScreeningInput 필수 필드를 제공하려면 최소 아래 capability가 True여야 한다.

| # | Capability | ScreeningInput 필수 필드 | 없으면 |
|:-:|-----------|-------------------------|--------|
| 1 | `supports_volume` | `avg_daily_volume_usd` | F2 PARTIAL_REJECT |
| 2 | `supports_atr` | `atr_pct` | F2 PARTIAL_REJECT |
| 3 | `supports_adx` | `adx` | F2 PARTIAL_REJECT |
| 4 | `supports_available_bars` | `available_bars` | F5 INSUFFICIENT_BARS |

### Capability 충족성 판정 (pure 함수)

```
is_screening_capable(cap: ProviderCapability) → bool:
    return all([cap.supports_volume, cap.supports_atr,
                cap.supports_adx, cap.supports_available_bars])
```

**규칙:** `is_screening_capable() == False`인 Provider 단독으로 ScreeningInput을 생성할 수 없다.

---

## 3. Provider × Asset Class 적합성

| Capability | CRYPTO | US_STOCK | KR_STOCK | 비고 |
|-----------|:------:|:--------:|:--------:|------|
| `supports_volume` | 필수 | 필수 | 필수 | 모든 시장 공통 |
| `supports_spread` | 선택 | 선택 | 선택 | 거래소에 따라 상이 |
| `supports_atr` | 필수 | 필수 | 필수 | OHLCV 기반 계산 가능 |
| `supports_adx` | 필수 | 필수 | 필수 | OHLCV 기반 계산 가능 |
| `supports_price_vs_ma` | 선택 | 선택 | 선택 | 종가 기반 계산 가능 |
| `supports_market_cap` | 선택 | 선택 | 선택 | 외부 API 필요 |
| `supports_per` | N/A | 필수* | 필수* | *주식만 (Stage 4) |
| `supports_roe` | N/A | 필수* | 필수* | *주식만 (Stage 4) |
| `supports_tvl` | DeFi만 | N/A | N/A | DeFi 섹터 한정 |
| `supports_available_bars` | 필수 | 필수 | 필수 | 히스토리 길이 |
| `supports_listing_age` | 선택 | 선택 | 선택 | 계약 공백 (§4 참조) |

*주식 시장의 PER/ROE는 Stage 4에서 사용하지만, None 시 skip이므로 "선택"에 가까움. 단, 전체 Stage 4가 무력화되므로 "필수에 준함"으로 표기.

---

## 4. Symbol Namespace 규약

### 4-1. 내부 표준 namespace

| 자산 클래스 | 형식 | 예시 |
|------------|------|------|
| CRYPTO | `{BASE}/{QUOTE}` | `BTC/USDT`, `SOL/USDT`, `ETH/USDT` |
| US_STOCK | `{TICKER}` | `AAPL`, `NVDA`, `MSFT` |
| KR_STOCK | `{6자리코드}` | `005930`, `000660`, `035420` |

### 4-2. Provider별 namespace 예시

| Provider | 원본 형식 | 내부 변환 |
|----------|-----------|-----------|
| Binance CCXT | `BTC/USDT` | 동일 (변환 불요) |
| CoinGecko | `bitcoin` | `BTC/USDT` (매핑 필요) |
| KRX | `삼성전자` | `005930` (코드 매핑 필요) |
| KIS US | `AAPL` | 동일 (변환 불요) |

### 4-3. Namespace 정규화 규칙

| # | 규칙 |
|:-:|------|
| N1 | 변환 함수는 Pure Zone에 배치 (I/O 없음) |
| N2 | 매핑 테이블은 상수 dict로 정의 (constitution.py 또는 별도 pure 모듈) |
| N3 | 매핑 실패 시 `SYMBOL_NAMESPACE_ERROR` 반환 (F7) |
| N4 | 대소문자 정규화: CRYPTO는 uppercase, US_STOCK은 uppercase |
| N5 | 구분자 정규화: CRYPTO는 `/` 필수 |

---

## 5. Freshness Granularity 체계

| 등급 | 값 | 의미 | 사용처 |
|------|-----|------|--------|
| `realtime` | < 1초 | WebSocket 실시간 | 미지원 (Stage 3B 범위 외) |
| `1m` | 1분 | 분봉 기반 | 거래소 REST API |
| `5m` | 5분 | 5분봉 기반 | 일반 조회 주기 |
| `1h` | 1시간 | 시간봉 기반 | 기본 screening 주기 |
| `1d` | 1일 | 일봉 기반 | 기본적분석 |
| `unknown` | 불명 | Provider가 주기 미선언 | 기본값 — stale 판정 시 보수적 처리 |

**규칙:** `freshness_granularity == "unknown"`이면 stale 판정 시 가장 짧은 허용 한도 적용 (보수적).

---

## 6. Composite Provider 합성 규칙

복수 Provider로 ScreeningInput을 조립할 때의 규칙.

### 6-1. 합성 순서

```
1. 각 Provider의 ProviderCapability 확인
2. 필수 4개 capability를 충족하는 Provider 조합 존재 확인
3. 각 Provider 호출 (Stage 3B-2 영역)
4. Namespace 정규화
5. Stale 판정 (각 snapshot 개별)
6. Partial 판정 (합산)
7. Quality grade 병합 (pessimistic merge)
8. ScreeningInput 생성
```

### 6-2. 합성 규칙

| # | 규칙 | 설명 |
|:-:|------|------|
| M1 | 같은 필드를 복수 Provider가 제공하면 **가장 최신 데이터** 채택 | timestamp 기반 |
| M2 | Quality grade는 **최저 등급** 채택 | pessimistic merge (F9) |
| M3 | Namespace가 다른 Provider는 **정규화 후 합성** | N1-N5 적용 |
| M4 | 합성 결과의 Capability는 **개별 Provider capability의 합집합** | `cap_a ∪ cap_b` |
| M5 | 합성 Provider도 `is_screening_capable()` 통과해야 함 | 필수 4개 체크 |

---

## 7. Capability × Failure Mode 교차표

| Capability | 미충족 시 Failure Mode | Decision |
|-----------|:---------------------:|----------|
| `supports_volume` = False | F2 | PARTIAL_REJECT |
| `supports_atr` = False | F2 | PARTIAL_REJECT |
| `supports_adx` = False | F2 | PARTIAL_REJECT |
| `supports_available_bars` = False | F5 | INSUFFICIENT_BARS |
| `supports_listing_age` = False | F6 | MISSING_LISTING_AGE |
| `supports_per` = False (주식) | F3 | PARTIAL_USABLE |
| `supports_roe` = False (주식) | F3 | PARTIAL_USABLE |
| `supports_tvl` = False (DeFi) | F3 | PARTIAL_USABLE |
| `freshness_granularity` = "unknown" | F4 risk | STALE_USABLE/REJECT |
| `symbol_namespace` 불일치 | F7 | SYMBOL_NAMESPACE_ERROR |

---

## 8. SymbolMetadata Frozen Dataclass (listing_age 공백 해소)

Boundary Inventory §5-4에서 식별된 `listing_age_days` 공백을 해소하기 위한 별도 dataclass.

### 8-1. 필드 정의

| # | 필드 | 타입 | 의미 | 기본값 |
|:-:|------|------|------|:------:|
| 1 | `symbol` | `str` | 종목 식별자 | 필수 |
| 2 | `listing_date` | `date \| None` | 상장일 | `None` |
| 3 | `delisting_date` | `date \| None` | 상장폐지일 | `None` |
| 4 | `primary_exchange` | `str \| None` | 주 거래소 | `None` |
| 5 | `symbol_aliases` | `tuple[str, ...] \| None` | 타 namespace 별칭 | `None` |

### 8-2. listing_age_days 계산 (pure 함수)

```
compute_listing_age(meta: SymbolMetadata, as_of: date) → int | None:
    if meta.listing_date is None → None
    return (as_of - meta.listing_date).days
```

### 8-3. 기존 계약 비침범 확인

| 항목 | 상태 |
|------|:----:|
| MarketDataSnapshot 수정 | ❌ 없음 |
| FundamentalSnapshot 수정 | ❌ 없음 |
| BacktestReadiness 수정 | ❌ 없음 |
| ProviderStatus 수정 | ❌ 없음 |
| 기존 4 ABC 수정 | ❌ 없음 |

**SymbolMetadata는 완전 신규 추가. 기존 Stage 3A 봉인 계약 미침범.**

---

```
CR-048 Stage 3B DataProvider Capability Matrix v1.0
Document ID: GOV-L3-STAGE3B-CAPABILITY-001
Date: 2026-04-03
Authority: A
Status: SUBMITTED
ProviderCapability: 20 fields (frozen dataclass)
Mandatory Capabilities: 4 (volume, atr, adx, available_bars)
Failure Mode Cross-ref: 10 mappings
Symbol Namespace: 5 rules (N1-N5)
Composite Rules: 5 (M1-M5)
listing_age: SymbolMetadata 별도 dataclass로 해소 (A 판정 대기)
```
