"""Data Provider — abstract interface for screening data sources.

Stage 3A + 3B-1, CR-048.  ABC/Protocol definitions + pure contracts.

This module defines the interface that data provider implementations
must follow.  No concrete implementation exists in Stage 3A.
External API calls, HTTP clients, DB sessions, and network access
are ALL deferred to Stage 3B.

Design reference: design_screening_engine.md §4
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum


# ── Data Quality ────────────────────────────────────────────────────


class DataQuality(str, Enum):
    """Quality grade for provider responses."""

    HIGH = "high"  # Fresh, complete data
    DEGRADED = "degraded"  # Partial data, some fields missing
    STALE = "stale"  # Data older than expected freshness
    UNAVAILABLE = "unavailable"  # Provider returned error or timeout


# ── Data Contracts ──────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Market data for a single symbol at a point in time.

    Used to populate ScreeningInput stages 2-3.
    """

    symbol: str
    timestamp: datetime | None = None
    price_usd: float | None = None
    market_cap_usd: float | None = None
    avg_daily_volume_usd: float | None = None
    spread_pct: float | None = None
    atr_pct: float | None = None
    adx: float | None = None
    price_vs_200ma: float | None = None
    quality: DataQuality = DataQuality.UNAVAILABLE


@dataclass(frozen=True)
class FundamentalSnapshot:
    """Fundamental / on-chain data for a single symbol.

    Used to populate ScreeningInput stage 4.
    """

    symbol: str
    timestamp: datetime | None = None
    per: float | None = None
    roe: float | None = None
    tvl_usd: float | None = None
    active_addresses_trend: float | None = None  # positive = growing
    revenue_growth_pct: float | None = None
    operating_margin_pct: float | None = None
    quality: DataQuality = DataQuality.UNAVAILABLE


@dataclass(frozen=True)
class BacktestReadiness:
    """Backtest data readiness for a single symbol.

    Used to populate ScreeningInput stage 5.
    """

    symbol: str
    available_bars: int | None = None
    sharpe_ratio: float | None = None
    missing_data_pct: float | None = None
    quality: DataQuality = DataQuality.UNAVAILABLE


@dataclass(frozen=True)
class ProviderStatus:
    """Health status of a data provider."""

    provider_name: str
    is_available: bool = False
    last_success: datetime | None = None
    error_message: str | None = None


# ── Abstract Base Classes ───────────────────────────────────────────


class MarketDataProvider(ABC):
    """Interface for market data providers (Stage 2-3 inputs).

    Stage 3A: Interface only.  No implementation permitted.
    Stage 3B: Concrete implementations (CoinGecko, KIS, KRX).
    """

    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketDataSnapshot:
        """Fetch current market data for a symbol.

        Returns MarketDataSnapshot with quality grade.
        Must not raise on provider failure — return UNAVAILABLE quality.
        """
        ...

    @abstractmethod
    async def get_market_data_batch(
        self,
        symbols: list[str],
    ) -> list[MarketDataSnapshot]:
        """Fetch market data for multiple symbols.

        Returns list of snapshots, one per symbol.
        Failed symbols get UNAVAILABLE quality, no exception raised.
        """
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """Check provider availability without fetching data."""
        ...


class FundamentalDataProvider(ABC):
    """Interface for fundamental / on-chain data providers (Stage 4 input).

    Stage 3A: Interface only.  No implementation permitted.
    Stage 3B: Concrete implementations (CoinGecko, KIS, KRX, DeFiLlama).
    """

    @abstractmethod
    async def get_fundamentals(self, symbol: str) -> FundamentalSnapshot:
        """Fetch fundamental data for a symbol.

        Returns FundamentalSnapshot with quality grade.
        Must not raise on provider failure — return UNAVAILABLE quality.
        """
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """Check provider availability without fetching data."""
        ...


class BacktestDataProvider(ABC):
    """Interface for backtest readiness data (Stage 5 input).

    Stage 3A: Interface only.  No implementation permitted.
    Stage 3B: Concrete implementation using local data / backtesting engine.
    """

    @abstractmethod
    async def get_readiness(self, symbol: str) -> BacktestReadiness:
        """Check backtest data readiness for a symbol.

        Returns BacktestReadiness with quality grade.
        Must not raise on provider failure — return UNAVAILABLE quality.
        """
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """Check provider availability without fetching data."""
        ...


