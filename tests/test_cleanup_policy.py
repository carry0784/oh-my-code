"""
K-Dexter Orphan/Stale Cleanup Policy Tests

Sprint Contract: CARD-2026-0330-CLEANUP (Level C)

Tests the staleness observation layer across 3 Ledgers:
  AXIS 1: Stale Detection (threshold, age, boundary values)
  AXIS 2: Terminal Protection (BLOCKED/RECEIPTED/FAILED never stale)
  AXIS 3: Board Aggregation (get_board() stale_count accuracy)
  AXIS 4: State Machine Preservation (no _TRANSITIONS change, no STALE state)
  AXIS 5: 4-Tier Board Integration (stale_count in dashboard response)
  AXIS 6: 3-Ledger Consistency (same pattern across Action/Execution/Submit)

Run: pytest tests/test_cleanup_policy.py -v
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Stub modules
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "app.core.database",
    "app.models",
    "app.models.order",
    "app.models.position",
    "app.models.signal",
    "app.models.trade",
    "app.models.asset_snapshot",
    "app.exchanges",
    "app.exchanges.factory",
    "app.exchanges.base",
    "app.exchanges.binance",
    "app.services.order_service",
    "app.services.position_service",
    "app.services.signal_service",
    "ccxt",
    "ccxt.async_support",
    "redis",
    "celery",
    "asyncpg",
    "kdexter",
    "kdexter.ledger",
    "kdexter.ledger.forbidden_ledger",
    "kdexter.audit",
    "kdexter.audit.evidence_store",
    "kdexter.state_machine",
    "kdexter.state_machine.security_state",
]

for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# -- Helpers ---------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _past_iso(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def _fixed_time() -> datetime:
    """Fixed reference time for deterministic tests."""
    return datetime(2026, 3, 30, 12, 0, 0, tzinfo=timezone.utc)


# -- AXIS 1: Stale Detection ---------------------------------------------- #

class TestStaleDetection:
    """Threshold, age, boundary values."""

    def test_action_proposal_fresh_is_not_stale(self):
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-fresh", task_type="test",
                           status="GUARDED", created_at=_now_iso())
        assert p.is_stale(threshold_seconds=600.0) is False

    def test_action_proposal_old_is_stale(self):
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-old", task_type="test",
                           status="GUARDED", created_at=_past_iso(700))
        assert p.is_stale(threshold_seconds=600.0) is True

    def test_boundary_exactly_at_threshold_is_not_stale(self):
        """At exactly threshold_seconds, should NOT be stale (> not >=)."""
        from app.agents.action_ledger import ActionProposal
        now = _fixed_time()
        created = (now - timedelta(seconds=600)).isoformat()
        p = ActionProposal(proposal_id="AP-boundary", task_type="test",
                           status="GUARDED", created_at=created)
        assert p.is_stale(threshold_seconds=600.0, now=now) is False

    def test_one_second_past_threshold_is_stale(self):
        from app.agents.action_ledger import ActionProposal
        now = _fixed_time()
        created = (now - timedelta(seconds=601)).isoformat()
        p = ActionProposal(proposal_id="AP-boundary2", task_type="test",
                           status="GUARDED", created_at=created)
        assert p.is_stale(threshold_seconds=600.0, now=now) is True

    def test_proposed_status_can_be_stale(self):
        """PROPOSED (non-terminal, no receipt) should also be detected as stale."""
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-proposed", task_type="test",
                           status="PROPOSED", created_at=_past_iso(700))
        assert p.is_stale(threshold_seconds=600.0) is True

    def test_empty_created_at_is_not_stale(self):
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-empty", task_type="test",
                           status="GUARDED", created_at="")
        assert p.is_stale(threshold_seconds=600.0) is False

    def test_proposal_with_receipt_is_not_stale(self):
        """Even if old, if receipt exists, not stale."""
        from app.agents.action_ledger import ActionProposal, ActionReceipt
        receipt = ActionReceipt(receipt_id="AR-1", proposal_id="AP-r",
                                pre_evidence_id="EV-1")
        p = ActionProposal(proposal_id="AP-r", task_type="test",
                           status="GUARDED", created_at=_past_iso(9999),
                           receipt=receipt)
        assert p.is_stale(threshold_seconds=600.0) is False


# -- AXIS 2: Terminal Protection ------------------------------------------ #

class TestTerminalProtection:
    """BLOCKED/RECEIPTED/FAILED are NEVER stale regardless of age."""

    def test_action_blocked_never_stale(self):
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-blk", task_type="test",
                           status="BLOCKED", created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False

    def test_action_receipted_never_stale(self):
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-rcp", task_type="test",
                           status="RECEIPTED", created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False

    def test_action_failed_never_stale(self):
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-fail", task_type="test",
                           status="FAILED", created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False

    def test_exec_blocked_never_stale(self):
        from app.services.execution_ledger import ExecutionProposal
        p = ExecutionProposal(proposal_id="EP-blk", agent_proposal_id="AP-1",
                              task_type="test", status="EXEC_BLOCKED",
                              created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False

    def test_exec_receipted_never_stale(self):
        from app.services.execution_ledger import ExecutionProposal
        p = ExecutionProposal(proposal_id="EP-rcp", agent_proposal_id="AP-1",
                              task_type="test", status="EXEC_RECEIPTED",
                              created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False

    def test_submit_blocked_never_stale(self):
        from app.services.submit_ledger import SubmitProposal
        p = SubmitProposal(proposal_id="SP-blk", agent_proposal_id="AP-1",
                           execution_proposal_id="EP-1", task_type="test",
                           status="SUBMIT_BLOCKED", created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False

    def test_submit_receipted_never_stale(self):
        from app.services.submit_ledger import SubmitProposal
        p = SubmitProposal(proposal_id="SP-rcp", agent_proposal_id="AP-1",
                           execution_proposal_id="EP-1", task_type="test",
                           status="SUBMIT_RECEIPTED", created_at=_past_iso(99999))
        assert p.is_stale(threshold_seconds=1.0) is False


# -- AXIS 3: Board Aggregation ------------------------------------------- #

class TestBoardAggregation:
    """get_board() stale_count accuracy."""

    def test_action_board_stale_count(self):
        from app.agents.action_ledger import ActionLedger
        ledger = ActionLedger(stale_threshold=60.0)

        # Create proposals with known ages using internal access
        from app.agents.action_ledger import ActionProposal
        fresh = ActionProposal(proposal_id="AP-fresh", task_type="t",
                               status="GUARDED", created_at=_now_iso())
        stale = ActionProposal(proposal_id="AP-stale", task_type="t",
                               status="GUARDED", created_at=_past_iso(120))
        blocked = ActionProposal(proposal_id="AP-blk", task_type="t",
                                 status="BLOCKED", created_at=_past_iso(9999))

        ledger._proposals = [fresh, stale, blocked]
        board = ledger.get_board()

        assert board["stale_count"] == 1  # only the GUARDED old one
        assert board["stale_threshold_seconds"] == 60.0

    def test_execution_board_stale_count(self):
        from app.services.execution_ledger import ExecutionLedger, ExecutionProposal
        ledger = ExecutionLedger(stale_threshold=30.0)

        stale1 = ExecutionProposal(proposal_id="EP-s1", agent_proposal_id="AP-1",
                                   task_type="t", status="EXEC_GUARDED",
                                   created_at=_past_iso(60))
        stale2 = ExecutionProposal(proposal_id="EP-s2", agent_proposal_id="AP-2",
                                   task_type="t", status="EXEC_PROPOSED",
                                   created_at=_past_iso(60))
        terminal = ExecutionProposal(proposal_id="EP-t", agent_proposal_id="AP-3",
                                     task_type="t", status="EXEC_RECEIPTED",
                                     created_at=_past_iso(60))

        ledger._proposals = [stale1, stale2, terminal]
        board = ledger.get_board()

        assert board["stale_count"] == 2  # both non-terminal old ones
        assert board["stale_threshold_seconds"] == 30.0

    def test_submit_board_stale_count(self):
        from app.services.submit_ledger import SubmitLedger, SubmitProposal
        ledger = SubmitLedger(stale_threshold=10.0)

        fresh = SubmitProposal(proposal_id="SP-f", agent_proposal_id="AP-1",
                               execution_proposal_id="EP-1", task_type="t",
                               status="SUBMIT_GUARDED", created_at=_now_iso())
        ledger._proposals = [fresh]
        board = ledger.get_board()

        assert board["stale_count"] == 0  # fresh, not stale


# -- AXIS 4: State Machine Preservation ---------------------------------- #

class TestStateMachinePreservation:
    """No _TRANSITIONS change, no STALE state added."""

    def test_action_transitions_unchanged(self):
        """ActionProposal _TRANSITIONS must not contain STALE."""
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-t", task_type="t")
        all_states = set(p._TRANSITIONS.keys())
        all_targets = set()
        for targets in p._TRANSITIONS.values():
            all_targets.update(targets)
        combined = all_states | all_targets
        assert "STALE" not in combined
        # Original 5 states preserved
        assert all_states == {"PROPOSED", "GUARDED", "BLOCKED", "RECEIPTED", "FAILED"}

    def test_execution_transitions_unchanged(self):
        from app.services.execution_ledger import ExecutionProposal
        p = ExecutionProposal(proposal_id="EP-t", agent_proposal_id="AP-1", task_type="t")
        all_states = set(p._TRANSITIONS.keys())
        assert "STALE" not in all_states
        assert "EXEC_STALE" not in all_states
        assert all_states == {"EXEC_PROPOSED", "EXEC_GUARDED", "EXEC_BLOCKED",
                              "EXEC_RECEIPTED", "EXEC_FAILED"}

    def test_submit_transitions_unchanged(self):
        from app.services.submit_ledger import SubmitProposal
        p = SubmitProposal(proposal_id="SP-t", agent_proposal_id="AP-1",
                           execution_proposal_id="EP-1", task_type="t")
        all_states = set(p._TRANSITIONS.keys())
        assert "STALE" not in all_states
        assert "SUBMIT_STALE" not in all_states
        assert all_states == {"SUBMIT_PROPOSED", "SUBMIT_GUARDED", "SUBMIT_BLOCKED",
                              "SUBMIT_RECEIPTED", "SUBMIT_FAILED"}

    def test_source_no_stale_in_transitions(self):
        """Source code scan: STALE must not appear in _TRANSITIONS definitions."""
        for filepath in [
            "app/agents/action_ledger.py",
            "app/services/execution_ledger.py",
            "app/services/submit_ledger.py",
        ]:
            source = Path(_REPO_ROOT / filepath).read_text(encoding="utf-8")
            # Find _TRANSITIONS dict definition lines
            in_transitions = False
            for line in source.splitlines():
                if "_TRANSITIONS" in line and "field(" in line:
                    in_transitions = True
                if in_transitions:
                    assert "STALE" not in line, f"STALE found in _TRANSITIONS in {filepath}: {line}"
                    if "repr=False" in line:
                        in_transitions = False

    def test_is_stale_does_not_mutate_status(self):
        """is_stale() must never change proposal.status."""
        from app.agents.action_ledger import ActionProposal
        p = ActionProposal(proposal_id="AP-mut", task_type="test",
                           status="GUARDED", created_at=_past_iso(9999))
        original_status = p.status
        result = p.is_stale(threshold_seconds=1.0)
        assert result is True
        assert p.status == original_status  # status unchanged


# -- AXIS 5: 4-Tier Board Integration ------------------------------------ #

class TestFourTierBoardIntegration:
    """stale_count in dashboard response."""

    def test_board_includes_stale_count(self):
        from app.services.four_tier_board_service import build_four_tier_board
        mock_ledger = MagicMock()
        mock_ledger.get_board.return_value = {
            "total": 5, "receipted_count": 2, "blocked_count": 1,
            "failed_count": 0, "orphan_count": 1,
            "stale_count": 3, "stale_threshold_seconds": 600.0,
            "guard_reason_top": [],
        }
        board = build_four_tier_board(action_ledger=mock_ledger)
        assert board.agent_tier.stale_count == 3
        assert board.agent_tier.stale_threshold_seconds == 600.0

    def test_board_stale_count_default_zero(self):
        from app.services.four_tier_board_service import build_four_tier_board
        mock_ledger = MagicMock()
        mock_ledger.get_board.return_value = {
            "total": 0, "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0,
            "guard_reason_top": [],
            # stale_count intentionally missing — should default to 0
        }
        board = build_four_tier_board(action_ledger=mock_ledger)
        assert board.agent_tier.stale_count == 0

    def test_board_response_serializable_with_stale(self):
        from app.services.four_tier_board_service import build_four_tier_board
        mock_ledger = MagicMock()
        mock_ledger.get_board.return_value = {
            "total": 2, "receipted_count": 1, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0,
            "stale_count": 1, "stale_threshold_seconds": 300.0,
            "guard_reason_top": [],
        }
        board = build_four_tier_board(
            action_ledger=mock_ledger,
            execution_ledger=mock_ledger,
            submit_ledger=mock_ledger,
        )
        serialized = json.dumps(board.model_dump())
        parsed = json.loads(serialized)
        assert "stale_count" in parsed["agent_tier"]
        assert "stale_count" in parsed["execution_tier"]
        assert "stale_count" in parsed["submit_tier"]


# -- AXIS 6: 3-Ledger Consistency ---------------------------------------- #

class TestThreeLedgerConsistency:
    """Same pattern across Action/Execution/Submit."""

    def test_all_proposals_have_is_stale_method(self):
        from app.agents.action_ledger import ActionProposal
        from app.services.execution_ledger import ExecutionProposal
        from app.services.submit_ledger import SubmitProposal

        for cls in [ActionProposal, ExecutionProposal, SubmitProposal]:
            assert hasattr(cls, "is_stale"), f"{cls.__name__} missing is_stale"

    def test_all_proposals_have_terminal_states(self):
        from app.agents.action_ledger import ActionProposal
        from app.services.execution_ledger import ExecutionProposal
        from app.services.submit_ledger import SubmitProposal

        ap = ActionProposal(proposal_id="AP", task_type="t")
        ep = ExecutionProposal(proposal_id="EP", agent_proposal_id="AP", task_type="t")
        sp = SubmitProposal(proposal_id="SP", agent_proposal_id="AP",
                            execution_proposal_id="EP", task_type="t")

        for p in [ap, ep, sp]:
            assert hasattr(p, "_TERMINAL_STATES"), f"{type(p).__name__} missing _TERMINAL_STATES"
            assert len(p._TERMINAL_STATES) == 3, f"{type(p).__name__} should have 3 terminal states"

    def test_all_ledgers_have_stale_threshold(self):
        from app.agents.action_ledger import ActionLedger
        from app.services.execution_ledger import ExecutionLedger
        from app.services.submit_ledger import SubmitLedger

        for cls in [ActionLedger, ExecutionLedger, SubmitLedger]:
            ledger = cls()
            assert hasattr(ledger, "_stale_threshold"), f"{cls.__name__} missing _stale_threshold"
            assert ledger._stale_threshold > 0

    def test_all_boards_include_stale_count(self):
        from app.agents.action_ledger import ActionLedger
        from app.services.execution_ledger import ExecutionLedger
        from app.services.submit_ledger import SubmitLedger

        for cls in [ActionLedger, ExecutionLedger, SubmitLedger]:
            ledger = cls()
            board = ledger.get_board()
            assert "stale_count" in board, f"{cls.__name__}.get_board() missing stale_count"
            assert "stale_threshold_seconds" in board

    def test_stale_thresholds_ordered(self):
        """Agent > Execution > Submit (farther from exchange = more tolerance)."""
        from app.agents.action_ledger import ActionLedger
        from app.services.execution_ledger import ExecutionLedger
        from app.services.submit_ledger import SubmitLedger

        agent = ActionLedger()
        execution = ExecutionLedger()
        submit = SubmitLedger()

        assert agent._stale_threshold > execution._stale_threshold
        assert execution._stale_threshold > submit._stale_threshold

    def test_source_no_write_methods_in_is_stale(self):
        """is_stale must not call any mutating methods."""
        for filepath in [
            "app/agents/action_ledger.py",
            "app/services/execution_ledger.py",
            "app/services/submit_ledger.py",
        ]:
            source = Path(_REPO_ROOT / filepath).read_text(encoding="utf-8")
            # Find is_stale method body
            in_method = False
            method_lines = []
            for line in source.splitlines():
                if "def is_stale(" in line:
                    in_method = True
                    continue
                if in_method:
                    if line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                        break
                    if line.strip().startswith("def "):
                        break
                    method_lines.append(line)
            body = "\n".join(method_lines)
            assert "self.status =" not in body, f"is_stale writes to status in {filepath}"
            assert "transition_to" not in body, f"is_stale calls transition_to in {filepath}"
            assert "self._proposals" not in body, f"is_stale accesses _proposals in {filepath}"
