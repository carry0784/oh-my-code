"""
C-04 Manual Action — Should-Never-Happen Invariants + Regression Guards

Phase 1 test-code only. C-04 구현 금지. 활성화 금지.
이 테스트는 향후 구현이 절대 위반하면 안 되는 경계를 코드로 고정한다.

대상: dashboard.html, dashboard.py, workers/, app/core/
범위: 자동 실행 금지, 체인 우회 금지, 내부 노출 금지, 회귀 보호
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"
WORKERS_DIR = PROJECT_ROOT / "workers"
CORE_DIR = PROJECT_ROOT / "app" / "core"


def _read_template():
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _read_dashboard_route():
    return DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# SNH-1: 자동 실행 금지 — C-04는 수동 트리거만 허용
# ===========================================================================
class TestC04NeverAutoExecute:
    """C-04 관련 자동 실행 패턴이 코드베이스에 없어야 한다."""

    def test_no_auto_execute_in_template(self):
        """템플릿에 autoExecute/auto_execute/auto-execute 패턴 금지."""
        html = _read_template().lower()
        assert "autoexecute" not in html
        assert "auto_execute" not in html
        assert "auto-execute" not in html

    def test_no_scheduled_action_for_c04(self):
        """C-04 영역 근처에 setInterval/setTimeout 기반 자동 트리거 금지."""
        html = _read_template()
        # C-04 card 영역 추출 (t3sc-c04 ~ 다음 t3sc 카드)
        c04_start = html.find('id="t3sc-c04"')
        if c04_start == -1:
            pytest.skip("t3sc-c04 element not found")
        c04_section = html[c04_start:c04_start + 2000]
        assert "setInterval" not in c04_section
        assert "setTimeout" not in c04_section

    def test_no_websocket_trigger_for_c04(self):
        """C-04에 WebSocket 기반 action trigger 금지."""
        html = _read_template().lower()
        # ws 기반 c04 트리거 패턴 확인
        assert "ws.send" not in html or "c04" not in html.split("ws.send")[0][-200:]

    def test_no_celery_task_for_c04(self):
        """workers/ 에 c04/manual_action 실행 celery task 금지."""
        for py_file in WORKERS_DIR.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8").lower()
            assert "manual_action" not in content, (
                f"Celery task referencing manual_action found: {py_file}"
            )
            assert "c04_execute" not in content, (
                f"Celery task referencing c04_execute found: {py_file}"
            )

    def test_no_agent_invocation_for_c04(self):
        """Agent/LLM이 C-04를 자동 호출하는 패턴 금지.
        Purpose transition: Phase 5 — manual endpoint exists but no agent trigger."""
        route_content = _read_dashboard_route()
        assert "agent_execute" not in route_content.lower()
        assert "llm_trigger" not in route_content.lower()
        assert "auto_manual_action" not in route_content.lower()


# ===========================================================================
# SNH-2: 체인 우회 금지 — 9단계 실행 체인 bypass 불가
# ===========================================================================
class TestC04NeverBypassChain:
    """9단계 실행 체인을 우회하는 패턴이 없어야 한다."""

    def test_no_skip_preflight_flag(self):
        """skip_preflight 파라미터가 route/core에 없어야 한다."""
        route_content = _read_dashboard_route()
        assert "skip_preflight" not in route_content
        for py_file in CORE_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            if "skip_preflight" in content:
                # recovery_preflight.py 자체는 제외
                if "recovery_preflight" not in py_file.name:
                    pytest.fail(f"skip_preflight found in {py_file.name}")

    def test_no_force_execute_flag(self):
        """force_execute / bypass_gate 파라미터 금지."""
        route_content = _read_dashboard_route()
        assert "force_execute" not in route_content
        assert "bypass_gate" not in route_content

    def test_no_emergency_override_for_c04(self):
        """C-04 전용 emergency override 경로 금지."""
        route_content = _read_dashboard_route().lower()
        assert "emergency_execute" not in route_content
        assert "override_c04" not in route_content
        assert "emergency_action" not in route_content

    def test_no_admin_backdoor_for_c04(self):
        """is_admin / superuser 기반 C-04 bypass 금지."""
        route_content = _read_dashboard_route()
        assert "is_admin" not in route_content
        assert "superuser" not in route_content
        assert "bypass_auth" not in route_content


# ===========================================================================
# SNH-3: 내부 정보 노출 금지 — 템플릿에서 디버그/내부 정보 미노출
# ===========================================================================
class TestC04NeverExposeInternal:
    """템플릿에 내부 정보가 노출되면 안 된다."""

    def test_no_chain_of_thought_in_template(self):
        html = _read_template().lower()
        assert "chain_of_thought" not in html
        assert "chain-of-thought" not in html

    def test_no_raw_prompt_in_template(self):
        html = _read_template().lower()
        assert "raw_prompt" not in html
        assert "raw-prompt" not in html

    def test_no_internal_reasoning_in_template(self):
        html = _read_template().lower()
        assert "internal_reasoning" not in html
        assert "internal-reasoning" not in html

    def test_no_debug_trace_in_template(self):
        html = _read_template().lower()
        assert "debug_trace" not in html
        assert "debug-trace" not in html

    def test_no_stack_trace_in_template(self):
        html = _read_template().lower()
        assert "stack_trace" not in html
        assert "stacktrace" not in html


# ===========================================================================
# SNH-4: 회귀 보호 — C-04 봉인 상태 + 기존 기준선 유지
# ===========================================================================
class TestC04RegressionGuards:
    """C-04 봉인 상태가 유지되고 기존 카드에 영향 없어야 한다."""

    def test_c04_still_sealed(self):
        """C-04 카드에 t3sc-sealed 클래스가 유지되어야 한다."""
        html = _read_template()
        assert 't3sc-sealed' in html

    def test_c04_still_shows_not_enabled(self):
        """'Not enabled in this phase' 텍스트가 유지되어야 한다."""
        html = _read_template()
        assert 'Not enabled in this phase' in html

    def test_render_c04_is_disabled_only(self):
        """_renderC04가 존재하더라도 disabled-only read-only renderer여야 한다.
        Purpose transition: absence check → disabled-only renderer check.
        This is control reinforcement, not relaxation."""
        html = _read_template()
        # _renderC04 exists as sealed read-only renderer
        assert '_renderC04' in html
        # Must NOT contain any action-capable patterns
        # Extract _renderC04 function body
        start = html.find('function _renderC04')
        assert start != -1, "_renderC04 function not found"
        # Check ~2000 chars of function body for prohibited patterns
        func_body = html[start:start + 2000].lower()
        assert 'button' not in func_body, "_renderC04 must not contain button"
        assert 'onclick' not in func_body, "_renderC04 must not contain onclick"
        assert '<form' not in func_body, "_renderC04 must not contain form"
        assert '.submit(' not in func_body, "_renderC04 must not contain .submit()"
        assert 'type="submit"' not in func_body, "_renderC04 must not contain submit button"
        assert 'fetch(' not in func_body, "_renderC04 must not contain fetch"
        assert 'xmlhttprequest' not in func_body, "_renderC04 must not contain XHR"
        assert '.dispatch(' not in func_body, "_renderC04 must not call dispatch()"
        assert 'dispatchevent' not in func_body, "_renderC04 must not dispatchEvent"
        assert 'hx-post' not in func_body, "_renderC04 must not contain hx-post"
        assert 'data-action' not in func_body, "_renderC04 must not contain data-action"

    def test_render_c04_controls_disabled_by_default(self):
        """C-04 카드의 버튼은 기본 disabled 상태여야 한다.
        Purpose transition: Phase 5 — button exists but disabled."""
        html = _read_template()
        assert 'id="t3sc-c04-exec-btn" disabled' in html
        # No inline onclick on any element
        c04_start = html.find('id="t3sc-c04"')
        next_card = html.find('id="t3sc-c05"', c04_start)
        c04_section = html[c04_start:next_card] if next_card != -1 else html[c04_start:c04_start + 2000]
        c04_lower = c04_section.lower()
        assert 'onclick' not in c04_lower
        assert '<input' not in c04_lower
        assert 'contenteditable' not in c04_lower

    def test_safe_cards_render_functions_intact(self):
        """기존 Safe Card 렌더 함수들이 유지되어야 한다."""
        html = _read_template()
        for card_num in ['01', '02', '03', '05', '06', '07', '08', '09']:
            assert f'_renderC{card_num}' in html, (
                f"_renderC{card_num} missing — Safe Card regression"
            )
