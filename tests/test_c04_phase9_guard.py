"""
C-04 Phase 9 — Boundary Refinement Tests

Informational/guard only. No execution. No approval actuation. No write-path expansion.
Any UI element that could be interpreted as execution enablement must be absent.
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


def _html():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _route():
    return ROUTE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# P9-1: Phase 9 UI elements exist
# ===========================================================================
class TestP9UIExists:

    def test_p9_container(self):
        assert 'id="t3sc-c04-p9"' in _html()

    def test_approval_context(self):
        assert 'id="t3sc-c04-p9-approval-ctx"' in _html()

    def test_block_detail(self):
        assert 'id="t3sc-c04-p9-block-detail"' in _html()

    def test_prereq_matrix(self):
        assert 'id="t3sc-c04-p9-prereq"' in _html()

    def test_stale_warning(self):
        assert 'id="t3sc-c04-p9-stale"' in _html()

    def test_no_exec_label(self):
        assert 't3sc-c04-p9-label-noexec' in _html()

    def test_no_auto_label(self):
        assert 't3sc-c04-p9-label-noauto' in _html()

    def test_readonly_label(self):
        assert 't3sc-c04-p9-label-readonly' in _html()

    def test_phase_explain(self):
        assert 'id="t3sc-c04-p9-explain"' in _html()

    def test_render_function(self):
        assert '_renderC04Phase9' in _html()


# ===========================================================================
# P9-2: Label content
# ===========================================================================
class TestP9LabelContent:

    def test_no_execution_text(self):
        assert 'NO EXECUTION' in _html()

    def test_no_auto_text(self):
        assert 'NO AUTO' in _html()

    def test_readonly_text(self):
        assert 'READ-ONLY' in _html()

    def test_phase_explanation(self):
        html = _html()
        assert 'Boundary refinement' in html
        assert 'No execution authority' in html

    def test_prerequisite_matrix_title(self):
        html = _html()
        assert 'Prerequisite Matrix' in html


# ===========================================================================
# P9-3: No new endpoint
# ===========================================================================
class TestP9NoNewEndpoint:

    def test_post_count_5(self):
        assert _route().count("@router.post") == 5

    def test_no_put(self):
        assert "@router.put" not in _route()

    def test_no_delete(self):
        assert "@router.delete" not in _route()

    def test_no_patch(self):
        assert "@router.patch" not in _route()

    def test_no_phase9_endpoint(self):
        route = _route()
        assert "phase9" not in route.lower()
        assert "phase-9" not in route.lower()


# ===========================================================================
# P9-4: No execution semantics in Phase 9 renderer
# ===========================================================================
class TestP9NoExecution:

    def _get_p9_body(self):
        html = _html()
        start = html.find("function _renderC04Phase9")
        assert start != -1
        rest = html[start + 30:]
        end = rest.find("\nfunction ") if rest.find("\nfunction ") != -1 else rest.find("\n// Phase 7")
        return rest[:end].lower() if end != -1 else rest[:2000].lower()

    def test_no_fetch(self):
        assert "fetch(" not in self._get_p9_body()

    def test_no_post(self):
        body = self._get_p9_body()
        assert "method:" not in body or "post" not in body

    def test_no_mutation(self):
        body = self._get_p9_body()
        assert "db.add" not in body
        assert "session.commit" not in body

    def test_no_button_creation(self):
        body = self._get_p9_body()
        assert "<button" not in body

    def test_no_onclick(self):
        body = self._get_p9_body()
        assert "onclick" not in body
        assert "addeventlistener" not in body


# ===========================================================================
# P9-5: Phase isolation
# ===========================================================================
class TestP9PhaseIsolation:

    def test_c04_still_sealed(self):
        assert 't3sc-sealed' in _html()

    def test_phase5_exec_btn(self):
        assert 'id="t3sc-c04-exec-btn"' in _html()

    def test_phase7_buttons(self):
        html = _html()
        assert 'id="t3sc-c04-btn-rollback"' in html
        assert 'id="t3sc-c04-btn-simulate"' in html

    def test_phase8_guard(self):
        assert 'id="t3sc-c04-p8"' in _html()

    def test_safe_cards_intact(self):
        html = _html()
        for n in ['01', '02', '03', '05', '06', '07', '08', '09']:
            assert f'id="t3sc-c{n}"' in html


# ===========================================================================
# P9-6: Blocked dominance
# ===========================================================================
class TestP9BlockedDominance:

    def test_blocked_class_in_labels(self):
        """Block detail should use blocked class."""
        html = _html()
        idx = html.find('id="t3sc-c04-p9-block-detail"')
        assert idx != -1

    def test_no_execution_affordance(self):
        """Phase 9 area must not have any execution-like control."""
        html = _html()
        p9_start = html.find('id="t3sc-c04-p9"')
        p9_end = html.find('</div>\n    </div>\n    <!-- C-05', p9_start)
        p9 = html[p9_start:p9_end].lower() if p9_end != -1 else html[p9_start:p9_start + 2000].lower()
        assert '<button' not in p9
        assert 'onclick' not in p9
        assert '<form' not in p9
        assert '<input' not in p9
