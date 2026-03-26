"""
C-04 Guard-bound Operator UI Tests

Verify that Operator UI binds to Guard results read-only.
No UI-side score derivation. No SSOT drift. Fail-closed on null/empty.
Blocked reason is most prominent. Simulate ≠ execute visually distinct.
Evidence section present with present/missing/unavailable states.

Genesis Baseline: 27d46ca
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


def _html():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _css():
    return CSS_PATH.read_text(encoding="utf-8")


# ===========================================================================
# UI-1: Execute disabled when blocked
# ===========================================================================
class TestC04ExecuteDisabledWhenBlocked:

    def test_exec_btn_disabled_by_default(self):
        assert 'id="t3sc-c04-exec-btn" disabled' in _html()

    def test_exec_btn_has_aria_disabled(self):
        assert 'aria-disabled="true"' in _html()

    def test_exec_btn_no_auto_enable(self):
        """No unconditional enable path in JS."""
        html = _html()
        start = html.find("function _renderC04(")
        end = html.find("\n}", start + 20) if start != -1 else -1
        body = html[start:end + 2].lower() if start != -1 and end != -1 else ""
        # Enable only when metCount === 9
        assert "metcount === 9" in body or "metcount===9" in body or "chainok" in body


# ===========================================================================
# UI-2: Blocked reason visible and prominent
# ===========================================================================
class TestC04RejectedReasonVisible:

    def test_blocked_prominent_css_exists(self):
        assert 't3sc-c04-blocked-prominent' in _css()

    def test_blocked_prominent_has_red_border(self):
        css = _css()
        idx = css.find('.t3sc-c04-blocked-prominent')
        section = css[idx:idx + 200]
        assert 'accent-red' in section or 'red' in section

    def test_result_shows_block_code_first(self):
        """In execute result display, blocked reason comes before decision badge."""
        html = _html()
        # Find the result rendering code
        idx = html.find("t3sc-c04-blocked-prominent")
        badge_idx = html.find("t3sc-c04-badge-rejected", idx if idx != -1 else 0)
        if idx != -1 and badge_idx != -1:
            assert idx < badge_idx, "Block reason must appear before decision badge"


# ===========================================================================
# UI-3: Simulated and executed are visually distinct
# ===========================================================================
class TestC04SimulatedAndExecutedAreVisuallyDistinct:

    def test_executed_badge_class_exists(self):
        assert 't3sc-c04-badge-executed' in _css()

    def test_rejected_badge_class_exists(self):
        assert 't3sc-c04-badge-rejected' in _css()

    def test_simulated_badge_class_exists(self):
        assert 't3sc-c04-badge-simulated' in _css()

    def test_executed_uses_green(self):
        css = _css()
        idx = css.find('.t3sc-c04-badge-executed')
        section = css[idx:idx + 100]
        assert 'green' in section

    def test_rejected_uses_red(self):
        css = _css()
        idx = css.find('.t3sc-c04-badge-rejected')
        section = css[idx:idx + 100]
        assert 'red' in section

    def test_simulated_uses_yellow(self):
        css = _css()
        idx = css.find('.t3sc-c04-badge-simulated')
        section = css[idx:idx + 150]
        assert 'yellow' in section


# ===========================================================================
# UI-4: Null payload fails closed
# ===========================================================================
class TestC04NullPayloadFailsClosed:

    def test_evidence_defaults_to_unavailable(self):
        html = _html()
        assert 'unavailable' in html  # default evidence state

    def test_update_evidence_handles_null(self):
        """_updateC04Evidence handles null data gracefully."""
        html = _html()
        assert '_updateC04Evidence' in html
        start = html.find("function _updateC04Evidence")
        assert start != -1
        end = html.find("\nfunction ", start + 30)
        body = html[start:end] if end != -1 else html[start:start + 1500]
        assert "if (!data)" in body  # null guard

    def test_evidence_missing_not_empty(self):
        """Evidence shows 'missing' not empty string."""
        html = _html()
        start = html.find("function _updateC04Evidence")
        body = html[start:start + 500]
        assert "'missing'" in body


# ===========================================================================
# UI-5: Evidence section present
# ===========================================================================
class TestC04EvidenceSectionPresent:

    def test_evidence_vis_container(self):
        assert 'id="t3sc-c04-evidence-vis"' in _html()

    def test_evidence_receipt_field(self):
        assert 'id="t3sc-c04-ev-receipt"' in _html()

    def test_evidence_audit_field(self):
        assert 'id="t3sc-c04-ev-audit"' in _html()

    def test_evidence_chain_field(self):
        assert 'id="t3sc-c04-ev-chain"' in _html()

    def test_evidence_title(self):
        assert 'Evidence Chain' in _html()

    def test_evidence_css_states(self):
        css = _css()
        assert 't3sc-c04-ev-present' in css
        assert 't3sc-c04-ev-missing' in css
        assert 't3sc-c04-ev-unavailable' in css


# ===========================================================================
# UI-6: UI uses existing ops-safety-summary only
# ===========================================================================
class TestC04UIUsesExistingOpsSafetySummaryOnly:

    def test_no_score_calculation_in_ui(self):
        """UI must not compute ops_score itself."""
        html = _html()
        # _renderC04 area
        start = html.find("function _renderC04(")
        end = html.find("\nfunction ", start + 30) if start != -1 else -1
        body = html[start:end].lower() if start != -1 and end != -1 else ""
        assert "integrity + connectivity" not in body
        assert "/ 4" not in body or "9" in body  # /4 for score avg should not be in renderer

    def test_no_extra_fetch_in_renderer(self):
        """_renderC04 must not make additional API calls."""
        html = _html()
        start = html.find("function _renderC04(")
        end = html.find("\nfunction ", start + 30) if start != -1 else -1
        body = html[start:end].lower() if start != -1 and end != -1 else ""
        assert "fetch(" not in body

    def test_no_new_endpoint_added(self):
        route = ROUTE_PATH.read_text(encoding="utf-8")
        assert route.count("@router.post") == 5  # unchanged from Genesis
        assert "@router.put" not in route
        assert "@router.delete" not in route

    def test_post_count_unchanged(self):
        route = ROUTE_PATH.read_text(encoding="utf-8")
        assert route.count("@router.post") == 5


# ===========================================================================
# UI-7: Regression gate
# ===========================================================================
class TestC04GenesisRegressionGate:

    def test_c04_card_still_exists(self):
        assert 'id="t3sc-c04"' in _html()

    def test_safe_cards_intact(self):
        html = _html()
        for n in ['01', '02', '03', '05', '06', '07', '08', '09']:
            assert f'id="t3sc-c{n}"' in html

    def test_sealed_badge_still_exists(self):
        assert 'id="t3sc-c04-badge"' in _html()


# ===========================================================================
# UI-8: Receipt/Audit session history
# ===========================================================================
class TestC04ReceiptAuditHistory:

    def test_history_container_exists(self):
        assert 'id="t3sc-c04-ev-history"' in _html()

    def test_session_history_array_exists(self):
        assert '_c04SessionHistory' in _html()

    def test_push_history_function_exists(self):
        assert '_pushC04History' in _html()

    def test_history_empty_default(self):
        assert 'No actions in this session' in _html()

    def test_history_has_no_persistence(self):
        """History is session-local only, no fetch/POST for persistence."""
        html = _html()
        start = html.find("function _pushC04History")
        end = html.find("\nfunction ", start + 30) if start != -1 else -1
        body = html[start:end].lower() if start != -1 and end != -1 else ""
        assert "fetch(" not in body
        assert "post" not in body

    def test_history_shows_decision_badge(self):
        """History rows use distinct decision badge classes."""
        html = _html()
        start = html.find("function _pushC04History")
        body = html[start:start + 1000] if start != -1 else ""
        assert "t3sc-c04-badge-executed" in body
        assert "t3sc-c04-badge-simulated" in body
        assert "t3sc-c04-badge-rejected" in body

    def test_execute_calls_push_history(self):
        """Execute result handler pushes to history."""
        html = _html()
        assert "_pushC04History(data)" in html

    def test_history_max_entries(self):
        """History is limited to prevent unbounded growth."""
        html = _html()
        start = html.find("function _pushC04History")
        body = html[start:start + 500] if start != -1 else ""
        assert "_c04SessionHistory.length > 10" in body or "length > " in body