# ── Composite Interface ─────────────────────────────────────────────


class ScreeningDataProvider(ABC):
    """Composite interface aggregating all data providers for screening.

    Stage 3A: Interface only.  No implementation permitted.
    Stage 3B: Concrete implementation composing the three providers.
    """

    @abstractmethod
    async def get_screening_data(
        self,
        symbol: str,
    ) -> tuple[MarketDataSnapshot, FundamentalSnapshot, BacktestReadiness]:
        """Fetch all screening data for a symbol in one call.

        Returns tuple of (market, fundamental, backtest) snapshots.
        Each snapshot has its own quality grade.
        """
        ...

    @abstractmethod
    async def get_provider_statuses(self) -> list[ProviderStatus]:
        """Return health status of all underlying providers."""
        ...


# ══════════════════════════════════════════════════════════════════════
# Stage 3B-1 Contracts — Pure dataclasses + policy functions
# ══════════════════════════════════════════════════════════════════════


# ── DataQualityDecision ───────────────────────────────────────────────


class DataQualityDecision(str, Enum):
    """Decision when converting DataProvider output to ScreeningInput.

    Stage 3B-1.  Scope: input quality judgment ONLY.
    NOT permitted to replace qualification judgment or runtime trade decisions.
    """

    OK = "ok"
    PARTIAL_USABLE = "partial_usable"
    PARTIAL_REJECT = "partial_reject"
    STALE_USABLE = "stale_usable"
    STALE_REJECT = "stale_reject"
    INSUFFICIENT_BARS = "insufficient_bars"
    MISSING_LISTING_AGE = "missing_listing_age"
    SYMBOL_NAMESPACE_ERROR = "symbol_namespace_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


# ── SymbolMetadata ────────────────────────────────────────────────────


@dataclass(frozen=True)
class SymbolMetadata:
    """Static metadata for a symbol, separate from OHLCV/indicator data.

    Stage 3B-1.  Resolves the listing_age_days gap identified in
    Boundary Inventory §5-4.  Pure Zone, no runtime/service imports.
    """

    symbol: str
    market: str
    listing_age_days: int | None = None
    is_active: bool = True
    as_of: datetime | None = None
    metadata_origin: str = "unknown"


def compute_listing_age(listing_date: date | None, as_of: date) -> int | None:
    """Compute listing age in days.  Pure function, no I/O."""
    if listing_date is None:
        return None
    return (as_of - listing_date).days


# ── ProviderCapability ────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderCapability:
    """Capability declaration for a DataProvider implementation.

    Stage 3B-1.  Each provider declares what it can supply.
    All bool fields default to False (conservative).
    """

    provider_name: str
    supported_asset_classes: frozenset[str] = field(default_factory=frozenset)
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


def is_screening_capable(cap: ProviderCapability) -> bool:
    """Check if a provider can supply all mandatory screening fields.

    Pure function.  Mandatory: volume, atr, adx, available_bars.
    """
    return all(
        [
            cap.supports_volume,
            cap.supports_atr,
            cap.supports_adx,
            cap.supports_available_bars,
        ]
    )


# ── Stale Policy (System Constants) ──────────────────────────────────
# SP-01: Stale limits are SYSTEM POLICY VALUES, not provider-determined.
# SP-02: Provider supplies facts (timestamp); system decides stale/not.


STALE_LIMITS: dict[tuple[str, str], timedelta] = {
    ("CRYPTO", "price"): timedelta(hours=1),
    ("CRYPTO", "fundamental"): timedelta(hours=24),
    ("US_STOCK", "price"): timedelta(hours=4),
    ("US_STOCK", "fundamental"): timedelta(days=7),
    ("KR_STOCK", "price"): timedelta(hours=4),
    ("KR_STOCK", "fundamental"): timedelta(days=7),
    ("ALL", "backtest"): timedelta(days=30),
}

# Fallback for unknown asset_class/data_type: most conservative limit
_FALLBACK_STALE_LIMIT = timedelta(hours=1)


