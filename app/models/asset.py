"""Asset Registry models — Symbol + ScreeningResult + sector/theme enums.

Phase 2 of CR-048.  Provides the 3-state (CORE/WATCH/EXCLUDED) symbol
registry and screening audit trail.

AssetClass is defined in strategy_registry.py and re-exported here
for convenience.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    String,
    Float,
    Integer,
    DateTime,
    Text,
    Boolean,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.strategy_registry import AssetClass  # re-export


# ── Enums ────────────────────────────────────────────────────────────


class AssetSector(str, Enum):
    """Allowed + excluded sectors across all asset classes."""

    # Crypto — allowed
    LAYER1 = "layer1"
    DEFI = "defi"
    AI = "ai"
    INFRA = "infra"

    # Crypto — excluded
    MEME = "meme"
    GAMEFI = "gamefi"
    LOW_LIQUIDITY_NEW_TOKEN = "low_liquidity_new_token"

    # US Stock — allowed
    TECH = "tech"
    HEALTHCARE = "healthcare"
    ENERGY = "energy"
    FINANCE = "finance"

    # US Stock — excluded
    HIGH_VALUATION_PURE_SW = "high_valuation_pure_sw"
    WEAK_CONSUMER_BETA = "weak_consumer_beta"

    # KR Stock — allowed
    SEMICONDUCTOR = "semiconductor"
    IT = "it"
    KR_FINANCE = "kr_finance"
    AUTOMOTIVE = "automotive"

    # KR Stock — excluded
    OIL_SENSITIVE = "oil_sensitive"
    LOW_LIQUIDITY_THEME = "low_liquidity_theme"


class AssetTheme(str, Enum):
    """Thematic tags for cross-sector grouping."""

    AI_SEMICONDUCTOR = "ai_semiconductor"
    CLOUD = "cloud"
    EV = "ev"
    RENEWABLE_ENERGY = "renewable_energy"
    DEFI_YIELD = "defi_yield"
    L1_SCALING = "l1_scaling"
    BIOTECH = "biotech"
    NONE = "none"


class SymbolStatus(str, Enum):
    """3-state symbol lifecycle."""

    CORE = "core"
    WATCH = "watch"
    EXCLUDED = "excluded"


class SymbolStatusReason(str, Enum):
    """Standardized reason codes for status transitions."""

    # EXCLUDED reasons
    EXCLUSION_BASELINE = "exclusion_baseline"
    LIQUIDITY_BELOW_THRESHOLD = "liquidity_below_threshold"
    DATA_INSUFFICIENT = "data_insufficient"
    MANUAL_EXCLUSION = "manual_exclusion"

    # WATCH reasons
    SCREENING_PARTIAL_PASS = "screening_partial_pass"
    CORE_DEMOTED = "core_demoted"
    TTL_EXPIRED = "ttl_expired"
    REGIME_CHANGE = "regime_change"

    # CORE reasons
    SCREENING_FULL_PASS = "screening_full_pass"
    MANUAL_PROMOTION = "manual_promotion"


class ScreeningStageReason(str, Enum):
    """Per-stage reason codes — identifies which specific check caused WATCH/EXCLUDED."""

    # Stage 1: Exclusion
    EXCLUDED_SECTOR = "excluded_sector"
    LOW_MARKET_CAP = "low_market_cap"
    RECENT_LISTING = "recent_listing"

    # Stage 2: Liquidity
    LOW_VOLUME = "low_volume"
    WIDE_SPREAD = "wide_spread"
    THIN_ORDER_BOOK = "thin_order_book"

    # Stage 3: Technical
    LOW_ATR = "low_atr"
    HIGH_ATR = "high_atr"
    LOW_ADX = "low_adx"
    BELOW_200MA = "below_200ma"

    # Stage 4: Fundamental
    HIGH_PER = "high_per"
    LOW_ROE = "low_roe"
    LOW_TVL = "low_tvl"
    FUNDAMENTAL_PLACEHOLDER = "fundamental_placeholder"

    # Stage 5: Backtest
    INSUFFICIENT_BARS = "insufficient_bars"
    NEGATIVE_SHARPE = "negative_sharpe"
    HIGH_MISSING_DATA = "high_missing_data"
    BACKTEST_PLACEHOLDER = "backtest_placeholder"

    # All pass
    ALL_STAGES_PASSED = "all_stages_passed"


# ── Symbol Canonicalization ──────────────────────────────────────────

# Canonical symbol format rules:
#   CRYPTO   : "BASE/QUOTE"   e.g. "SOL/USDT", "BTC/USDT", "ETH/USDT"
#   US_STOCK : "TICKER"       e.g. "AAPL", "NVDA", "MSFT"
#   KR_STOCK : "6-digit code" e.g. "005930", "000660", "035420"
#
# All symbols are stored uppercase. Leading zeros preserved for KR_STOCK.


def canonicalize_symbol(raw: str, asset_class: AssetClass) -> str:
    """Normalize a symbol string to canonical form.

    Rules:
      - Strip whitespace, uppercase
      - CRYPTO: ensure BASE/QUOTE format
      - US_STOCK: ticker only (no exchange prefix)
      - KR_STOCK: 6-digit zero-padded code
    """
    s = raw.strip().upper()

    if asset_class == AssetClass.KR_STOCK:
        # Strip non-digit, zero-pad to 6
        digits = "".join(c for c in s if c.isdigit())
        return digits.zfill(6)

    if asset_class == AssetClass.US_STOCK:
        # Remove any exchange prefix like "NYSE:" or "NASDAQ:"
        if ":" in s:
            s = s.split(":")[-1]
        return s

    # CRYPTO: already expected as BASE/QUOTE
    return s


# ── Excluded sector set (derived from shared constitution source) ─────

from app.core.constitution import FORBIDDEN_SECTOR_VALUES

EXCLUDED_SECTORS: frozenset[AssetSector] = frozenset(
    AssetSector(v) for v in FORBIDDEN_SECTOR_VALUES
)


# ── Symbol Model ─────────────────────────────────────────────────────


class Symbol(Base):
    """Universe symbol — the central asset registry entry."""

    __tablename__ = "symbols"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Identity
    symbol: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))

    # Classification
    asset_class: Mapped[AssetClass] = mapped_column(
        SQLEnum(AssetClass, values_callable=lambda e: [x.value for x in e]),
    )
    sector: Mapped[AssetSector] = mapped_column(
        SQLEnum(AssetSector, values_callable=lambda e: [x.value for x in e]),
    )
    theme: Mapped[AssetTheme] = mapped_column(
        SQLEnum(AssetTheme, values_callable=lambda e: [x.value for x in e]),
        default=AssetTheme.NONE,
    )

    # Market data
    exchanges: Mapped[str] = mapped_column(Text)  # JSON array of broker codes
    market_cap_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_daily_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 3-state status
    status: Mapped[SymbolStatus] = mapped_column(
        SQLEnum(SymbolStatus, values_callable=lambda e: [x.value for x in e]),
        default=SymbolStatus.WATCH,
        index=True,
    )
    status_reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Screening
    screening_score: Mapped[float] = mapped_column(Float, default=0.0)
    qualification_status: Mapped[str] = mapped_column(
        String(20), default="unchecked"
    )  # unchecked / pass / fail — separate from screening status
    promotion_eligibility_status: Mapped[str] = mapped_column(
        String(30), default="unchecked"
    )  # unchecked / eligible_for_paper / paper_hold / ... — separate from qualification
    paper_evaluation_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending / hold / pass / fail / quarantine — separate from promotion eligibility
    paper_pass_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )  # explicit timestamp of last paper evaluation PASS — freshness anchor
    regime_allow: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array

    # Candidate TTL
    candidate_expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Operational flags
    paper_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    live_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)

    # Override audit (who/why/when for manual_override)
    override_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Broker policy reference
    broker_policy: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── ScreeningResult Model ────────────────────────────────────────────


class ScreeningResult(Base):
    """Append-only screening audit — records each screening pass/fail."""

    __tablename__ = "screening_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    symbol_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)

    # 5-stage screening results (each bool = pass/fail)
    stage1_exclusion: Mapped[bool] = mapped_column(Boolean, default=False)
    stage2_liquidity: Mapped[bool] = mapped_column(Boolean, default=False)
    stage3_technical: Mapped[bool] = mapped_column(Boolean, default=False)
    stage4_fundamental: Mapped[bool] = mapped_column(Boolean, default=False)
    stage5_backtest: Mapped[bool] = mapped_column(Boolean, default=False)

    # Aggregate
    all_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)

    # Per-stage reason codes (which specific check failed/passed)
    stage_reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Detail
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Result action
    resulting_status: Mapped[SymbolStatus] = mapped_column(
        SQLEnum(SymbolStatus, values_callable=lambda e: [x.value for x in e]),
    )

    screened_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── SymbolStatusAudit Model ─────────────────────────────────────────


class SymbolStatusAudit(Base):
    """Append-only audit trail for symbol status transitions.

    Static table definition (Stage 2A).  Actual writes are Stage 2B.
    Records who/what/when/why for every status change.
    """

    __tablename__ = "symbol_status_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    symbol_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)

    # Transition
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    reason_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Actor
    triggered_by: Mapped[str] = mapped_column(String(100))  # system|operator|screener|ttl
    approval_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # low|medium|high

    # Context
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Timestamp
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
