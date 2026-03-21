"""
Intent Drift Engine — L15 K-Dexter AOS

Purpose: continuously monitor whether current system behavior diverges
from the user's original intent (as captured in CLARIFYING/SPEC_READY states).

Drift score: 0.0 = identical to intent, 1.0 = completely diverged.

Thresholds (OQ-4 resolved — config/thresholds.py):
  < DRIFT_WARN_THRESHOLD  (0.15): normal — no action
  ≥ DRIFT_WARN_THRESHOLD  (0.15): warn — log, continue
  ≥ DRIFT_HIGH_THRESHOLD  (0.35): BLOCK — execution forbidden until reviewed

Governance: B2 (governance_layer_map.md — L15)
Gate: G-19 Drift Gate (criteria now defined via DRIFT_HIGH_THRESHOLD)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from kdexter.config.thresholds import DRIFT_HIGH_THRESHOLD, DRIFT_WARN_THRESHOLD


class DriftLevel(Enum):
    NORMAL = "NORMAL"       # score < DRIFT_WARN_THRESHOLD
    WARNING = "WARNING"     # DRIFT_WARN_THRESHOLD ≤ score < DRIFT_HIGH_THRESHOLD
    HIGH = "HIGH"           # score ≥ DRIFT_HIGH_THRESHOLD — execution BLOCKED


@dataclass
class DriftCheckResult:
    score: float
    level: DriftLevel
    blocked: bool
    dimensions: dict[str, float]   # per-dimension breakdown
    checked_at: datetime = field(default_factory=datetime.utcnow)
    reason: Optional[str] = None


@dataclass
class IntentSnapshot:
    """
    Snapshot of the user's original intent, captured at CLARIFYING state.
    Used as the reference point for all subsequent drift measurements.
    """
    intent_id: str
    captured_at: datetime = field(default_factory=datetime.utcnow)
    intent_text: str = ""
    goal_scope: list[str] = field(default_factory=list)     # e.g. ["spot_trading", "KRW_pairs"]
    risk_budget: float = 0.02                                # e.g. max 2% loss per trade
    allowed_exchanges: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)


class IntentDriftEngine:
    """
    L15 Intent Drift Engine.

    Measures drift across 4 dimensions, each weighted equally (0.25 each):
      1. scope_drift     — current execution scope vs original goal_scope
      2. risk_drift      — current risk exposure vs original risk_budget
      3. rule_drift      — Rule Ledger changes since intent capture
      4. goal_drift      — current optimization target vs original intent_text embedding

    Total drift_score = weighted average of 4 dimensions.

    NOTE: Dimensions 1~3 are implemented here as stubs. Dimension 4 (goal_drift
    via embedding comparison) requires LLM integration — TODO in later step.
    """

    DIMENSION_WEIGHT: float = 0.25   # equal weight for all 4 dimensions

    def __init__(self, intent: IntentSnapshot) -> None:
        self._intent = intent
        self._last_result: Optional[DriftCheckResult] = None

    @property
    def last_result(self) -> Optional[DriftCheckResult]:
        return self._last_result

    def check(
        self,
        current_scope: list[str],
        current_risk_exposure: float,
        rule_change_count: int,
        goal_embedding_distance: float = 0.0,   # 0.0 until LLM integration
    ) -> DriftCheckResult:
        """
        Compute drift score from current system state vs captured intent.

        Args:
            current_scope:            active execution scope labels
            current_risk_exposure:    current max risk per trade (0.0~1.0)
            rule_change_count:        number of Rule Ledger changes since intent capture
            goal_embedding_distance:  cosine distance of current goal vs original (0=same)

        Returns:
            DriftCheckResult with score, level, blocked flag, and dimension breakdown.
        """
        scope_drift = self._measure_scope_drift(current_scope)
        risk_drift = self._measure_risk_drift(current_risk_exposure)
        rule_drift = self._measure_rule_drift(rule_change_count)
        goal_drift = min(1.0, goal_embedding_distance)

        dimensions = {
            "scope_drift": scope_drift,
            "risk_drift":  risk_drift,
            "rule_drift":  rule_drift,
            "goal_drift":  goal_drift,
        }
        score = sum(dimensions.values()) * self.DIMENSION_WEIGHT

        if score >= DRIFT_HIGH_THRESHOLD:
            level = DriftLevel.HIGH
        elif score >= DRIFT_WARN_THRESHOLD:
            level = DriftLevel.WARNING
        else:
            level = DriftLevel.NORMAL

        result = DriftCheckResult(
            score=round(score, 4),
            level=level,
            blocked=(level == DriftLevel.HIGH),
            dimensions=dimensions,
            reason=self._build_reason(dimensions, score) if level != DriftLevel.NORMAL else None,
        )
        self._last_result = result
        return result

    # ── Dimension measurements ──────────────────────────────────────────── #

    def _measure_scope_drift(self, current_scope: list[str]) -> float:
        """
        Jaccard distance between original goal_scope and current_scope.
        0.0 = identical, 1.0 = completely different sets.
        """
        original = set(self._intent.goal_scope)
        current = set(current_scope)
        if not original and not current:
            return 0.0
        if not original or not current:
            return 1.0
        intersection = len(original & current)
        union = len(original | current)
        return round(1.0 - intersection / union, 4)

    def _measure_risk_drift(self, current_risk_exposure: float) -> float:
        """
        Normalized deviation from original risk_budget.
        Capped at 1.0.
        """
        original = self._intent.risk_budget
        if original == 0.0:
            return 0.0 if current_risk_exposure == 0.0 else 1.0
        drift = abs(current_risk_exposure - original) / original
        return min(1.0, round(drift, 4))

    def _measure_rule_drift(self, rule_change_count: int) -> float:
        """
        Maps rule change count to a drift score.
        0 changes → 0.0, 20+ changes → 1.0 (linear, capped).
        Rationale: 20 rule changes since intent capture implies significant
        structural evolution — high drift regardless of other dimensions.
        """
        MAX_CHANGES = 20
        return min(1.0, round(rule_change_count / MAX_CHANGES, 4))

    @staticmethod
    def _build_reason(dimensions: dict[str, float], total: float) -> str:
        top = max(dimensions, key=lambda k: dimensions[k])
        return (
            f"drift_score={total:.3f} ≥ threshold. "
            f"Highest contributor: {top}={dimensions[top]:.3f}"
        )
