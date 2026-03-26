"""
Card C-35: Retry Policy Gate

Purpose:
  System-level gate that determines whether a retry pass should
  proceed at all, before individual plan eligibility checks.

Design:
  - Checks global conditions before retry execution
  - Fail-closed: gate errors → deny retry
  - Read-only: does not modify state
  - No daemon, scheduler, background worker

Gate conditions:
  1. Store must have pending plans
  2. System must not be in lockdown/maintenance mode
  3. Global retry enabled flag must be true
  4. Max concurrent passes must not be exceeded
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class GateDecision:
    """Result of retry policy gate evaluation."""
    allowed: bool
    reason: str
    pending_count: int = 0
    gate_checks: int = 0
    gate_passed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetryPolicyGate:
    """
    System-level gate for retry pass execution.

    Evaluates global conditions before allowing retry execution.
    Does NOT evaluate individual plan eligibility (that's C-29/C-31).
    """

    def __init__(
        self,
        enabled: bool = True,
        max_pending_threshold: int = 500,
        maintenance_mode: bool = False,
    ) -> None:
        self._enabled = enabled
        self._max_pending_threshold = max_pending_threshold
        self._maintenance_mode = maintenance_mode
        self._pass_in_progress = False

    def evaluate(self, plan_store: Any) -> GateDecision:
        """
        Evaluate whether a retry pass should proceed.

        Args:
            plan_store: RetryPlanStore instance (C-30)

        Returns:
            GateDecision with allowed flag and reason.

        Fail-closed: errors → deny.
        """
        try:
            return self._evaluate_impl(plan_store)
        except Exception:
            return GateDecision(
                allowed=False,
                reason="gate_evaluation_error",
            )

    def _evaluate_impl(self, plan_store: Any) -> GateDecision:
        decision = GateDecision(allowed=True, reason="", gate_checks=0, gate_passed=0)

        # Check 1: Global enabled
        decision.gate_checks += 1
        if not self._enabled:
            decision.allowed = False
            decision.reason = "retry_globally_disabled"
            return decision
        decision.gate_passed += 1

        # Check 2: Maintenance mode
        decision.gate_checks += 1
        if self._maintenance_mode:
            decision.allowed = False
            decision.reason = "maintenance_mode_active"
            return decision
        decision.gate_passed += 1

        # Check 3: Pass not already in progress
        decision.gate_checks += 1
        if self._pass_in_progress:
            decision.allowed = False
            decision.reason = "pass_already_in_progress"
            return decision
        decision.gate_passed += 1

        # Check 4: Pending plans exist
        decision.gate_checks += 1
        try:
            pending = plan_store.pending_count()
            decision.pending_count = pending
        except Exception:
            decision.allowed = False
            decision.reason = "store_unavailable"
            return decision

        if pending == 0:
            decision.allowed = False
            decision.reason = "no_pending_plans"
            return decision
        decision.gate_passed += 1

        # Check 5: Not over threshold
        decision.gate_checks += 1
        if pending > self._max_pending_threshold:
            decision.allowed = False
            decision.reason = f"pending_exceeds_threshold ({pending}/{self._max_pending_threshold})"
            return decision
        decision.gate_passed += 1

        decision.reason = "all_gates_passed"
        return decision

    def acquire_pass(self) -> bool:
        """Mark a pass as in-progress. Returns False if already running."""
        if self._pass_in_progress:
            return False
        self._pass_in_progress = True
        return True

    def release_pass(self) -> None:
        """Release the pass lock."""
        self._pass_in_progress = False

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable retry globally."""
        self._enabled = enabled

    def set_maintenance(self, active: bool) -> None:
        """Enable or disable maintenance mode."""
        self._maintenance_mode = active

    def get_state(self) -> dict[str, Any]:
        """Get current gate state."""
        return {
            "enabled": self._enabled,
            "maintenance_mode": self._maintenance_mode,
            "pass_in_progress": self._pass_in_progress,
            "max_pending_threshold": self._max_pending_threshold,
        }
