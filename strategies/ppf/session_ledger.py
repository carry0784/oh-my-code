"""PPF Session Failure Budget Ledger (LV-3).

Authority: PPF-LIVE-VERIFICATION-001 / LV-3

Purpose:
    Track session-level failure budgets, enforce abort/cooldown rules,
    and accumulate divergence events from LV-2 execution ledger into
    session-level counters.

    LV-3 is NOT production rollout. It is bounded live session verification.

Session Observation Fields:
    - session_id: unique session identifier
    - session_start_ts: session start timestamp
    - session_end_ts: session end timestamp (None if still active)
    - consecutive_divergence_count: consecutive divergences without stable
    - reject_count: total rejects in this session
    - timeout_count: total timeouts in this session
    - high_severity_divergence_count: HIGH severity divergences
    - exposure_by_asset: {asset: exposure_value}
    - abort_triggered: True if session was aborted
    - abort_reason: reason for abort (None if not aborted)
    - forced_cooldown_until: cooldown expiry (None if no cooldown)
    - expected_session_path: expected session outcome
    - actual_session_path: actual session outcome

Session Interpretation:
    - session_execution_stability: STABLE / DEGRADED / ABORTED
    - budget_pressure_state: NORMAL / ELEVATED / CRITICAL / OVERRUN
    - divergence_accumulation_state: CLEAN / ACCUMULATING / SATURATED
    - bounded_exposure_integrity: WITHIN_BOUNDS / APPROACHING_LIMIT / EXCEEDED
    - venue_session_reliability: RELIABLE / DEGRADED / UNRELIABLE

Session Failure Budget:
    - max_reject_per_session: reject budget limit
    - max_timeout_per_session: timeout budget limit
    - max_high_divergence_per_session: high-severity divergence limit
    - session_abort_threshold: threshold for forced abort
    - forced_cooldown_after_abort: cooldown duration after abort

Constitution constraints:
    - Any budget overrun must be logged
    - Budget state must be classifiable
    - Abort threshold breach must stop the session
    - Cooldown must be enforced after abort
    - Cooldown re-entry must be denied
    - Silent continuation after abort is forbidden
    - Blocker severity always overrides remaining budget
    - recovery_allowed must remain constitution-bound
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from strategies.ppf.execution_ledger import (
    DivergenceLedgerEntry,
    DivergenceSeverity,
    DivergenceType,
    ExecutionDivergenceLedger,
    ExecutionObservation,
    ExecutionPath,
)


# ---------------------------------------------------------------------------
# Session-Level Enums
# ---------------------------------------------------------------------------

class SessionPath(str, enum.Enum):
    """Canonical session-level outcome paths."""

    STABLE_COMPLETION = "stable_completion"
    DEGRADED_COMPLETION = "degraded_completion"
    ABORT_REJECT_OVERRUN = "abort_reject_overrun"
    ABORT_TIMEOUT_OVERRUN = "abort_timeout_overrun"
    ABORT_DIVERGENCE_OVERRUN = "abort_divergence_overrun"
    ABORT_BLOCKER = "abort_blocker"
    COOLDOWN_ACTIVE = "cooldown_active"
    NOT_STARTED = "not_started"


class SessionStability(str, enum.Enum):
    """Session execution stability classification."""

    STABLE = "stable"
    DEGRADED = "degraded"
    ABORTED = "aborted"


class BudgetPressureState(str, enum.Enum):
    """Budget pressure classification."""

    NORMAL = "normal"        # 0-49% of any budget consumed
    ELEVATED = "elevated"    # 50-79% of any budget consumed
    CRITICAL = "critical"    # 80-99% of any budget consumed
    OVERRUN = "overrun"      # 100%+ of any budget consumed


class DivergenceAccumulationState(str, enum.Enum):
    """Divergence accumulation classification."""

    CLEAN = "clean"               # no divergences
    ACCUMULATING = "accumulating"  # divergences present, within budget
    SATURATED = "saturated"        # at or near budget limit


class ExposureIntegrity(str, enum.Enum):
    """Bounded exposure integrity classification."""

    WITHIN_BOUNDS = "within_bounds"
    APPROACHING_LIMIT = "approaching_limit"
    EXCEEDED = "exceeded"


class VenueSessionReliability(str, enum.Enum):
    """Session-level venue reliability."""

    RELIABLE = "reliable"
    DEGRADED = "degraded"
    UNRELIABLE = "unreliable"


# ---------------------------------------------------------------------------
# Session Observation
# ---------------------------------------------------------------------------

@dataclass
class SessionObservation:
    """LV-3 observation fields for a single bounded live session."""

    session_id: str = field(default_factory=lambda: f"S-{uuid.uuid4().hex[:12]}")
    session_start_ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    session_end_ts: Optional[str] = None
    consecutive_divergence_count: int = 0
    reject_count: int = 0
    timeout_count: int = 0
    high_severity_divergence_count: int = 0
    exposure_by_asset: dict[str, float] = field(default_factory=dict)
    abort_triggered: bool = False
    abort_reason: Optional[str] = None
    forced_cooldown_until: Optional[str] = None
    expected_session_path: SessionPath = SessionPath.STABLE_COMPLETION
    actual_session_path: SessionPath = SessionPath.NOT_STARTED


# ---------------------------------------------------------------------------
# Session Interpretation
# ---------------------------------------------------------------------------

@dataclass
class SessionInterpretation:
    """LV-3 interpretation scores for a bounded live session."""

    session_execution_stability: SessionStability = SessionStability.STABLE
    budget_pressure_state: BudgetPressureState = BudgetPressureState.NORMAL
    divergence_accumulation_state: DivergenceAccumulationState = (
        DivergenceAccumulationState.CLEAN
    )
    bounded_exposure_integrity: ExposureIntegrity = ExposureIntegrity.WITHIN_BOUNDS
    venue_session_reliability: VenueSessionReliability = (
        VenueSessionReliability.RELIABLE
    )


# ---------------------------------------------------------------------------
# Session Failure Budget Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionBudgetConfig:
    """Immutable session failure budget configuration.

    Frozen to enforce C10 (no runtime parameter adaptation).
    """

    max_reject_per_session: int = 3
    max_timeout_per_session: int = 2
    max_high_divergence_per_session: int = 1
    session_abort_threshold: int = 5    # total failures across all types
    forced_cooldown_seconds: int = 300  # 5 minutes after abort
    max_exposure_per_asset: float = 0.01  # micro-size bounded


# ---------------------------------------------------------------------------
# Session Failure Budget Ledger
# ---------------------------------------------------------------------------

class SessionFailureBudgetLedger:
    """Tracks session-level failure budgets and enforces abort/cooldown.

    Constitution constraints:
    - Any budget overrun must be logged
    - Abort threshold breach must stop the session
    - Cooldown must be enforced after abort
    - Cooldown re-entry must be denied
    - Silent continuation after abort is forbidden
    - Blocker severity always overrides remaining budget
    """

    def __init__(self, config: SessionBudgetConfig) -> None:
        self._config = config
        self._observation = SessionObservation()
        self._divergence_ledger = ExecutionDivergenceLedger()
        self._aborted: bool = False
        self._abort_reason: Optional[str] = None
        self._cooldown_active: bool = False
        self._cooldown_until: Optional[str] = None
        self._total_failure_count: int = 0
        self._receipt_id: str = f"LV3-{uuid.uuid4().hex[:12]}"

    # -- Properties --

    @property
    def session_id(self) -> str:
        return self._observation.session_id

    @property
    def config(self) -> SessionBudgetConfig:
        return self._config

    @property
    def observation(self) -> SessionObservation:
        return self._observation

    @property
    def divergence_ledger(self) -> ExecutionDivergenceLedger:
        return self._divergence_ledger

    @property
    def is_aborted(self) -> bool:
        return self._aborted

    @property
    def abort_reason(self) -> Optional[str]:
        return self._abort_reason

    @property
    def is_cooldown_active(self) -> bool:
        return self._cooldown_active

    @property
    def cooldown_until(self) -> Optional[str]:
        return self._cooldown_until

    @property
    def receipt_id(self) -> str:
        return self._receipt_id

    @property
    def reject_count(self) -> int:
        return self._observation.reject_count

    @property
    def timeout_count(self) -> int:
        return self._observation.timeout_count

    @property
    def high_divergence_count(self) -> int:
        return self._observation.high_severity_divergence_count

    @property
    def total_failure_count(self) -> int:
        return self._total_failure_count

    # -- Budget checking --

    def is_reject_budget_exceeded(self) -> bool:
        return self._observation.reject_count >= self._config.max_reject_per_session

    def is_timeout_budget_exceeded(self) -> bool:
        return self._observation.timeout_count >= self._config.max_timeout_per_session

    def is_high_divergence_budget_exceeded(self) -> bool:
        return (
            self._observation.high_severity_divergence_count
            >= self._config.max_high_divergence_per_session
        )

    def is_abort_threshold_exceeded(self) -> bool:
        return self._total_failure_count >= self._config.session_abort_threshold

    # -- Core operations --

    def record_execution_event(
        self,
        exec_obs: ExecutionObservation,
        divergence_severity: DivergenceSeverity,
        divergence_type: DivergenceType,
    ) -> Optional[str]:
        """Record an execution event and update session counters.

        Returns:
            abort_reason if session must abort, None otherwise.
        """
        # Constitution: silent continuation after abort is forbidden
        if self._aborted:
            return self._abort_reason

        # Constitution: cooldown re-entry must be denied
        if self._cooldown_active:
            return f"COOLDOWN_REENTRY_DENIED (until {self._cooldown_until})"

        # Record in LV-2 divergence ledger (continuity)
        if divergence_type != DivergenceType.NONE:
            self._divergence_ledger.record_divergence(
                expected=exec_obs.expected_path,
                actual=exec_obs.actual_path,
                divergence_type=divergence_type,
                severity=divergence_severity,
            )

        # Update session counters based on divergence
        if divergence_severity == DivergenceSeverity.BLOCKER:
            # Constitution: blocker severity always overrides remaining budget
            return self._abort("BLOCKER_DIVERGENCE", SessionPath.ABORT_BLOCKER)

        if exec_obs.reject_code is not None:
            self._observation.reject_count += 1
            self._total_failure_count += 1

        if exec_obs.timeout_flag:
            self._observation.timeout_count += 1
            self._total_failure_count += 1

        if divergence_severity == DivergenceSeverity.HIGH:
            self._observation.high_severity_divergence_count += 1
            self._total_failure_count += 1

        # Update consecutive divergence tracking
        if divergence_type != DivergenceType.NONE:
            self._observation.consecutive_divergence_count += 1
        else:
            self._observation.consecutive_divergence_count = 0

        # Check budget overruns
        if self.is_reject_budget_exceeded():
            return self._abort(
                f"REJECT_BUDGET_OVERRUN ({self._observation.reject_count}"
                f"/{self._config.max_reject_per_session})",
                SessionPath.ABORT_REJECT_OVERRUN,
            )

        if self.is_timeout_budget_exceeded():
            return self._abort(
                f"TIMEOUT_BUDGET_OVERRUN ({self._observation.timeout_count}"
                f"/{self._config.max_timeout_per_session})",
                SessionPath.ABORT_TIMEOUT_OVERRUN,
            )

        if self.is_high_divergence_budget_exceeded():
            return self._abort(
                f"HIGH_DIVERGENCE_OVERRUN ({self._observation.high_severity_divergence_count}"
                f"/{self._config.max_high_divergence_per_session})",
                SessionPath.ABORT_DIVERGENCE_OVERRUN,
            )

        if self.is_abort_threshold_exceeded():
            return self._abort(
                f"TOTAL_FAILURE_THRESHOLD ({self._total_failure_count}"
                f"/{self._config.session_abort_threshold})",
                SessionPath.ABORT_REJECT_OVERRUN,
            )

        return None  # No abort

    def _abort(self, reason: str, path: SessionPath) -> str:
        """Execute session abort and activate cooldown.

        Constitution:
        - Abort must be explicit and logged
        - Cooldown must be explicit and enforced
        """
        self._aborted = True
        self._abort_reason = reason
        self._observation.abort_triggered = True
        self._observation.abort_reason = reason
        self._observation.actual_session_path = path
        self._observation.session_end_ts = datetime.now(timezone.utc).isoformat()

        # Activate forced cooldown
        from datetime import timedelta
        cooldown_end = (
            datetime.now(timezone.utc)
            + timedelta(seconds=self._config.forced_cooldown_seconds)
        )
        self._cooldown_active = True
        self._cooldown_until = cooldown_end.isoformat()
        self._observation.forced_cooldown_until = self._cooldown_until

        return reason

    def complete_session(self, degraded: bool = False) -> None:
        """Mark session as complete (non-aborted).

        Args:
            degraded: True if session had divergences but completed.
        """
        if self._aborted:
            return  # Already aborted, cannot complete

        self._observation.session_end_ts = datetime.now(timezone.utc).isoformat()

        if degraded:
            self._observation.actual_session_path = SessionPath.DEGRADED_COMPLETION
        else:
            self._observation.actual_session_path = SessionPath.STABLE_COMPLETION

    def update_exposure(self, asset: str, exposure: float) -> Optional[str]:
        """Update exposure for an asset. Returns abort reason if exceeded."""
        self._observation.exposure_by_asset[asset] = exposure

        if exposure > self._config.max_exposure_per_asset:
            return self._abort(
                f"EXPOSURE_EXCEEDED ({asset}: {exposure}"
                f" > {self._config.max_exposure_per_asset})",
                SessionPath.ABORT_DIVERGENCE_OVERRUN,
            )
        return None

    # -- Interpretation --

    def compute_interpretation(self) -> SessionInterpretation:
        """Compute session-level interpretation from accumulated state."""
        # Stability
        if self._aborted:
            stability = SessionStability.ABORTED
        elif self._total_failure_count > 0:
            stability = SessionStability.DEGRADED
        else:
            stability = SessionStability.STABLE

        # Budget pressure
        max_ratio = 0.0
        if self._config.max_reject_per_session > 0:
            max_ratio = max(
                max_ratio,
                self._observation.reject_count / self._config.max_reject_per_session,
            )
        if self._config.max_timeout_per_session > 0:
            max_ratio = max(
                max_ratio,
                self._observation.timeout_count / self._config.max_timeout_per_session,
            )
        if self._config.max_high_divergence_per_session > 0:
            max_ratio = max(
                max_ratio,
                (self._observation.high_severity_divergence_count
                 / self._config.max_high_divergence_per_session),
            )

        if max_ratio >= 1.0:
            pressure = BudgetPressureState.OVERRUN
        elif max_ratio >= 0.8:
            pressure = BudgetPressureState.CRITICAL
        elif max_ratio >= 0.5:
            pressure = BudgetPressureState.ELEVATED
        else:
            pressure = BudgetPressureState.NORMAL

        # Divergence accumulation
        div_count = self._divergence_ledger.entry_count
        if div_count == 0:
            accumulation = DivergenceAccumulationState.CLEAN
        elif div_count >= self._config.session_abort_threshold:
            accumulation = DivergenceAccumulationState.SATURATED
        else:
            accumulation = DivergenceAccumulationState.ACCUMULATING

        # Exposure integrity
        exposure_ok = True
        exposure_approaching = False
        for asset, exp in self._observation.exposure_by_asset.items():
            if exp > self._config.max_exposure_per_asset:
                exposure_ok = False
            elif exp > self._config.max_exposure_per_asset * 0.8:
                exposure_approaching = True

        if not exposure_ok:
            exposure_state = ExposureIntegrity.EXCEEDED
        elif exposure_approaching:
            exposure_state = ExposureIntegrity.APPROACHING_LIMIT
        else:
            exposure_state = ExposureIntegrity.WITHIN_BOUNDS

        # Venue reliability
        sev_counts = self._divergence_ledger.severity_counts()
        high_plus = sev_counts.get("high", 0) + sev_counts.get("blocker", 0)
        medium = sev_counts.get("medium", 0)

        if high_plus > 0:
            venue = VenueSessionReliability.UNRELIABLE
        elif medium > 0:
            venue = VenueSessionReliability.DEGRADED
        else:
            venue = VenueSessionReliability.RELIABLE

        return SessionInterpretation(
            session_execution_stability=stability,
            budget_pressure_state=pressure,
            divergence_accumulation_state=accumulation,
            bounded_exposure_integrity=exposure_state,
            venue_session_reliability=venue,
        )

    # -- Reporting --

    def summary(self) -> dict:
        """Return session summary for reporting."""
        interp = self.compute_interpretation()
        return {
            "session_id": self._observation.session_id,
            "receipt_id": self._receipt_id,
            "reject_count": self._observation.reject_count,
            "timeout_count": self._observation.timeout_count,
            "high_divergence_count": self._observation.high_severity_divergence_count,
            "total_failure_count": self._total_failure_count,
            "consecutive_divergence_count": self._observation.consecutive_divergence_count,
            "is_aborted": self._aborted,
            "abort_reason": self._abort_reason,
            "cooldown_active": self._cooldown_active,
            "cooldown_until": self._cooldown_until,
            "actual_session_path": self._observation.actual_session_path.value,
            "stability": interp.session_execution_stability.value,
            "budget_pressure": interp.budget_pressure_state.value,
            "divergence_accumulation": interp.divergence_accumulation_state.value,
            "exposure_integrity": interp.bounded_exposure_integrity.value,
            "venue_reliability": interp.venue_session_reliability.value,
            "divergence_ledger_entries": self._divergence_ledger.entry_count,
            "divergence_severity_counts": self._divergence_ledger.severity_counts(),
            "exposure_by_asset": dict(self._observation.exposure_by_asset),
        }
