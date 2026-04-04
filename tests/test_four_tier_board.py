"""
K-Dexter 4-Tier Board Tests

Tests the unified 4-tier seal chain dashboard board:
  AXIS 1: Board Assembly (service builds correct response from live ledgers)
  AXIS 2: Missing Tier (disconnected tier → connected=False, zero counts)
  AXIS 3: Order Tier (OrderExecutor history aggregation)
  AXIS 4: Derived Flags (execution_ready / submit_ready counts)
  AXIS 5: Block Reasons (aggregated top block reasons across tiers)
  AXIS 6: Lineage (recent lineage trace from submit → order)
  AXIS 7: Schema (response model validation)
  AXIS 8: Dashboard Endpoint (API route integration)

Run: pytest tests/test_four_tier_board.py -v
"""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

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


def _make_action_ledger_board(
    total=5,
    receipted=2,
    blocked=1,
    failed=0,
    orphan=2,
    guard_reason_top=None,
):
    """Create a mock ActionLedger with get_board() returning given counts."""
    mock = MagicMock()
    mock.get_board.return_value = {
        "total": total,
        "receipted_count": receipted,
        "blocked_count": blocked,
        "failed_count": failed,
        "orphan_count": orphan,
        "guard_reason_top": guard_reason_top or [],
    }
    return mock


def _make_execution_ledger_board(
    total=4,
    receipted=3,
    blocked=0,
    failed=1,
    orphan=0,
    guard_reason_top=None,
):
    mock = MagicMock()
    mock.get_board.return_value = {
        "total": total,
        "receipted_count": receipted,
        "blocked_count": blocked,
        "failed_count": failed,
        "orphan_count": orphan,
        "guard_reason_top": guard_reason_top or [],
    }
    return mock


def _make_submit_ledger_board(
    total=3,
    receipted=2,
    blocked=1,
    failed=0,
    orphan=0,
    guard_reason_top=None,
    proposals=None,
):
    mock = MagicMock()
    mock.get_board.return_value = {
        "total": total,
        "receipted_count": receipted,
        "blocked_count": blocked,
        "failed_count": failed,
        "orphan_count": orphan,
        "guard_reason_top": guard_reason_top or [],
    }
    mock.get_proposals.return_value = proposals or []
    return mock


def _make_order_executor(orders=None):
    """Create a mock OrderExecutor with get_history() and get_order_by_proposal()."""
    mock = MagicMock()
    mock.get_history.return_value = orders or []
    mock.get_order_by_proposal.return_value = None
    return mock


# -- AXIS 1: Board Assembly ------------------------------------------------ #


