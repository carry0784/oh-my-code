"""PPF Execution Divergence Ledger (LV-2).

Authority: PPF-LIVE-VERIFICATION-001 / LV-2

Purpose:
    Record expected vs actual execution paths and classify divergences.
    Any unexpected divergence must be logged, classified, and evaluated
    against constitution-bound recovery rules.

Execution Observation Fields:
    - order_submit_ts: timestamp of order submission
    - venue_ack_ts: timestamp of venue acknowledgment (None if no ack)
    - reject_code: venue reject code (None if accepted)
    - cancel_reason: cancellation reason (None if not cancelled)
    - partial_fill_qty: partial fill quantity (0 if none)
    - final_fill_qty: final filled quantity (0 if not filled)
    - timeout_flag: True if order timed out
    - venue_latency_ms: ack latency in milliseconds (None if no ack)
    - expected_path: the path PPF expected (submit/ack/fill)
    - actual_path: the path that actually occurred

Execution Interpretation:
    - execution_quality_score: 0.0 (worst) to 1.0 (perfect execution)
    - order_path_consistency: CONSISTENT / DIVERGENT
    - venue_reliability_state: RELIABLE / DEGRADED / UNRELIABLE
    - divergence_severity: NONE / LOW / MEDIUM / HIGH / BLOCKER

Divergence Ledger Entry:
    - expected_path
    - actual_path
    - divergence_type: classification of what diverged
    - divergence_severity
    - stop_triggered: True if this divergence requires stage stop
    - recovery_allowed: True if constitution allows recovery
    - receipt_id: unique receipt identifier
    - event_ts: timestamp of divergence event

Constitution constraints (carried from LV-2 RAW_GO):
    - Any unexpected divergence must be logged
    - Severity must be classified
    - Blocker severity must stop the stage
    - recovery_allowed must be constitution-bound
    - Silent continuation after blocker divergence is forbidden
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExecutionPath(str, enum.Enum):
    """Canonical execution paths for LV-2 verification."""

    SUBMIT_ACK_FILL = "submit_ack_fill"
    SUBMIT_ACK_PARTIAL_FILL = "submit_ack_partial_fill"
    SUBMIT_ACK_CANCEL = "submit_ack_cancel"
    SUBMIT_REJECT = "submit_reject"
    SUBMIT_TIMEOUT = "submit_timeout"
    SUBMIT_ACK_TIMEOUT = "submit_ack_timeout"
    NO_SUBMIT = "no_submit"


class DivergenceType(str, enum.Enum):
    """Types of execution divergence."""

    NONE = "none"
    PATH_MISMATCH = "path_mismatch"
    LATENCY_EXCEEDED = "latency_exceeded"
    UNEXPECTED_REJECT = "unexpected_reject"
    UNEXPECTED_CANCEL = "unexpected_cancel"
    UNEXPECTED_PARTIAL = "unexpected_partial"
    UNEXPECTED_TIMEOUT = "unexpected_timeout"
    MISSING_ACK = "missing_ack"
    UNKNOWN = "unknown"


class DivergenceSeverity(str, enum.Enum):
    """Severity classification of divergence."""

    NONE = "none"
    LOW = "low"          # cosmetic, no impact on verification
    MEDIUM = "medium"    # investigation required, stage may continue
    HIGH = "high"        # investigation required, stage paused
    BLOCKER = "blocker"  # stage must stop, correction chain required


class OrderPathConsistency(str, enum.Enum):
    """Whether actual path matched expected."""

    CONSISTENT = "consistent"
    DIVERGENT = "divergent"


class VenueReliabilityState(str, enum.Enum):
    """Venue reliability classification based on accumulated evidence."""

    RELIABLE = "reliable"
    DEGRADED = "degraded"
    UNRELIABLE = "unreliable"


# ---------------------------------------------------------------------------
# Execution Observation (per-order)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionObservation:
    """LV-2 observation fields for a single order lifecycle.

    All timestamps are ISO 8601 UTC strings. None means event did not occur.
    """

    order_submit_ts: Optional[str] = None
    venue_ack_ts: Optional[str] = None
    reject_code: Optional[str] = None
    cancel_reason: Optional[str] = None
    partial_fill_qty: float = 0.0
    final_fill_qty: float = 0.0
    timeout_flag: bool = False
    venue_latency_ms: Optional[float] = None
    expected_path: ExecutionPath = ExecutionPath.NO_SUBMIT
    actual_path: ExecutionPath = ExecutionPath.NO_SUBMIT


# ---------------------------------------------------------------------------
# Execution Interpretation (per-order)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionInterpretation:
    """LV-2 interpretation scores for a single order lifecycle."""

    execution_quality_score: float = 0.0
    order_path_consistency: OrderPathConsistency = OrderPathConsistency.CONSISTENT
    venue_reliability_state: VenueReliabilityState = VenueReliabilityState.RELIABLE
    divergence_severity: DivergenceSeverity = DivergenceSeverity.NONE


# ---------------------------------------------------------------------------
# Divergence Ledger Entry
# ---------------------------------------------------------------------------

@dataclass
class DivergenceLedgerEntry:
    """Single entry in the Execution Divergence Ledger.

    Constitution constraints:
    - Any unexpected divergence must be logged (this dataclass)
    - Severity must be classified (divergence_severity)
    - Blocker severity must stop the stage (stop_triggered=True)
    - recovery_allowed must be constitution-bound
    - Silent continuation after blocker is forbidden
    """

    expected_path: ExecutionPath
    actual_path: ExecutionPath
    divergence_type: DivergenceType
    divergence_severity: DivergenceSeverity
    stop_triggered: bool
    recovery_allowed: bool
    receipt_id: str = field(default_factory=lambda: f"LV2-{uuid.uuid4().hex[:12]}")
    event_ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Execution Divergence Ledger
# ---------------------------------------------------------------------------

class ExecutionDivergenceLedger:
    """Accumulates divergence entries for LV-2 verification.

    Provides aggregate statistics and blocker detection.
    """

    def __init__(self) -> None:
        self._entries: list[DivergenceLedgerEntry] = []
        self._stopped: bool = False
        self._stop_reason: Optional[str] = None

    @property
    def entries(self) -> list[DivergenceLedgerEntry]:
        return list(self._entries)

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    @property
    def stop_reason(self) -> Optional[str]:
        return self._stop_reason

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def blocker_count(self) -> int:
        return sum(
            1 for e in self._entries
            if e.divergence_severity == DivergenceSeverity.BLOCKER
        )

    @property
    def has_blockers(self) -> bool:
        return self.blocker_count > 0

    def record(self, entry: DivergenceLedgerEntry) -> None:
        """Record a divergence entry.

        If severity is BLOCKER, stage is stopped immediately.
        Silent continuation after blocker is forbidden (constitution).
        """
        self._entries.append(entry)

        if entry.divergence_severity == DivergenceSeverity.BLOCKER:
            self._stopped = True
            self._stop_reason = (
                f"BLOCKER divergence: {entry.divergence_type.value} "
                f"(receipt={entry.receipt_id})"
            )

    def record_divergence(
        self,
        expected: ExecutionPath,
        actual: ExecutionPath,
        divergence_type: DivergenceType,
        severity: DivergenceSeverity,
        recovery_allowed: bool = False,
    ) -> DivergenceLedgerEntry:
        """Convenience method: create and record a divergence entry.

        Args:
            expected: Expected execution path.
            actual: Actual execution path.
            divergence_type: Classification of what diverged.
            severity: Severity classification.
            recovery_allowed: Whether constitution allows recovery.

        Returns:
            The created entry (for inspection/testing).
        """
        stop = severity == DivergenceSeverity.BLOCKER
        entry = DivergenceLedgerEntry(
            expected_path=expected,
            actual_path=actual,
            divergence_type=divergence_type,
            divergence_severity=severity,
            stop_triggered=stop,
            recovery_allowed=recovery_allowed if not stop else False,
        )
        self.record(entry)
        return entry

    def severity_counts(self) -> dict[str, int]:
        """Return count by severity level."""
        counts: dict[str, int] = {s.value: 0 for s in DivergenceSeverity}
        for e in self._entries:
            counts[e.divergence_severity.value] += 1
        return counts

    def summary(self) -> dict:
        """Return ledger summary for reporting."""
        return {
            "total_entries": len(self._entries),
            "severity_counts": self.severity_counts(),
            "is_stopped": self._stopped,
            "stop_reason": self._stop_reason,
            "has_blockers": self.has_blockers,
        }


# ---------------------------------------------------------------------------
# Interpretation Functions
# ---------------------------------------------------------------------------

def compute_execution_interpretation(
    obs: ExecutionObservation,
    latency_threshold_ms: float = 1000.0,
) -> ExecutionInterpretation:
    """Compute LV-2 interpretation scores from execution observation.

    Args:
        obs: Execution observation for a single order.
        latency_threshold_ms: Maximum acceptable venue latency.

    Returns:
        ExecutionInterpretation with quality/consistency/reliability/severity.
    """
    # Path consistency
    if obs.expected_path == obs.actual_path:
        consistency = OrderPathConsistency.CONSISTENT
    else:
        consistency = OrderPathConsistency.DIVERGENT

    # Venue reliability
    if obs.timeout_flag:
        reliability = VenueReliabilityState.DEGRADED
    elif obs.reject_code is not None:
        reliability = VenueReliabilityState.DEGRADED
    elif (obs.venue_latency_ms is not None
          and obs.venue_latency_ms > latency_threshold_ms):
        reliability = VenueReliabilityState.DEGRADED
    else:
        reliability = VenueReliabilityState.RELIABLE

    # Divergence severity
    severity = DivergenceSeverity.NONE
    if consistency == OrderPathConsistency.DIVERGENT:
        # Classify severity based on what actually happened
        if obs.actual_path == ExecutionPath.SUBMIT_TIMEOUT:
            severity = DivergenceSeverity.HIGH
        elif obs.actual_path == ExecutionPath.SUBMIT_REJECT:
            if obs.expected_path == ExecutionPath.SUBMIT_ACK_FILL:
                severity = DivergenceSeverity.MEDIUM
            else:
                severity = DivergenceSeverity.LOW
        elif obs.actual_path == ExecutionPath.SUBMIT_ACK_CANCEL:
            severity = DivergenceSeverity.MEDIUM
        elif obs.actual_path == ExecutionPath.SUBMIT_ACK_PARTIAL_FILL:
            severity = DivergenceSeverity.LOW
        else:
            severity = DivergenceSeverity.MEDIUM

    # Execution quality score (0.0 = worst, 1.0 = perfect)
    quality = 1.0

    # Penalize path divergence
    if consistency == OrderPathConsistency.DIVERGENT:
        quality -= 0.4

    # Penalize timeout
    if obs.timeout_flag:
        quality -= 0.3

    # Penalize high latency
    if (obs.venue_latency_ms is not None
            and obs.venue_latency_ms > latency_threshold_ms):
        quality -= 0.2

    # Penalize partial fill (incomplete)
    if (obs.partial_fill_qty > 0
            and obs.final_fill_qty < obs.partial_fill_qty):
        quality -= 0.1

    # Clamp
    quality = max(0.0, min(1.0, quality))

    return ExecutionInterpretation(
        execution_quality_score=round(quality, 4),
        order_path_consistency=consistency,
        venue_reliability_state=reliability,
        divergence_severity=severity,
    )


def classify_divergence(
    obs: ExecutionObservation,
) -> DivergenceType:
    """Classify the type of divergence from observation.

    Returns NONE if paths match.
    """
    if obs.expected_path == obs.actual_path:
        return DivergenceType.NONE

    actual = obs.actual_path

    if actual == ExecutionPath.SUBMIT_REJECT:
        return DivergenceType.UNEXPECTED_REJECT
    elif actual == ExecutionPath.SUBMIT_TIMEOUT:
        return DivergenceType.UNEXPECTED_TIMEOUT
    elif actual == ExecutionPath.SUBMIT_ACK_TIMEOUT:
        return DivergenceType.UNEXPECTED_TIMEOUT
    elif actual == ExecutionPath.SUBMIT_ACK_CANCEL:
        return DivergenceType.UNEXPECTED_CANCEL
    elif actual == ExecutionPath.SUBMIT_ACK_PARTIAL_FILL:
        return DivergenceType.UNEXPECTED_PARTIAL

    # Check for missing ack
    if (obs.order_submit_ts is not None
            and obs.venue_ack_ts is None
            and not obs.timeout_flag
            and obs.reject_code is None):
        return DivergenceType.MISSING_ACK

    return DivergenceType.PATH_MISMATCH
