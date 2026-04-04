"""
K-Dexter Agent Action Ledger Tests

Tests the transplanted controls from Skill Loop:
  AXIS 1: Proposal Board (lifecycle, status tracking)
  AXIS 2: Apply Guard (4 checks: risk, governance, size, cost)
  AXIS 3: Receipt Trail (evidence linking, fail-closed receipt)
  AXIS 4: Boundary (no exchange imports, append-only)
  AXIS 5: State Machine (forbidden transitions, fail-closed enforcement)
  AXIS 6: Fingerprint & Duplicate Suppression

Run: pytest tests/test_agent_action_ledger.py -v
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── Helpers ─────────────────────────────────────────────────────────────── #


def _make_ledger():
    from app.agents.action_ledger import ActionLedger

    return ActionLedger(max_buffer=100)


def _good_risk():
    return {"approved": True, "position_size": 5000, "risk_score": 0.3, "confidence": 0.8}


def _bad_risk():
    return {"approved": False, "position_size": 5000, "risk_score": 0.9}


def _oversized_risk():
    return {"approved": True, "position_size": 999999, "risk_score": 0.5}


# ── AXIS 1: Proposal Board ─────────────────────────────────────────────── #


class TestProposalBoard:
    """Proposal creation, lifecycle states, board view."""

    def test_proposal_created_on_guard(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            task_type="execute_trade",
            symbol="BTC/USDT",
            exchange="binance",
            risk_result=_good_risk(),
            pre_evidence_id="ev-001",
        )
        assert proposal.proposal_id.startswith("AP-")
        assert proposal.task_type == "execute_trade"
        assert proposal.symbol == "BTC/USDT"
        assert ledger.count == 1

    def test_board_groups_by_status(self):
        ledger = _make_ledger()
        # One guarded (pass) - different symbols to avoid duplicate
        ledger.propose_and_guard("t1", "BTC", "binance", _good_risk(), "ev-1")
        # One blocked (fail)
        ledger.propose_and_guard("t2", "ETH", "binance", _bad_risk(), "ev-2")

        board = ledger.get_board()
        assert board["total"] == 2
        assert len(board["guarded"]) == 1
        assert len(board["blocked"]) == 1
        assert board["blocked_count"] == 1

    def test_proposal_lifecycle_guarded_to_receipted(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-1",
        )
        assert proposal.status == "GUARDED"
        ledger.record_receipt(proposal, {"stage": "ready", "adjusted_size": 5000})
        assert proposal.status == "RECEIPTED"

    def test_proposal_lifecycle_guarded_to_failed(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "SOL",
            "binance",
            _good_risk(),
            "ev-1",
        )
        assert proposal.status == "GUARDED"
        ledger.record_failure(proposal, "Connection timeout")
        assert proposal.status == "FAILED"

    def test_orphan_detection(self):
        """GUARDED proposals without receipt show as orphans."""
        ledger = _make_ledger()
        ledger.propose_and_guard("t1", "BTC", "binance", _good_risk(), "ev-1")
        board = ledger.get_board()
        assert board["orphan_count"] == 1  # GUARDED but no receipt yet

    def test_guard_reason_top(self):
        """Board includes top blocking reasons."""
        ledger = _make_ledger()
        ledger.propose_and_guard("t1", "BTC", "binance", _bad_risk(), "ev-1")
        ledger.propose_and_guard("t2", "ETH", "binance", _bad_risk(), "ev-2")
        board = ledger.get_board()
        assert len(board["guard_reason_top"]) >= 1
        assert "RISK_APPROVED" in board["guard_reason_top"][0]


# ── AXIS 2: Apply Guard ────────────────────────────────────────────────── #


class TestApplyGuard:
    """4-check gate: risk, governance, size, cost."""

    def test_all_pass(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-1",
        )
        assert passed is True
        assert proposal.status == "GUARDED"
        assert proposal.guard_checks["RISK_APPROVED"]["passed"] is True
        assert proposal.guard_checks["GOVERNANCE_CLEAR"]["passed"] is True
        assert proposal.guard_checks["SIZE_BOUND"]["passed"] is True
        assert proposal.guard_checks["COST_BUDGET"]["passed"] is True

    def test_risk_not_approved_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _bad_risk(),
            "ev-1",
        )
        assert passed is False
        assert proposal.status == "BLOCKED"
        assert proposal.guard_checks["RISK_APPROVED"]["passed"] is False

    def test_no_governance_evidence_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            pre_evidence_id=None,
        )
        assert passed is False
        assert proposal.status == "BLOCKED"
        assert proposal.guard_checks["GOVERNANCE_CLEAR"]["passed"] is False

    def test_oversized_position_blocks(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _oversized_risk(),
            "ev-1",
        )
        assert passed is False
        assert proposal.guard_checks["SIZE_BOUND"]["passed"] is False

    def test_cost_budget_exhausted_blocks(self):
        ledger = _make_ledger()
        mock_cc = MagicMock()
        mock_budget = MagicMock()
        mock_budget.current = 1000
        mock_budget.limit = 1000  # exhausted
        mock_cc.get_budget.return_value = mock_budget

        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "DOGE",
            "binance",
            _good_risk(),
            "ev-1",
            cost_controller=mock_cc,
        )
        assert passed is False
        assert proposal.guard_checks["COST_BUDGET"]["passed"] is False

    def test_no_force_override_exists(self):
        """Apply Guard has no --force equivalent. No bypass method."""
        ledger = _make_ledger()
        assert not hasattr(ledger, "force_apply")
        assert not hasattr(ledger, "force_guard")
        assert not hasattr(ledger, "bypass_guard")


# ── AXIS 3: Receipt Trail ──────────────────────────────────────────────── #


class TestReceiptTrail:
    """Receipt creation, evidence linking, fail-closed receipt."""

    def test_receipt_links_evidence(self):
        ledger = _make_ledger()
        passed, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-pre-123",
        )
        receipt = ledger.record_receipt(
            proposal, {"stage": "ready"}, post_evidence_id="ev-post-456"
        )
        assert receipt.receipt_id.startswith("AR-")
        assert receipt.pre_evidence_id == "ev-pre-123"
        assert receipt.post_evidence_id == "ev-post-456"
        assert receipt.proposal_id == proposal.proposal_id

    def test_receipt_contains_guard_checks(self):
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(
            "execute_trade",
            "ETH",
            "binance",
            _good_risk(),
            "ev-1",
        )
        receipt = ledger.record_receipt(proposal, {"stage": "ready"})
        assert "RISK_APPROVED" in receipt.guard_checks
        assert "GOVERNANCE_CLEAR" in receipt.guard_checks
        assert "SIZE_BOUND" in receipt.guard_checks
        assert "COST_BUDGET" in receipt.guard_checks

    def test_receipt_to_dict_serializable(self):
        """Receipt must be JSON-serializable for flush."""
        import json

        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(
            "execute_trade",
            "SOL",
            "binance",
            _good_risk(),
            "ev-1",
        )
        receipt = ledger.record_receipt(proposal, {"stage": "ready", "adjusted_size": 5000})
        serialized = json.dumps(receipt.to_dict())
        assert "AR-" in serialized

    def test_receipt_blocked_for_unguarded_proposal(self):
        """Fail-closed: cannot receipt a proposal that didn't pass guard."""
        from app.agents.action_ledger import ActionProposal, StateTransitionError

        raw = ActionProposal(
            proposal_id="AP-test",
            task_type="test",
            status="PROPOSED",
            created_at="2026-01-01T00:00:00Z",
        )
        ledger = _make_ledger()
        with pytest.raises(StateTransitionError, match="guard_passed is False"):
            ledger.record_receipt(raw, {"stage": "ready"})

    def test_receipt_blocked_for_blocked_proposal(self):
        """Fail-closed: cannot receipt a BLOCKED proposal."""
        from app.agents.action_ledger import StateTransitionError

        ledger = _make_ledger()
        _, blocked = ledger.propose_and_guard(
            "execute_trade",
            "XRP",
            "binance",
            _bad_risk(),
            "ev-1",
        )
        assert blocked.status == "BLOCKED"
        with pytest.raises(StateTransitionError):
            ledger.record_receipt(blocked, {"stage": "ready"})


