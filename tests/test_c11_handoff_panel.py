"""
Card C-11: Incident Summary / Handoff Receipt Panel — Tests

검수 범위:
  C11-1: Operator Panel Handoff Receipt 블록
  C11-2: JS 렌더링 함수 — 인계 요약 로직
  C11-3: CSS 스타일
  C11-4: Tab 2 통합
  C11-5: 금지 조항 확인

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
    fn_start = content.index("function renderHandoffReceipt")
    fn_end = content.index("function renderKeyFacts")
    return content[fn_start:fn_end]


# ===========================================================================
# C11-1: Operator Panel 블록
# ===========================================================================
class TestC11HandoffBlock:
    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="handoff-receipt-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="handoff-receipt-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Handoff Receipt" in content


# ===========================================================================
# C11-2: JS 렌더링 함수
# ===========================================================================
class TestC11RenderFunction:
    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderHandoffReceipt" in content

    def test_shows_overall_status(self):
        fn_body = _get_fn_body()
        assert "STATUS:" in fn_body

    def test_shows_incident_line(self):
        fn_body = _get_fn_body()
        assert "INCIDENT:" in fn_body

    def test_shows_sources_summary(self):
        fn_body = _get_fn_body()
        assert "SOURCES:" in fn_body

    def test_shows_venues_summary(self):
        fn_body = _get_fn_body()
        assert "VENUES:" in fn_body

    def test_shows_polled_timestamp(self):
        fn_body = _get_fn_body()
        assert "POLLED:" in fn_body

    def test_shows_action_line(self):
        fn_body = _get_fn_body()
        assert "ACTION:" in fn_body

    def test_shows_provenance_summary(self):
        fn_body = _get_fn_body()
        assert "PROVENANCE:" in fn_body

    def test_shows_generated_timestamp(self):
        fn_body = _get_fn_body()
        assert "GENERATED:" in fn_body

    def test_uses_pre_tag_for_copyable_output(self):
        """복붙 가능한 pre 태그 사용."""
        fn_body = _get_fn_body()
        assert "<pre" in fn_body
        assert "ho-receipt" in fn_body

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in _get_fn_body()

    def test_caps_triage_at_3(self):
        """ACTION 라인은 최대 3개까지."""
        fn_body = _get_fn_body()
        assert "slice(0, 3)" in fn_body

    def test_references_incident_sources(self):
        """기존 incident/status 데이터 소스를 참조한다."""
        fn_body = _get_fn_body()
        assert "loop_monitor" in fn_body
        assert "doctrine" in fn_body
        assert "work_state" in fn_body
        assert "source_freshness" in fn_body
        assert "venueStates" in fn_body

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
            assert f not in fn_body, f"Forbidden string '{f}'"


# ===========================================================================
# C11-3: CSS
# ===========================================================================
class TestC11CSS:
    def test_receipt_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ho-receipt" in content

    def test_monospace_font(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        idx = content.index(".ho-receipt")
        section = content[idx : idx + 300]
        assert "monospace" in section

    def test_user_select_all(self):
        """전체 선택 가능하도록 user-select: all 설정."""
        content = CSS_PATH.read_text(encoding="utf-8")
        idx = content.index(".ho-receipt")
        section = content[idx : idx + 300]
        assert "user-select" in section


# ===========================================================================
# C11-4: Tab 2 통합
# ===========================================================================
class TestC11Integration:
    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderHandoffReceipt(data, venueStates)" in content

    def test_block_between_triage_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        tc_pos = content.index('id="triage-checklist-block"')
        ho_pos = content.index('id="handoff-receipt-block"')
        el_pos = content.index('id="event-log-block"')
        assert tc_pos < ho_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in [
            "key-facts-block",
            "loop-ceiling-block",
            "quote-feed-block",
            "venue-status-block",
            "freshness-timeline-block",
            "provenance-block",
            "triage-checklist-block",
            "event-log-block",
            "incident-overlay",
        ]:
            assert bid in content, f"{bid} must be preserved"
