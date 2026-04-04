"""
Card C-02: Loop Monitor Visibility Enhancement — Tests

검수 범위:
  C02-1: API 필드 확장 (daily/weekly counts, ceilings)
  C02-2: Operator Panel Loop Ceiling Monitor 블록
  C02-3: CSS 게이지 스타일
  C02-4: Tab 2 통합

Card B / C-01 / C-fix 봉인 유지. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy modules (same pattern as test_dashboard.py)
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
_trade_mock.Trade.id = "id"
_trade_mock.Trade.exchange = "exchange"

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
DASHBOARD_ROUTE_PATH = PROJECT_ROOT / "app" / "api" / "routes" / "dashboard.py"


# ===========================================================================
# C02-1: API field expansion
# ===========================================================================
class TestC02APIFields:
    """_get_loop_monitor_info()에 daily/weekly 필드가 추가되었는지 검증."""

    def _get_fn_body(self):
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r'def _get_loop_monitor_info.*?(?=\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_loop_monitor_info not found"
        return fn_match.group()

    def test_daily_count_serialized(self):
        """C02-1a: daily_count 필드가 직렬화에 포함된다."""
        assert '"daily_count"' in self._get_fn_body()

    def test_daily_ceiling_serialized(self):
        """C02-1b: daily_ceiling 필드가 직렬화에 포함된다."""
        assert '"daily_ceiling"' in self._get_fn_body()

    def test_weekly_count_serialized(self):
        """C02-1c: weekly_count 필드가 직렬화에 포함된다."""
        assert '"weekly_count"' in self._get_fn_body()

    def test_weekly_ceiling_serialized(self):
        """C02-1d: weekly_ceiling 필드가 직렬화에 포함된다."""
        assert '"weekly_ceiling"' in self._get_fn_body()

    def test_existing_fields_preserved(self):
        """C02-1e: 기존 필드(health, max_usage_ratio, incident_count, incident_ceiling)가 보존된다."""
        fn_body = self._get_fn_body()
        for field in ['"health"', '"max_usage_ratio"', '"incident_count"', '"incident_ceiling"']:
            assert field in fn_body, f"Existing field {field} must be preserved"

    def test_fail_closed_uses_hasattr(self):
        """C02-1f: daily/weekly 필드 접근 시 hasattr 안전 검사를 사용한다."""
        fn_body = self._get_fn_body()
        assert 'hasattr(status, "daily_count")' in fn_body
        assert 'hasattr(status, "weekly_count")' in fn_body

    def test_no_forbidden_fields(self):
        """C02-1g: 금지 필드가 API 헬퍼에 포함되지 않는다."""
        fn_body = self._get_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden field '{f}' in loop monitor helper"


# ===========================================================================
# C02-2: Operator Panel block
# ===========================================================================
class TestC02OperatorPanel:
    """Tab 2 좌측 Operator Workspace에 Loop Ceiling Monitor 블록 검증."""

    def test_loop_ceiling_body_element_exists(self):
        """C02-2a: loop-ceiling-body 요소가 템플릿에 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="loop-ceiling-body"' in content

    def test_loop_ceiling_block_exists(self):
        """C02-2b: loop-ceiling-block 요소가 템플릿에 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="loop-ceiling-block"' in content

    def test_render_function_exists(self):
        """C02-2c: renderLoopCeilingMonitor 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderLoopCeilingMonitor" in content

    def test_references_data_loop_monitor(self):
        """C02-2d: 렌더 함수가 data.loop_monitor를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderLoopCeilingMonitor")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        assert "data.loop_monitor" in fn_body

    def test_four_loop_names_referenced(self):
        """C02-2e: 4개 루프 이름이 참조된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderLoopCeilingMonitor")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        for name in ['RECOVERY', 'MAIN', 'SELF_IMPROVEMENT', 'EVOLUTION']:
            assert name in fn_body, f"Loop name {name} must be referenced"

    def test_not_available_fallback(self):
        """C02-2f: 미연결 시 NOT AVAILABLE 표시."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderLoopCeilingMonitor")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        assert "NOT AVAILABLE" in fn_body

    def test_no_forbidden_strings(self):
        """C02-2g: 렌더 함수에 금지 문자열이 없다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderLoopCeilingMonitor")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in loop ceiling render"

    def test_renders_gauge_bars(self):
        """C02-2h: 게이지 바 요소가 렌더링된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderLoopCeilingMonitor")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        assert "loop-gauge-bar" in fn_body
        assert "loop-gauge-fill" in fn_body

    def test_renders_daily_and_weekly(self):
        """C02-2i: daily/weekly 게이지가 조건부 렌더링된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderLoopCeilingMonitor")
        fn_end = content.index("function renderKeyFacts")
        fn_body = content[fn_start:fn_end]
        assert "daily_ceiling" in fn_body
        assert "weekly_ceiling" in fn_body
        assert "daily_count" in fn_body
        assert "weekly_count" in fn_body


