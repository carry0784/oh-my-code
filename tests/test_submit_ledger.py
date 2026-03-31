"""
K-Dexter Submit Ledger Tests

Tests the Submit boundary controls (final gate before order submission):
  AXIS 1: Submit Board (lifecycle, status tracking, orphan detection)
  AXIS 2: Submit Guard (6 checks: exec_receipted, governance, cost, lockdown, exchange, size)
  AXIS 3: Receipt fail-closed (receipt requires SUBMIT_GUARDED + guard_passed)
  AXIS 4: State Machine (forbidden transitions, terminal states)
  AXIS 5: Boundary (no exchange imports, append-only, no force)
  AXIS 6: Lineage (3-tier: agent -> execution -> submit)

Run: pytest tests/test_submit_ledger.py -v
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# -- Helpers ---------------------------------------------------------------- #

def _make_ledger():
    from app.services.submit_ledger import SubmitLedger
    return SubmitLedger(max_buffer=100)


def _good_risk():
    return {"approved": True, "position_size": 5000, "risk_score": 0.3}


def _oversized_risk():
    return {"approved": True, "position_size": 999999, "risk_score": 0.5}


def _guard_args(**overrides):
    """Default args for propose_and_guard."""
    defaults = {
        "task_type": "execute_trade",
        "symbol": "BTC/USDT",
        "exchange": "binance",
        "agent_proposal_id": "AP-test-001",
        "execution_proposal_id": "EP-test-001",
        "execution_proposal_status": "EXEC_RECEIPTED",
        "risk_result": _good_risk(),
        "pre_evidence_id": "ev-pre-001",
    }
    defaults.update(overrides)
    return defaults


# -- AXIS 1: Submit Board -------------------------------------------------- #

class TestSubmitBoard:
    """Proposal creation, lifecycle, board view, orphan detection."""

    def test_proposal_created_on_guard(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(**_guard_args())
        assert proposal.proposal_id.startswith("SP-")
        assert proposal.agent_proposal_id == "AP-test-001"
        assert proposal.execution_proposal_id == "EP-test-001"
        assert ledger.count == 1

    def test_board_groups_by_status(self):
        ledger = _make_ledger()
        # One guarded
        ledger.propose_and_guard(**_guard_args(symbol="BTC"))
        # One blocked (exec not receipted)
        ledger.propose_and_guard(**_guard_args(symbol="ETH", execution_proposal_status="EXEC_GUARDED"))
        board = ledger.get_board()
        assert board["total"] == 2
        assert len(board["submit_guarded"]) == 1
        assert len(board["submit_blocked"]) == 1

    def test_lifecycle_guarded_to_receipted(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args())
        assert proposal.status == "SUBMIT_GUARDED"
        assert proposal.submit_ready is False
        ledger.record_receipt(proposal, {"stage": "ready", "adjusted_size": 5000})
        assert proposal.status == "SUBMIT_RECEIPTED"
        assert proposal.submit_ready is True

    def test_lifecycle_guarded_to_failed(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="SOL"))
        ledger.record_failure(proposal, "timeout")
        assert proposal.status == "SUBMIT_FAILED"
        assert proposal.submit_ready is False

    def test_orphan_detection(self):
        ledger = _make_ledger()
        ledger.propose_and_guard(**_guard_args())
        board = ledger.get_board()
        assert board["orphan_count"] == 1

    def test_submit_ready_at_in_receipt(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="AVAX"))
        receipt = ledger.record_receipt(proposal, {"stage": "ready"})
        assert receipt.submit_ready_at != ""


# -- AXIS 2: Submit Guard (6 checks) -------------------------------------- #

class TestSubmitGuard:
    """6-check gate: exec_receipted, governance, cost, lockdown, exchange, size."""

    def test_all_pass(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(**_guard_args())
        assert passed is True
        assert proposal.status == "SUBMIT_GUARDED"
        assert proposal.guard_checks["EXEC_RECEIPTED"]["passed"] is True
        assert proposal.guard_checks["GOVERNANCE_FINAL"]["passed"] is True
        assert proposal.guard_checks["COST_FINAL"]["passed"] is True
        assert proposal.guard_checks["LOCKDOWN_FINAL"]["passed"] is True
        assert proposal.guard_checks["EXCHANGE_ALLOWED"]["passed"] is True
        assert proposal.guard_checks["SIZE_SUBMIT_CHECK"]["passed"] is True

    def test_exec_not_receipted_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(execution_proposal_status="EXEC_GUARDED")
        )
        assert passed is False
        assert proposal.guard_checks["EXEC_RECEIPTED"]["passed"] is False

    def test_no_governance_evidence_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="ETH", pre_evidence_id=None)
        )
        assert passed is False
        assert proposal.guard_checks["GOVERNANCE_FINAL"]["passed"] is False

    def test_cost_exhausted_blocks(self):
        ledger = _make_ledger()
        mock_cc = MagicMock()
        mock_budget = MagicMock()
        mock_budget.current = 500
        mock_budget.limit = 500
        mock_cc.get_budget.return_value = mock_budget
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="DOGE"), cost_controller=mock_cc,
        )
        assert passed is False
        assert proposal.guard_checks["COST_FINAL"]["passed"] is False

    def test_lockdown_blocks(self):
        ledger = _make_ledger()
        mock_ctx = MagicMock()
        mock_ctx.is_locked_down.return_value = True
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="XRP"), security_ctx=mock_ctx,
        )
        assert passed is False
        assert proposal.guard_checks["LOCKDOWN_FINAL"]["passed"] is False

    def test_quarantine_blocks(self):
        ledger = _make_ledger()
        mock_ctx = MagicMock()
        mock_ctx.is_locked_down.return_value = False
        mock_ctx.sandbox_only.return_value = True
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="LINK"), security_ctx=mock_ctx,
        )
        assert passed is False
        assert proposal.guard_checks["LOCKDOWN_FINAL"]["passed"] is False

    def test_exchange_not_allowed_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="BTC/OKX", exchange="okx")
        )
        assert passed is False
        assert proposal.guard_checks["EXCHANGE_ALLOWED"]["passed"] is False
        assert "okx" in proposal.guard_checks["EXCHANGE_ALLOWED"]["detail"]

    def test_exchange_none_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="BTC/NONE", exchange=None)
        )
        assert passed is False
        assert proposal.guard_checks["EXCHANGE_ALLOWED"]["passed"] is False

    def test_oversized_position_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="ADA", risk_result=_oversized_risk())
        )
        assert passed is False
        assert proposal.guard_checks["SIZE_SUBMIT_CHECK"]["passed"] is False

    def test_no_force_override(self):
        ledger = _make_ledger()
        assert not hasattr(ledger, "force_apply")
        assert not hasattr(ledger, "force_guard")
        assert not hasattr(ledger, "bypass_guard")


# -- AXIS 3: Receipt fail-closed ------------------------------------------ #

class TestReceiptFailClosed:
    """Receipt requires SUBMIT_GUARDED + guard_passed=True."""

    def test_receipt_on_guarded_succeeds(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args())
        receipt = ledger.record_receipt(proposal, {"stage": "ready"})
        assert receipt.receipt_id.startswith("SR-")
        assert proposal.submit_ready is True

    def test_receipt_on_unguarded_raises(self):
        from app.services.submit_ledger import SubmitProposal, SubmitStateTransitionError
        raw = SubmitProposal(
            proposal_id="SP-test", agent_proposal_id="AP-test",
            execution_proposal_id="EP-test",
            task_type="test", status="SUBMIT_PROPOSED",
            created_at="2026-01-01T00:00:00Z",
        )
        ledger = _make_ledger()
        with pytest.raises(SubmitStateTransitionError, match="guard_passed is False"):
            ledger.record_receipt(raw, {"stage": "ready"})

    def test_receipt_on_blocked_raises(self):
        from app.services.submit_ledger import SubmitStateTransitionError
        ledger = _make_ledger()
        _, blocked = ledger.propose_and_guard(
            **_guard_args(symbol="DOT", execution_proposal_status="EXEC_BLOCKED")
        )
        assert blocked.status == "SUBMIT_BLOCKED"
        with pytest.raises(SubmitStateTransitionError):
            ledger.record_receipt(blocked, {"stage": "ready"})

    def test_receipt_contains_lineage_ids(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="MATIC"))
        receipt = ledger.record_receipt(proposal, {"stage": "ready"})
        assert receipt.agent_proposal_id == "AP-test-001"
        assert receipt.execution_proposal_id == "EP-test-001"


# -- AXIS 4: State Machine ------------------------------------------------ #

class TestStateMachine:
    """Forbidden transitions, terminal states."""

    def test_proposed_to_receipted_forbidden(self):
        from app.services.submit_ledger import SubmitProposal, SubmitStateTransitionError
        raw = SubmitProposal(
            proposal_id="SP-test", agent_proposal_id="AP-test",
            execution_proposal_id="EP-test",
            task_type="test", status="SUBMIT_PROPOSED",
            created_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(SubmitStateTransitionError, match="Forbidden transition"):
            raw.transition_to("SUBMIT_RECEIPTED")

    def test_blocked_is_terminal(self):
        from app.services.submit_ledger import SubmitStateTransitionError
        ledger = _make_ledger()
        _, blocked = ledger.propose_and_guard(
            **_guard_args(symbol="UNI", execution_proposal_status="EXEC_FAILED")
        )
        with pytest.raises(SubmitStateTransitionError):
            blocked.transition_to("SUBMIT_GUARDED")

    def test_receipted_is_terminal(self):
        from app.services.submit_ledger import SubmitStateTransitionError
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="ATOM"))
        ledger.record_receipt(proposal, {"stage": "ready"})
        with pytest.raises(SubmitStateTransitionError):
            proposal.transition_to("SUBMIT_FAILED")

    def test_failed_is_terminal(self):
        from app.services.submit_ledger import SubmitStateTransitionError
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="FTM"))
        ledger.record_failure(proposal, "error")
        with pytest.raises(SubmitStateTransitionError):
            proposal.transition_to("SUBMIT_RECEIPTED")

    def test_no_state_regression(self):
        from app.services.submit_ledger import SubmitStateTransitionError
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="NEAR"))
        with pytest.raises(SubmitStateTransitionError):
            proposal.transition_to("SUBMIT_PROPOSED")

    def test_failure_on_blocked_raises(self):
        from app.services.submit_ledger import SubmitStateTransitionError
        ledger = _make_ledger()
        _, blocked = ledger.propose_and_guard(
            **_guard_args(symbol="SAND", execution_proposal_status="EXEC_BLOCKED")
        )
        with pytest.raises(SubmitStateTransitionError):
            ledger.record_failure(blocked, "error")


# -- AXIS 5: Boundary ----------------------------------------------------- #

class TestBoundary:
    """No exchange imports, append-only, no force."""

    def test_no_exchange_import(self):
        import importlib
        source = importlib.util.find_spec("app.services.submit_ledger")
        if source and source.origin:
            content = Path(source.origin).read_text(encoding="utf-8")
            assert "from exchanges" not in content
            assert "import exchanges" not in content

    def test_no_order_service_import(self):
        import importlib
        source = importlib.util.find_spec("app.services.submit_ledger")
        if source and source.origin:
            content = Path(source.origin).read_text(encoding="utf-8")
            assert "order_service" not in content.lower() or "never submits orders" in content.lower()

    def test_append_only(self):
        ledger = _make_ledger()
        ledger.propose_and_guard(**_guard_args())
        ledger.propose_and_guard(**_guard_args(symbol="ETH", execution_proposal_status="EXEC_BLOCKED"))
        assert ledger.count == 2
        assert not hasattr(ledger, "delete")
        assert not hasattr(ledger, "remove")
        assert not hasattr(ledger, "clear_proposals")


# -- AXIS 6: Lineage (3-tier) --------------------------------------------- #

class TestLineage:
    """Agent -> Execution -> Submit lineage chain."""

    def test_agent_and_execution_ids_linked(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args())
        assert proposal.agent_proposal_id == "AP-test-001"
        assert proposal.execution_proposal_id == "EP-test-001"

    def test_lineage_without_exec_receipt_blocked(self):
        """Execution proposal not EXEC_RECEIPTED -> SUBMIT_BLOCKED."""
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            **_guard_args(symbol="LTC", execution_proposal_status="EXEC_GUARDED")
        )
        assert passed is False
        assert "EXEC_RECEIPTED" in str(proposal.guard_checks)

    def test_get_full_lineage_3tier(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(**_guard_args(symbol="CRV"))
        ledger.record_receipt(proposal, {"stage": "ready"})
        lineage = ledger.get_full_lineage(proposal.proposal_id)
        assert lineage is not None
        assert lineage["agent_proposal_id"] == "AP-test-001"
        assert lineage["execution_proposal_id"] == "EP-test-001"
        assert lineage["submit_ready"] is True
        assert lineage["receipt_id"] is not None

    def test_lineage_not_found(self):
        ledger = _make_ledger()
        assert ledger.get_full_lineage("SP-nonexistent") is None

    def test_duplicate_suppression(self):
        ledger = _make_ledger()
        passed1, _ = ledger.propose_and_guard(**_guard_args(symbol="BTC"))
        assert passed1 is True
        passed2, p2 = ledger.propose_and_guard(**_guard_args(symbol="BTC"))
        assert passed2 is False
        assert "DUPLICATE" in str(p2.guard_reasons)
