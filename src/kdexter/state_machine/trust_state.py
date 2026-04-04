"""
Trust State Machine — K-Dexter AOS

States (degradation order):
  TRUSTED → DEGRADED → UNRELIABLE → STALE → DECAYING → ISOLATED → RECOVERY

Decay function (OQ-5 resolved — see config/thresholds.py):
  Event-based with slow linear background.
  score(t+Δt) = score(t)
                - TRUST_DECAY_BACKGROUND_RATE * Δt_hours
                - step_down per failure event
                + step_up per success event
                clamped [0.0, 1.0]
"""
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

from kdexter.config.thresholds import (
    TRUST_DECAY_BACKGROUND_RATE,
    TRUST_DECAY_ON_CRITICAL,
    TRUST_DECAY_ON_HIGH,
    TRUST_DECAY_ON_MEDIUM,
    TRUST_RECOVERY_ON_SUCCESS,
    TRUST_RECOVERY_ON_RECOVERY_COMPLETE,
    TRUST_BOUNDARY_TRUSTED,
    TRUST_BOUNDARY_DEGRADED,
    TRUST_BOUNDARY_UNRELIABLE,
    TRUST_BOUNDARY_DECAYING,
    TRUST_BOUNDARY_STALE,
)


class TrustStateEnum(Enum):
    TRUSTED = "TRUSTED"
    DEGRADED = "DEGRADED"
    UNRELIABLE = "UNRELIABLE"
    STALE = "STALE"       # time-based expiry
    DECAYING = "DECAYING"
    ISOLATED = "ISOLATED"
    RECOVERY = "RECOVERY"

    def allows_execution(self) -> bool:
        return self in {TrustStateEnum.TRUSTED, TrustStateEnum.DEGRADED}

    def requires_monitoring(self) -> bool:
        return self in {TrustStateEnum.DECAYING, TrustStateEnum.STALE}


# Failure severity → step-down map
_FAILURE_STEP_DOWN: dict[str, float] = {
    "CRITICAL": TRUST_DECAY_ON_CRITICAL,
    "HIGH":     TRUST_DECAY_ON_HIGH,
    "MEDIUM":   TRUST_DECAY_ON_MEDIUM,
    "LOW":      0.0,   # LOW failures do not affect trust score
}


@dataclass
class TrustStateContext:
    component_id: str
    current: TrustStateEnum = TrustStateEnum.TRUSTED
    score: float = 1.0          # 0.0 ~ 1.0
    last_refreshed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_transition: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def on_failure(self, severity: str) -> None:
        """
        Apply event-based step-down on failure.
        severity: CRITICAL / HIGH / MEDIUM / LOW
        """
        step = _FAILURE_STEP_DOWN.get(severity.upper(), 0.0)
        self.score = round(max(0.0, self.score - step), 6)
        self.last_refreshed = datetime.now(timezone.utc)
        self._update_state_from_score()

    def on_success(self) -> None:
        """Apply step-up on successful execution."""
        self.score = round(min(1.0, self.score + TRUST_RECOVERY_ON_SUCCESS), 6)
        self.last_refreshed = datetime.now(timezone.utc)
        self._update_state_from_score()

    def on_recovery_complete(self) -> None:
        """Apply larger step-up after Recovery Loop completes for this component."""
        self.score = round(min(1.0, self.score + TRUST_RECOVERY_ON_RECOVERY_COMPLETE), 6)
        self.last_refreshed = datetime.now(timezone.utc)
        self._update_state_from_score()

    def apply_background_decay(self, elapsed_hours: float) -> None:
        """
        Apply slow linear background decay.
        Called periodically by L19 Trust Decay Engine scheduler.
        Rate: TRUST_DECAY_BACKGROUND_RATE per hour (0.002 = 0.2%/hr).
        """
        self.score = round(max(0.0, self.score - TRUST_DECAY_BACKGROUND_RATE * elapsed_hours), 6)
        self._update_state_from_score()

    def enter_recovery(self) -> None:
        """Mark component as entering trust recovery process."""
        self.current = TrustStateEnum.RECOVERY
        self.last_transition = datetime.now(timezone.utc)

    def _update_state_from_score(self) -> None:
        previous = self.current
        if self.current == TrustStateEnum.RECOVERY:
            return  # recovery state is managed explicitly, not score-driven

        if self.score >= TRUST_BOUNDARY_TRUSTED:
            new_state = TrustStateEnum.TRUSTED
        elif self.score >= TRUST_BOUNDARY_DEGRADED:
            new_state = TrustStateEnum.DEGRADED
        elif self.score >= TRUST_BOUNDARY_UNRELIABLE:
            new_state = TrustStateEnum.UNRELIABLE
        elif self.score >= TRUST_BOUNDARY_DECAYING:
            new_state = TrustStateEnum.DECAYING
        elif self.score >= TRUST_BOUNDARY_STALE:
            new_state = TrustStateEnum.STALE
        else:
            new_state = TrustStateEnum.ISOLATED

        if new_state != previous:
            self.current = new_state
            self.last_transition = datetime.now(timezone.utc)
