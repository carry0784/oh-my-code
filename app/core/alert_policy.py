"""
Card C-21: Alert Policy — Escalation rules for routed incidents.

Purpose:
  Apply escalation policy on top of routing decisions.
  Routing classifies severity. Policy decides escalation behavior:
  - Should we escalate a repeated degraded state to external?
  - Should we suppress duplicate alerts?
  - Should we add urgency markers?

Design:
  routing  = classify (C-14)
  policy   = escalate (C-21)
  sender   = deliver  (C-15/C-20)

  - Read-only: no state mutation beyond escalation counter
  - Fail-closed: policy errors fall through to original routing
  - Deterministic for same input + counter state
  - No hidden reasoning, no debug traces

Policy rules:
  1. DUPLICATE SUPPRESSION:
     Same severity_tier + highest_incident within cooldown → suppress
  2. DEGRADED ESCALATION:
     Repeated low-severity degraded (N consecutive) → escalate to high
  3. CLEAR DE-ESCALATION:
     After incident resolves → send one "resolved" notification
  4. URGENCY MARKERS:
     critical tier → add "urgent" flag
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_COOLDOWN_SECONDS = 300  # 5 min duplicate suppression
DEFAULT_ESCALATION_THRESHOLD = 3  # consecutive degraded → escalate


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class PolicyDecision:
    """Result of applying escalation policy to a routing decision."""

    action: str  # "send" | "suppress" | "escalate" | "resolve"
    channels: list[str] = field(default_factory=list)
    severity_tier: str = ""
    reason: str = ""
    urgent: bool = False
    suppressed: bool = False


@dataclass
class _PolicyState:
    """Internal state for duplicate suppression and escalation tracking."""

    last_severity: str = ""
    last_incident: str = ""
    last_sent_at: Optional[datetime] = None
    consecutive_degraded: int = 0
    was_incident_active: bool = False


# ---------------------------------------------------------------------------
# Alert Policy Engine
# ---------------------------------------------------------------------------


class AlertPolicy:
    """
    Stateful escalation policy engine.

    Consumes routing decisions and applies escalation rules.
    Single instance per process. State is in-memory only.
    """

    def __init__(
        self,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        escalation_threshold: int = DEFAULT_ESCALATION_THRESHOLD,
    ) -> None:
        self._cooldown = cooldown_seconds
        self._escalation_threshold = escalation_threshold
        self._state = _PolicyState()

    def evaluate(
        self,
        routing: dict[str, Any],
        snapshot: Optional[dict[str, Any]] = None,
    ) -> PolicyDecision:
        """
        Apply escalation policy to a routing decision.

        Args:
            routing: Output of route_snapshot() (C-14)
            snapshot: Optional snapshot for context

        Returns:
            PolicyDecision with action, channels, and escalation metadata.

        Fail-closed: returns original routing on any error.
        """
        try:
            return self._evaluate_impl(routing, snapshot)
        except Exception:
            # Fail-closed: pass through original routing
            return PolicyDecision(
                action="send",
                channels=list(routing.get("channels", [])),
                severity_tier=routing.get("severity_tier", "unknown"),
                reason="policy_error_fallthrough",
            )

    def _evaluate_impl(
        self,
        routing: dict[str, Any],
        snapshot: Optional[dict[str, Any]],
    ) -> PolicyDecision:
        now = datetime.now(timezone.utc)
        channels = list(routing.get("channels", []))
        severity = routing.get("severity_tier", "clear")
        reason = routing.get("reason", "")
        incident = ""
        if snapshot:
            incident = snapshot.get("highest_incident", "NONE")

        # Rule 1: CLEAR DE-ESCALATION — send "resolved" if was active
        if severity == "clear":
            if self._state.was_incident_active:
                self._state.was_incident_active = False
                self._state.consecutive_degraded = 0
                self._state.last_severity = severity
                self._state.last_incident = incident
                self._state.last_sent_at = now
                return PolicyDecision(
                    action="resolve",
                    channels=["console", "snapshot"],
                    severity_tier="clear",
                    reason="incident resolved",
                )
            self._state.consecutive_degraded = 0
            return PolicyDecision(
                action="suppress",
                channels=[],
                severity_tier="clear",
                reason="no incident, no change",
                suppressed=True,
            )

        # Rule 2: DUPLICATE SUPPRESSION
        if (
            self._state.last_sent_at is not None
            and severity == self._state.last_severity
            and incident == self._state.last_incident
        ):
            elapsed = (now - self._state.last_sent_at).total_seconds()
            if elapsed < self._cooldown:
                return PolicyDecision(
                    action="suppress",
                    channels=[],
                    severity_tier=severity,
                    reason=f"duplicate suppressed (cooldown {int(self._cooldown - elapsed)}s remaining)",
                    suppressed=True,
                )

        # Rule 3: DEGRADED ESCALATION
        if severity == "low":
            self._state.consecutive_degraded += 1
            if self._state.consecutive_degraded >= self._escalation_threshold:
                self._state.was_incident_active = True
                self._state.last_severity = "high"
                self._state.last_incident = incident
                self._state.last_sent_at = now
                self._state.consecutive_degraded = 0
                return PolicyDecision(
                    action="escalate",
                    channels=["console", "snapshot", "external"],
                    severity_tier="high",
                    reason=f"escalated: {self._escalation_threshold} consecutive degraded",
                )

        # Rule 4: URGENCY for critical
        urgent = severity == "critical"

        # Default: send as-is
        self._state.was_incident_active = severity in ("critical", "high")
        self._state.last_severity = severity
        self._state.last_incident = incident
        self._state.last_sent_at = now
        if severity == "low":
            pass  # consecutive_degraded already incremented
        else:
            self._state.consecutive_degraded = 0

        return PolicyDecision(
            action="send",
            channels=channels,
            severity_tier=severity,
            reason=reason,
            urgent=urgent,
        )

    def reset(self) -> None:
        """Reset policy state (for testing)."""
        self._state = _PolicyState()
