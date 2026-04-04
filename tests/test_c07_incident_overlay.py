"""
Card C-07: Incident Overlay Enhancement — Tests

검수 범위:
  C07-1: Incident Overlay HTML 블록
  C07-2: JS 렌더링 함수 — 우선순위 판정 로직
  C07-3: CSS 스타일
  C07-4: Tab 2 통합 및 기존 블록 보존
  C07-5: 금지 조항 확인

Sealed layers 미접촉. API 변경 없음. 기존 v2 데이터 소비만.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

sys.modules["app.models.position"].Position = MagicMock()
sys.modules["app.models.position"].PositionSide = MagicMock()
sys.modules["app.models.order"].Order = MagicMock()
sys.modules["app.models.order"].OrderStatus = MagicMock()
sys.modules["app.models.trade"].Trade = MagicMock()
sys.modules["app.models.signal"].Signal = MagicMock()
sys.modules["app.core.database"].Base = MagicMock()
sys.modules["app.core.database"].get_db = MagicMock()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"


def _get_fn_body():
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    fn_start = content.index("function renderIncidentOverlay")
    fn_end = content.index("function renderKeyFacts")
    return content[fn_start:fn_end]


# ===========================================================================
# C07-1: HTML 블록
# ===========================================================================
class TestC07IncidentOverlayBlock:
    def test_incident_overlay_element_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="incident-overlay"' in content

    def test_starts_hidden(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "io-hidden" in content

    def test_positioned_before_workspace(self):
        """Overlay는 t2-workspace 앞에 위치한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        overlay_pos = content.index('id="incident-overlay"')
        workspace_pos = content.index('class="t2-workspace"')
        assert overlay_pos < workspace_pos


# ===========================================================================
# C07-2: JS 렌더링 함수 — 우선순위 판정
# ===========================================================================
class TestC07RenderFunction:
    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderIncidentOverlay" in content

    def test_checks_security_state(self):
        """LOCKDOWN / QUARANTINED 판정."""
        fn_body = _get_fn_body()
        assert "'LOCKDOWN'" in fn_body
        assert "'QUARANTINED'" in fn_body

    def test_checks_loop_monitor(self):
        """Loop EXCEEDED / CRITICAL 판정."""
        fn_body = _get_fn_body()
        assert "loop_monitor" in fn_body
        assert "any_exceeded" in fn_body

    def test_checks_doctrine_violations(self):
        """Doctrine violation 판정."""
        fn_body = _get_fn_body()
        assert "doctrine" in fn_body
        assert "violation_count" in fn_body
        assert "CONSTITUTIONAL" in fn_body

    def test_checks_work_state(self):
        """Work FAILED / BLOCKED 판정."""
        fn_body = _get_fn_body()
        assert "work_state" in fn_body
        assert "'FAILED'" in fn_body
        assert "'BLOCKED'" in fn_body

    def test_checks_venue_disconnected(self):
        """Venue DISCONNECTED 판정."""
        fn_body = _get_fn_body()
        assert "'DISCONNECTED'" in fn_body
        assert "venueStates" in fn_body

    def test_checks_quote_feed_down(self):
        """Quote feed DISCONNECTED 판정."""
        fn_body = _get_fn_body()
        assert "quote_data" in fn_body
        assert "QUOTE FEED DOWN" in fn_body

    def test_checks_trust_degraded(self):
        """Trust non-executable 판정."""
        fn_body = _get_fn_body()
        assert "trust_state" in fn_body
        assert "allows_execution" in fn_body

    def test_sorts_by_severity(self):
        """severity 기준 정렬."""
        fn_body = _get_fn_body()
        assert "incidents.sort(" in fn_body
        assert "severity" in fn_body

    def test_shows_primary_and_secondary(self):
        """Primary(최심각) + secondary(보조 2~3건) 분리."""
        fn_body = _get_fn_body()
        assert "io-primary" in fn_body
        assert "io-secondary" in fn_body
        assert "incidents.slice(1, 3)" in fn_body

    def test_hides_when_no_incidents(self):
        """사건 없으면 overlay 숨김."""
        fn_body = _get_fn_body()
        assert "io-hidden" in fn_body

    def test_no_forbidden_strings(self):
        fn_body = _get_fn_body()
        forbidden = [
            "agent_analysis",
            "raw_prompt",
            "chain_of_thought",
            "internal_reasoning",
            "debug_trace",
            "error_class",
            "traceback",
            "exception_type",
            "stack",
            "internal_state_dump",
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in incident overlay"


# ===========================================================================
# C07-3: CSS
# ===========================================================================
class TestC07CSS:
    def test_container_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".io-container" in content

    def test_hidden_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".io-hidden" in content

    def test_severity_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in [".io-critical", ".io-warning", ".io-caution"]:
            assert cls in content, f"Severity class {cls} must exist"

    def test_critical_has_blink(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        idx = content.index(".io-critical")
        section = content[idx : idx + 200]
        assert "blink" in section or "animation" in section

    def test_primary_and_secondary_classes(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".io-primary" in content
        assert ".io-secondary" in content


# ===========================================================================
# C07-4: Tab 2 통합
# ===========================================================================
class TestC07Integration:
    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderIncidentOverlay(data, venueStates)" in content

    def test_called_before_key_facts(self):
        """Incident overlay가 renderKeyFacts보다 먼저 호출된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderTab2")
        fn_section = content[fn_start : fn_start + 500]
        io_pos = fn_section.index("renderIncidentOverlay")
        kf_pos = fn_section.index("renderKeyFacts")
        assert io_pos < kf_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in [
            "key-facts-block",
            "loop-ceiling-block",
            "quote-feed-block",
            "venue-status-block",
            "event-log-block",
        ]:
            assert f'id="{bid}"' in content, f"Block {bid} must be preserved"

    def test_existing_functions_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for fn in [
            "renderLoopCeilingMonitor",
            "renderQuoteFeedMonitor",
            "renderVenueStatusMonitor",
            "renderAIWorkspace",
        ]:
            assert f"function {fn}" in content, f"{fn} must be preserved"
