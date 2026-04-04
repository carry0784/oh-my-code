"""
C-04 Phase 6→7 — Display + Recovery Tests

Phase 6 display evolved into Phase 7 interactive recovery.
This file validates:
- Phase 7 recovery sections exist
- Recovery endpoints are chain-gated
- No auto rollback/retry
- No background/queue/worker
- Write path bounded to approved POST endpoints only
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
HANDLER_PATH = PROJECT_ROOT / "app" / "core" / "manual_action_handler.py"
RECOVERY_PATH = PROJECT_ROOT / "app" / "core" / "manual_recovery_handler.py"


def _html():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _route():
    return ROUTE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# P67-1: Phase 7 recovery UI elements exist
# ===========================================================================
class TestC04Phase7UIExists:
    def test_p7_container_exists(self):
        assert 'id="t3sc-c04-p7"' in _html()

    def test_rollback_button_exists(self):
        assert 'id="t3sc-c04-btn-rollback"' in _html()

    def test_retry_button_exists(self):
        assert 'id="t3sc-c04-btn-retry"' in _html()

    def test_simulate_button_exists(self):
        assert 'id="t3sc-c04-btn-simulate"' in _html()

    def test_preview_button_exists(self):
        assert 'id="t3sc-c04-btn-preview"' in _html()

    def test_result_area_exists(self):
        assert 'id="t3sc-c04-p7-result"' in _html()

    def test_render_function_exists(self):
        assert "_renderC04Phase6" in _html()


# ===========================================================================
# P67-2: Recovery endpoints are chain-gated
# ===========================================================================
class TestC04Phase7Endpoints:
    def test_rollback_endpoint_exists(self):
        assert "manual-action/rollback" in _route()

    def test_retry_endpoint_exists(self):
        assert "manual-action/retry" in _route()

    def test_simulate_endpoint_exists(self):
        assert "manual-action/simulate" in _route()

    def test_preview_endpoint_exists(self):
        assert "manual-action/preview" in _route()

    def test_all_endpoints_use_chain_validation(self):
        route = _route()
        assert "_build_ops_safety_summary" in route

    def test_post_count_is_5(self):
        """5 POST endpoints: execute + rollback + retry + simulate + preview."""
        assert _route().count("@router.post") == 5

    def test_no_put_in_routes(self):
        assert "@router.put" not in _route()

    def test_no_delete_in_routes(self):
        assert "@router.delete" not in _route()

    def test_no_patch_in_routes(self):
        assert "@router.patch" not in _route()


# ===========================================================================
# P67-3: No auto/background/queue
# ===========================================================================
class TestC04Phase7NoAuto:
    def test_no_auto_rollback(self):
        content = RECOVERY_PATH.read_text(encoding="utf-8")
        assert "def auto_rollback" not in content

    def test_no_auto_retry(self):
        content = RECOVERY_PATH.read_text(encoding="utf-8")
        assert "def auto_retry" not in content

    def test_no_background_thread(self):
        content = RECOVERY_PATH.read_text(encoding="utf-8")
        assert "threading.Thread" not in content
        assert "BackgroundTask" not in content

    def test_no_queue_call(self):
        content = RECOVERY_PATH.read_text(encoding="utf-8")
        assert ".enqueue(" not in content
        assert "send_task(" not in content

    def test_buttons_disabled_by_default(self):
        html = _html()
        assert 'id="t3sc-c04-btn-rollback" disabled' in html
        assert 'id="t3sc-c04-btn-retry" disabled' in html
        assert 'id="t3sc-c04-btn-simulate" disabled' in html
        assert 'id="t3sc-c04-btn-preview" disabled' in html


# ===========================================================================
# P67-4: Simulation is read-only
# ===========================================================================
class TestC04Phase7Simulation:
    def test_simulation_note_in_schema(self):
        from app.schemas.manual_recovery_schema import SimulationReceipt

        r = SimulationReceipt(
            receipt_id="test",
            operator_id="op",
            timestamp="2026-01-01",
            decision="SIMULATED",
        )
        assert "SIMULATED" in r.simulation_note
        assert "not a guarantee" in r.simulation_note

    def test_preview_note_in_schema(self):
        from app.schemas.manual_recovery_schema import PreviewResult

        r = PreviewResult()
        assert "not guarantee" in r.preview_note.lower()
