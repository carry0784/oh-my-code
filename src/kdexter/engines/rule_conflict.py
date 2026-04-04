"""
Rule Conflict Engine -- L16 K-Dexter AOS

Purpose: detect conflicts between active rules in the RuleLedger.
Two rules conflict when their conditions overlap and actions contradict.

Output: conflict_count (int) -> EvaluationContext.conflict_count -> Gate G-20 (conflict_count == 0)

Governance: B2 (governance_layer_map.md -- L16)
Gate: G-20 CONFLICT_CHECK at VALIDATING[5]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from kdexter.ledger.rule_ledger import Rule


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class ConflictPair:
    """A pair of rules that conflict."""
    rule_a_id: str
    rule_b_id: str
    reason: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConflictCheckResult:
    """Result of a conflict scan."""
    conflict_count: int
    conflicts: list[ConflictPair] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rules_scanned: int = 0


# ------------------------------------------------------------------ #
# Conflict detection helpers
# ------------------------------------------------------------------ #

# Actions that are mutually exclusive
_CONTRADICTORY_ACTIONS: list[tuple[str, str]] = [
    ("BLOCK", "ALLOW"),
    ("BUY", "SELL"),
    ("OPEN", "CLOSE"),
    ("ENABLE", "DISABLE"),
    ("INCREASE", "DECREASE"),
]


def _actions_contradict(action_a: str, action_b: str) -> bool:
    """Check if two action strings contain contradictory directives."""
    a_upper = action_a.upper()
    b_upper = action_b.upper()
    for left, right in _CONTRADICTORY_ACTIONS:
        if (left in a_upper and right in b_upper) or \
           (right in a_upper and left in b_upper):
            return True
    return False


def _conditions_overlap(cond_a: str, cond_b: str) -> bool:
    """
    Heuristic overlap detection for rule conditions.

    Two conditions overlap if:
    1. They are identical (exact match)
    2. They share the same metric reference (e.g. both mention 'loss' or 'price')

    NOTE: Full DSL expression overlap analysis is a future enhancement.
    For now, this heuristic catches the most common conflicts.
    """
    if not cond_a or not cond_b:
        return False
    # Exact match
    if cond_a.strip() == cond_b.strip():
        return True
    # Token-based overlap: extract alphanumeric tokens, check intersection
    tokens_a = set(cond_a.lower().split())
    tokens_b = set(cond_b.lower().split())
    # Remove common operators/noise
    noise = {"<", ">", "<=", ">=", "==", "!=", "and", "or", "not", "if", "then", "is"}
    tokens_a -= noise
    tokens_b -= noise
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    # If more than half the tokens overlap, conditions likely overlap
    min_size = min(len(tokens_a), len(tokens_b))
    return len(overlap) >= max(1, min_size * 0.5)


# ------------------------------------------------------------------ #
# L16 Rule Conflict Engine
# ------------------------------------------------------------------ #

class RuleConflictEngine:
    """
    L16 Rule Conflict Engine.

    Scans active rules from RuleLedger for pairwise conflicts.
    A conflict is detected when two rules have overlapping conditions
    AND contradictory actions.

    Usage:
        engine = RuleConflictEngine()
        result = engine.check(ledger.list_all())
        # result.conflict_count -> feed into EvaluationContext
    """

    def __init__(self) -> None:
        self._last_result: Optional[ConflictCheckResult] = None
        self._history: list[ConflictCheckResult] = []

    @property
    def last_result(self) -> Optional[ConflictCheckResult]:
        return self._last_result

    def check(self, rules: list[Rule]) -> ConflictCheckResult:
        """
        Scan all active rules for pairwise conflicts.

        Args:
            rules: list of active Rule objects (from RuleLedger.list_all())

        Returns:
            ConflictCheckResult with conflict_count for EvaluationContext
        """
        conflicts: list[ConflictPair] = []

        for i in range(len(rules)):
            for j in range(i + 1, len(rules)):
                ra, rb = rules[i], rules[j]
                if _conditions_overlap(ra.condition, rb.condition) and \
                   _actions_contradict(ra.action, rb.action):
                    conflicts.append(ConflictPair(
                        rule_a_id=ra.rule_id,
                        rule_b_id=rb.rule_id,
                        reason=f"Overlapping conditions with contradictory actions: "
                               f"'{ra.action}' vs '{rb.action}'",
                    ))

        result = ConflictCheckResult(
            conflict_count=len(conflicts),
            conflicts=conflicts,
            rules_scanned=len(rules),
        )
        self._last_result = result
        self._history.append(result)
        return result

    def history(self) -> list[ConflictCheckResult]:
        """Return all previous check results."""
        return list(self._history)
