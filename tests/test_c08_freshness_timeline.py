"""
Card C-08: Freshness / Staleness Timeline Visibility — Tests

검수 범위:
  C08-1: API source_freshness 헬퍼
  C08-2: Operator Panel Freshness Timeline 블록
  C08-3: JS 렌더링 함수
  C08-4: CSS 스타일
  C08-5: Tab 2 통합 및 기존 블록 보존
  C08-6: 금지 조항 및 상태 구분 원칙

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


# ===========================================================================
# C08-1: API source_freshness 헬퍼
# ===========================================================================
class TestC08APIHelper:

    def _get_fn_body(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r'def _get_source_freshness_summary.*?(?=\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_source_freshness_summary not found"
        return fn_match.group()

    def test_helper_exists(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "def _get_source_freshness_summary" in content

    def test_v2_returns_source_freshness_key(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"source_freshness"' in content

    def test_returns_sources_list(self):
        assert '"sources"' in self._get_fn_body()

    def test_returns_summary_counts(self):
        fn_body = self._get_fn_body()
        for key in ['"fresh"', '"stale"', '"unknown"', '"disconnected"']:
            assert key in fn_body, f"Summary key {key} must exist"

    def test_returns_polled_at(self):
        assert '"polled_at"' in self._get_fn_body()

    def test_includes_venue_freshness_sources(self):
        assert '"venue:' in self._get_fn_body() or "venue:" in self._get_fn_body()

    def test_includes_quote_feed_sources(self):
        assert '"quote:' in self._get_fn_body() or "quote:" in self._get_fn_body()

    def test_includes_runtime_sources(self):
        fn_body = self._get_fn_body()
        assert '"loop_monitor"' in fn_body
        assert '"work_state"' in fn_body
        assert '"trust_state"' in fn_body
        assert '"doctrine"' in fn_body

    def test_distinguishes_fresh_stale_unknown_disconnected(self):
        """absence ≠ stale ≠ disconnected 구분."""
        fn_body = self._get_fn_body()
        assert '"fresh"' in fn_body
        assert '"stale"' in fn_body
        assert '"unknown"' in fn_body
        assert '"disconnected"' in fn_body

    def test_no_new_db_queries(self):
        """기존 v2_result에서만 집계, 새 DB 쿼리 없음."""
        fn_body = self._get_fn_body()
        assert "await" not in fn_body
        assert "db.execute" not in fn_body


# ===========================================================================
# C08-2: Operator Panel 블록
# ===========================================================================
class TestC08FreshnessBlock:

    def test_block_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="freshness-timeline-block"' in content

    def test_body_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="freshness-timeline-body"' in content

    def test_title_correct(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Freshness Timeline" in content


# ===========================================================================
# C08-3: JS 렌더링 함수
# ===========================================================================
class TestC08RenderFunction:

    def _get_fn_body(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderFreshnessTimeline")
        fn_end = content.index("function renderKeyFacts")
        return content[fn_start:fn_end]

    def test_function_exists(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderFreshnessTimeline" in content

    def test_references_source_freshness(self):
        assert "source_freshness" in self._get_fn_body()

    def test_not_available_fallback(self):
        assert "NOT AVAILABLE" in self._get_fn_body()

    def test_groups_by_source_type(self):
        fn_body = self._get_fn_body()
        assert "source_type" in fn_body
        assert "position_proxy" in fn_body or "Position Proxy" in fn_body

    def test_shows_status_badges(self):
        fn_body = self._get_fn_body()
        assert "FRESH" in fn_body
        assert "STALE" in fn_body
        assert "UNKNOWN" in fn_body
        assert "DISCONNECTED" in fn_body

    def test_shows_timestamp(self):
        assert "last_updated" in self._get_fn_body()

    def test_shows_age(self):
        assert "age_seconds" in self._get_fn_body()

    def test_shows_summary_bar(self):
        assert "ft-summary" in self._get_fn_body()

    def test_no_forbidden_strings(self):
        fn_body = self._get_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in freshness timeline"


# ===========================================================================
# C08-4: CSS
# ===========================================================================
class TestC08CSS:

    def test_source_row_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ft-source-row" in content

    def test_badge_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ft-badge" in content

    def test_status_colors(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in ['.ft-fresh', '.ft-stale', '.ft-disconnected', '.ft-unknown']:
            assert cls in content, f"CSS class {cls} must exist"

    def test_summary_class(self):
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".ft-summary" in content


# ===========================================================================
# C08-5: Tab 2 통합
# ===========================================================================
class TestC08Integration:

    def test_called_from_render_tab2(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderFreshnessTimeline(data)" in content

    def test_block_between_venue_status_and_event_log(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        vs_pos = content.index('id="venue-status-block"')
        ft_pos = content.index('id="freshness-timeline-block"')
        el_pos = content.index('id="event-log-block"')
        assert vs_pos < ft_pos < el_pos

    def test_existing_blocks_preserved(self):
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in ['key-facts-block', 'loop-ceiling-block', 'quote-feed-block',
                     'venue-status-block', 'event-log-block', 'incident-overlay']:
            assert bid in content, f"{bid} must be preserved"

    def test_existing_venue_freshness_preserved(self):
        """기존 venue_freshness API 무변경."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "async def _get_venue_freshness" in content
