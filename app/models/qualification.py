"""Backtest Qualification models — QualificationResult + enums.

Phase 4A of CR-048.  Provides:
  - QualificationStatus: UNCHECKED / PASS / FAIL
  - DisqualifyReason: separate enum from ScreeningStageReason
  - QualificationResult: append-only audit record per strategy×symbol evaluation

The qualification layer sits between screening (Phase 3A) and
paper shadow (Phase 4B).  A symbol can be screening-CORE but
qualification-FAIL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, Float, Integer, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ── Enums ────────────────────────────────────────────────────────────


class QualificationStatus(str, Enum):
    """Qualification lifecycle — independent of screening status."""

    UNCHECKED = "unchecked"
    PASS = "pass"
    FAIL = "fail"


class DisqualifyReason(str, Enum):
    """Reason codes for qualification failure.

    Deliberately separate from ScreeningStageReason to keep
    screening (data availability) and qualification (strategy fitness)
    concerns distinct.
    """

    # Data compatibility
    INCOMPATIBLE_TIMEFRAME = "incompatible_timeframe"
    INCOMPATIBLE_ASSET_CLASS = "incompatible_asset_class"

    # Warmup
    INSUFFICIENT_WARMUP = "insufficient_warmup"

    # Causality / leakage
    FUTURE_DATA_LEAK = "future_data_leak"
    LOOKAHEAD_BIAS = "lookahead_bias"

    # Data quality
    MISSING_DATA_EXCESS = "missing_data_excess"
    TIMESTAMP_DISORDER = "timestamp_disorder"
    DUPLICATE_BARS = "duplicate_bars"

    # Minimum bars
    INSUFFICIENT_BARS = "insufficient_bars"

    # Performance
    NEGATIVE_SHARPE = "negative_sharpe"
    EXCESSIVE_DRAWDOWN = "excessive_drawdown"

    # Cost adjustment
    NEGATIVE_AFTER_COSTS = "negative_after_costs"
    EXCESSIVE_TURNOVER = "excessive_turnover"

    # Placeholder
    QUALIFICATION_PLACEHOLDER = "qualification_placeholder"


# ── QualificationResult Model ────────────────────────────────────────


class QualificationResult(Base):
    """Append-only qualification audit record.

    One record per (strategy, symbol, timeframe) evaluation.
    """

    __tablename__ = "qualification_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # What was evaluated
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))  # e.g. "1h", "4h", "1d"

    # Dataset identity
    dataset_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 of dataset used
    bars_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    date_range_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_range_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 7-check results (each bool = pass/fail)
    check_data_compat: Mapped[bool] = mapped_column(Boolean, default=False)
    check_warmup: Mapped[bool] = mapped_column(Boolean, default=False)
    check_leakage: Mapped[bool] = mapped_column(Boolean, default=False)
    check_data_quality: Mapped[bool] = mapped_column(Boolean, default=False)
    check_min_bars: Mapped[bool] = mapped_column(Boolean, default=False)
    check_performance: Mapped[bool] = mapped_column(Boolean, default=False)
    check_cost_sanity: Mapped[bool] = mapped_column(Boolean, default=False)

    # Aggregate
    all_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    qualification_status: Mapped[QualificationStatus] = mapped_column(
        SQLEnum(QualificationStatus, values_callable=lambda e: [x.value for x in e]),
        default=QualificationStatus.UNCHECKED,
    )
    disqualify_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    failed_checks: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of all failed check names, e.g. ["data_quality", "performance"]

    # Metrics snapshot (JSON)
    metrics_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Detail (JSON — full check breakdown)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
