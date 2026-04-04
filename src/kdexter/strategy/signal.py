"""
Signal Model -- K-Dexter AOS v4

Defines the standard signal format that flows through the L4~L8 pipeline.
A Signal represents a trading opportunity detected by strategy logic.

Pipeline flow:
  Signal -> RiskFilter -> PositionSizer -> ExecutionCell -> TCL
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SignalDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalStrength(Enum):
    STRONG = "STRONG"        # high confidence
    MODERATE = "MODERATE"    # medium confidence
    WEAK = "WEAK"            # low confidence -- may be filtered


class SignalStatus(Enum):
    PENDING = "PENDING"          # created, not yet processed
    RISK_APPROVED = "RISK_APPROVED"  # passed risk filter
    RISK_REJECTED = "RISK_REJECTED"  # blocked by risk
    SIZED = "SIZED"              # position size calculated
    DISPATCHED = "DISPATCHED"    # sent to TCL
    FILLED = "FILLED"           # order confirmed
    REJECTED = "REJECTED"       # rejected at any stage
    EXPIRED = "EXPIRED"         # signal too old


@dataclass
class Signal:
    """
    Standard signal format for the strategy pipeline.

    Created by strategy logic (L6 agents), consumed by:
      - L3 RiskFilter: checks drawdown, exposure, forbidden pairs
      - L8 PositionSizer: calculates quantity from signal + account state
      - L8 ExecutionCell: converts to TCLCommand and dispatches
    """
    signal_id: str
    strategy_id: str               # which strategy produced this
    exchange: str                   # "binance", "upbit", etc.
    symbol: str                     # "BTC/USDT", "ETH/KRW", etc.
    direction: SignalDirection
    strength: SignalStrength = SignalStrength.MODERATE

    # Price context
    entry_price: Optional[float] = None    # desired entry (None = market)
    stop_loss: Optional[float] = None      # risk boundary
    take_profit: Optional[float] = None    # target exit

    # Risk params (filled by strategy, validated by RiskFilter)
    max_risk_pct: float = 0.02             # max % of account to risk
    max_position_pct: float = 0.10         # max % of account in this position

    # Pipeline state
    status: SignalStatus = SignalStatus.PENDING
    quantity: Optional[float] = None       # filled by PositionSizer
    rejection_reason: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    ttl_seconds: int = 300                 # signal expires after 5 min

    @property
    def is_expired(self) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    def approve_risk(self) -> None:
        self.status = SignalStatus.RISK_APPROVED
        self.processed_at = datetime.now(timezone.utc)

    def reject(self, reason: str) -> None:
        self.status = SignalStatus.RISK_REJECTED
        self.rejection_reason = reason
        self.processed_at = datetime.now(timezone.utc)

    def set_size(self, quantity: float) -> None:
        self.quantity = quantity
        self.status = SignalStatus.SIZED

    def mark_dispatched(self) -> None:
        self.status = SignalStatus.DISPATCHED

    def mark_filled(self) -> None:
        self.status = SignalStatus.FILLED

    def mark_expired(self) -> None:
        self.status = SignalStatus.EXPIRED