def check_stale(
    snapshot_timestamp: datetime | None,
    asset_class: str,
    data_type: str,
    now_utc: datetime,
) -> DataQualityDecision:
    """Determine if data is stale based on system policy constants.

    Pure function.  No I/O, no DB, no network.
    SP-03: Only references system policy constants (STALE_LIMITS).
    SP-04: Provider freshness claims are ignored; system policy prevails.

    Args:
        snapshot_timestamp: When the data was produced (UTC).
        asset_class: "CRYPTO", "US_STOCK", "KR_STOCK".
        data_type: "price", "fundamental", "backtest".
        now_utc: Current time (passed in, no clock access).
    """
    if snapshot_timestamp is None:
        return DataQualityDecision.STALE_REJECT

    limit = STALE_LIMITS.get(
        (asset_class, data_type),
        STALE_LIMITS.get(("ALL", data_type), _FALLBACK_STALE_LIMIT),
    )

    # Normalise timezone: treat naive timestamps as UTC
    ts = snapshot_timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age = now_utc - ts
    if age <= limit:
        return DataQualityDecision.OK
    return DataQualityDecision.STALE_REJECT


# ── Partial Data Policy ──────────────────────────────────────────────


def check_partial(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
) -> DataQualityDecision:
    """Check if mandatory screening fields are present.

    Pure function.  Mandatory: volume, atr, adx, available_bars.
    Optional fields missing → PARTIAL_USABLE.
    All present → OK.
    """
    mandatory = [
        market.avg_daily_volume_usd,
        market.atr_pct,
        market.adx,
        backtest.available_bars,
    ]
    if any(v is None for v in mandatory):
        return DataQualityDecision.PARTIAL_REJECT

    optional = [
        market.market_cap_usd,
        market.spread_pct,
        market.price_vs_200ma,
    ]
    if any(v is None for v in optional):
        return DataQualityDecision.PARTIAL_USABLE

    return DataQualityDecision.OK


# ── Symbol Namespace Normalization ───────────────────────────────────


def normalize_symbol(raw_symbol: str, asset_class: str) -> str | None:
    """Normalize a symbol to internal namespace format.

    Pure function.  Returns None on namespace error.

    Internal formats:
      CRYPTO:   "BTC/USDT" (uppercase, slash separator)
      US_STOCK: "AAPL" (uppercase ticker)
      KR_STOCK: "005930" (6-digit code)
    """
    if not raw_symbol or not raw_symbol.strip():
        return None

    raw = raw_symbol.strip()

    if asset_class == "CRYPTO":
        upper = raw.upper()
        if "/" in upper:
            return upper
        return None  # no separator → namespace error

    if asset_class == "US_STOCK":
        upper = raw.upper()
        if upper.isalpha():
            return upper
        return None

    if asset_class == "KR_STOCK":
        digits = raw.strip()
        if digits.isdigit() and len(digits) == 6:
            return digits
        return None

    return None


# ── Failure Mode Recovery Tag ────────────────────────────────────────


class FailureModeRecovery(str, Enum):
    """Whether a failure mode is recoverable.

    Stage 3B-1.  Tags for future retry/fallback policy design (3B-2).
    """

    RECOVERABLE = "recoverable"
    NON_RECOVERABLE = "non_recoverable"


# F1-F9 recovery classification
FAILURE_MODE_RECOVERY: dict[str, FailureModeRecovery] = {
    "F1_EMPTY": FailureModeRecovery.RECOVERABLE,
    "F2_PARTIAL_MANDATORY": FailureModeRecovery.NON_RECOVERABLE,
    "F3_PARTIAL_OPTIONAL": FailureModeRecovery.RECOVERABLE,
    "F4_STALE": FailureModeRecovery.RECOVERABLE,
    "F5_INSUFFICIENT_BARS": FailureModeRecovery.NON_RECOVERABLE,
    "F6_MISSING_LISTING_AGE": FailureModeRecovery.RECOVERABLE,
    "F7_SYMBOL_NAMESPACE": FailureModeRecovery.NON_RECOVERABLE,
    "F8_PROVIDER_TIMEOUT": FailureModeRecovery.RECOVERABLE,
    "F9_QUALITY_CONFLICT": FailureModeRecovery.RECOVERABLE,
}
