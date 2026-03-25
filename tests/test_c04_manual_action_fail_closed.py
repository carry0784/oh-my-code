"""
C-04 Manual Action — Fail-Closed Tests

Phase 1 test-code only. C-04 구현 금지. 활성화 금지.
이 테스트는 unknown/missing/incomplete/disconnected 상태가
항상 fail-closed로 처리되어야 함을 코드 수준으로 봉인한다.

대상: C-04 contract — fail-closed 규칙
범위: unknown state, missing dependency, HTML 봉인 상태
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"

# Stub heavy dependencies for safe schema import
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
    "app.exchanges.okx",
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

for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Safe model stubs
_pos_mock = sys.modules["app.models.position"]
_pos_mock.Position = MagicMock()
_pos_mock.PositionSide = MagicMock()
_order_mock = sys.modules["app.models.order"]
_order_mock.Order = MagicMock()
_order_mock.OrderStatus = MagicMock()

# ===========================================================================
# Test-local contract
# ===========================================================================

CHAIN_STAGES = (
    "pipeline_ready", "preflight_ready", "gate_open",
    "approval_ok", "policy_ok", "risk_ok",
    "auth_ok", "scope_ok", "evidence_present",
)

STAGE_TO_BLOCK = {
    "pipeline_ready": "PIPELINE_NOT_READY",
    "preflight_ready": "PREFLIGHT_NOT_READY",
    "gate_open": "GATE_CLOSED",
    "approval_ok": "APPROVAL_REQUIRED",
    "policy_ok": "POLICY_BLOCKED",
    "risk_ok": "RISK_NOT_OK",
    "auth_ok": "AUTH_NOT_OK",
    "scope_ok": "SCOPE_NOT_OK",
    "evidence_present": "EVIDENCE_MISSING",
}


def _evaluate_chain(state: dict) -> tuple:
    """Test-local 9단계 체인 평가. 실패 시 (False, block_code) 반환."""
    for stage in CHAIN_STAGES:
        val = state.get(stage)
        if not val:
            return (False, STAGE_TO_BLOCK.get(stage, "MANUAL_ACTION_DISABLED"))
    return (True, None)


def _read_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _read_dashboard_route():
    return DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# FC-1: unknown state => blocked
# ===========================================================================
class TestC04FailClosedUnknownState:
    """모든 unknown 상태는 blocked로 처리되어야 한다."""

    def test_unknown_pipeline_state_blocks(self):
        """pipeline_ready가 unknown이면 blocked."""
        state = {s: True for s in CHAIN_STAGES}
        state["pipeline_ready"] = None
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "PIPELINE_NOT_READY"

    def test_unknown_preflight_state_blocks(self):
        """preflight_ready가 unknown이면 blocked."""
        from app.schemas.preflight_schema import PreflightDecision
        # NOT_READY or BLOCKED => blocked
        assert PreflightDecision.READY.value == "READY"
        state = {s: True for s in CHAIN_STAGES}
        state["preflight_ready"] = None
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "PREFLIGHT_NOT_READY"

    def test_unknown_gate_state_blocks(self):
        """gate_open이 unknown이면 blocked."""
        from app.schemas.execution_gate_schema import GateDecision
        assert GateDecision.CLOSED.value == "CLOSED"
        state = {s: True for s in CHAIN_STAGES}
        state["gate_open"] = None
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "GATE_CLOSED"

    def test_unknown_approval_state_blocks(self):
        """approval_ok가 unknown이면 blocked."""
        from app.schemas.operator_approval_schema import ApprovalDecision
        assert ApprovalDecision.REJECTED.value == "REJECTED"
        state = {s: True for s in CHAIN_STAGES}
        state["approval_ok"] = None
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "APPROVAL_REQUIRED"

    def test_unknown_policy_state_blocks(self):
        """policy_ok가 unknown이면 blocked."""
        state = {s: True for s in CHAIN_STAGES}
        state["policy_ok"] = None
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "POLICY_BLOCKED"

    def test_none_state_for_all_defaults_to_blocked(self):
        """모든 단계가 None이면 첫 번째 단계의 block code."""
        state = {s: None for s in CHAIN_STAGES}
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "PIPELINE_NOT_READY"


# ===========================================================================
# FC-2: missing dependency => block code
# ===========================================================================
class TestC04FailClosedMissingDependency:
    """필수 의존성이 없으면 반드시 대응하는 block code 반환."""

    def test_missing_preflight_result_blocks(self):
        state = {s: True for s in CHAIN_STAGES}
        state["preflight_ready"] = False
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "PREFLIGHT_NOT_READY"

    def test_missing_gate_result_blocks(self):
        state = {s: True for s in CHAIN_STAGES}
        state["gate_open"] = False
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "GATE_CLOSED"

    def test_missing_approval_result_blocks(self):
        state = {s: True for s in CHAIN_STAGES}
        state["approval_ok"] = False
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "APPROVAL_REQUIRED"

    def test_missing_policy_result_blocks(self):
        state = {s: True for s in CHAIN_STAGES}
        state["policy_ok"] = False
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "POLICY_BLOCKED"

    def test_missing_evidence_blocks(self):
        state = {s: True for s in CHAIN_STAGES}
        state["evidence_present"] = False
        allowed, code = _evaluate_chain(state)
        assert allowed is False
        assert code == "EVIDENCE_MISSING"

    def test_incomplete_dependency_set_blocks(self):
        """일부 단계만 있는 불완전 의존성 세트는 blocked."""
        partial_state = {
            "pipeline_ready": True,
            "preflight_ready": True,
            # 나머지 단계 누락
        }
        allowed, code = _evaluate_chain(partial_state)
        assert allowed is False


# ===========================================================================
# FC-3: HTML 봉인 상태 — interactive element 부재
# ===========================================================================
class TestC04FailClosedHTMLState:
    """C-04 영역에 interactive element가 없어야 한다."""

    def test_interactive_elements_disabled_by_default(self):
        """C-04 카드의 interactive 요소는 기본 disabled 상태여야 한다.
        Purpose transition: Phase 5 — button exists but disabled."""
        html = _read_template()
        assert 'id="t3sc-c04-exec-btn" disabled' in html
        # No input/select/textarea should exist
        c04_start = html.find('id="t3sc-c04"')
        next_card = html.find('id="t3sc-c05"', c04_start)
        c04_section = html[c04_start:next_card] if next_card != -1 else html[c04_start:c04_start + 2000]
        c04_lower = c04_section.lower()
        assert '<input' not in c04_lower
        assert '<select' not in c04_lower
        assert '<textarea' not in c04_lower

    def test_post_endpoints_are_chain_gated(self):
        """C-04 POST endpoints가 존재하되 chain-gated이어야 한다.
        Phase 7: execute + rollback + retry + simulate + preview."""
        route = _read_dashboard_route()
        assert "manual-action/execute" in route
        assert "validate_and_execute" in route
        assert "_build_ops_safety_summary" in route
        assert "manual-action/rollback" in route
        assert "manual-action/simulate" in route

    def test_no_write_handler_in_dashboard(self):
        """dashboard route에 write 기반 action handler 없어야 한다."""
        route = _read_dashboard_route()
        assert "execute_manual" not in route
        assert "trigger_action" not in route
        assert "submit_action" not in route

    def test_no_hidden_enable_path(self):
        """hidden enable/unlock 경로가 없어야 한다."""
        route = _read_dashboard_route()
        assert "enable_c04" not in route
        assert "unlock_action" not in route
        assert "activate_manual" not in route

    def test_no_action_wiring_in_template(self):
        """템플릿에서 C-04 action 관련 JS wiring 없어야 한다."""
        html = _read_template()
        assert 'c04Action' not in html
        assert 'c04Submit' not in html
        assert 'manualActionTrigger' not in html

    def test_no_optimistic_wording_in_c04(self):
        """C-04 영역에 낙관적 실행 문구가 없어야 한다."""
        html = _read_template().lower()
        forbidden_phrases = [
            "ready to execute",
            "click to run",
            "start execution",
            "proceed with action",
            "action available",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in html, f"Optimistic phrase found: {phrase}"
