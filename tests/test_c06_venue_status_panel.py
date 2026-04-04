"""
Card C-06: Venue Status Monitor Panel — Tests

검수 범위:
  C06-1: Operator Panel Venue Status Monitor 블록
  C06-2: JS 렌더링 함수 구조
  C06-3: CSS 스타일
  C06-4: Tab 2 통합 및 기존 블록 보존
  C06-5: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
API 변경 없음 — 기존 v2 데이터 집계만.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy modules
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance",
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
    fn_start = content.index("function renderVenueStatusMonitor")
    fn_end = content.index("function renderKeyFacts")
    return content[fn_start:fn_end]


# ===========================================================================
# C06-1: Operator Panel 블록
# ===========================================================================
class TestC06VenueStatusBlock:

    def test_venue_status_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="venue-status-body"' in content

    def test_venue_status_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="venue-status-block"' in content

    def test_block_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Venue Status Monitor" in content


# ===========================================================================
# C06-2: JS 렌더링 함수
# ===========================================================================
class TestC06RenderFunction:

    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderVenueStatusMonitor" in content

    def test_references_venue_freshness(self):
        assert "venue_freshness" in _get_fn_body()

    def test_references_quote_data(self):
        assert "quote_data" in _get_fn_body()

    def test_references_open_orders(self):
        assert "open_orders" in _get_fn_body()

    def test_references_position_count(self):
        assert "position_count" in _get_fn_body()

    def test_derives_connection_state(self):
        """연결 상태 판별 로직이 존재한다."""
        fn_body = _get_fn_body()
        for state in ['CONNECTED', 'DEGRADED', 'STALE', 'DISCONNECTED', 'NO_POSITIONS']:
            assert state in fn_body, f"Connection state {state} must be referenced"

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in _get_fn_body()

    def test_shows_age_per_venue(self):
        assert "age_seconds" in _get_fn_body()

    def test_shows_overall_summary(self):
        fn_body = _get_fn_body()
        assert "totalConnected" in fn_body
        assert "totalDown" in fn_body

    def test_no_forbidden_strings(self):
        fn_body = _get_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in venue status render"


# ===========================================================================
# C06-3: CSS
# ===========================================================================
class TestC06CSS:

    def test_venue_row_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".vs-venue-row" in content

    def test_badge_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".vs-badge" in content

    def test_connection_state_colors(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in ['.vs-connected', '.vs-degraded', '.vs-stale', '.vs-disconnected']:
            assert cls in content, f"CSS class {cls} must exist"

    def test_overall_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".vs-overall" in content


# ===========================================================================
# C06-4: Tab 2 통합
# ===========================================================================
class TestC06Integration:

    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderVenueStatusMonitor(data)" in content

    def test_panel_between_quote_feed_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        qf_pos = content.index('id="quote-feed-block"')
        vs_pos = content.index('id="venue-status-block"')
        el_pos = content.index('id="event-log-block"')
        assert qf_pos < vs_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in ['key-facts-block', 'loop-ceiling-block', 'quote-feed-block', 'event-log-block']:
            assert f'id="{bid}"' in content, f"Block {bid} must be preserved"

    def test_existing_functions_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for fn in ['renderLoopCeilingMonitor', 'renderQuoteFeedMonitor',
                    'renderAIWorkspace', 'renderQuoteFields']:
            assert f"function {fn}" in content, f"{fn} must be preserved"