# ===========================================================================
# C02-3: CSS gauge styles
# ===========================================================================
class TestC02GaugeCSS:
    """게이지 바 CSS 클래스 검증."""

    def test_gauge_bar_class(self):
        """C02-3a: .loop-gauge-bar 클래스가 CSS에 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".loop-gauge-bar" in content

    def test_gauge_fill_class(self):
        """C02-3b: .loop-gauge-fill 클래스가 CSS에 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ".loop-gauge-fill" in content

    def test_health_color_classes(self):
        """C02-3c: 4단계 health 색상 클래스가 존재한다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        for cls in ['--healthy', '--warning', '--critical', '--exceeded']:
            assert f".loop-gauge-fill{cls}" in content, f"Color class {cls} must exist"

    def test_exceeded_has_blink(self):
        """C02-3d: EXCEEDED 상태에 blink 애니메이션이 적용된다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        # Find the exceeded rule
        exceeded_idx = content.index(".loop-gauge-fill--exceeded")
        exceeded_section = content[exceeded_idx:exceeded_idx + 200]
        assert "blink" in exceeded_section or "animation" in exceeded_section


# ===========================================================================
# C02-4: Tab 2 integration
# ===========================================================================
class TestC02Integration:
    """Tab 2 통합 및 기존 블록 보존 검증."""

    def test_called_from_render_tab2(self):
        """C02-4a: renderTab2에서 renderLoopCeilingMonitor가 호출된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderLoopCeilingMonitor(data)" in content

    def test_panel_in_tab2_left_section(self):
        """C02-4b: Loop Ceiling Monitor가 Tab 2 좌측(Operator) 섹션에 위치한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        # loop-ceiling-block must appear between key-facts-block and event-log-block
        kf_pos = content.index('id="key-facts-block"')
        lc_pos = content.index('id="loop-ceiling-block"')
        el_pos = content.index('id="event-log-block"')
        assert kf_pos < lc_pos < el_pos, "Loop ceiling block must be between key-facts and event-log"

    def test_existing_tab2_blocks_preserved(self):
        """C02-4c: 기존 Tab 2 블록이 보존된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for block_id in ['key-facts-block', 'event-log-block', 'checkpoint-block']:
            assert f'id="{block_id}"' in content, f"Existing block {block_id} must be preserved"

    def test_ai_workspace_functions_unchanged(self):
        """C02-4d: AI Workspace 함수 이름이 보존된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for fn_name in ['renderConfirmedFacts', 'renderDetectedAnomalies',
                        'renderPossibleCauses', 'renderRiskWarnings',
                        'renderRecommendedChecks']:
            assert f"function {fn_name}" in content, f"{fn_name} must be preserved"

    def test_block_title_correct(self):
        """C02-4e: 블록 타이틀이 'Loop Ceiling Monitor'이다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Loop Ceiling Monitor" in content
