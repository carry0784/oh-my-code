"""
OhlcvHistory Model — Phase A (400-Day Backtest Data Plane)
Persistent OHLCV candle storage for deterministic backtest replay.

Design constraints:
  - Backtest data plane ONLY — not connected to runtime/execution path
  - Read-only replay interface for backtesting engine
  - Write path: bulk historical data ingestion only
  - Unique constraint: (exchange, symbol, timeframe, open_time) — one canonical candle per slot
  - Event metadata columns for future event_week_resilience_score

No runtime/business logic dependency. No execution path coupling.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OhlcvHistory(Base):
    """Historical OHLCV candle for backtest replay.

    One row = one candle (exchange + symbol + timeframe + open_time).
    Designed for 400-day bulk storage per symbol.
    """

    __tablename__ = "ohlcv_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # ── Identity ────────────────────────────────────────────────────
    exchange: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(
        String(10), nullable=False, default="1h"
    )  # 1m, 5m, 15m, 1h, 4h, 1d

    # ── OHLCV ───────────────────────────────────────────────────────
    open_time: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )  # Unix ms timestamp
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Event Metadata (future event_week_resilience_score) ─────────
    event_week_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    macro_event_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # FOMC, CPI, NFP, HALVING, etc.
    high_volatility_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # ── Timestamps ──────────────────────────────────────────────────
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ── Constraints ─────────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "exchange", "symbol", "timeframe", "open_time",
            name="uq_ohlcv_canonical_slot",
        ),
        Index(
            "ix_ohlcv_lookup",
            "exchange", "symbol", "timeframe", "open_time",
        ),
    )
