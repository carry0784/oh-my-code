"""Stage 3B-2: Provider stubs — sync, fixture-based, no I/O.

Layer 2 (Provider Stub) of the 3-layer architecture.
Test-only.  Must NOT be imported from app/ production code.

Rules:
  SB-01: Fixture data only (constructor-injected)
  SB-02: No httpx/requests/aiohttp/ccxt/sqlalchemy imports
  SB-03: No os.environ/dotenv/open()
  SB-04: No async def (sync only)
  SB-05: Stub → real provider transition requires separate Stage approval
  SB-06: ProviderCapability declared in fixtures, not hardcoded here
  SB-07: tests/ subtree only
  SB-08: screening_transform.py must NOT import this
"""

from __future__ import annotations

from app.services.data_provider import (
    BacktestReadiness,
    FundamentalSnapshot,
    MarketDataSnapshot,
    ProviderCapability,
    ProviderStatus,
)


class StubMarketDataProvider:
    """Fixture-based market data stub.  Sync only, no I/O."""

    def __init__(self, fixtures: dict[str, MarketDataSnapshot]) -> None:
        self._fixtures = fixtures

    def get_market_data(self, symbol: str) -> MarketDataSnapshot:
        return self._fixtures.get(symbol, MarketDataSnapshot(symbol=symbol))

    def get_market_data_batch(
        self,
        symbols: list[str],
    ) -> list[MarketDataSnapshot]:
        return [self.get_market_data(s) for s in symbols]

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            provider_name="stub_market",
            is_available=True,
        )


class StubBacktestDataProvider:
    """Fixture-based backtest data stub.  Sync only, no I/O."""

    def __init__(self, fixtures: dict[str, BacktestReadiness]) -> None:
        self._fixtures = fixtures

    def get_readiness(
        self,
        symbol: str,
        timeframe: str = "1h",
        min_bars: int = 500,
    ) -> BacktestReadiness:
        return self._fixtures.get(symbol, BacktestReadiness(symbol=symbol))

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            provider_name="stub_backtest",
            is_available=True,
        )


class StubFundamentalDataProvider:
    """Fixture-based fundamental data stub.  Sync only, no I/O."""

    def __init__(self, fixtures: dict[str, FundamentalSnapshot]) -> None:
        self._fixtures = fixtures

    def get_fundamentals(self, symbol: str) -> FundamentalSnapshot:
        return self._fixtures.get(symbol, FundamentalSnapshot(symbol=symbol))

    def health_check(self) -> ProviderStatus:
        return ProviderStatus(
            provider_name="stub_fundamental",
            is_available=True,
        )


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
