"""Load Decision Receipt — append-only audit trail for runtime load decisions.

Phase 5A+5B of CR-048.  Records every load eligibility evaluation:
why a strategy×symbol was loaded or rejected, with full status snapshot
and artifact fingerprints used at decision time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LoadDecisionReceipt(Base):
    """Append-only record of every runtime load eligibility decision."""

    __tablename__ = "load_decision_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # What was being loaded
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol_id: Mapped[str] = mapped_column(String(36), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))

    # Decision
    decision: Mapped[str] = mapped_column(String(20))  # approved / rejected
    primary_reason: Mapped[str | None] = mapped_column(
        String(60), nullable=True
    )  # first failing check reason

    # Multi-failure visibility
    failed_checks: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON list of failed check names

    # Full status snapshot at decision time
    status_snapshot: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: all 4 status axes + system guards + fingerprints

    # Artifact fingerprints used at decision time (Phase 5B)
    strategy_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 of strategy bundle
    fp_fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 of feature pack bundle

    decided_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
