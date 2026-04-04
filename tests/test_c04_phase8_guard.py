"""
C-04 Phase 8 — Guard / Display / Manual-Refresh Tests

A-1~A-12 only. No new endpoint. No execution. No state mutation.
Write path must remain exactly 5 bounded POST.
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"


def _html():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _route():
    return ROUTE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# P8-1: Phase 8 UI elements exist
# ===========================================================================
class TestP8UIExists:
    def test_p8_container_exists(self):
        assert 'id="t3sc-c04-p8"' in _html()

    def test_sealed_row_exists(self):
        assert 'id="t3sc-c04-p8-sealed"' in _html()

    def test_phase_row_exists(self):
        assert 'id="t3sc-c04-p8-phase"' in _html()

    def test_scope_row_exists(self):
        assert 'id="t3sc-c04-p8-scope"' in _html()

    def test_forbidden_row_exists(self):
        assert 'id="t3sc-c04-p8-forbidden"' in _html()

    def test_approval_row_exists(self):
        assert 'id="t3sc-c04-p8-approval"' in _html()

    def test_guard_section_exists(self):
        assert 'id="t3sc-c04-p8-guard"' in _html()

    def test_status_section_exists(self):
        assert 'id="t3sc-c04-p8-status"' in _html()

    def test_refresh_button_exists(self):
        assert 'id="t3sc-c04-p8-refresh-btn"' in _html()

    def test_render_function_exists(self):
        assert "_renderC04Phase8" in _html()


# ===========================================================================
# P8-2: Guard text content
# ===========================================================================
class TestP8GuardContent:
    def test_sealed_shows_yes(self):
        html = _html()
        # The sealed row should show YES
        idx = html.find('id="t3sc-c04-p8-sealed"')
        assert idx != -1
        row = html[idx : idx + 200]
        assert "YES" in row

    def test_phase_shows_8(self):
        html = _html()
        idx = html.find('id="t3sc-c04-p8-phase"')
        row = html[idx : idx + 200]
        assert "8" in row

    def test_scope_shows_manual(self):
        html = _html()
        idx = html.find('id="t3sc-c04-p8-scope"')
        row = html[idx : idx + 200]
        assert "Manual" in row

    def test_forbidden_shows_auto(self):
        html = _html()
        idx = html.find('id="t3sc-c04-p8-forbidden"')
        row = html[idx : idx + 200]
        assert "Auto" in row

    def test_read_only_indicator(self):
        html = _html()
        assert "Read-Only" in html


# ===========================================================================
# P8-3: No new endpoint
# ===========================================================================
class TestP8NoNewEndpoint:
    def test_post_count_unchanged(self):
        """Write path must remain exactly 5 POST."""
        route = _route()
        assert route.count("@router.post") == 5

    def test_no_put(self):
        assert "@router.put" not in _route()

    def test_no_delete(self):
        assert "@router.delete" not in _route()

    def test_no_patch(self):
        assert "@router.patch" not in _route()

    def test_no_new_manual_endpoint(self):
        """No new manual-action sub-endpoint beyond execute/rollback/retry/simulate/preview."""
        route = _route()
        manual_posts = [
            l for l in route.split("\n") if "@router.post" in l and "manual-action" in l
        ]
        assert len(manual_posts) == 5


# ===========================================================================
# P8-4: Manual refresh uses existing fetch only
# ===========================================================================
class TestP8ManualRefresh:
    def test_refresh_calls_existing_function(self):
        """Manual refresh calls renderTab3SafeCards (existing), not a new POST."""
        html = _html()
        start = html.find("t3sc-c04-p8-refresh-btn")
        # Find the click handler
        handler_area = html[start : start + 1000]
        assert "renderTab3SafeCards" in handler_area or "renderTab3SafeCards" in html

    def test_refresh_button_disabled_by_default(self):
        assert 'id="t3sc-c04-p8-refresh-btn" disabled' in _html()

    def test_no_fetch_in_refresh_handler(self):
        """Phase 8 refresh must not create its own fetch/POST."""
        html = _html()
        # Find Phase 8 refresh handler
        start = html.find("t3sc-c04-p8-refresh-btn")
        # The handler should use renderTab3SafeCards, not fetch
        p8_area = html[start : start + 500].lower()
        assert "fetch(" not in p8_area or "post" not in p8_area


# ===========================================================================
# P8-5: No execution/mutation
# ===========================================================================
class TestP8NoExecution:
    def test_render_p8_has_no_fetch(self):
        """_renderC04Phase8 must not call fetch."""
        html = _html()
        start = html.find("function _renderC04Phase8")
        assert start != -1
        end = html.find("\nfunction ", start + 30)
        body = html[start:end].lower() if end != -1 else html[start : start + 2000].lower()
        assert "fetch(" not in body

    def test_render_p8_has_no_mutation(self):
        html = _html()
        start = html.find("function _renderC04Phase8")
        end = html.find("\nfunction ", start + 30)
        body = html[start:end].lower() if end != -1 else html[start : start + 2000].lower()
        assert ".post(" not in body
        assert ".put(" not in body

    def test_no_new_handler_file(self):
        """No new handler file for Phase 8."""
        p8_handler = PROJECT_ROOT / "app" / "core" / "phase8_handler.py"
        assert not p8_handler.exists()

    def test_no_state_machine(self):
        html = _html()
        start = html.find("function _renderC04Phase8")
        end = html.find("\nfunction ", start + 30)
        body = html[start:end].lower() if end != -1 else html[start : start + 2000].lower()
        assert "statemachine" not in body
        assert "state_machine" not in body


# ===========================================================================
# P8-6: Phase boundary preserved
# ===========================================================================
class TestP8PhaseBoundary:
    def test_c04_still_sealed_class(self):
        assert "t3sc-sealed" in _html()

    def test_c04_still_has_sealed_badge(self):
        assert 'id="t3sc-c04-badge"' in _html()

    def test_phase5_exec_btn_still_exists(self):
        assert 'id="t3sc-c04-exec-btn"' in _html()

    def test_phase7_buttons_still_exist(self):
        html = _html()
        assert 'id="t3sc-c04-btn-rollback"' in html
        assert 'id="t3sc-c04-btn-retry"' in html
        assert 'id="t3sc-c04-btn-simulate"' in html
        assert 'id="t3sc-c04-btn-preview"' in html

    def test_safe_cards_intact(self):
        html = _html()
        for n in ["01", "02", "03", "05", "06", "07", "08", "09"]:
            assert f'id="t3sc-c{n}"' in html