class TestBoardAssembly:
    """Service builds correct response from live ledgers."""

    def test_full_board_all_tiers_connected(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(),
            execution_ledger=_make_execution_ledger_board(),
            submit_ledger=_make_submit_ledger_board(),
            order_executor=_make_order_executor(),
        )
        assert board.agent_tier.connected is True
        assert board.execution_tier.connected is True
        assert board.submit_tier.connected is True
        assert board.order_tier.connected is True

    def test_tier_names_correct(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(),
            execution_ledger=_make_execution_ledger_board(),
            submit_ledger=_make_submit_ledger_board(),
            order_executor=_make_order_executor(),
        )
        assert board.agent_tier.tier_name == "Agent"
        assert board.agent_tier.tier_number == 1
        assert board.execution_tier.tier_name == "Execution"
        assert board.execution_tier.tier_number == 2
        assert board.submit_tier.tier_name == "Submit"
        assert board.submit_tier.tier_number == 3
        assert board.order_tier.tier_name == "Orders"
        assert board.order_tier.tier_number == 4

    def test_agent_tier_counts_match_board(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(
                total=10, receipted=5, blocked=3, failed=1, orphan=1
            ),
        )
        assert board.agent_tier.total == 10
        assert board.agent_tier.receipted_count == 5
        assert board.agent_tier.blocked_count == 3
        assert board.agent_tier.failed_count == 1
        assert board.agent_tier.orphan_count == 1

    def test_total_guard_checks_is_25(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.total_guard_checks == 25

    def test_seal_chain_complete_flag(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.seal_chain_complete is True

    def test_generated_at_populated(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.generated_at != ""
        # Should be ISO format
        assert "T" in board.generated_at


# -- AXIS 2: Missing Tier ------------------------------------------------- #


class TestMissingTier:
    """Disconnected tier → connected=False, zero counts."""

    def test_all_none_returns_disconnected(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.agent_tier.connected is False
        assert board.execution_tier.connected is False
        assert board.submit_tier.connected is False
        assert board.order_tier.connected is False

    def test_partial_connection(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(),
            # execution, submit, order all None
        )
        assert board.agent_tier.connected is True
        assert board.execution_tier.connected is False
        assert board.submit_tier.connected is False
        assert board.order_tier.connected is False

    def test_disconnected_tier_has_zero_counts(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.agent_tier.total == 0
        assert board.agent_tier.receipted_count == 0
        assert board.agent_tier.blocked_count == 0
        assert board.order_tier.total == 0
        assert board.order_tier.filled_count == 0


# -- AXIS 3: Order Tier --------------------------------------------------- #


class TestOrderTier:
    """OrderExecutor history aggregation."""

    def test_order_status_counts(self):
        from app.services.four_tier_board_service import build_four_tier_board

        orders = [
            {"status": "FILLED", "dry_run": True},
            {"status": "FILLED", "dry_run": True},
            {"status": "ERROR", "dry_run": False},
            {"status": "TIMEOUT", "dry_run": False},
            {"status": "PARTIAL", "dry_run": False},
        ]
        board = build_four_tier_board(order_executor=_make_order_executor(orders))
        assert board.order_tier.total == 5
        assert board.order_tier.filled_count == 2
        assert board.order_tier.error_count == 1
        assert board.order_tier.timeout_count == 1
        assert board.order_tier.partial_count == 1
        assert board.order_tier.dry_run_count == 2

    def test_empty_history(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(order_executor=_make_order_executor([]))
        assert board.order_tier.total == 0
        assert board.order_tier.connected is True

    def test_all_dry_run(self):
        from app.services.four_tier_board_service import build_four_tier_board

        orders = [
            {"status": "FILLED", "dry_run": True},
            {"status": "FILLED", "dry_run": True},
        ]
        board = build_four_tier_board(order_executor=_make_order_executor(orders))
        assert board.order_tier.dry_run_count == 2
        assert board.order_tier.filled_count == 2


# -- AXIS 4: Derived Flags ------------------------------------------------ #


class TestDerivedFlags:
    """execution_ready / submit_ready counts."""

    def test_derived_flags_from_ledgers(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            execution_ledger=_make_execution_ledger_board(receipted=3, orphan=2),
            submit_ledger=_make_submit_ledger_board(receipted=1, orphan=1),
        )
        assert board.derived_flags.execution_ready_true == 3
        assert board.derived_flags.execution_ready_pending == 2
        assert board.derived_flags.submit_ready_true == 1
        assert board.derived_flags.submit_ready_pending == 1

    def test_derived_flags_no_ledgers(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.derived_flags.execution_ready_true == 0
        assert board.derived_flags.execution_ready_pending == 0
        assert board.derived_flags.submit_ready_true == 0
        assert board.derived_flags.submit_ready_pending == 0


# -- AXIS 5: Block Reasons ------------------------------------------------ #


class TestBlockReasons:
    """Aggregated top block reasons across tiers."""

    def test_aggregated_reasons(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(
                guard_reason_top=["COST_BUDGET: 3", "SIZE_BOUND: 1"]
            ),
            execution_ledger=_make_execution_ledger_board(
                guard_reason_top=["LOCKDOWN_CHECK: 2", "COST_BUDGET: 1"]
            ),
            submit_ledger=_make_submit_ledger_board(guard_reason_top=["EXCHANGE_ALLOWED: 2"]),
        )
        # COST_BUDGET should be aggregated: 3+1=4
        assert len(board.top_block_reasons_all) > 0
        # Find COST_BUDGET in aggregated list
        cost_entry = [r for r in board.top_block_reasons_all if "COST_BUDGET" in r]
        assert len(cost_entry) == 1
        assert "4" in cost_entry[0]

    def test_empty_reasons(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.top_block_reasons_all == []


# -- AXIS 6: Lineage ------------------------------------------------------ #


class TestLineage:
    """Recent lineage trace from submit → order."""

    def test_lineage_from_proposals(self):
        from app.services.four_tier_board_service import build_four_tier_board

        proposals = [
            {
                "proposal_id": "SP-001",
                "agent_proposal_id": "AP-001",
                "execution_proposal_id": "EP-001",
                "status": "SUBMIT_RECEIPTED",
                "submit_ready": True,
            },
        ]
        board = build_four_tier_board(
            submit_ledger=_make_submit_ledger_board(proposals=proposals),
        )
        assert len(board.recent_lineage) == 1
        entry = board.recent_lineage[0]
        assert entry.agent_proposal_id == "AP-001"
        assert entry.execution_proposal_id == "EP-001"
        assert entry.submit_proposal_id == "SP-001"

    def test_lineage_empty_without_submit_ledger(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.recent_lineage == []

    def test_lineage_with_order_match(self):
        from app.services.four_tier_board_service import build_four_tier_board

        proposals = [
            {
                "proposal_id": "SP-match",
                "agent_proposal_id": "AP-match",
                "execution_proposal_id": "EP-match",
                "status": "SUBMIT_RECEIPTED",
                "submit_ready": True,
            },
        ]
        executor = _make_order_executor()
        mock_order = MagicMock()
        mock_order.order_id = "OX-20260330-abc123"
        executor.get_order_by_proposal.return_value = mock_order

        board = build_four_tier_board(
            submit_ledger=_make_submit_ledger_board(proposals=proposals),
            order_executor=executor,
        )
        assert board.recent_lineage[0].order_id == "OX-20260330-abc123"


# -- AXIS 7: Schema ------------------------------------------------------- #


class TestSchema:
    """Response model validation."""

    def test_response_serializable(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(),
            execution_ledger=_make_execution_ledger_board(),
            submit_ledger=_make_submit_ledger_board(),
            order_executor=_make_order_executor(),
        )
        serialized = json.dumps(board.model_dump())
        parsed = json.loads(serialized)
        assert "agent_tier" in parsed
        assert "execution_tier" in parsed
        assert "submit_tier" in parsed
        assert "order_tier" in parsed

    def test_no_raw_reasoning_exposure(self):
        """Board must not expose raw reasoning, prompts, or error_class."""
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board(
            action_ledger=_make_action_ledger_board(),
        )
        serialized = json.dumps(board.model_dump())
        assert "reasoning" not in serialized
        assert "prompt" not in serialized
        assert "error_class" not in serialized

    def test_tier_summary_fields(self):
        from app.schemas.four_tier_board_schema import TierSummary

        tier = TierSummary(tier_name="Test", tier_number=0)
        assert tier.total == 0
        assert tier.connected is False

    def test_order_tier_summary_fields(self):
        from app.schemas.four_tier_board_schema import OrderTierSummary

        tier = OrderTierSummary()
        assert tier.tier_name == "Orders"
        assert tier.tier_number == 4
        assert tier.filled_count == 0


# -- AXIS 8: Dashboard Endpoint ------------------------------------------- #


class TestDashboardEndpoint:
    """API route integration."""

    def test_source_has_four_tier_board_endpoint(self):
        """Dashboard routes must include /api/four-tier-board."""
        source = Path(__file__).resolve().parent.parent / "app" / "api" / "routes" / "dashboard.py"
        content = source.read_text(encoding="utf-8")
        assert "/api/four-tier-board" in content
        assert "four_tier_board" in content
        assert "build_four_tier_board" in content

    def test_v2_includes_four_tier_board(self):
        """v2 data endpoint must include four_tier_board field."""
        source = Path(__file__).resolve().parent.parent / "app" / "api" / "routes" / "dashboard.py"
        content = source.read_text(encoding="utf-8")
        assert 'result["four_tier_board"]' in content

    def test_endpoint_is_read_only(self):
        """Four-tier board endpoint must NOT call any write methods (outside comments)."""
        source = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "services"
            / "four_tier_board_service.py"
        )
        content = source.read_text(encoding="utf-8")
        # Strip comment lines and docstrings, check actual code
        code_lines = []
        in_docstring = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = not in_docstring
                continue
            if in_docstring or stripped.startswith("#"):
                continue
            code_lines.append(line)
        code_only = "\n".join(code_lines)
        # Must not call mutating methods in actual code
        assert ".propose_and_guard(" not in code_only
        assert ".record_receipt(" not in code_only
        assert ".record_failure(" not in code_only
        assert ".transition_to(" not in code_only
        assert ".flush_to_file(" not in code_only
