"""
Card C-05: Quote Feed Monitor Panel — Tests

검수 범위:
  C05-1: Operator Panel Quote Feed Monitor 블록
  C05-2: JS 렌더링 함수 구조
  C05-3: CSS 스타일
  C05-4: Tab 2 통합 및 기존 블록 보존
  C05-5: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy modules
# ---------------------------------------------------------------------------
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

_pos_mock = sys.modules["app.models.position"]
_pos_mock.Position = MagicMock()
_pos_mock.PositionSide = MagicMock()

_order_mock = sys.modules["app.models.order"]
_order_mock.Order = MagicMock()
_order_mock.OrderStatus = MagicMock()

_trade_mock = sys.modules["app.models.trade"]
_trade_mock.Trade = MagicMock()

_signal_mock = sys.modules["app.models.signal"]
_signal_mock.Signal = MagicMock()

_db_mod = sys.modules["app.core.database"]
_db_mod.Base = MagicMock()
_db_mod.get_db = MagicMock()


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = PROJECT_ROOT / "app" / "templates" / "dashboard.html"
CSS_PATH = PROJECT_ROOT / "app" / "static" / "css" / "dashboard.css"


# ===========================================================================
# C05-1: Operator Panel 블록
# ===========================================================================
class TestC05QuoteFeedBlock:
    """Tab 2 Operator Workspace에 Quote Feed Monitor 블록 검증."""

    def test_quote_feed_body_exists(self):
        """C05-1a: quote-feed-body 요소가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="quote-feed-body"' in content

    def test_quote_feed_block_exists(self):
        """C05-1b: quote-feed-block 요소가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="quote-feed-block"' in content

    def test_block_title_correct(self):
        """C05-1c: 블록 타이틀이 'Quote Feed Monitor'이다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Quote Feed Monitor" in content


# ===========================================================================
# C05-2: JS 렌더링 함수
# ===========================================================================
class TestC05RenderFunction:
    """renderQuoteFeedMonitor JS 함수 검증."""

    def _get_fn_body(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderQuoteFeedMonitor")
        fn_end = content.index("function renderKeyFacts")
        return content[fn_start:fn_end]

    def test_function_exists(self):
        """C05-2a: renderQuoteFeedMonitor 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderQuoteFeedMonitor" in content

    def test_references_quote_data(self):
        """C05-2b: data.quote_data를 참조한다."""
        assert "data.quote_data" in self._get_fn_body()

    def test_not_available_fallback(self):
        """C05-2c: 미연결 시 NOT AVAILABLE 표시."""
        assert "NOT AVAILABLE" in self._get_fn_body()

    def test_displays_bid_ask(self):
        """C05-2d: bid/ask 값을 표시한다."""
        fn_body = self._get_fn_body()
        assert "sq.bid" in fn_body
        assert "sq.ask" in fn_body

    def test_displays_spread(self):
        """C05-2e: spread 값을 표시한다."""
        fn_body = self._get_fn_body()
        assert "sq.spread" in fn_body

    def test_displays_trust_state(self):
        """C05-2f: trust_state 배지를 표시한다."""
        fn_body = self._get_fn_body()
        assert "trust_state" in fn_body

    def test_displays_age(self):
        """C05-2g: age_seconds를 표시한다."""
        fn_body = self._get_fn_body()
        assert "age_seconds" in fn_body

    def test_shows_venue_summary(self):
        """C05-2h: venue_summary를 사용한다."""
        fn_body = self._get_fn_body()
        assert "_venue_summary" in fn_body

    def test_shows_overall_feed_count(self):
        """C05-2i: 전체 LIVE/STALE 카운트를 표시한다."""
        fn_body = self._get_fn_body()
        assert "totalLive" in fn_body
        assert "totalStale" in fn_body

    def test_no_forbidden_strings(self):
        """C05-2j: 금지 문자열이 없다."""
        fn_body = self._get_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in quote feed render"


# ===========================================================================
# C05-3: CSS 스타일
# ===========================================================================
class TestC05CSS:
    """Quote Feed Monitor CSS 검증."""

    def test_venue_row_class(self):
        """C05-3a: .qf-venue-row 클래스가 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".qf-venue-row" in content

    def test_badge_class(self):
        """C05-3b: .qf-badge 클래스가 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".qf-badge" in content

    def test_trust_state_colors(self):
        """C05-3c: LIVE/STALE/DISCONNECTED/UNAVAILABLE 색상 클래스가 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in ['.qf-live', '.qf-stale', '.qf-disconnected', '.qf-unavailable']:
            assert cls in content, f"Color class {cls} must exist"

    def test_symbol_row_class(self):
        """C05-3d: .qf-symbol-row 클래스가 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".qf-symbol-row" in content


# ===========================================================================
# C05-4: Tab 2 통합
# ===========================================================================
class TestC05Integration:
    """Tab 2 통합 및 기존 블록 보존 검증."""

    def test_called_from_render_tab2(self):
        """C05-4a: renderTab2에서 renderQuoteFeedMonitor가 호출된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderQuoteFeedMonitor(data)" in content

    def test_panel_between_loop_and_event_log(self):
        """C05-4b: Quote Feed Monitor가 Loop Ceiling과 Event Log 사이에 위치한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        lc_pos = content.index('id="loop-ceiling-block"')
        qf_pos = content.index('id="quote-feed-block"')
        el_pos = content.index('id="event-log-block"')
        assert lc_pos < qf_pos < el_pos

    def test_existing_blocks_preserved(self):
        """C05-4c: 기존 Tab 2 블록이 보존된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for block_id in ['key-facts-block', 'loop-ceiling-block', 'event-log-block', 'checkpoint-block']:
            assert f'id="{block_id}"' in content, f"Block {block_id} must be preserved"

    def test_existing_ai_workspace_preserved(self):
        """C05-4d: AI Workspace 함수가 보존된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderAIWorkspace" in content

    def test_existing_quote_fields_preserved(self):
        """C05-4e: 기존 renderQuoteFields 함수가 보존된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderQuoteFields" in content
