# CR-048 Stage 3B-2 Stub Contract

**문서 ID:** DESIGN-STAGE3B2-002
**작성일:** 2026-04-03
**CR:** CR-048
**변경 등급:** L0 (설계 문서)
**전제:** Stage 3B-1 SEALED (5075/5075 PASS)

---

## 1. ABC Sync Wrapper 전략

Stage 3A ABC는 `async def`로 정의되었다. Stub은 **sync 전용**이어야 한다.

**해법:** Stub은 ABC를 직접 상속하지 않고, **동일 메서드 시그니처의 sync 구현체**로 작성.
테스트에서 structural subtyping (메서드 존재 확인)으로 계약 준수를 확인.

**이유:**
- async ABC를 sync로 상속하면 coroutine 미대기 RuntimeWarning 발생 (Stage 2B OBS-001과 동일 패턴 방지)
- Stub 목적은 "계약 형태 검증"이지 "async 런타임 동작 검증"이 아님
- sync stub으로 pure transformation 테스트를 경고 없이 실행 가능

---

## 2. Stub 클래스 정의

### 2.1 StubMarketDataProvider

```python
class StubMarketDataProvider:
    """Fixture-based market data stub. Sync only, no I/O."""

    def __init__(self, fixtures: dict[str, MarketDataSnapshot]) -> None:
        self._fixtures = fixtures

    def get_market_data(self, symbol: str) -> MarketDataSnapshot:
        return self._fixtures.get(symbol, MarketDataSnapshot(symbol=symbol))

    def get_market_data_batch(self, symbols: list[str]) -> list[MarketDataSnapshot]:
        return [self.get_market_data(s) for s in symbols]

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(provider_name="stub_market", is_available=True)
```

**fail-closed:** fixture에 없는 symbol → MarketDataSnapshot(symbol=symbol) → quality=UNAVAILABLE → validate REJECT.

---

### 2.2 StubBacktestDataProvider

```python
class StubBacktestDataProvider:
    """Fixture-based backtest data stub. Sync only, no I/O."""

    def __init__(self, fixtures: dict[str, BacktestReadiness]) -> None:
        self._fixtures = fixtures

    def get_readiness(self, symbol: str, timeframe: str = "1h",
                      min_bars: int = 500) -> BacktestReadiness:
        return self._fixtures.get(symbol, BacktestReadiness(symbol=symbol))

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(provider_name="stub_backtest", is_available=True)
```

---

### 2.3 StubFundamentalDataProvider

```python
class StubFundamentalDataProvider:
    """Fixture-based fundamental data stub. Sync only, no I/O."""

    def __init__(self, fixtures: dict[str, FundamentalSnapshot]) -> None:
        self._fixtures = fixtures

    def get_fundamentals(self, symbol: str) -> FundamentalSnapshot:
        return self._fixtures.get(symbol, FundamentalSnapshot(symbol=symbol))

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(provider_name="stub_fundamental", is_available=True)
```

---

### 2.4 StubScreeningDataProvider

```python
class StubScreeningDataProvider:
    """Composes market + backtest + fundamental stubs."""

    def __init__(
        self,
        market: StubMarketDataProvider,
        backtest: StubBacktestDataProvider,
        fundamental: StubFundamentalDataProvider,
    ) -> None:
        self.market = market
        self.backtest = backtest
        self.fundamental = fundamental

    def get_provider_statuses(self) -> list[ProviderStatus]:
        return [
            self.market.health_check(),
            self.backtest.health_check(),
            self.fundamental.health_check(),
        ]
```

---

## 3. Stub 불변 규칙

| 규칙 ID | 내용 | 검증 방법 |
|---------|------|-----------|
| SB-01 | Stub은 fixture data만 반환 | AST: 메서드 body에 네트워크/DB 호출 없음 |
| SB-02 | httpx, requests, aiohttp, ccxt, sqlalchemy import 금지 | import graph |
| SB-03 | os.environ, dotenv, open() 접근 금지 | AST |
| SB-04 | async def 금지 (sync only) | AST: AsyncFunctionDef 없음 |
| SB-05 | Stub → real provider 전환은 별도 Stage 승인 | 정책 |
| SB-06 | ProviderCapability는 fixture에서 선언 | capability가 fixtures 파일에만 존재 |
| SB-07 | `tests/` 하위에만 배치 | 파일 경로 |
| SB-08 | screening_transform.py에서 stub import 금지 | import graph |

---

## 4. Stub ProviderCapability 표준 프로파일

| Profile | asset_classes | vol | spr | atr | adx | ma | mcap | per | roe | tvl | bars | shrp | miss | list | capable |
|---------|:------------:|:---:|:---:|:---:|:---:|:--:|:----:|:---:|:---:|:---:|:----:|:----:|:----:|:----:|:-------:|
| `full_crypto` | {CRYPTO} | T | T | T | T | T | T | F | F | T | T | T | T | T | **YES** |
| `full_us_stock` | {US_STOCK} | T | T | T | T | T | T | T | T | F | T | T | T | T | **YES** |
| `full_kr_stock` | {KR_STOCK} | T | T | T | T | T | T | F | F | F | T | T | T | T | **YES** |
| `minimal_crypto` | {CRYPTO} | T | F | T | T | F | F | F | F | F | T | F | F | F | **YES** |
| `degraded_crypto` | {CRYPTO} | T | F | T | F | F | F | F | F | F | F | F | F | F | **NO** |
| `empty` | {} | F | F | F | F | F | F | F | F | F | F | F | F | F | **NO** |

**검증:** 각 프로파일의 `is_screening_capable()` 결과가 capable 열과 일치해야 함.

---

## 5. Fixture 주입 패턴

```python
from tests.fixtures.screening_fixtures import (
    FIXTURE_BTC_MARKET, FIXTURE_BTC_BACKTEST,
    FIXTURE_SOL_MARKET, FIXTURE_SOL_BACKTEST,
    FIXTURE_AAPL_MARKET, FIXTURE_AAPL_BACKTEST, FIXTURE_AAPL_FUNDAMENTAL,
    FIXTURE_005930_MARKET, FIXTURE_005930_BACKTEST,
)

market_stub = StubMarketDataProvider({
    "BTC/USDT": FIXTURE_BTC_MARKET,
    "SOL/USDT": FIXTURE_SOL_MARKET,
    "AAPL": FIXTURE_AAPL_MARKET,
    "005930": FIXTURE_005930_MARKET,
})
```

---

## 6. 미등록 symbol 동작 (fail-closed)

| 시나리오 | Stub 반환 | quality | validate 결과 |
|----------|-----------|:-------:|:-------------:|
| fixture에 있는 symbol | 해당 fixture | HIGH 등 | OK / PARTIAL_USABLE |
| fixture에 없는 symbol | 빈 snapshot | **UNAVAILABLE** | **PARTIAL_REJECT** |
| 빈 fixture map | 모든 symbol → 빈 snapshot | UNAVAILABLE | **전부 REJECT** |

---

```
CR-048 Stage 3B-2 Stub Contract v1.0
Document ID: DESIGN-STAGE3B2-002
Date: 2026-04-03
Status: SUBMITTED
```
