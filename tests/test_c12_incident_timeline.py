"""
Card C-12: Incident Chronology Panel — Tests

검수 범위:
  C12-1: Timeline panel HTML 블록
  C12-2: JS 렌더링 함수 — chronology 로직
  C12-3: CSS 스타일
  C12-4: Tab 2 통합
  C12-5: 상태 구분 원칙 및 금지 조항

Sealed layers 미접촉. API 변경 없음. 기존 v2 데이터 소비만.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance", "app.exchanges.okx",
    "app.services", "app.services.order_service",
    "app.services.position_service", "app.services.signal_service",
    "ccxt", "ccxt.async_support", "redis", "celery", "asyncpg",
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
    fn_start = content.index("function renderIncidentChronology")
    fn_end = content.index("function renderKeyFacts")
    return content[fn_start:fn_end]


# ===========================================================================
# C12-1: Timeline panel HTML
# ===========================================================================
class TestC12TimelineBlock:

    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="incident-chronology-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="incident-chronology-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Incident Chronology" in content


# ===========================================================================
# C12-2: JS chronology render function
# ===========================================================================
class TestC12RenderFunction:

    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderIncidentChronology" in content

    def test_consumes_existing_v2_fields(self):
        """기존 v2 payload 필드만 참조한다."""
        fn_body = _get_fn_body()
        assert "source_freshness" in fn_body
        assert "loop_monitor" in fn_body
        assert "work_state" in fn_body
        assert "venue_freshness" in fn_body
        assert "quote_data" in fn_body
        assert "doctrine" in fn_body
        assert "governance" in fn_body

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in _get_fn_body()

    def test_all_clear_when_empty(self):
        assert "ALL CLEAR" in _get_fn_body()

    def test_shows_timestamps(self):
        fn_body = _get_fn_body()
        assert "ic-time" in fn_body

    def test_shows_age(self):
        fn_body = _get_fn_body()
        assert "ic-age" in fn_body
        assert "age_seconds" in fn_body

    def test_sorts_entries(self):
        fn_body = _get_fn_body()
        assert "entries.sort(" in fn_body

    def test_caps_display_rows(self):
        fn_body = _get_fn_body()
        assert "MAX_ROWS" in fn_body
        assert "slice(0, MAX_ROWS)" in fn_body

    def test_shows_overflow(self):
        assert "ic-overflow" in _get_fn_body()

    def test_shows_venue_disconnected(self):
        fn_body = _get_fn_body()
        assert "DISCONNECTED" in fn_body

    def test_shows_venue_stale(self):
        fn_body = _get_fn_body()
        assert "STALE" in fn_body

    def test_shows_venue_degraded(self):
        fn_body = _get_fn_body()
        assert "DEGRADED" in fn_body

    def test_shows_security_state(self):
        fn_body = _get_fn_body()
        assert "security_state" in fn_body


# ===========================================================================
# C12-3: CSS
# ===========================================================================
class TestC12CSS:

    def test_row_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ic-row" in content

    def test_badge_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ic-badge" in content

    def test_time_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ic-time" in content

    def test_label_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ic-label" in content

    def test_clear_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ic-clear" in content


# ===========================================================================
# C12-4: Tab 2 통합
# ===========================================================================
class TestC12Integration:

    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderIncidentChronology(data, venueStates)" in content

    def test_block_between_handoff_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ho_pos = content.index('id="handoff-receipt-block"')
        ic_pos = content.index('id="incident-chronology-block"')
        el_pos = content.index('id="event-log-block"')
        assert ho_pos < ic_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in ['key-facts-block', 'loop-ceiling-block', 'quote-feed-block',
                     'venue-status-block', 'freshness-timeline-block',
                     'provenance-block', 'triage-checklist-block',
                     'handoff-receipt-block', 'event-log-block',
                     'incident-overlay']:
            assert bid in content, f"{bid} must be preserved"


# ===========================================================================
# C12-5: 상태 구분 원칙 및 금지 조항
# ===========================================================================
class TestC12StateDistinction:

    def test_distinguishes_unknown_stale_disconnected(self):
        """unknown / stale / disconnected가 별도로 존재한다."""
        fn_body = _get_fn_body()
        assert "'unknown'" in fn_body
        assert "'stale'" in fn_body
        assert "'disconnected'" in fn_body

    def test_distinguishes_fresh_from_others(self):
        assert "'fresh'" in _get_fn_body()

    def test_no_forbidden_strings(self):
        fn_body = _get_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}'"

    def test_is_not_raw_log_viewer(self):
        """raw log viewer가 아닌 요약 패널이다."""
        fn_body = _get_fn_body()
        assert "console.log" not in fn_body
        assert "JSON.stringify" not in fn_body
        assert "innerHTML" in fn_body  # renders structured HTML, not raw dumps
