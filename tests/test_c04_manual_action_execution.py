"""
C-04 Manual Action — Phase 5 Execution Tests

9-stage chain gating. Fail-closed. Synchronous only.
Receipt + audit on every attempt (success, rejection, failure).
No background / queue / worker / command bus.
No rollback / retry / polling / dry-run / partial preview.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Stub heavy dependencies
_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance", "app.exchanges.okx",
    "app.services", "app.services.order_service",
    "app.services.position_service", "app.services.signal_service",
    "ccxt", "ccxt.async_support", "redis", "celery", "asyncpg",
]
for m in _STUB_MODULES:
    if m not in sys.modules:
        sys.modules[m] = MagicMock()
sys.modules["app.models.position"].Position = MagicMock()
sys.modules["app.models.position"].PositionSide = MagicMock()
sys.modules["app.models.order"].Order = MagicMock()
sys.modules["app.models.order"].OrderStatus = MagicMock()

from app.schemas.manual_action_schema import (
    ManualActionChainState,
    ManualActionCommand,
    ManualActionDecision,
    ManualActionReceipt,
    ManualActionStageStatus,
)
from app.core.manual_action_handler import build_chain_state, validate_and_execute

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


def _all_pass_data():
    """Safety data where all 9 stages pass."""
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
# EX-1: Chain validation — all pass → EXECUTED
# ===========================================================================
class TestC04ChainAllPass:

    def test_all_pass_returns_executed(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.decision == ManualActionDecision.EXECUTED

    def test_all_pass_has_receipt_id(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.receipt_id.startswith("RCP-")

    def test_all_pass_has_action_id(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.action_id.startswith("MA-")

    def test_all_pass_has_audit_id(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.audit_id.startswith("AUD-")

    def test_all_pass_chain_state_all_pass(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.chain_state.all_pass is True

    def test_all_pass_no_block_code(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.block_code == ""


# ===========================================================================
# EX-2: Single stage blocked → REJECTED
# ===========================================================================
class TestC04ChainSingleBlocked:

    def test_pipeline_blocked(self):
        d = _all_pass_data()
        d["pipeline_state"] = "BLOCKED"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "PIPELINE_NOT_READY"

    def test_preflight_blocked(self):
        d = _all_pass_data()
        d["preflight_decision"] = "NOT_READY"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "PREFLIGHT_NOT_READY"

    def test_gate_blocked(self):
        d = _all_pass_data()
        d["gate_decision"] = "CLOSED"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "GATE_CLOSED"

    def test_approval_blocked(self):
        d = _all_pass_data()
        d["approval_decision"] = "REJECTED"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "APPROVAL_REQUIRED"

    def test_policy_blocked(self):
        d = _all_pass_data()
        d["policy_decision"] = "DRIFT"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "POLICY_BLOCKED"

    def test_risk_blocked(self):
        d = _all_pass_data()
        d["ops_score"] = 0.3
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "RISK_NOT_OK"

    def test_auth_blocked(self):
        d = _all_pass_data()
        d["trading_authorized"] = False
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "AUTH_NOT_OK"

    def test_scope_blocked(self):
        d = _all_pass_data()
        d["lockdown_state"] = "LOCKDOWN"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "SCOPE_NOT_OK"

    def test_evidence_blocked_fallback(self):
        d = _all_pass_data()
        d["preflight_evidence_id"] = "fallback-pf-001"
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED
        assert receipt.block_code == "EVIDENCE_MISSING"


# ===========================================================================
# EX-3: Missing/malformed data → fail-closed
# ===========================================================================
class TestC04FailClosed:

    def test_none_data_rejected(self):
        receipt = validate_and_execute(None)
        assert receipt.decision == ManualActionDecision.REJECTED

    def test_empty_data_rejected(self):
        receipt = validate_and_execute({})
        assert receipt.decision == ManualActionDecision.REJECTED

    def test_missing_single_key_rejected(self):
        d = _all_pass_data()
        del d["gate_decision"]
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED

    def test_null_value_rejected(self):
        d = _all_pass_data()
        d["ops_score"] = None
        receipt = validate_and_execute(d)
        assert receipt.decision == ManualActionDecision.REJECTED


# ===========================================================================
# EX-4: Receipt created for every attempt type
# ===========================================================================
class TestC04ReceiptAlways:

    def test_success_has_receipt(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.receipt_id != ""

    def test_rejection_has_receipt(self):
        receipt = validate_and_execute({})
        assert receipt.receipt_id != ""
        assert receipt.decision == ManualActionDecision.REJECTED

    def test_receipt_has_operator(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.operator_id != ""

    def test_receipt_has_timestamp(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.timestamp != ""

    def test_rejection_has_block_code(self):
        d = _all_pass_data()
        d["gate_decision"] = "CLOSED"
        receipt = validate_and_execute(d)
        assert receipt.block_code != ""

    def test_rejection_has_reason(self):
        d = _all_pass_data()
        d["gate_decision"] = "CLOSED"
        receipt = validate_and_execute(d)
        assert receipt.reason != ""


# ===========================================================================
# EX-5: Audit on every attempt
# ===========================================================================
class TestC04AuditAlways:

    def test_success_has_audit_id(self):
        receipt = validate_and_execute(_all_pass_data())
        assert receipt.audit_id.startswith("AUD-")

    def test_rejection_has_audit_id(self):
        receipt = validate_and_execute({})
        assert receipt.audit_id.startswith("AUD-")


# ===========================================================================
# EX-6: Chain state contract
# ===========================================================================
class TestC04ChainState:

    def test_all_pass_chain(self):
        chain = build_chain_state(_all_pass_data())
        assert chain.all_pass is True

    def test_empty_data_all_missing(self):
        chain = build_chain_state({})
        assert chain.all_pass is False
        assert chain.pipeline == ManualActionStageStatus.MISSING

    def test_none_data_all_missing(self):
        chain = build_chain_state(None)
        assert chain.all_pass is False

    def test_first_blocked_stage_name(self):
        d = _all_pass_data()
        d["approval_decision"] = "REJECTED"
        chain = build_chain_state(d)
        assert chain.first_blocked_stage == "approval"


# ===========================================================================
# EX-7: Prohibition checks — no forbidden patterns
# ===========================================================================
class TestC04Prohibitions:

    def test_endpoint_exists_in_routes(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert "manual-action/execute" in content

    def test_endpoint_is_post(self):
        content = ROUTE_PATH.read_text(encoding="utf-8")
        assert '@router.post("/api/manual-action/execute"' in content

    def test_no_celery_task_in_handler(self):
        handler_path = PROJECT_ROOT / "app" / "core" / "manual_action_handler.py"
        content = handler_path.read_text(encoding="utf-8")
        assert "celery" not in content.lower()
        assert "task(" not in content
        assert "delay(" not in content

    def test_no_queue_call_in_handler(self):
        """Handler must not use queue APIs (enqueue/put/send_task)."""
        handler_path = PROJECT_ROOT / "app" / "core" / "manual_action_handler.py"
        content = handler_path.read_text(encoding="utf-8")
        assert ".enqueue(" not in content
        assert ".put(" not in content
        assert "send_task(" not in content

    def test_no_background_thread_in_handler(self):
        """Handler must not spawn threads or background tasks."""
        handler_path = PROJECT_ROOT / "app" / "core" / "manual_action_handler.py"
        content = handler_path.read_text(encoding="utf-8")
        assert "threading.Thread" not in content
        assert "BackgroundTask" not in content
        assert "asyncio.create_task" not in content

    def test_no_rollback_call_in_handler(self):
        """Handler must not perform rollback operations."""
        handler_path = PROJECT_ROOT / "app" / "core" / "manual_action_handler.py"
        content = handler_path.read_text(encoding="utf-8")
        assert "def rollback" not in content
        assert ".rollback(" not in content

    def test_no_retry_call_in_handler(self):
        """Handler must not perform retry operations."""
        handler_path = PROJECT_ROOT / "app" / "core" / "manual_action_handler.py"
        content = handler_path.read_text(encoding="utf-8")
        assert "def retry" not in content
        assert ".retry(" not in content
        assert "max_retries" not in content

    def test_no_form_submit_in_template(self):
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        c04_start = html.find('id="t3sc-c04"')
        next_card = html.find('id="t3sc-c05"', c04_start)
        c04 = html[c04_start:next_card].lower()
        assert '<form' not in c04
        assert 'type="submit"' not in c04

    def test_no_keyboard_trigger_in_template(self):
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        c04_start = html.find('id="t3sc-c04"')
        next_card = html.find('id="t3sc-c05"', c04_start)
        c04 = html[c04_start:next_card].lower()
        assert 'onkeydown' not in c04
        assert 'onkeypress' not in c04
        assert 'onkeyup' not in c04

    def test_button_disabled_by_default_in_html(self):
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="t3sc-c04-exec-btn" disabled' in html

    def test_two_step_confirm_exists(self):
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="t3sc-c04-confirm"' in html
        assert 'id="t3sc-c04-confirm-yes"' in html
        assert 'id="t3sc-c04-confirm-no"' in html


# ===========================================================================
# EX-8: Schema contract checks
# ===========================================================================
class TestC04SchemaContract:

    def test_receipt_has_required_fields(self):
        fields = ManualActionReceipt.model_fields
        assert "receipt_id" in fields
        assert "action_id" in fields
        assert "operator_id" in fields
        assert "timestamp" in fields
        assert "decision" in fields
        assert "chain_state" in fields
        assert "block_code" in fields
        assert "reason" in fields
        assert "audit_id" in fields

    def test_command_has_required_fields(self):
        fields = ManualActionCommand.model_fields
        assert "action_id" in fields
        assert "operator_id" in fields
        assert "timestamp" in fields
        assert "chain_state" in fields

    def test_chain_state_has_9_stages(self):
        fields = ManualActionChainState.model_fields
        expected = ["pipeline", "preflight", "gate", "approval", "policy", "risk", "auth", "scope", "evidence"]
        for stage in expected:
            assert stage in fields, f"Missing stage: {stage}"

    def test_decision_enum_has_3_values(self):
        values = [e.value for e in ManualActionDecision]
        assert "EXECUTED" in values
        assert "REJECTED" in values
        assert "FAILED" in values
        assert len(values) == 3
