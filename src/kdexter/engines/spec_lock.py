"""
Spec Lock Engine -- L22 K-Dexter AOS

Purpose: prevent spec mutations after SPEC_READY state is reached.
Tracks all mutation attempts while locked and counts blocked mutations.

Output: spec_mutation_count (int) -> EvaluationContext.spec_mutation_count -> Gate G-26
        Gate G-26 criterion: spec_mutation_count == 0

Governance: B1 (constitution tier — spec integrity is a hard constraint)
Gate: G-26 LOCK_CHECK at VALIDATING[10]
Mandatory: M-17 (spec lock check must run at VALIDATING[10])
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class BlockedMutation:
    """Record of a single rejected mutation attempt."""
    field_name: str
    old_value: Any
    new_value: Any
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SpecLockResult:
    """Snapshot of spec lock state, suitable for gate evaluation."""
    locked: bool
    mutation_count: int
    mutations_blocked: list[BlockedMutation] = field(default_factory=list)


# ------------------------------------------------------------------ #
# L22 Spec Lock Engine
# ------------------------------------------------------------------ #

class SpecLockEngine:
    """
    L22 Spec Lock Engine (B1 tier).

    Locks the spec after SPEC_READY state is reached.  Any mutation attempt
    while locked is rejected, recorded, and counted.  The running count feeds
    EvaluationContext.spec_mutation_count which Gate G-26 checks for == 0.

    M-17: spec lock check must execute as VALIDATING internal check [10].

    Usage:
        engine = SpecLockEngine()
        engine.lock()                                    # called on SPEC_READY
        allowed = engine.check_mutation("symbol", "BTC", "ETH")  # False
        result = engine.get_result()
        # result.mutation_count -> feed into EvaluationContext.spec_mutation_count
    """

    def __init__(self) -> None:
        self._locked: bool = False
        self._mutations_blocked: list[BlockedMutation] = []

    # ---------------------------------------------------------------- #
    # Lock control
    # ---------------------------------------------------------------- #

    def lock(self) -> None:
        """Lock the spec.  Called when work state reaches SPEC_READY."""
        self._locked = True

    def unlock(self) -> None:
        """
        Unlock the spec.  Clears all blocked-mutation history.

        Intended for use when a new spec cycle begins (e.g., DRAFT reset)
        or during REDESIGN when the spec itself is intentionally replaced.
        """
        self._locked = False
        self._mutations_blocked = []

    @property
    def is_locked(self) -> bool:
        """True if the spec is currently locked."""
        return self._locked

    # ---------------------------------------------------------------- #
    # Mutation check
    # ---------------------------------------------------------------- #

    def check_mutation(
        self,
        field_name: str,
        old_value: Any,
        new_value: Any,
    ) -> bool:
        """
        Check whether a spec field mutation is permitted.

        If unlocked:  mutation is allowed  — returns True.
        If locked:    mutation is rejected  — records the attempt, returns False.

        Args:
            field_name: name of the spec field being changed
            old_value:  current value of the field
            new_value:  proposed new value of the field

        Returns:
            True  — mutation is allowed (spec not locked, or values identical)
            False — mutation is blocked (spec is locked and values differ)
        """
        if not self._locked:
            return True

        # Identical value is not a real mutation — do not penalise it.
        if old_value == new_value:
            return True

        self._mutations_blocked.append(
            BlockedMutation(
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
            )
        )
        return False

    # ---------------------------------------------------------------- #
    # Result / reporting
    # ---------------------------------------------------------------- #

    @property
    def mutation_count(self) -> int:
        """Total number of blocked mutation attempts since last unlock."""
        return len(self._mutations_blocked)

    def get_result(self) -> SpecLockResult:
        """
        Return current spec lock state as a SpecLockResult.

        SpecLockResult.mutation_count is the value to assign to
        EvaluationContext.spec_mutation_count before gate evaluation.
        """
        return SpecLockResult(
            locked=self._locked,
            mutation_count=self.mutation_count,
            mutations_blocked=list(self._mutations_blocked),
        )

    def reset_mutation_count(self) -> None:
        """
        Clear the blocked-mutation history without unlocking.

        Use sparingly — only when a deliberate spec amendment has been
        reviewed and approved upstream (e.g., after REDESIGN approval).
        """
        self._mutations_blocked = []
