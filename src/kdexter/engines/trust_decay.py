"""
Trust Decay Engine -- L19 K-Dexter AOS

Purpose: manage trust score decay and recovery for system components.
Wraps TrustStateContext with periodic background decay and event processing.

Output: trust_score (float) -> EvaluationContext.trust_score -> Gate G-23 (trust_score >= 0.60)

Governance: B2 (governance_layer_map.md -- L19)
Gate: G-23 TRUST_CHECK at VALIDATING[8]
Thresholds: config/thresholds.py (OQ-5 resolved)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from kdexter.config.thresholds import (
    TRUST_BOUNDARY_DEGRADED,
    TRUST_DECAY_BACKGROUND_RATE,
)
from kdexter.state_machine.trust_state import TrustStateContext, TrustStateEnum


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class TrustCheckResult:
    """Result of a trust check."""
    component_id: str
    trust_score: float
    trust_state: TrustStateEnum
    passed_gate: bool          # score >= TRUST_BOUNDARY_DEGRADED (0.60)
    decay_applied: float       # background decay applied this check
    checked_at: datetime = field(default_factory=datetime.utcnow)


# ------------------------------------------------------------------ #
# L19 Trust Decay Engine
# ------------------------------------------------------------------ #

class TrustDecayEngine:
    """
    L19 Trust Decay Engine.

    Manages one or more TrustStateContext instances, applying background
    decay based on elapsed time and processing failure/success events.

    Usage:
        engine = TrustDecayEngine()
        engine.register("main_strategy", TrustStateContext("main_strategy"))
        result = engine.check("main_strategy")
        # result.trust_score -> feed into EvaluationContext
    """

    def __init__(self) -> None:
        self._components: dict[str, TrustStateContext] = {}
        self._last_check_time: dict[str, datetime] = {}

    def register(self, component_id: str, ctx: TrustStateContext) -> None:
        """Register a component for trust tracking."""
        self._components[component_id] = ctx
        self._last_check_time[component_id] = datetime.utcnow()

    def unregister(self, component_id: str) -> None:
        """Remove a component from tracking."""
        self._components.pop(component_id, None)
        self._last_check_time.pop(component_id, None)

    def get_context(self, component_id: str) -> Optional[TrustStateContext]:
        """Get the TrustStateContext for a component."""
        return self._components.get(component_id)

    def check(self, component_id: str) -> TrustCheckResult:
        """
        Apply background decay since last check and return current trust state.

        Args:
            component_id: registered component identifier

        Returns:
            TrustCheckResult with trust_score for EvaluationContext

        Raises:
            KeyError: if component_id not registered
        """
        ctx = self._components[component_id]
        now = datetime.utcnow()
        last = self._last_check_time.get(component_id, now)

        elapsed_hours = (now - last).total_seconds() / 3600.0
        decay_applied = 0.0

        if elapsed_hours > 0:
            decay_applied = TRUST_DECAY_BACKGROUND_RATE * elapsed_hours
            ctx.apply_background_decay(elapsed_hours)

        self._last_check_time[component_id] = now

        return TrustCheckResult(
            component_id=component_id,
            trust_score=ctx.score,
            trust_state=ctx.current,
            passed_gate=ctx.score >= TRUST_BOUNDARY_DEGRADED,
            decay_applied=round(decay_applied, 6),
        )

    def on_failure(self, component_id: str, severity: str) -> None:
        """Record a failure event for a component."""
        self._components[component_id].on_failure(severity)

    def on_success(self, component_id: str) -> None:
        """Record a success event for a component."""
        self._components[component_id].on_success()

    def on_recovery_complete(self, component_id: str) -> None:
        """Record a recovery completion for a component."""
        self._components[component_id].on_recovery_complete()

    def check_all(self) -> dict[str, TrustCheckResult]:
        """Check all registered components, return dict of results."""
        return {cid: self.check(cid) for cid in self._components}

    def lowest_trust(self) -> Optional[TrustCheckResult]:
        """Return the component with the lowest trust score, or None if empty."""
        if not self._components:
            return None
        results = self.check_all()
        return min(results.values(), key=lambda r: r.trust_score)