# ── AXIS 4: Boundary ───────────────────────────────────────────────────── #


class TestBoundary:
    """ActionLedger boundary enforcement."""

    def test_no_exchange_import(self):
        """action_ledger.py must not import exchanges/."""
        import importlib

        source = importlib.util.find_spec("app.agents.action_ledger")
        if source and source.origin:
            content = Path(source.origin).read_text(encoding="utf-8")
            assert "from exchanges" not in content, "ActionLedger must not import exchanges"
            assert "import exchanges" not in content, "ActionLedger must not import exchanges"

    def test_no_order_service_import(self):
        """action_ledger.py must not import OrderService."""
        import importlib

        source = importlib.util.find_spec("app.agents.action_ledger")
        if source and source.origin:
            content = Path(source.origin).read_text(encoding="utf-8")
            assert "order_service" not in content.lower() or "# no order" in content.lower(), (
                "ActionLedger must not reference OrderService"
            )

    def test_append_only(self):
        """Proposals cannot be deleted from the ledger."""
        ledger = _make_ledger()
        ledger.propose_and_guard("t1", "BTC", "binance", _good_risk(), "ev-1")
        ledger.propose_and_guard("t2", "ETH", "binance", _bad_risk(), "ev-2")
        assert ledger.count == 2
        assert not hasattr(ledger, "delete")
        assert not hasattr(ledger, "remove")
        assert not hasattr(ledger, "clear_proposals")


# ── AXIS 5: State Machine ──────────────────────────────────────────────── #


