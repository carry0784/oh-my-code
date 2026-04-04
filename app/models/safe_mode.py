"""Safe Mode state model + transition audit records.

Safe Mode is the system's operational state that restricts trading
activity when runtime integrity violations are detected.

States:
  NORMAL            — full operation
  SM3_RECOVERY_ONLY — no new entry, exit allowed, analysis+draft allowed
  SM2_EXIT_ONLY     — no new entry, exit allowed (SL/TP/reverse signal)
  SM1_OBSERVE_ONLY  — no entry, no exit (exchange-side SL/TP only)

Transitions:
  Auto:   NORMAL -> SM3 only
  Manual: SM3 -> SM2 -> SM1 -> NORMAL (each requires approval)
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ── Safe Mode States ─────────────────────────────────────────────────


class SafeModeState(str, Enum):
    NORMAL = "normal"
    SM3_RECOVERY_ONLY = "sm3_recovery_only"
    SM2_EXIT_ONLY = "sm2_exit_only"
    SM1_OBSERVE_ONLY = "sm1_observe_only"


# ── Reason Codes (standardized) ──────────────────────────────────────


class SafeModeReasonCode(str, Enum):
    DRIFT_STRATEGY_BUNDLE = "drift_strategy_bundle"
    DRIFT_FEATURE_PACK_BUNDLE = "drift_feature_pack_bundle"
    DRIFT_BROKER_POLICY_BUNDLE = "drift_broker_policy_bundle"
    DRIFT_RISK_LIMIT_BUNDLE = "drift_risk_limit_bundle"
    DUPLICATE_DRIFT_SUPPRESSED = "duplicate_drift_suppressed"
    MANUAL_ENTRY = "manual_entry"
    MANUAL_RELEASE = "manual_release"
    STABILITY_CONFIRMED = "stability_confirmed"


# ── Current Safe Mode State (singleton row) ──────────────────────────


class SafeModeStatus(Base):
    """Current system safe mode state.  Single row table."""

    __tablename__ = "safe_mode_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    current_state: Mapped[SafeModeState] = mapped_column(
        SQLEnum(SafeModeState, values_callable=lambda e: [x.value for x in e]),
        default=SafeModeState.NORMAL,
    )
    previous_state: Mapped[SafeModeState | None] = mapped_column(
        SQLEnum(SafeModeState, values_callable=lambda e: [x.value for x in e]),
        nullable=True,
    )
    entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entered_reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ── Transition Audit Record (append-only) ────────────────────────────


class SafeModeTransition(Base):
    """Append-only audit trail for every Safe Mode state transition."""

    __tablename__ = "safe_mode_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    from_state: Mapped[str] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    reason_code: Mapped[str] = mapped_column(String(50))
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
