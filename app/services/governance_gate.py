"""
GovernanceGate — CR-044 Phase 7
Governance checkpoint for autonomous decisions.

Rules:
  - Promotions (PAPER_TRADING → PROMOTED) always require operator in Mode 1
  - Demotions and retirements can be auto-approved (fail-closed safety)
  - dry_run=True blocks all actual execution

Pure computation — no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.core.logging import get_logger
from app.services.strategy_lifecycle import StrategyState, TransitionRequest

logger = get_logger(__name__)


@dataclass
class GovernanceDecision:
    request_id: str = ""
    decision: str = ""  # "APPROVED", "REJECTED", "PENDING_OPERATOR"
    reason: str = ""
    auto_decided: bool = False
    operator_required: bool = False
    timestamp: str = ""


class GovernanceGate:
    """Gates autonomous decisions through governance rules."""

    def __init__(
        self,
        dry_run: bool = True,
        auto_approve_threshold: float = 0.8,
    ):
        self.dry_run = dry_run
        self.auto_approve_threshold = auto_approve_threshold
        self.decision_log: list[GovernanceDecision] = []

    def check(self, request: TransitionRequest, fitness: float = 0.0) -> GovernanceDecision:
        decision = GovernanceDecision(
            request_id=str(uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Promotions always require operator in dry_run / Mode 1
        if request.to_state == StrategyState.PROMOTED:
            if self.dry_run:
                decision.decision = "PENDING_OPERATOR"
                decision.reason = "Promotion requires operator approval in Mode 1"
                decision.operator_required = True
            elif fitness >= self.auto_approve_threshold:
                decision.decision = "APPROVED"
                decision.reason = f"Fitness {fitness:.4f} >= threshold {self.auto_approve_threshold}"
                decision.auto_decided = True
            else:
                decision.decision = "PENDING_OPERATOR"
                decision.reason = f"Fitness {fitness:.4f} < threshold {self.auto_approve_threshold}"
                decision.operator_required = True
        # Demotions: auto-approve (fail-closed safety)
        elif request.to_state in (StrategyState.DEMOTED, StrategyState.RETIRED):
            decision.decision = "APPROVED"
            decision.reason = "Risk-reducing transition auto-approved"
            decision.auto_decided = True
        # Validations and paper trading: auto-approve
        elif request.to_state in (StrategyState.VALIDATED, StrategyState.PAPER_TRADING):
            decision.decision = "APPROVED"
            decision.reason = "Non-risk transition auto-approved"
            decision.auto_decided = True
        else:
            decision.decision = "REJECTED"
            decision.reason = f"Unknown transition to {request.to_state.value}"

        self.decision_log.append(decision)
        logger.info("governance_decision",
                     decision=decision.decision,
                     to_state=request.to_state.value,
                     auto=decision.auto_decided)
        return decision

    def get_pending(self) -> list[GovernanceDecision]:
        return [d for d in self.decision_log if d.decision == "PENDING_OPERATOR"]