class TestStateMachine:
    """Forbidden transitions, fail-closed enforcement."""

    def test_blocked_to_guarded_forbidden(self):
        """BLOCKED is terminal -- cannot transition to GUARDED."""
        from app.agents.action_ledger import StateTransitionError

        ledger = _make_ledger()
        _, blocked = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _bad_risk(),
            "ev-1",
        )
        with pytest.raises(StateTransitionError, match="Forbidden transition"):
            blocked.transition_to("GUARDED")

    def test_receipted_is_terminal(self):
        """RECEIPTED is terminal -- no further transitions."""
        from app.agents.action_ledger import StateTransitionError

        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(
            "execute_trade",
            "ADA",
            "binance",
            _good_risk(),
            "ev-1",
        )
        ledger.record_receipt(proposal, {"stage": "ready"})
        assert proposal.status == "RECEIPTED"
        with pytest.raises(StateTransitionError):
            proposal.transition_to("FAILED")

    def test_failed_is_terminal(self):
        """FAILED is terminal -- no further transitions."""
        from app.agents.action_ledger import StateTransitionError

        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(
            "execute_trade",
            "DOT",
            "binance",
            _good_risk(),
            "ev-1",
        )
        ledger.record_failure(proposal, "error")
        assert proposal.status == "FAILED"
        with pytest.raises(StateTransitionError):
            proposal.transition_to("RECEIPTED")

    def test_proposed_to_receipted_forbidden(self):
        """Cannot skip GUARDED and go directly to RECEIPTED."""
        from app.agents.action_ledger import StateTransitionError, ActionProposal

        raw = ActionProposal(
            proposal_id="AP-test",
            task_type="test",
            status="PROPOSED",
            created_at="2026-01-01T00:00:00Z",
        )
        with pytest.raises(StateTransitionError, match="Forbidden transition"):
            raw.transition_to("RECEIPTED")

    def test_no_state_regression(self):
        """Cannot go backwards in the state machine."""
        from app.agents.action_ledger import StateTransitionError

        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(
            "execute_trade",
            "AVAX",
            "binance",
            _good_risk(),
            "ev-1",
        )
        assert proposal.status == "GUARDED"
        with pytest.raises(StateTransitionError):
            proposal.transition_to("PROPOSED")

    def test_record_failure_on_blocked_raises(self):
        """Cannot record failure on a BLOCKED proposal."""
        from app.agents.action_ledger import StateTransitionError

        ledger = _make_ledger()
        _, blocked = ledger.propose_and_guard(
            "execute_trade",
            "LINK",
            "binance",
            _bad_risk(),
            "ev-1",
        )
        with pytest.raises(StateTransitionError):
            ledger.record_failure(blocked, "error")


# ── AXIS 6: Fingerprint & Duplicate Suppression ────────────────────────── #


class TestFingerprint:
    """Duplicate proposal detection and suppression."""

    def test_fingerprint_generated(self):
        """Every proposal gets a fingerprint."""
        ledger = _make_ledger()
        _, proposal = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-1",
        )
        assert proposal.fingerprint != ""
        assert len(proposal.fingerprint) == 12

    def test_duplicate_blocked_within_cooldown(self):
        """Same fingerprint within cooldown window is blocked."""
        ledger = _make_ledger()
        # First: passes
        passed1, p1 = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-1",
        )
        assert passed1 is True
        # Second: same params, within cooldown -> blocked as duplicate
        passed2, p2 = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-2",
        )
        assert passed2 is False
        assert p2.status == "BLOCKED"
        assert "DUPLICATE" in str(p2.guard_reasons)

    def test_different_symbols_not_duplicate(self):
        """Different symbols produce different fingerprints."""
        ledger = _make_ledger()
        passed1, _ = ledger.propose_and_guard(
            "execute_trade",
            "BTC",
            "binance",
            _good_risk(),
            "ev-1",
        )
        passed2, _ = ledger.propose_and_guard(
            "execute_trade",
            "ETH",
            "binance",
            _good_risk(),
            "ev-2",
        )
        assert passed1 is True
        assert passed2 is True  # different symbol, not duplicate

    def test_fingerprint_deterministic(self):
        """Same inputs produce same fingerprint."""
        from app.agents.action_ledger import ActionLedger

        fp1 = ActionLedger._compute_fingerprint("execute_trade", "BTC", "binance", 5000)
        fp2 = ActionLedger._compute_fingerprint("execute_trade", "BTC", "binance", 5000)
        assert fp1 == fp2

    def test_size_bucket_groups_similar(self):
        """Similar sizes (same 1000-bucket) produce same fingerprint."""
        from app.agents.action_ledger import ActionLedger

        fp1 = ActionLedger._compute_fingerprint("execute_trade", "BTC", "binance", 5100)
        fp2 = ActionLedger._compute_fingerprint("execute_trade", "BTC", "binance", 5900)
        assert fp1 == fp2  # both in 5000 bucket
