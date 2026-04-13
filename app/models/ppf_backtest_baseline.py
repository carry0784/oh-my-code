"""PPF Backtest Baseline — stores Phase A backtest results for Phase B comparison.

Records aggregated PPF gate metrics from historical bar-by-bar evaluation so that
live/shadow Phase B results can be diffed against the sealed baseline.

DML contract:
  INSERT: allowed (ppf_backtest tasks only, one row per sealed run)
  SELECT: allowed (read-only queries)
  UPDATE: PROHIBITED (baseline rows are immutable once written)
  DELETE: PROHIBITED

FK: ZERO (independent of all existing tables)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PPFBacktestBaseline(Base):
    """PPF backtest baseline record for Phase A → Phase B comparison."""

    __tablename__ = "ppf_backtest_baselines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID

    # -- Run identification --
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="1h")

    # -- PPF config fingerprint --
    ppf_params_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # -- Aggregated metrics (for quick comparison without parsing JSON) --
    total_bars: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluated_bars: Mapped[int] = mapped_column(Integer, nullable=False)
    deny_rate: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_rate: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fpr: Mapped[float] = mapped_column(Float, nullable=False)
    allow_count: Mapped[int] = mapped_column(Integer, nullable=False)
    deny_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # -- Distribution snapshots (JSON) --
    deny_reason_distribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_distribution: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- Full result blob --
    result_json: Mapped[str] = mapped_column(Text, nullable=False)

    # -- Freeze/Seal fields --
    frozen: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True when baseline is frozen for Phase B comparison",
    )
    frozen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        doc="UTC timestamp when baseline was frozen",
    )
    frozen_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Process or user that froze the baseline",
    )
    seal_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="SHA-256 of frozen field values for tamper detection",
    )
    preflight_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Data hash from OhlcvPreflightValidator at freeze time",
    )
    phase_b_started: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True when Phase B collection has begun",
    )
    phase_b_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    invalidated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True if baseline was invalidated (never delete)",
    )
    invalidated_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # -- Metadata --
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_ppf_baseline_symbol_exchange_tf", "symbol", "exchange", "timeframe"),
        Index("ix_ppf_baseline_params_hash", "ppf_params_hash"),
    )
