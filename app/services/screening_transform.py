"""Stage 3B-2: ScreeningInput Transformation — pure functions only.

Converts DataProvider output to ScreeningInput via validate → build pipeline.
No async, no I/O, no DB, no network.

Layer 1 (Pure Transformation) of the 3-layer architecture:
  L1: screening_transform.py  (this file)
  L2: tests/stubs/screening_stubs.py  (test-only)
  L3: runtime/service path  (BLOCKED in 3B-2)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.models.asset import AssetClass, AssetSector
from app.services.data_provider import (
    BacktestReadiness,
    DataQualityDecision,
    FundamentalSnapshot,
    MarketDataSnapshot,
    SymbolMetadata,
    check_partial,
    check_stale,
    normalize_symbol,
)
from app.services.symbol_screener import ScreeningInput


# ── Constants ────────────────────────────────────────────────────────


_REJECT_DECISIONS: frozenset[DataQualityDecision] = frozenset(
    {
        DataQualityDecision.PARTIAL_REJECT,
        DataQualityDecision.STALE_REJECT,
        DataQualityDecision.SYMBOL_NAMESPACE_ERROR,
        DataQualityDecision.PROVIDER_UNAVAILABLE,
    }
)


# ── ScreeningInputSource (audit-only) ────────────────────────────────


@dataclass(frozen=True)
class ScreeningInputSource:
    """Records WHERE each ScreeningInput field value came from.

    Audit-only.  Does NOT influence screener computation.
    Paired with ScreeningInput in TransformResult.
    """

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


# ── TransformResult ──────────────────────────────────────────────────


@dataclass(frozen=True)
class TransformResult:
    """Result of the validate+build pipeline.

    Invariants:
      - REJECT decision → screening_input is None, source is None
      - OK/USABLE decision → screening_input is not None, source is not None
    """

    decision: DataQualityDecision
    screening_input: ScreeningInput | None = None
    source: ScreeningInputSource | None = None


# ── Validate ─────────────────────────────────────────────────────────


def validate_screening_preconditions(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    metadata: SymbolMetadata | None,
    asset_class: str,
    now_utc: datetime,
) -> DataQualityDecision:
    """Pre-validate before building ScreeningInput.

    Pure function.  Fail-fast order (fixed):
      1. normalize_symbol → SYMBOL_NAMESPACE_ERROR
      2. check_stale → STALE_REJECT
      3. check_partial → PARTIAL_REJECT or PARTIAL_USABLE or OK
    """
    # Step 1: namespace
    normalized = normalize_symbol(market.symbol, asset_class)
    if normalized is None:
        return DataQualityDecision.SYMBOL_NAMESPACE_ERROR

    # Step 2: staleness
    stale = check_stale(market.timestamp, asset_class, "price", now_utc)
    if stale == DataQualityDecision.STALE_REJECT:
        return DataQualityDecision.STALE_REJECT

    # Step 3: partial data
    partial = check_partial(market, backtest)
    return partial


# ── Build ────────────────────────────────────────────────────────────


def build_screening_input(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    fundamental: FundamentalSnapshot | None,
    metadata: SymbolMetadata | None,
    asset_class: AssetClass,
    sector: AssetSector,
) -> ScreeningInput:
    """Convert DataProvider output to ScreeningInput.

    Pure function.  Caller MUST call validate_screening_preconditions() first
    and only proceed if the result is not in _REJECT_DECISIONS.
    """
    return ScreeningInput(
        symbol=market.symbol,
        asset_class=asset_class,
        sector=sector,
        market_cap_usd=market.market_cap_usd,
        listing_age_days=(metadata.listing_age_days if metadata is not None else None),
        avg_daily_volume_usd=market.avg_daily_volume_usd,
        spread_pct=market.spread_pct,
        atr_pct=market.atr_pct,
        adx=market.adx,
        price_vs_200ma=market.price_vs_200ma,
        per=fundamental.per if fundamental is not None else None,
        roe=fundamental.roe if fundamental is not None else None,
        tvl_usd=fundamental.tvl_usd if fundamental is not None else None,
        available_bars=backtest.available_bars,
        sharpe_ratio=backtest.sharpe_ratio,
        missing_data_pct=backtest.missing_data_pct,
    )


# ── Full Pipeline ────────────────────────────────────────────────────


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

    Pure function.  No async, no I/O, no DB.
    """
    decision = validate_screening_preconditions(
        market,
        backtest,
        metadata,
        asset_class.value,
        now_utc,
    )

    if decision in _REJECT_DECISIONS:
        return TransformResult(decision=decision)

    screening_input = build_screening_input(
        market,
        backtest,
        fundamental,
        metadata,
        asset_class,
        sector,
    )

    source = ScreeningInputSource(
        symbol=market.symbol,
        market_provider=market_provider,
        backtest_provider=backtest_provider,
        fundamental_provider=fundamental_provider,
        metadata_provider=metadata_provider,
        market_timestamp=market.timestamp,
        stale_decision=decision,
        partial_decision=decision,
        build_timestamp=now_utc,
    )

    return TransformResult(
        decision=decision,
        screening_input=screening_input,
        source=source,
    )
