"""
C-04 Phase 7 — Recovery / Simulation / Preview Tests

Manual only. Sync only. Chain-gated. Receipt + audit.
No auto rollback/retry. No background. No queue. No polling.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

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
    "app.services",
    "app.services.order_service",
    "app.services.position_service",
    "app.services.signal_service",
    "ccxt",
    "ccxt.async_support",
    "redis",
    "celery",
    "asyncpg",
]
for m in _STUB_MODULES:
    if m not in sys.modules:
        sys.modules[m] = MagicMock()
sys.modules["app.models.position"].Position = MagicMock()
sys.modules["app.models.position"].PositionSide = MagicMock()
sys.modules["app.models.order"].Order = MagicMock()
sys.modules["app.models.order"].OrderStatus = MagicMock()

from app.core.manual_recovery_handler import (
    manual_rollback,
    manual_retry,
    simulate_action,
    preview_action,
)
from app.schemas.manual_recovery_schema import RecoveryDecision, SimulationDecision

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
HANDLER_PATH = PROJECT_ROOT / "app" / "core" / "manual_recovery_handler.py"


def _all_pass():
    return {
        "pipeline_state": "ALL_CLEAR",
        "preflight_decision": "READY",
        "gate_decision": "OPEN",
        "approval_decision": "APPROVED",
        "policy_decision": "MATCH",
        "ops_score": 0.85,
        "trading_authorized": True,
        "lockdown_state": "NORMAL",
        "preflight_evidence_id": "pf-real-001",
        "gate_evidence_id": "gate-real-001",
        "approval_id": "apr-real-001",
    }


# ===========================================================================
# P7-1: Manual Rollback
# ===========================================================================
class TestP7Rollback:
    def test_rollback_chain_pass_executes(self):
        r = manual_rollback(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.decision == RecoveryDecision.EXECUTED

    def test_rollback_chain_fail_rejects(self):
        d = _all_pass()
        d["gate_decision"] = "CLOSED"
        r = manual_rollback(d, original_receipt_id="RCP-orig-001")
        assert r.decision == RecoveryDecision.REJECTED
        assert r.block_code == "GATE_CLOSED"

    def test_rollback_missing_receipt_rejects(self):
        r = manual_rollback(_all_pass(), original_receipt_id="")
        assert r.decision == RecoveryDecision.REJECTED
        assert r.block_code == "MISSING_ORIGINAL_RECEIPT"

    def test_rollback_has_receipt_id(self):
        r = manual_rollback(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.receipt_id.startswith("RCP-RB-")

    def test_rollback_has_audit_id(self):
        r = manual_rollback(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.audit_id.startswith("AUD-RB-")

    def test_rollback_none_data_fails(self):
        r = manual_rollback(None, original_receipt_id="RCP-orig-001")
        assert r.decision == RecoveryDecision.REJECTED

    def test_rollback_type_is_rollback(self):
        r = manual_rollback(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.recovery_type == "rollback"


# ===========================================================================
# P7-2: Manual Retry
# ===========================================================================
class TestP7Retry:
    def test_retry_chain_pass_executes(self):
        r = manual_retry(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.decision == RecoveryDecision.EXECUTED

    def test_retry_chain_fail_rejects(self):
        d = _all_pass()
        d["approval_decision"] = "REJECTED"
        r = manual_retry(d, original_receipt_id="RCP-orig-001")
        assert r.decision == RecoveryDecision.REJECTED

    def test_retry_missing_receipt_rejects(self):
        r = manual_retry(_all_pass(), original_receipt_id="")
        assert r.decision == RecoveryDecision.REJECTED

    def test_retry_has_receipt_id(self):
        r = manual_retry(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.receipt_id.startswith("RCP-RT-")

    def test_retry_has_audit_id(self):
        r = manual_retry(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.audit_id.startswith("AUD-RT-")

    def test_retry_type_is_retry(self):
        r = manual_retry(_all_pass(), original_receipt_id="RCP-orig-001")
        assert r.recovery_type == "retry"


# ===========================================================================
# P7-3: Simulation
# ===========================================================================
class TestP7Simulation:
    def test_simulate_chain_pass_simulated(self):
        r = simulate_action(_all_pass())
        assert r.decision == SimulationDecision.SIMULATED

    def test_simulate_chain_fail_rejected(self):
        d = _all_pass()
        d["pipeline_state"] = "BLOCKED"
        r = simulate_action(d)
        assert r.decision == SimulationDecision.REJECTED

    def test_simulate_has_note(self):
        r = simulate_action(_all_pass())
        assert "SIMULATED" in r.simulation_note
        assert "not a guarantee" in r.simulation_note

    def test_simulate_has_receipt(self):
        r = simulate_action(_all_pass())
        assert r.receipt_id.startswith("RCP-SIM-")

    def test_simulate_has_audit(self):
        r = simulate_action(_all_pass())
        assert r.audit_id.startswith("AUD-SIM-")

    def test_simulate_empty_data_rejected(self):
        r = simulate_action({})
        assert r.decision == SimulationDecision.REJECTED


# ===========================================================================
# P7-4: Preview
# ===========================================================================
class TestP7Preview:
    def test_preview_chain_pass(self):
        r = preview_action(_all_pass())
        assert r.chain_met == 9
        assert "All conditions met" in r.action_summary

    def test_preview_chain_blocked(self):
        d = _all_pass()
        d["gate_decision"] = "CLOSED"
        r = preview_action(d)
        assert r.chain_met < 9
        assert "Blocked" in r.action_summary

    def test_preview_has_note(self):
        r = preview_action(_all_pass())
        assert "not guarantee" in r.preview_note.lower()

    def test_preview_empty_data(self):
        r = preview_action({})
        assert r.chain_met < 9


# ===========================================================================
# P7-5: Prohibitions
# ===========================================================================
class TestP7Prohibitions:
    def test_no_auto_rollback_in_handler(self):
        content = HANDLER_PATH.read_text(encoding="utf-8")
        assert "def auto_rollback" not in content
        assert "automatic" not in content.lower().replace("no automatic", "").replace("no auto", "")

    def test_no_auto_retry_in_handler(self):
        content = HANDLER_PATH.read_text(encoding="utf-8")
        assert "def auto_retry" not in content

    def test_no_background_in_handler(self):
        content = HANDLER_PATH.read_text(encoding="utf-8")
        assert "BackgroundTask" not in content
        assert "threading.Thread" not in content

    def test_no_queue_in_handler(self):
        content = HANDLER_PATH.read_text(encoding="utf-8")
        assert ".enqueue(" not in content
        assert "send_task(" not in content

    def test_endpoints_exist(self):
        route = ROUTE_PATH.read_text(encoding="utf-8")
        assert "manual-action/rollback" in route
        assert "manual-action/retry" in route
        assert "manual-action/simulate" in route
        assert "manual-action/preview" in route

    def test_all_endpoints_are_post(self):
        route = ROUTE_PATH.read_text(encoding="utf-8")
        post_count = route.count("@router.post")
        assert post_count == 5  # execute + rollback + retry + simulate + preview

    def test_simulation_no_mutation(self):
        """Simulation handler must not call any mutation function."""
        content = HANDLER_PATH.read_text(encoding="utf-8")
        # Find simulate_action function
        start = content.find("def simulate_action")
        end = content.find("\ndef ", start + 1)
        body = content[start:end] if end != -1 else content[start:]
        assert "db.add" not in body
        assert "session.commit" not in body
        assert "execute_trade" not in body
