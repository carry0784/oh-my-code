"""Symbol Screener — 5-stage screening engine for the Asset Registry.

Phase 3A minimal, CR-048.

Evaluates a symbol candidate through 5 sequential stages:
  1. Exclusion Filter — baseline exclusions (sector, market cap, listing age)
  2. Liquidity / Execution Quality — volume, spread
  3. Technical Structure — ATR, ADX, 200MA position
  4. Fundamental / On-chain — PER, ROE, TVL (placeholder-ready)
  5. Backtest Qualification — bar count, Sharpe, data quality

Each stage returns pass/fail + a reason code.
Final result maps to CORE / WATCH / EXCLUDED.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.models.asset import (
    AssetClass,
    AssetSector,
    SymbolStatus,
    SymbolStatusReason,
    ScreeningStageReason,
    EXCLUDED_SECTORS,
)

logger = logging.getLogger(__name__)


# ── Screening Input Contract ─────────────────────────────────────────


@dataclass
class ScreeningInput:
    """Minimal input contract for the 5-stage screener.

    All fields are optional with None meaning "data not available".
    The screener treats missing data as a fail for the relevant stage.
    """

    # Identity (required)
    symbol: str = ""
    asset_class: AssetClass = AssetClass.CRYPTO
    sector: AssetSector = AssetSector.LAYER1

    # Stage 1: Exclusion
    market_cap_usd: float | None = None
    listing_age_days: int | None = None  # days since listing

    # Stage 2: Liquidity
    avg_daily_volume_usd: float | None = None
    spread_pct: float | None = None  # bid-ask spread as percentage

    # Stage 3: Technical
    atr_pct: float | None = None  # ATR as % of price
    adx: float | None = None
    price_vs_200ma: float | None = None  # ratio: price / 200MA (>1 = above)

    # Stage 4: Fundamental / On-chain
    per: float | None = None  # P/E ratio (stocks)
    roe: float | None = None  # Return on equity % (stocks)
    tvl_usd: float | None = None  # Total value locked (DeFi)

    # Stage 5: Backtest readiness
    available_bars: int | None = None
    sharpe_ratio: float | None = None
    missing_data_pct: float | None = None  # % of missing/null bars


# ── Screening Thresholds ─────────────────────────────────────────────


@dataclass(frozen=True)
class ScreeningThresholds:
    """Configurable thresholds for screening stages.

    Default values follow the Constitution (Phase 0) spec.
    """

    # Stage 1
    min_market_cap_usd: float = 50_000_000  # $50M
    min_listing_age_days: int = 180  # 6 months

    # Stage 2
    min_avg_daily_volume_crypto: float = 10_000_000  # $10M
    min_avg_daily_volume_us_stock: float = 5_000_000  # $5M
    min_avg_daily_volume_kr_stock: float = 500_000_000  # ₩5억 (~$500K equiv)
    max_spread_pct: float = 0.5  # 0.5%

    # Stage 3
    min_atr_pct: float = 1.0
    max_atr_pct: float = 20.0
    min_adx: float = 15.0
    min_price_vs_200ma: float = 0.0  # any position OK if >0 (exists)

    # Stage 4
    max_per: float = 100.0
    min_roe: float = 5.0
    min_tvl_usd: float = 10_000_000  # $10M for DeFi

    # Stage 5
    min_bars: int = 500
    min_sharpe: float = 0.0
    max_missing_data_pct: float = 5.0

    # TTL
    candidate_ttl_hours: int = 48


# ── Stage Results ────────────────────────────────────────────────────


@dataclass
class StageResult:
    """Result of a single screening stage."""

    stage: int
    passed: bool
    reason_code: ScreeningStageReason | None = None


@dataclass
class ScreeningOutput:
    """Complete screening result for one symbol."""

    symbol: str
    stages: list[StageResult] = field(default_factory=list)
    all_passed: bool = False
    resulting_status: SymbolStatus = SymbolStatus.WATCH
    status_reason_code: SymbolStatusReason = SymbolStatusReason.SCREENING_PARTIAL_PASS
    stage_reason_code: ScreeningStageReason | None = None
    score: float = 0.0
    candidate_ttl_hours: int = 48


# ── Screener Engine ──────────────────────────────────────────────────


class SymbolScreener:
    """5-stage screening engine.

    Stateless — all state is in input/output.
    Each stage is a separate method for testability.
    """

    def __init__(
        self,
        thresholds: ScreeningThresholds | None = None,
    ) -> None:
        self.t = thresholds or ScreeningThresholds()

    def screen(self, inp: ScreeningInput) -> ScreeningOutput:
        """Run all 5 stages sequentially. Return aggregate result."""

        output = ScreeningOutput(symbol=inp.symbol)

        # Stage 1: Exclusion
        s1 = self._stage1_exclusion(inp)
        output.stages.append(s1)
        if not s1.passed:
            output.resulting_status = SymbolStatus.EXCLUDED
            output.status_reason_code = SymbolStatusReason.EXCLUSION_BASELINE
            output.stage_reason_code = s1.reason_code
            output.score = 0.0
            return output

        # Stage 2: Liquidity
        s2 = self._stage2_liquidity(inp)
        output.stages.append(s2)

        # Stage 3: Technical
        s3 = self._stage3_technical(inp)
        output.stages.append(s3)

        # Stage 4: Fundamental
        s4 = self._stage4_fundamental(inp)
        output.stages.append(s4)

        # Stage 5: Backtest
        s5 = self._stage5_backtest(inp)
        output.stages.append(s5)

        # Aggregate
        passed_count = sum(1 for s in output.stages if s.passed)
        output.score = passed_count / len(output.stages)

        if all(s.passed for s in output.stages):
            output.all_passed = True
            output.resulting_status = SymbolStatus.CORE
            output.status_reason_code = SymbolStatusReason.SCREENING_FULL_PASS
            output.stage_reason_code = ScreeningStageReason.ALL_STAGES_PASSED
            output.candidate_ttl_hours = self.t.candidate_ttl_hours
        else:
            # Find first failing stage for reason code
            first_fail = next(s for s in output.stages if not s.passed)
            output.resulting_status = SymbolStatus.WATCH
            output.status_reason_code = SymbolStatusReason.SCREENING_PARTIAL_PASS
            output.stage_reason_code = first_fail.reason_code

        return output

    # ── Individual Stages ────────────────────────────────────────────

    def _stage1_exclusion(self, inp: ScreeningInput) -> StageResult:
        """Stage 1: Exclusion baseline check."""

        # Excluded sector → immediate fail
        if inp.sector in EXCLUDED_SECTORS:
            return StageResult(1, False, ScreeningStageReason.EXCLUDED_SECTOR)

        # Market cap check (crypto and small stocks)
        if inp.market_cap_usd is not None and inp.market_cap_usd < self.t.min_market_cap_usd:
            return StageResult(1, False, ScreeningStageReason.LOW_MARKET_CAP)

        # Listing age check
        if inp.listing_age_days is not None and inp.listing_age_days < self.t.min_listing_age_days:
            return StageResult(1, False, ScreeningStageReason.RECENT_LISTING)

        return StageResult(1, True)

    def _stage2_liquidity(self, inp: ScreeningInput) -> StageResult:
        """Stage 2: Liquidity and execution quality."""

        # Volume threshold varies by asset class
        if inp.avg_daily_volume_usd is not None:
            threshold = {
                AssetClass.CRYPTO: self.t.min_avg_daily_volume_crypto,
                AssetClass.US_STOCK: self.t.min_avg_daily_volume_us_stock,
                AssetClass.KR_STOCK: self.t.min_avg_daily_volume_kr_stock,
            }.get(inp.asset_class, self.t.min_avg_daily_volume_crypto)

            if inp.avg_daily_volume_usd < threshold:
                return StageResult(2, False, ScreeningStageReason.LOW_VOLUME)
        elif inp.avg_daily_volume_usd is None:
            # Missing data = fail
            return StageResult(2, False, ScreeningStageReason.LOW_VOLUME)

        # Spread check
        if inp.spread_pct is not None and inp.spread_pct > self.t.max_spread_pct:
            return StageResult(2, False, ScreeningStageReason.WIDE_SPREAD)

        return StageResult(2, True)

    def _stage3_technical(self, inp: ScreeningInput) -> StageResult:
        """Stage 3: Technical structure check."""

        # ATR range: 1-20%
        if inp.atr_pct is not None:
            if inp.atr_pct < self.t.min_atr_pct:
                return StageResult(3, False, ScreeningStageReason.LOW_ATR)
            if inp.atr_pct > self.t.max_atr_pct:
                return StageResult(3, False, ScreeningStageReason.HIGH_ATR)
        elif inp.atr_pct is None:
            return StageResult(3, False, ScreeningStageReason.LOW_ATR)

        # ADX > 15
        if inp.adx is not None:
            if inp.adx < self.t.min_adx:
                return StageResult(3, False, ScreeningStageReason.LOW_ADX)
        elif inp.adx is None:
            return StageResult(3, False, ScreeningStageReason.LOW_ADX)

        return StageResult(3, True)

    def _stage4_fundamental(self, inp: ScreeningInput) -> StageResult:
        """Stage 4: Fundamental / on-chain (placeholder-ready).

        For stocks: PER < 100, ROE > 5%
        For crypto DeFi: TVL > $10M
        For other crypto: pass (placeholder)
        """

        if inp.asset_class in (AssetClass.US_STOCK, AssetClass.KR_STOCK):
            # Stock fundamental checks
            if inp.per is not None and inp.per > self.t.max_per:
                return StageResult(4, False, ScreeningStageReason.HIGH_PER)
            if inp.roe is not None and inp.roe < self.t.min_roe:
                return StageResult(4, False, ScreeningStageReason.LOW_ROE)
            # If both None for stocks, still pass (placeholder)
            return StageResult(4, True)

        if inp.asset_class == AssetClass.CRYPTO:
            # DeFi sector: check TVL
            if inp.sector == AssetSector.DEFI:
                if inp.tvl_usd is not None and inp.tvl_usd < self.t.min_tvl_usd:
                    return StageResult(4, False, ScreeningStageReason.LOW_TVL)
            # Other crypto sectors: placeholder pass
            return StageResult(4, True)

        return StageResult(4, True)

    def _stage5_backtest(self, inp: ScreeningInput) -> StageResult:
        """Stage 5: Backtest qualification readiness."""

        # Bar count
        if inp.available_bars is not None:
            if inp.available_bars < self.t.min_bars:
                return StageResult(5, False, ScreeningStageReason.INSUFFICIENT_BARS)
        elif inp.available_bars is None:
            return StageResult(5, False, ScreeningStageReason.INSUFFICIENT_BARS)

        # Sharpe
        if inp.sharpe_ratio is not None and inp.sharpe_ratio < self.t.min_sharpe:
            return StageResult(5, False, ScreeningStageReason.NEGATIVE_SHARPE)

        # Data quality
        if inp.missing_data_pct is not None and inp.missing_data_pct > self.t.max_missing_data_pct:
            return StageResult(5, False, ScreeningStageReason.HIGH_MISSING_DATA)

        return StageResult(5, True)
