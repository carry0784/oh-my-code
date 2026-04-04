"""
CR-046 Phase 0: Governance Preflight Tests

Verifies that GovernanceGate, ExecutionGate, and StrategyLifecycle
support the required PAPER_TRADING auto-approval and PROMOTED manual-approval patterns.
"""

import pytest

from app.services.governance_gate import GovernanceGate, GovernanceDecision
from app.services.strategy_lifecycle import (
    StrategyState,
    StrategyLifecycleManager,
    TransitionRequest,
    ALLOWED_TRANSITIONS,
)


class TestPaperTradingTransition:
    """PAPER_TRADING transition must be auto-approved."""

    def test_paper_trading_transition_auto_approved(self):
        gate = GovernanceGate(dry_run=True)
        request = TransitionRequest(
            genome_id="test-smc-wt",
            from_state=StrategyState.VALIDATED,
            to_state=StrategyState.PAPER_TRADING,
            reason="CR-046 Phase 5a SOL paper rollout",
        )
        decision = gate.check(request)
        assert decision.decision == "APPROVED"
        assert decision.auto_decided is True
        assert decision.operator_required is False

    def test_paper_trading_in_allowed_transitions(self):
        allowed = ALLOWED_TRANSITIONS[StrategyState.VALIDATED]
        assert StrategyState.PAPER_TRADING in allowed


class TestPromotedTransition:
    """PROMOTED transition must require manual approval in dry_run/Mode 1."""

    def test_promoted_transition_requires_manual_approval(self):
        gate = GovernanceGate(dry_run=True)
        request = TransitionRequest(
            genome_id="test-smc-wt",
            from_state=StrategyState.PAPER_TRADING,
            to_state=StrategyState.PROMOTED,
            reason="Attempting promotion",
        )
        decision = gate.check(request)
        assert decision.decision == "PENDING_OPERATOR"
        assert decision.operator_required is True
        assert decision.auto_decided is False

    def test_promoted_in_allowed_transitions(self):
        allowed = ALLOWED_TRANSITIONS[StrategyState.PAPER_TRADING]
        assert StrategyState.PROMOTED in allowed


class TestExecutionGateBlocksWhenLockdown:
    """ExecutionGate must block (CLOSED) when lockdown is active.

    We test the condition logic structurally: 4 conditions AND,
    any failure -> CLOSED.
    """

    def test_execution_gate_blocks_when_lockdown(self):
        # ExecutionGate uses app.main imports which require full app context.
        # We verify the structural guarantee: 4 conditions AND, all must pass.
        from app.core.execution_gate import evaluate_execution_gate

        # Without running app (no app.state), all conditions fail-closed -> CLOSED
        result = evaluate_execution_gate()
        assert result.decision.value == "CLOSED"
        assert result.conditions_met < 4


class TestDryRunEnforced:
    """dry_run=True must be the default for GovernanceGate."""

    def test_dry_run_true_enforced_in_paper_state(self):
        gate = GovernanceGate()  # default constructor
        assert gate.dry_run is True

        # With dry_run=True, PROMOTED is always PENDING_OPERATOR
        request = TransitionRequest(
            genome_id="test",
            from_state=StrategyState.PAPER_TRADING,
            to_state=StrategyState.PROMOTED,
            reason="test",
        )
        decision = gate.check(request)
        assert decision.decision == "PENDING_OPERATOR"


class TestLifecycleStateTransitions:
    """Verify CANDIDATE → VALIDATED → PAPER_TRADING → PROMOTED path."""

    def test_full_lifecycle_path(self):
        mgr = StrategyLifecycleManager()
        mgr.register("smc-wt-sol")

        # CANDIDATE → VALIDATED
        assert mgr.request_transition(
            TransitionRequest(
                genome_id="smc-wt-sol",
                from_state=StrategyState.CANDIDATE,
                to_state=StrategyState.VALIDATED,
                reason="Phase 1-4 passed",
            )
        )

        # VALIDATED → PAPER_TRADING
        assert mgr.request_transition(
            TransitionRequest(
                genome_id="smc-wt-sol",
                from_state=StrategyState.VALIDATED,
                to_state=StrategyState.PAPER_TRADING,
                reason="CR-046 Phase 5a approved",
            )
        )

        # PAPER_TRADING → PROMOTED
        assert mgr.request_transition(
            TransitionRequest(
                genome_id="smc-wt-sol",
                from_state=StrategyState.PAPER_TRADING,
                to_state=StrategyState.PROMOTED,
                reason="A manual approval",
            )
        )

        record = mgr.get_state("smc-wt-sol")
        assert record.current_state == StrategyState.PROMOTED
        assert record.promotion_count == 1

    def test_invalid_transition_rejected(self):
        mgr = StrategyLifecycleManager()
        mgr.register("smc-wt-sol")

        # CANDIDATE → PROMOTED (not allowed)
        result = mgr.request_transition(
            TransitionRequest(
                genome_id="smc-wt-sol",
                from_state=StrategyState.CANDIDATE,
                to_state=StrategyState.PROMOTED,
                reason="skip ahead",
            )
        )
        assert result is False
