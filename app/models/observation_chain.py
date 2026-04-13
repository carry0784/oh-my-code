"""Observation Chain — time-series long-term system state snapshots.

Append-only log of periodic system observations for long-term trend
analysis, drift detection, and regime transition tracking.

Each entry captures a point-in-time snapshot of:
  - Market state (regime, price, volatility)
  - Strategy state (signal counts, consensus ratios)
  - Infrastructure state (data coverage, shadow task health)
  - Novelty/anomaly markers

DML contract:
  INSERT: allowed (scheduled observer only)
  SELECT: allowed (read-only queries)
  UPDATE: PROHIBITED (append-only)
  DELETE: PROHIBITED
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ObservationChainEntry(Base):
    """Single point-in-time observation in the long-term chain."""

    __tablename__ = "observation_chain"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # -- Observation identity --
    observed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    observation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="hourly"
    )  # hourly, daily, weekly, manual

    # -- Market snapshot --
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    regime_v1: Mapped[str | None] = mapped_column(String(32), nullable=True)
    regime_v2: Mapped[str | None] = mapped_column(String(32), nullable=True)
    realized_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    choppiness_index: Mapped[float | None] = mapped_column(Float, nullable=True)

    # -- Strategy snapshot --
    active_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signal_count_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consensus_ratio_24h: Mapped[float | None] = mapped_column(Float, nullable=True)

    # -- Infrastructure snapshot --
    ohlcv_coverage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    shadow_task_healthy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ppf_baseline_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # -- Novelty / anomaly --
    novelty_detected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    anomaly_flag: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # PRICE_SPIKE, VOLUME_SURGE, REGIME_SHIFT, etc.

    # -- Metadata --
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_obs_chain_symbol_ts", "symbol", "observed_at"),
        Index("ix_obs_chain_type", "observation_type"),
        Index("ix_obs_chain_regime", "regime_v1", "regime_v2"),
    )
