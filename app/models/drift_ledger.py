"""Minimal Drift Ledger — records runtime immutability zone violations.

This is NOT the full Recovery Ledger (Phase 9).  It records only
bundle hash mismatches detected by the Runtime Verifier.

Fields are the minimum required for audit + Phase 9 consumption:
  bundle_type, expected_hash, observed_hash, detected_at,
  action, sm3_candidate, severity, canonical_snapshot
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DriftAction(str, Enum):
    REFUSE_LOAD = "refuse_load"
    QUARANTINE_CANDIDATE = "quarantine_candidate"
    RUNTIME_DRIFT_DETECTED = "runtime_drift_detected"


class DriftSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class BundleType(str, Enum):
    STRATEGY = "strategy"
    FEATURE_PACK = "feature_pack"
    BROKER_POLICY = "broker_policy"
    RISK_LIMIT = "risk_limit"


class DriftLedgerEntry(Base):
    __tablename__ = "drift_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    bundle_type: Mapped[BundleType] = mapped_column(
        SQLEnum(BundleType, values_callable=lambda e: [x.value for x in e]),
    )

    expected_hash: Mapped[str] = mapped_column(String(64))
    observed_hash: Mapped[str] = mapped_column(String(64))

    detected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    action: Mapped[DriftAction] = mapped_column(
        SQLEnum(DriftAction, values_callable=lambda e: [x.value for x in e]),
    )

    sm3_candidate: Mapped[bool] = mapped_column(Boolean, default=True)

    severity: Mapped[DriftSeverity] = mapped_column(
        SQLEnum(DriftSeverity, values_callable=lambda e: [x.value for x in e]),
    )

    # Canonical JSON snapshot for audit — "why did the hash change?"
    canonical_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Consumer dedup — marks event as processed by recovery policy engine
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
