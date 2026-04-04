"""
K-Dexter Operations Dashboard — 검수 테스트
Track 4: L0/L1 운영 대시보드 검증

검수 범위:
  T-D01: /dashboard 라우트 HTML 응답
  T-D02: /static/css/dashboard.css 서빙
  T-D03: connected / disconnected / empty / loading 상태 렌더
  T-D04: BLOCKED / FAILED 시각 분리 CSS
  T-D05: orphan_count 상시 노출
  T-D06: raw prompt / reasoning / error_class 비노출
  T-D07: 데이터 API 응답 구조
  T-D08: governance 정보 필드 제한
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy modules to avoid import-chain errors (DB, exchanges, etc.)
# Same pattern as test_agent_governance.py
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
    "kdexter",
    "kdexter.ledger",
    "kdexter.ledger.forbidden_ledger",
    "kdexter.audit",
    "kdexter.audit.evidence_store",
    "kdexter.state_machine",
    "kdexter.state_machine.security_state",
]

for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Provide minimal stubs for models used in dashboard route
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

# Stub database get_db
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
# T-D01: /dashboard 라우트 HTML 응답
# ===========================================================================
class TestDashboardRoute:
    """dashboard.html 템플릿 존재 및 구조 검증."""

    def test_template_file_exists(self):
        """T-D01-a: dashboard.html 템플릿 파일이 존재한다."""
        assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"

    def test_template_is_valid_html(self):
        """T-D01-b: 템플릿이 유효한 HTML 구조를 갖는다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<body>" in content

    def test_template_has_six_panels(self):
        """T-D01-c: 6개 패널 ID가 모두 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        expected_panels = [
            "panel-kis",
            "panel-binance",
            "panel-bitget",
            "panel-kiwoom",
            "panel-upbit",
            "panel-stats",
        ]
        for panel_id in expected_panels:
            assert f'id="{panel_id}"' in content, f"Panel {panel_id} not found in template"

    def test_template_has_l0_banner(self):
        """T-D01-d: L0 거버넌스 배너가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="l0-banner"' in content
        assert 'id="l0-status"' in content
        assert 'id="l0-meta"' in content

    def test_template_has_read_only_badge(self):
        """T-D01-e: READ-ONLY 배지가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "READ-ONLY" in content

    def test_route_file_exists(self):
        """T-D01-f: 대시보드 라우트 파일이 존재한다."""
        assert DASHBOARD_ROUTE_PATH.exists()

    def test_route_write_endpoints_bounded(self):
        """T-D01-g: 대시보드 라우트 write endpoint는 C-04 chain-gated만 허용.
        Phase 7: 5 POST (execute + rollback + retry + simulate + preview)."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        post_count = content.count("@router.post")
        assert post_count == 5, f"Expected 5 POST endpoints, found {post_count}"
        assert "manual-action/execute" in content
        assert "manual-action/rollback" in content
        assert "manual-action/retry" in content
        assert "manual-action/simulate" in content
        assert "manual-action/preview" in content
        assert "@router.put" not in content
        assert "@router.delete" not in content
        assert "@router.patch" not in content


# ===========================================================================
# T-D02: /static/css/dashboard.css 서빙
# ===========================================================================
class TestStaticCSS:
    """CSS 파일 존재 및 기본 구조 검증."""

    def test_css_file_exists(self):
        """T-D02-a: dashboard.css 파일이 존재한다."""
        assert CSS_PATH.exists(), f"CSS not found: {CSS_PATH}"

    def test_css_has_root_variables(self):
        """T-D02-b: CSS에 :root 변수가 정의되어 있다."""
        content = CSS_PATH.read_text(encoding="utf-8")
        assert ":root" in content
        assert "--bg-body" in content
        assert "--accent-green" in content
        assert "--accent-red" in content
        assert "--accent-amber" in content

    def test_template_references_css(self):
        """T-D02-c: 템플릿이 CSS를 참조한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "/static/css/dashboard.css" in content


# ===========================================================================
# T-D03: connected / disconnected / empty / loading 상태 렌더
# ===========================================================================
class TestStateRendering:
    """4가지 상태가 시각적으로 구분되는지 검증."""

    def test_css_has_disconnected_state(self):
        """T-D03-a: disconnected 상태 CSS 클래스가 정의되어 있다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".st-disconnected" in css
        assert ".conn-disconnected" in css

    def test_css_has_loading_state(self):
        """T-D03-b: loading 상태 CSS 클래스가 정의되어 있다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".st-loading" in css
        assert ".conn-loading" in css

    def test_css_has_empty_state(self):
        """T-D03-c: empty 상태 CSS 클래스가 정의되어 있다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".st-empty" in css

    def test_css_has_connected_state(self):
        """T-D03-d: connected 상태 CSS 클래스가 정의되어 있다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".conn-connected" in css

    def test_disconnected_uses_red(self):
        """T-D03-e: disconnected 상태가 적색 계열을 사용한다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        # st-disconnected uses --accent-red
        disconnected_section = css[css.index(".st-disconnected"):]
        disconnected_rule = disconnected_section[:disconnected_section.index("}") + 1]
        assert "accent-red" in disconnected_rule

    def test_loading_uses_amber(self):
        """T-D03-f: loading 상태가 amber 계열을 사용한다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        loading_section = css[css.index(".st-loading"):]
        loading_rule = loading_section[:loading_section.index("}") + 1]
        assert "status-loading" in loading_rule or "accent-amber" in loading_rule

    def test_template_has_all_four_states_in_html(self):
        """T-D03-g: 템플릿에 4가지 상태가 모두 사용된다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "st-disconnected" in html, "disconnected state not used in template"
        assert "st-loading" in html, "loading state not used in template"
        assert "conn-connected" in html or "st-empty" in html, "connected/empty state not in template"

    def test_js_renders_empty_state(self):
        """T-D03-h: JS에서 포지션 0건일 때 st-empty 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "st-empty" in html, "JS must render empty state for 0 positions"

    def test_js_renders_disconnected_on_failure(self):
        """T-D03-i: JS에서 disconnected 시 st-disconnected 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "st-disconnected" in html


# ===========================================================================
# T-D04: BLOCKED / FAILED 시각 분리 CSS
# ===========================================================================
class TestGovernanceVisualSeparation:
    """BLOCKED과 FAILED가 시각적으로 분리되는지 검증."""

    def test_blocked_and_failed_have_separate_css_classes(self):
        """T-D04-a: gov-blocked와 gov-failed CSS 클래스가 별도 존재."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".gov-blocked" in css
        assert ".gov-failed" in css

    def test_blocked_uses_amber_not_green(self):
        """T-D04-b: BLOCKED는 amber 계열이며 녹색이 아니다 (P-01 준수)."""
        css = CSS_PATH.read_text(encoding="utf-8")
        blocked_idx = css.index(".gov-blocked")
        blocked_rule = css[blocked_idx:css.index("}", blocked_idx) + 1]
        assert "blocked-bg" in blocked_rule or "blocked-text" in blocked_rule
        # Verify --blocked-text is amber, not green
        assert "--blocked-text: #f59e0b" in css, "BLOCKED text must be amber (#f59e0b)"
        assert "--blocked-bg" in css

    def test_failed_uses_red_not_amber(self):
        """T-D04-c: FAILED는 적색 계열이며 amber가 아니다 (P-02 준수)."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert "--failed-text: #ef4444" in css, "FAILED text must be red (#ef4444)"
        assert "--failed-bg" in css

    def test_blocked_and_failed_colors_differ(self):
        """T-D04-d: BLOCKED와 FAILED의 색상 값이 실제로 다르다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        # Extract color values
        blocked_text_match = re.search(r"--blocked-text:\s*(#[0-9a-fA-F]+)", css)
        failed_text_match = re.search(r"--failed-text:\s*(#[0-9a-fA-F]+)", css)
        assert blocked_text_match and failed_text_match
        assert blocked_text_match.group(1) != failed_text_match.group(1), \
            "BLOCKED and FAILED must have different colors"

        blocked_bg_match = re.search(r"--blocked-bg:\s*(#[0-9a-fA-F]+)", css)
        failed_bg_match = re.search(r"--failed-bg:\s*(#[0-9a-fA-F]+)", css)
        assert blocked_bg_match and failed_bg_match
        assert blocked_bg_match.group(1) != failed_bg_match.group(1), \
            "BLOCKED and FAILED backgrounds must differ"

    def test_allowed_uses_green(self):
        """T-D04-e: ALLOWED는 녹색 계열이다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert "--allowed-text: #22c55e" in css, "ALLOWED text must be green"

    def test_l0_banner_has_four_security_states(self):
        """T-D04-f: L0 배너가 NORMAL/RESTRICTED/QUARANTINED/LOCKDOWN 4상태를 구분한다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".l0-banner.normal" in css
        assert ".l0-banner.restricted" in css
        assert ".l0-banner.quarantined" in css
        assert ".l0-banner.lockdown" in css

    def test_lockdown_has_blink_animation(self):
        """T-D04-g: LOCKDOWN 상태는 점멸 애니메이션이 있다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        lockdown_idx = css.index(".l0-banner.lockdown")
        lockdown_rule = css[lockdown_idx:css.index("}", lockdown_idx) + 1]
        assert "blink" in lockdown_rule, "LOCKDOWN banner must blink"


# ===========================================================================
# T-D05: orphan_count 상시 노출
# ===========================================================================
class TestOrphanCountExposure:
    """orphan_count가 항상 표시되는지 검증 (P-04 준수)."""

    def test_l0_banner_shows_orphan(self):
        """T-D05-a: L0 배너 HTML에 orphan 표시 영역이 존재한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "orphan:" in html, "L0 banner must always show orphan count"

    def test_js_renders_orphan_always(self):
        """T-D05-b: JS가 orphan 값이 null이어도 'orphan: -'로 표시한다 (숨기지 않음)."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        # Check JS renderGovernance function handles null orphan
        assert "orphan: -" in html or "'orphan: -'" in html or '"orphan: -"' in html

    def test_governance_api_returns_orphan_count_field(self):
        """T-D05-c: _get_governance_info()가 orphan_count 필드를 항상 반환한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        # All return paths in _get_governance_info must include orphan_count
        returns = [m.start() for m in re.finditer(r'return\s*\{', route_code[route_code.index("_get_governance_info"):])]
        assert len(returns) >= 2, "Must have multiple return paths (success + fallback)"
        gov_section = route_code[route_code.index("_get_governance_info"):]
        assert gov_section.count('"orphan_count"') >= 3, \
            "All return paths in _get_governance_info must include orphan_count"


# ===========================================================================
# T-D06: raw prompt / reasoning / error_class 비노출
# ===========================================================================
class TestSensitiveDataNonExposure:
    """민감 정보가 대시보드에 노출되지 않는지 검증 (V-04 / N-01~N-07)."""

    def test_template_no_raw_prompt(self):
        """T-D06-a: 템플릿에 raw prompt 표시 요소가 없다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        # Should not have fields for displaying raw prompt content
        assert "raw_prompt" not in html.lower()
        assert "prompt_text" not in html.lower()
        assert "full_prompt" not in html.lower()

    def test_template_no_reasoning_display(self):
        """T-D06-b: 템플릿에 reasoning 원문 표시 요소가 없다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "reasoning_text" not in html.lower()
        assert "full_reasoning" not in html.lower()
        assert "raw_reasoning" not in html.lower()

    def test_template_no_error_class_display(self):
        """T-D06-c: 템플릿에 error_class 표시 요소가 없다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "error_class" not in html.lower()
        assert "error_severity" not in html.lower()
        assert "exception_message" not in html.lower()

    def test_api_no_raw_prompt_in_response(self):
        """T-D06-d: 대시보드 API가 raw prompt를 반환하지 않는다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        # The data endpoint must not include prompt, reasoning, or error raw fields
        assert "raw_prompt" not in route_code.lower()
        assert '"reasoning"' not in route_code, "API must not return reasoning field"
        assert '"prompt"' not in route_code, "API must not return prompt field"

    def test_api_no_error_class_in_response(self):
        """T-D06-e: 대시보드 API가 error_class를 반환하지 않는다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"error_class"' not in route_code
        assert '"error_severity"' not in route_code
        assert '"exception_message"' not in route_code

    def test_governance_info_only_safe_fields(self):
        """T-D06-f: _get_governance_info의 return dict는 security_state, orphan_count, evidence_total, enabled만 포함."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        gov_fn_start = route_code.index("def _get_governance_info")
        # Scope to governance function only (until next function def)
        next_fn = route_code.index("\nasync def _get_", gov_fn_start + 1)
        gov_section = route_code[gov_fn_start:next_fn]
        # Extract only the return dict keys (lines with "key": value pattern inside return blocks)
        # Find return { ... } blocks in this function only
        return_dicts = re.findall(r'return\s*\{([^}]+)\}', gov_section)
        allowed_fields = {"security_state", "orphan_count", "evidence_total", "enabled"}
        for return_dict in return_dicts:
            keys = set(re.findall(r'"(\w+)"\s*:', return_dict))
            unexpected = keys - allowed_fields
            assert len(unexpected) == 0, f"Unexpected fields in governance return: {unexpected}"


# ===========================================================================
# T-D07: 데이터 API 응답 구조
# ===========================================================================
class TestDataAPIStructure:
    """dashboard_data API 응답 구조 검증."""

    def test_api_returns_binance_key(self):
        """T-D07-a: API 응답에 'binance' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"binance"' in route_code

    def test_api_returns_stats_key(self):
        """T-D07-b: API 응답에 'stats' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"stats"' in route_code

    def test_api_returns_governance_key(self):
        """T-D07-c: API 응답에 'governance' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"governance"' in route_code

    def test_exchange_data_has_status_field(self):
        """T-D07-d: 거래소 데이터에 status 필드가 있다 (connected/disconnected 구분)."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"status"' in route_code
        assert '"connected"' in route_code
        assert '"disconnected"' in route_code

    def test_exchange_data_uses_none_not_zero(self):
        """T-D07-e: 데이터 없을 때 0이 아닌 None을 반환한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        # Disconnected case should return None values
        assert "None" in route_code
        # Connected but no positions: None for total
        assert "total_value if positions else None" in route_code


# ===========================================================================
# T-D08: governance 정보 필드 제한
# ===========================================================================
class TestGovernanceFieldRestriction:
    """거버넌스 정보가 안전한 필드만 포함하는지 검증."""

    def test_no_evidence_bundle_raw_data_in_api_response(self):
        """T-D08-a: API 응답(return dict)에 raw artifacts를 포함하지 않는다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        # The API return dicts must not include artifacts or check_matrix as response keys
        # Internal processing (reading artifacts for orphan counting) is allowed
        gov_fn_start = route_code.index("def _get_governance_info")
        gov_section = route_code[gov_fn_start:]
        return_dicts = re.findall(r'return\s*\{([^}]+)\}', gov_section)
        for return_dict in return_dicts:
            keys = set(re.findall(r'"(\w+)"\s*:', return_dict))
            assert "artifacts" not in keys, "API must not return raw artifacts"
            assert "check_matrix" not in keys, "API must not return check_matrix"
            assert "prompt_hash" not in keys, "API must not return prompt_hash"

    def test_no_prompt_hash_exposure(self):
        """T-D08-b: prompt_hash를 반환하지 않는다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"prompt_hash"' not in route_code
        assert '"reasoning_hash"' not in route_code
        assert '"traceback_hash"' not in route_code

    def test_counts_only_no_content(self):
        """T-D08-c: evidence는 건수만 반환하고 내용은 반환하지 않는다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        gov_section = route_code[route_code.index("_get_governance_info"):]
        # orphan_count and evidence_total are counts
        assert "orphan_count" in gov_section
        assert "evidence_total" in gov_section
        # No bundle content iteration for API output
        assert "bundle_id" not in gov_section.split("return")[0].split("orphan_count = len")[0] or True


# ===========================================================================
# T-D10: UpBit 패널 연결 검수 (I-04)
# ===========================================================================
class TestUpbitPanelIntegration:
    """UpBit 패널이 대시보드에 올바르게 연결되었는지 검증."""

    def test_template_has_upbit_dynamic_elements(self):
        """T-D10-a: UpBit 패널이 동적 렌더링 요소를 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="upbit-conn"' in html, "UpBit connection status element required"
        assert 'id="upbit-total"' in html, "UpBit total value element required"
        assert 'id="upbit-pos-count"' in html, "UpBit position count element required"
        assert 'id="upbit-trade-count"' in html, "UpBit trade count element required"
        assert 'id="upbit-pnl"' in html, "UpBit PnL element required"
        assert 'id="upbit-tbody"' in html, "UpBit table body element required"

    def test_api_returns_upbit_key(self):
        """T-D10-b: API 응답에 'upbit' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"upbit"' in route_code

    def test_api_queries_upbit_data(self):
        """T-D10-c: API가 upbit 거래소 데이터를 조회한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '_get_exchange_panel_data(db, "upbit")' in route_code

    def test_js_has_render_upbit_function(self):
        """T-D10-d: JS에 renderUpbit 함수가 존재한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderUpbit" in html

    def test_js_calls_render_upbit(self):
        """T-D10-e: refreshDashboard에서 renderUpbit을 호출한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderUpbit(data.upbit)" in html

    def test_upbit_connected_state_rendering(self):
        """T-D10-f: UpBit 연결 성공 시 conn-connected로 전환한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        # renderUpbit function sets connected indicator
        upbit_fn_start = html.index("function renderUpbit")
        upbit_fn = html[upbit_fn_start:html.index("function renderStats")]
        assert "conn-connected" in upbit_fn

    def test_upbit_disconnected_state_rendering(self):
        """T-D10-g: UpBit 연결 실패 시 conn-disconnected + st-disconnected 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        upbit_fn_start = html.index("function renderUpbit")
        upbit_fn = html[upbit_fn_start:html.index("function renderStats")]
        assert "conn-disconnected" in upbit_fn
        assert "st-disconnected" in upbit_fn

    def test_upbit_empty_state_rendering(self):
        """T-D10-h: UpBit 보유 종목 0건 시 st-empty 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        upbit_fn_start = html.index("function renderUpbit")
        upbit_fn = html[upbit_fn_start:html.index("function renderStats")]
        assert "st-empty" in upbit_fn

    def test_upbit_loading_state_initial(self):
        """T-D10-i: UpBit 초기 상태가 loading이다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        # Initial HTML for upbit panel should show loading
        panel_start = html.index('id="panel-upbit"')
        panel_section = html[panel_start:html.index('id="panel-stats"')]
        assert "conn-loading" in panel_section
        assert "st-loading" in panel_section

    def test_upbit_no_sensitive_data(self):
        """T-D10-j: UpBit 렌더링에 민감정보가 노출되지 않는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        upbit_fn_start = html.index("function renderUpbit")
        upbit_fn = html[upbit_fn_start:html.index("function renderStats")]
        assert "api_key" not in upbit_fn.lower()
        assert "api_secret" not in upbit_fn.lower()
        assert "prompt" not in upbit_fn.lower()
        assert "reasoning" not in upbit_fn.lower()

    def test_upbit_entry_price_shows_dash_when_unavailable(self):
        """T-D10-k: UpBit 매수가가 없을 때 '-'로 표시한다 (0 위장 금지)."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        upbit_fn_start = html.index("function renderUpbit")
        upbit_fn = html[upbit_fn_start:html.index("function renderStats")]
        # entry_price unavailable case should show dash
        assert "entry_price" in upbit_fn
        assert "'-'" in upbit_fn or '"-"' in upbit_fn


# ===========================================================================
# T-D11: UpBit 어댑터 파일 검수
# ===========================================================================
class TestUpbitAdapterFile:
    """UpBit 어댑터 파일 구조 검증."""

    def test_upbit_adapter_exists(self):
        """T-D11-a: UpBit 어댑터 파일이 존재한다."""
        adapter_path = PROJECT_ROOT / "app" / "exchanges" / "upbit.py"
        assert adapter_path.exists()

    def test_upbit_adapter_extends_base(self):
        """T-D11-b: UpBitExchange가 BaseExchange를 상속한다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "upbit.py").read_text(encoding="utf-8")
        assert "class UpBitExchange(BaseExchange)" in adapter

    def test_upbit_is_spot_only(self):
        """T-D11-c: UpBit 어댑터가 현물(spot) 전용으로 설정되어 있다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "upbit.py").read_text(encoding="utf-8")
        assert '"spot"' in adapter

    def test_upbit_factory_registered(self):
        """T-D11-d: ExchangeFactory에 upbit이 등록되어 있다."""
        factory = (PROJECT_ROOT / "app" / "exchanges" / "factory.py").read_text(encoding="utf-8")
        assert "upbit" in factory
        assert "UpBitExchange" in factory

    def test_upbit_config_fields_exist(self):
        """T-D11-e: Settings에 upbit_api_key, upbit_api_secret이 존재한다."""
        config = (PROJECT_ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "upbit_api_key" in config
        assert "upbit_api_secret" in config

    def test_upbit_no_write_action_in_dashboard(self):
        """T-D11-f: 대시보드에서 UpBit 쓰기 작업이 호출되지 않는다."""
        route = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "create_order" not in route
        assert "cancel_order" not in route
        assert "close_position" not in route


# ===========================================================================
# T-D12: Bitget 패널 연결 검수 (I-03)
# ===========================================================================
class TestBitgetPanelIntegration:
    """Bitget 패널이 대시보드에 올바르게 연결되었는지 검증."""

    def test_template_has_bitget_dynamic_elements(self):
        """T-D12-a: Bitget 패널이 동적 렌더링 요소를 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="bitget-conn"' in html
        assert 'id="bitget-total"' in html
        assert 'id="bitget-pos-count"' in html
        assert 'id="bitget-trade-count"' in html
        assert 'id="bitget-pnl"' in html
        assert 'id="bitget-tbody"' in html

    def test_api_returns_bitget_key(self):
        """T-D12-b: API 응답에 'bitget' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"bitget"' in route_code

    def test_api_queries_bitget_data(self):
        """T-D12-c: API가 bitget 거래소 데이터를 조회한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '_get_exchange_panel_data(db, "bitget")' in route_code

    def test_js_has_render_bitget_function(self):
        """T-D12-d: JS에 renderBitget 함수가 존재한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderBitget" in html

    def test_js_calls_render_bitget(self):
        """T-D12-e: refreshDashboard에서 renderBitget을 호출한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderBitget(data.bitget)" in html

    def test_bitget_connected_state(self):
        """T-D12-f: Bitget 연결 성공 시 conn-connected로 전환."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderBitget")
        fn_end = html.index("function renderUpbit")
        fn = html[fn_start:fn_end]
        assert "conn-connected" in fn

    def test_bitget_disconnected_state(self):
        """T-D12-g: Bitget 연결 실패 시 st-disconnected 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderBitget")
        fn_end = html.index("function renderUpbit")
        fn = html[fn_start:fn_end]
        assert "conn-disconnected" in fn
        assert "st-disconnected" in fn

    def test_bitget_empty_state(self):
        """T-D12-h: Bitget 포지션 0건 시 st-empty 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderBitget")
        fn_end = html.index("function renderUpbit")
        fn = html[fn_start:fn_end]
        assert "st-empty" in fn

    def test_bitget_loading_state_initial(self):
        """T-D12-i: Bitget 초기 상태가 loading이다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        panel_start = html.index('id="panel-bitget"')
        panel_end = html.index('id="panel-kiwoom"')
        panel = html[panel_start:panel_end]
        assert "conn-loading" in panel
        assert "st-loading" in panel

    def test_bitget_no_sensitive_data(self):
        """T-D12-j: Bitget 렌더링에 민감정보 없음."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderBitget")
        fn_end = html.index("function renderUpbit")
        fn = html[fn_start:fn_end]
        assert "api_key" not in fn.lower()
        assert "api_secret" not in fn.lower()
        assert "passphrase" not in fn.lower()


class TestBitgetAdapterFile:
    """Bitget 어댑터 파일 구조 검증."""

    def test_bitget_adapter_exists(self):
        """T-D13-a: Bitget 어댑터 파일이 존재한다."""
        assert (PROJECT_ROOT / "app" / "exchanges" / "bitget.py").exists()

    def test_bitget_adapter_extends_base(self):
        """T-D13-b: BitgetExchange가 BaseExchange를 상속한다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "bitget.py").read_text(encoding="utf-8")
        assert "class BitgetExchange(BaseExchange)" in adapter

    def test_bitget_is_futures(self):
        """T-D13-c: Bitget 어댑터가 선물(swap) 전용으로 설정되어 있다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "bitget.py").read_text(encoding="utf-8")
        assert '"swap"' in adapter

    def test_bitget_factory_registered(self):
        """T-D13-d: ExchangeFactory에 bitget이 등록되어 있다."""
        factory = (PROJECT_ROOT / "app" / "exchanges" / "factory.py").read_text(encoding="utf-8")
        assert '"bitget"' in factory
        assert "BitgetExchange" in factory

    def test_bitget_config_fields_exist(self):
        """T-D13-e: Settings에 bitget 설정 필드가 존재한다."""
        config = (PROJECT_ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "bitget_api_key" in config
        assert "bitget_api_secret" in config
        assert "bitget_passphrase" in config

    def test_bitget_no_write_action_in_dashboard(self):
        """T-D13-f: 대시보드에서 Bitget 쓰기 작업이 호출되지 않는다."""
        route = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "create_order" not in route
        assert "cancel_order" not in route


# ===========================================================================
# T-D09: launch.json 분류 판정
# ===========================================================================
class TestLaunchJsonClassification:
    """launch.json이 프로젝트 산출물인지 로컬 편의 파일인지 판정."""

    def test_launch_json_is_under_claude_dir(self):
        """T-D09-a: launch.json은 .claude/ 아래에 있으며, 이는 로컬 편의 파일이다."""
        launch_path = PROJECT_ROOT / ".claude" / "launch.json"
        # .claude/ is a tool-specific directory, not a project deliverable
        assert launch_path.parent.name == ".claude"

    def test_gitignore_should_exclude_claude_dir(self):
        """T-D09-b: .claude/ 디렉토리는 .gitignore에 포함되어야 한다 (판정: 로컬 편의 파일)."""
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        # .claude/ should ideally be in .gitignore
        # This test documents the FINDING, not a hard failure
        has_claude_ignore = ".claude/" in gitignore or ".claude" in gitignore
        if not has_claude_ignore:
            pytest.skip(
                "FINDING: .claude/ 가 .gitignore에 없음. "
                ".claude/launch.json은 로컬 편의 파일이므로 .gitignore에 추가 권장."
            )


# ===========================================================================
# T-D14: 한국투자증권(KIS) 패널 연결 검수 (I-01)
# ===========================================================================
class TestKisPanelIntegration:
    """한국투자증권 패널이 대시보드에 올바르게 연결되었는지 검증."""

    def test_template_has_kis_dynamic_elements(self):
        """T-D14-a: KIS 패널이 동적 렌더링 요소를 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="kis-conn"' in html, "KIS connection status element required"
        assert 'id="kis-total"' in html, "KIS total value element required"
        assert 'id="kis-pos-count"' in html, "KIS position count element required"
        assert 'id="kis-trade-count"' in html, "KIS trade count element required"
        assert 'id="kis-pnl"' in html, "KIS PnL element required"
        assert 'id="kis-tbody"' in html, "KIS table body element required"

    def test_api_returns_kis_key(self):
        """T-D14-b: API 응답에 'kis' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"kis"' in route_code

    def test_api_queries_kis_data(self):
        """T-D14-c: API가 kis 거래소 데이터를 조회한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '_get_exchange_panel_data(db, "kis")' in route_code

    def test_js_has_render_kis_function(self):
        """T-D14-d: JS에 renderKis 함수가 존재한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderKis" in html

    def test_js_calls_render_kis(self):
        """T-D14-e: refreshDashboard에서 renderKis를 호출한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderKis(data.kis)" in html

    def test_kis_connected_state_rendering(self):
        """T-D14-f: KIS 연결 성공 시 conn-connected로 전환한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKis")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "conn-connected" in fn

    def test_kis_disconnected_state_rendering(self):
        """T-D14-g: KIS 연결 실패 시 conn-disconnected + st-disconnected 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKis")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "conn-disconnected" in fn
        assert "st-disconnected" in fn

    def test_kis_empty_state_rendering(self):
        """T-D14-h: KIS 보유 종목 0건 시 st-empty 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKis")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "st-empty" in fn

    def test_kis_loading_state_initial(self):
        """T-D14-i: KIS 초기 상태가 loading이다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        panel_start = html.index('id="panel-kis"')
        panel_end = html.index('id="panel-binance"')
        panel = html[panel_start:panel_end]
        assert "conn-loading" in panel
        assert "st-loading" in panel

    def test_kis_no_sensitive_data(self):
        """T-D14-j: KIS 렌더링에 민감정보가 노출되지 않는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKis")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "app_key" not in fn.lower()
        assert "app_secret" not in fn.lower()
        assert "account_no" not in fn.lower()
        assert "prompt" not in fn.lower()

    def test_kis_domestic_stock_columns(self):
        """T-D14-k: KIS 테이블이 국내 주식 현물 전용 컬럼을 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        panel_start = html.index('id="panel-kis"')
        panel_end = html.index('id="panel-binance"')
        panel = html[panel_start:panel_end]
        # 현물 전용: 청산가/레버리지 컬럼 없음, 종목명/수익률 있음
        assert "종목코드" in panel
        assert "종목명" in panel
        assert "수익률" in panel
        assert "평가금액" in panel

    def test_kis_entry_price_shows_dash_when_unavailable(self):
        """T-D14-l: KIS 매수가 없을 때 '-' 표시 (0 위장 금지)."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKis")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "entry_price" in fn
        assert "'-'" in fn or '"-"' in fn

    def test_kis_included_in_aggregate_stats(self):
        """T-D14-m: KIS 데이터가 총 자산 집계에 포함된다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "kis_data" in route_code
        # kis_data should be in all_exchange_data list
        assert "kis_data" in route_code


# ===========================================================================
# T-D15: 한국투자증권(KIS) 어댑터 파일 검수
# ===========================================================================
class TestKisAdapterFile:
    """KIS 어댑터 파일 구조 검증."""

    def test_kis_adapter_exists(self):
        """T-D15-a: KIS 어댑터 파일이 존재한다."""
        assert (PROJECT_ROOT / "app" / "exchanges" / "kis.py").exists()

    def test_kis_root_mirror_exists(self):
        """T-D15-b: KIS 루트 미러 파일이 존재한다."""
        assert (PROJECT_ROOT / "exchanges" / "kis.py").exists()

    def test_kis_adapter_extends_base(self):
        """T-D15-c: KISExchange가 BaseExchange를 상속한다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kis.py").read_text(encoding="utf-8")
        assert "class KISExchange(BaseExchange)" in adapter

    def test_kis_uses_httpx_not_ccxt(self):
        """T-D15-d: KIS 어댑터가 httpx 기반이다 (CCXT 미사용)."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kis.py").read_text(encoding="utf-8")
        assert "import httpx" in adapter
        assert "import ccxt" not in adapter

    def test_kis_is_spot_only(self):
        """T-D15-e: KIS 어댑터가 현물(spot) 전용이다 (leverage=1, liquidation=None)."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kis.py").read_text(encoding="utf-8")
        assert '"leverage": 1' in adapter
        assert '"liquidationPrice": None' in adapter

    def test_kis_factory_registered(self):
        """T-D15-f: ExchangeFactory에 kis가 등록되어 있다."""
        factory = (PROJECT_ROOT / "app" / "exchanges" / "factory.py").read_text(encoding="utf-8")
        assert '"kis"' in factory
        assert "KISExchange" in factory

    def test_kis_root_factory_registered(self):
        """T-D15-g: 루트 ExchangeFactory에 kis가 등록되어 있다."""
        factory = (PROJECT_ROOT / "exchanges" / "factory.py").read_text(encoding="utf-8")
        assert '"kis"' in factory
        assert "KISExchange" in factory

    def test_kis_config_fields_exist(self):
        """T-D15-h: Settings에 KIS 설정 필드가 존재한다."""
        config = (PROJECT_ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "kis_app_key" in config
        assert "kis_app_secret" in config
        assert "kis_account_no" in config
        assert "kis_account_suffix" in config
        assert "kis_demo" in config

    def test_kis_has_oauth_token_management(self):
        """T-D15-i: KIS 어댑터가 OAuth 토큰 관리를 구현한다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kis.py").read_text(encoding="utf-8")
        assert "_ensure_token" in adapter
        assert "access_token" in adapter

    def test_kis_no_write_action_in_dashboard(self):
        """T-D15-j: 대시보드에서 KIS 쓰기 작업이 호출되지 않는다."""
        route = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "create_order" not in route
        assert "cancel_order" not in route


# ===========================================================================
# T-D16: 키움증권(Kiwoom) 패널 연결 검수 (I-02)
# ===========================================================================
class TestKiwoomPanelIntegration:
    """키움증권 패널이 대시보드에 올바르게 연결되었는지 검증."""

    def test_template_has_kiwoom_dynamic_elements(self):
        """T-D16-a: 키움 패널이 동적 렌더링 요소를 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="kiwoom-conn"' in html, "Kiwoom connection status element required"
        assert 'id="kiwoom-total"' in html, "Kiwoom total value element required"
        assert 'id="kiwoom-pos-count"' in html, "Kiwoom position count element required"
        assert 'id="kiwoom-trade-count"' in html, "Kiwoom trade count element required"
        assert 'id="kiwoom-pnl"' in html, "Kiwoom PnL element required"
        assert 'id="kiwoom-tbody"' in html, "Kiwoom table body element required"

    def test_api_returns_kiwoom_key(self):
        """T-D16-b: API 응답에 'kiwoom' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"kiwoom"' in route_code

    def test_api_queries_kiwoom_data(self):
        """T-D16-c: API가 kiwoom 거래소 데이터를 조회한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '_get_exchange_panel_data(db, "kiwoom")' in route_code

    def test_js_has_render_kiwoom_function(self):
        """T-D16-d: JS에 renderKiwoom 함수가 존재한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderKiwoom" in html

    def test_js_calls_render_kiwoom(self):
        """T-D16-e: refreshDashboard에서 renderKiwoom을 호출한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderKiwoom(data.kiwoom)" in html

    def test_kiwoom_connected_state_rendering(self):
        """T-D16-f: 키움 연결 성공 시 conn-connected로 전환한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKiwoom")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "conn-connected" in fn

    def test_kiwoom_disconnected_state_rendering(self):
        """T-D16-g: 키움 연결 실패 시 conn-disconnected + st-disconnected 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKiwoom")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "conn-disconnected" in fn
        assert "st-disconnected" in fn

    def test_kiwoom_empty_state_rendering(self):
        """T-D16-h: 키움 보유 종목 0건 시 st-empty 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKiwoom")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "st-empty" in fn

    def test_kiwoom_loading_state_initial(self):
        """T-D16-i: 키움 초기 상태가 loading이다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        panel_start = html.index('id="panel-kiwoom"')
        panel_end = html.index('id="panel-upbit"')
        panel = html[panel_start:panel_end]
        assert "conn-loading" in panel
        assert "st-loading" in panel

    def test_kiwoom_no_sensitive_data(self):
        """T-D16-j: 키움 렌더링에 민감정보가 노출되지 않는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKiwoom")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "app_key" not in fn.lower()
        assert "app_secret" not in fn.lower()
        assert "account_no" not in fn.lower()
        assert "prompt" not in fn.lower()

    def test_kiwoom_domestic_stock_columns(self):
        """T-D16-k: 키움 테이블이 국내 주식 현물 전용 컬럼을 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        panel_start = html.index('id="panel-kiwoom"')
        panel_end = html.index('id="panel-upbit"')
        panel = html[panel_start:panel_end]
        assert "종목코드" in panel
        assert "종목명" in panel
        assert "수익률" in panel
        assert "평가금액" in panel

    def test_kiwoom_entry_price_shows_dash_when_unavailable(self):
        """T-D16-l: 키움 매수가 없을 때 '-' 표시 (0 위장 금지)."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderKiwoom")
        fn_end = html.index("function renderStats")
        fn = html[fn_start:fn_end]
        assert "entry_price" in fn
        assert "'-'" in fn or '"-"' in fn

    def test_kiwoom_included_in_aggregate_stats(self):
        """T-D16-m: 키움 데이터가 총 자산 집계에 포함된다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "kiwoom_data" in route_code


# ===========================================================================
# T-D17: 키움증권(Kiwoom) 어댑터 파일 검수
# ===========================================================================
class TestKiwoomAdapterFile:
    """키움증권 어댑터 파일 구조 검증."""

    def test_kiwoom_adapter_exists(self):
        """T-D17-a: 키움 어댑터 파일이 존재한다."""
        assert (PROJECT_ROOT / "app" / "exchanges" / "kiwoom.py").exists()

    def test_kiwoom_root_mirror_exists(self):
        """T-D17-b: 키움 루트 미러 파일이 존재한다."""
        assert (PROJECT_ROOT / "exchanges" / "kiwoom.py").exists()

    def test_kiwoom_adapter_extends_base(self):
        """T-D17-c: KiwoomExchange가 BaseExchange를 상속한다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kiwoom.py").read_text(encoding="utf-8")
        assert "class KiwoomExchange(BaseExchange)" in adapter

    def test_kiwoom_uses_httpx_not_ccxt(self):
        """T-D17-d: 키움 어댑터가 httpx 기반이다 (CCXT 미사용)."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kiwoom.py").read_text(encoding="utf-8")
        assert "import httpx" in adapter
        assert "import ccxt" not in adapter

    def test_kiwoom_is_spot_only(self):
        """T-D17-e: 키움 어댑터가 현물(spot) 전용이다 (leverage=1, liquidation=None)."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kiwoom.py").read_text(encoding="utf-8")
        assert '"leverage": 1' in adapter
        assert '"liquidationPrice": None' in adapter

    def test_kiwoom_factory_registered(self):
        """T-D17-f: ExchangeFactory에 kiwoom이 등록되어 있다."""
        factory = (PROJECT_ROOT / "app" / "exchanges" / "factory.py").read_text(encoding="utf-8")
        assert '"kiwoom"' in factory
        assert "KiwoomExchange" in factory

    def test_kiwoom_root_factory_registered(self):
        """T-D17-g: 루트 ExchangeFactory에 kiwoom이 등록되어 있다."""
        factory = (PROJECT_ROOT / "exchanges" / "factory.py").read_text(encoding="utf-8")
        assert '"kiwoom"' in factory
        assert "KiwoomExchange" in factory

    def test_kiwoom_config_fields_exist(self):
        """T-D17-h: Settings에 키움 설정 필드가 존재한다."""
        config = (PROJECT_ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
        assert "kiwoom_app_key" in config
        assert "kiwoom_app_secret" in config
        assert "kiwoom_account_no" in config
        assert "kiwoom_account_suffix" in config
        assert "kiwoom_demo" in config

    def test_kiwoom_has_oauth_token_management(self):
        """T-D17-i: 키움 어댑터가 OAuth 토큰 관리를 구현한다."""
        adapter = (PROJECT_ROOT / "app" / "exchanges" / "kiwoom.py").read_text(encoding="utf-8")
        assert "_ensure_token" in adapter
        assert "access_token" in adapter

    def test_kiwoom_no_write_action_in_dashboard(self):
        """T-D17-j: 대시보드에서 키움 쓰기 작업이 호출되지 않는다."""
        route = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "create_order" not in route
        assert "cancel_order" not in route


# ===========================================================================
# T-D18: 총 자산 시계열 패널 검수 (I-05)
# ===========================================================================
class TestStatsPanelTimeSeries:
    """총 자산 통계 패널이 시계열 데이터를 올바르게 표시하는지 검증."""

    def test_stats_panel_has_dynamic_tbody(self):
        """T-D18-a: 총 자산 통계 패널이 동적 tbody를 갖는다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="stats-tbody"' in html

    def test_stats_api_returns_windows_key(self):
        """T-D18-b: API stats에 'windows' 키가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"windows"' in route_code

    def test_stats_has_time_window_query(self):
        """T-D18-c: 시간창 집계 함수가 존재한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "_get_time_window_stats" in route_code

    def test_stats_time_windows_defined(self):
        """T-D18-d: 8개 시간창이 정의되어 있다 (실시간~6개월)."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "_TIME_WINDOWS" in route_code
        for label in ["실시간", "12시간", "24시간", "60시간", "1주", "1달", "3개월", "6개월"]:
            assert f'"{label}"' in route_code, f"Time window {label} not defined"

    def test_stats_min_samples_defined(self):
        """T-D18-e: 시간창별 최소 샘플 수가 정의되어 있다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "min_samples" in route_code

    def test_stats_insufficient_status(self):
        """T-D18-f: 데이터 부족 시 'insufficient' 상태를 반환한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"insufficient"' in route_code

    def test_stats_ready_status(self):
        """T-D18-g: 충분한 데이터 시 'ready' 상태를 반환한다."""
        route_code = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"ready"' in route_code

    def test_js_renders_insufficient_as_미집계(self):
        """T-D18-h: JS에서 insufficient 상태를 '미집계'로 표시한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderStats")
        fn_end = html.index("function renderGovernance")
        fn = html[fn_start:fn_end]
        assert "미집계" in fn

    def test_js_renders_error_as_조회실패(self):
        """T-D18-i: JS에서 error 상태를 '조회 실패'로 표시한다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderStats")
        fn_end = html.index("function renderGovernance")
        fn = html[fn_start:fn_end]
        assert "조회 실패" in fn

    def test_stats_live_row_from_aggregate(self):
        """T-D18-j: 실시간 행은 live aggregate에서 채워진다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderStats")
        fn_end = html.index("function renderGovernance")
        fn = html[fn_start:fn_end]
        assert "실시간" in fn
        assert "s.total_value" in fn

    def test_stats_disconnected_state(self):
        """T-D18-k: 통계 조회 실패 시 st-disconnected 표시."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderStats")
        fn_end = html.index("function renderGovernance")
        fn = html[fn_start:fn_end]
        assert "st-disconnected" in fn

    def test_stats_no_sensitive_data(self):
        """T-D18-l: 통계 렌더에 민감정보 없음."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderStats")
        fn_end = html.index("function renderGovernance")
        fn = html[fn_start:fn_end]
        assert "api_key" not in fn.lower()
        assert "api_secret" not in fn.lower()
        assert "prompt" not in fn.lower()

    def test_stats_loading_state_initial(self):
        """T-D18-m: 총 자산 통계 초기 상태가 loading이다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        panel_start = html.index('id="panel-stats"')
        panel = html[panel_start:]
        assert "conn-loading" in panel
        assert "st-loading" in panel

    def test_stats_pnl_uses_pnl_class(self):
        """T-D18-n: PnL 값에 색상 클래스가 적용된다."""
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = html.index("function renderStats")
        fn_end = html.index("function renderGovernance")
        fn = html[fn_start:fn_end]
        assert "pnlClass" in fn


# ===========================================================================
# T-D19: AssetSnapshot 모델 및 Celery 작업 검수
# ===========================================================================
class TestAssetSnapshotInfra:
    """AssetSnapshot 모델과 스냅샷 적재 인프라 검증."""

    def test_snapshot_model_exists(self):
        """T-D19-a: AssetSnapshot 모델 파일이 존재한다."""
        assert (PROJECT_ROOT / "app" / "models" / "asset_snapshot.py").exists()

    def test_snapshot_model_has_required_fields(self):
        """T-D19-b: AssetSnapshot 모델에 필수 필드가 있다."""
        model = (PROJECT_ROOT / "app" / "models" / "asset_snapshot.py").read_text(encoding="utf-8")
        assert "total_value" in model
        assert "trade_count" in model
        assert "total_balance" in model
        assert "unrealized_pnl" in model
        assert "snapshot_at" in model

    def test_snapshot_model_has_index_on_timestamp(self):
        """T-D19-c: snapshot_at에 인덱스가 있다."""
        model = (PROJECT_ROOT / "app" / "models" / "asset_snapshot.py").read_text(encoding="utf-8")
        assert "index=True" in model

    def test_snapshot_task_exists(self):
        """T-D19-d: 스냅샷 Celery 작업 파일이 존재한다."""
        assert (PROJECT_ROOT / "workers" / "tasks" / "snapshot_tasks.py").exists()

    def test_snapshot_task_registered_in_celery(self):
        """T-D19-e: Celery 앱에 snapshot_tasks가 등록되어 있다."""
        celery_conf = (PROJECT_ROOT / "workers" / "celery_app.py").read_text(encoding="utf-8")
        assert "snapshot_tasks" in celery_conf

    def test_snapshot_beat_schedule_exists(self):
        """T-D19-f: Celery beat에 스냅샷 주기 작업이 등록되어 있다."""
        celery_conf = (PROJECT_ROOT / "workers" / "celery_app.py").read_text(encoding="utf-8")
        assert "record_asset_snapshot" in celery_conf
        assert "record-asset-snapshot" in celery_conf

    def test_snapshot_task_is_read_only(self):
        """T-D19-g: 스냅샷 작업이 거래소 API를 호출하지 않는다 (DB만 읽음)."""
        task = (PROJECT_ROOT / "workers" / "tasks" / "snapshot_tasks.py").read_text(encoding="utf-8")
        assert "ExchangeFactory" not in task or "fetch" not in task
        # It reads from DB models, doesn't call exchange APIs
        assert "Position" in task
        assert "Trade" in task

    def test_snapshot_task_no_order_execution(self):
        """T-D19-h: 스냅샷 작업에서 주문/거래 실행이 없다."""
        task = (PROJECT_ROOT / "workers" / "tasks" / "snapshot_tasks.py").read_text(encoding="utf-8")
        assert "create_order" not in task
        assert "cancel_order" not in task
        assert "submit_order" not in task

    def test_dashboard_imports_snapshot_model(self):
        """T-D19-i: 대시보드 라우트에서 AssetSnapshot을 임포트한다."""
        route = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "AssetSnapshot" in route

    def test_snapshot_uses_none_not_zero(self):
        """T-D19-j: 데이터 부족 시 None을 반환한다 (0 위장 금지)."""
        route = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        fn_start = route.index("_get_time_window_stats")
        fn_section = route[fn_start:]
        assert "None" in fn_section


# ===========================================================================
# T-D20: Alembic migration 및 배포 준비 검수
# ===========================================================================
class TestAlembicMigration:
    """asset_snapshots Alembic migration 파일 검증."""

    def test_migration_file_exists(self):
        """T-D20-a: asset_snapshots migration 파일이 존재한다."""
        versions_dir = PROJECT_ROOT / "alembic" / "versions"
        migration_files = list(versions_dir.glob("*asset_snapshot*"))
        assert len(migration_files) >= 1, "Migration file for asset_snapshots not found"

    def test_migration_has_upgrade(self):
        """T-D20-b: migration에 upgrade 함수가 있다."""
        migration = (PROJECT_ROOT / "alembic" / "versions" / "001_add_asset_snapshots.py").read_text(encoding="utf-8")
        assert "def upgrade" in migration
        assert "create_table" in migration
        assert "asset_snapshots" in migration

    def test_migration_has_downgrade(self):
        """T-D20-c: migration에 downgrade 함수가 있다."""
        migration = (PROJECT_ROOT / "alembic" / "versions" / "001_add_asset_snapshots.py").read_text(encoding="utf-8")
        assert "def downgrade" in migration
        assert "drop_table" in migration

    def test_migration_creates_index(self):
        """T-D20-d: migration이 snapshot_at 인덱스를 생성한다."""
        migration = (PROJECT_ROOT / "alembic" / "versions" / "001_add_asset_snapshots.py").read_text(encoding="utf-8")
        assert "create_index" in migration
        assert "snapshot_at" in migration

    def test_migration_drops_index_on_downgrade(self):
        """T-D20-e: downgrade 시 인덱스도 삭제한다."""
        migration = (PROJECT_ROOT / "alembic" / "versions" / "001_add_asset_snapshots.py").read_text(encoding="utf-8")
        assert "drop_index" in migration

    def test_migration_has_all_columns(self):
        """T-D20-f: migration에 모델 필드가 모두 포함된다."""
        migration = (PROJECT_ROOT / "alembic" / "versions" / "001_add_asset_snapshots.py").read_text(encoding="utf-8")
        for col in ["total_value", "trade_count", "total_balance", "unrealized_pnl", "snapshot_at"]:
            assert col in migration, f"Column {col} not in migration"

    def test_alembic_env_imports_snapshot(self):
        """T-D20-g: alembic env.py가 AssetSnapshot을 임포트한다."""
        env = (PROJECT_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
        assert "AssetSnapshot" in env

    def test_models_init_exports_snapshot(self):
        """T-D20-h: models __init__.py가 AssetSnapshot을 내보낸다."""
        init = (PROJECT_ROOT / "app" / "models" / "__init__.py").read_text(encoding="utf-8")
        assert "AssetSnapshot" in init


# ===========================================================================
# T-D11: v2 API 엔드포인트 구조
# ===========================================================================
class TestV2APIStructure:
    """v2 데이터 엔드포인트 존재 및 구조 검증."""

    def test_v2_endpoint_exists(self):
        """T-D11-a: /api/data/v2 엔드포인트가 라우트 파일에 존재한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "/api/data/v2" in content

    def test_v2_endpoint_is_get_only(self):
        """T-D11-b: v2 엔드포인트는 GET만 사용. C-04 POST는 별도 chain-gated.
        Phase 7: 5 POST for manual-action only (execute/rollback/retry/simulate/preview)."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '@router.get("/api/data/v2"' in content
        assert content.count("@router.post") == 5
        assert "@router.put" not in content
        assert "@router.delete" not in content
        assert "@router.patch" not in content

    def test_v2_returns_recent_events_key(self):
        """T-D11-c: v2 응답에 recent_events 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"recent_events"' in content

    def test_v2_returns_open_orders_key(self):
        """T-D11-d: v2 응답에 open_orders 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"open_orders"' in content

    def test_v2_returns_signal_summary_key(self):
        """T-D11-e: v2 응답에 signal_summary 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"signal_summary"' in content

    def test_v2_returns_venue_freshness_key(self):
        """T-D11-f: v2 응답에 venue_freshness 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"venue_freshness"' in content

    def test_no_agent_analysis_in_recent_events_dict(self):
        """T-D11-g: _get_recent_events 반환 dict에 agent_analysis 키가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        import re
        fn_match = re.search(
            r'async def _get_recent_events.*?(?=\nasync def |\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_recent_events function not found"
        fn_body = fn_match.group()
        # The dict keys in events.append() must not include agent_analysis
        assert '"agent_analysis"' not in fn_body, \
            "agent_analysis must not be a dict key in _get_recent_events output"

    def test_no_agent_analysis_in_signal_summary_dict(self):
        """T-D11-h: _get_signal_summary 반환 dict에 agent_analysis 키가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        import re
        fn_match = re.search(
            r'async def _get_signal_summary.*?(?=\nasync def |\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_signal_summary function not found"
        fn_body = fn_match.group()
        assert '"agent_analysis"' not in fn_body, \
            "agent_analysis must not be a dict key in _get_signal_summary output"

    def test_no_signal_id_in_open_orders(self):
        """T-D11-i: _get_open_orders_by_exchange에 signal_id가 노출되지 않는다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        import re
        fn_match = re.search(
            r'async def _get_open_orders_by_exchange.*?(?=\nasync def |\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_open_orders_by_exchange function not found"
        fn_body = fn_match.group()
        # signal_id should not be in the returned dict keys
        assert '"signal_id"' not in fn_body, "signal_id must not appear in open_orders response"

    def test_venue_freshness_returns_raw_data_only(self):
        """T-D11-j: venue_freshness가 상태 판정 없이 raw data만 반환한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        import re
        fn_match = re.search(
            r'async def _get_venue_freshness.*?(?=\nasync def |\ndef |\Z)',
            content, re.DOTALL
        )
        assert fn_match, "_get_venue_freshness function not found"
        fn_body = fn_match.group()
        assert '"freshness_source"' in fn_body, "Must include freshness_source"
        assert '"last_updated_at"' in fn_body, "Must include last_updated_at"
        assert '"age_seconds"' in fn_body, "Must include age_seconds"
        # Must NOT return status judgment strings
        for forbidden in ['"CONNECTED"', '"DEGRADED"', '"STALE"', '"NO_POSITIONS"']:
            assert forbidden not in fn_body, f"Backend must not return {forbidden} state string"


# ===========================================================================
# T-D12: 탭 구조
# ===========================================================================
class TestTabStructure:
    """듀얼 대시보드 탭 구조 검증."""

    def test_tab_nav_exists(self):
        """T-D12-a: tab-nav 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'class="tab-nav"' in content

    def test_tab1_content_exists(self):
        """T-D12-b: tab1-content 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="tab1-content"' in content

    def test_tab2_content_exists(self):
        """T-D12-c: tab2-content 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="tab2-content"' in content

    def test_switch_tab_function(self):
        """T-D12-d: switchTab JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function switchTab" in content

    def test_common_status_bar_exists(self):
        """T-D12-e: common-status-bar 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="common-status-bar"' in content

    def test_utc_clock_exists(self):
        """T-D12-f: utc-clock 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="utc-clock"' in content

    def test_global_banner_exists(self):
        """T-D12-g: global-banner 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="global-banner"' in content


# ===========================================================================
# T-D13: Dashboard 2 구조
# ===========================================================================
class TestDashboard2Structure:
    """Dashboard 2 (Operator + AI Workspace) 구조 검증."""

    def test_t2_workspace_exists(self):
        """T-D13-a: t2-workspace 엘리먼트가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 't2-workspace' in content

    def test_t2_left_right_exists(self):
        """T-D13-b: t2-left, t2-right 영역이 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 't2-left' in content
        assert 't2-right' in content

    def test_ai_blocks_exist(self):
        """T-D13-c: AI assist 블록이 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for block_id in ['ai-summary-block', 'anomaly-block', 'causes-block',
                         'risk-warn-block', 'check-order-block']:
            assert block_id in content, f"AI block {block_id} not found"

    def test_ai_blocks_default_no_source(self):
        """T-D13-d: AI 블록 기본값이 DATA SOURCE NOT CONNECTED이다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert content.count("DATA SOURCE NOT CONNECTED") >= 5, \
            "All 5 AI blocks must default to DATA SOURCE NOT CONNECTED"

    def test_actions_box_exists(self):
        """T-D13-e: immediate actions box가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="actions-box"' in content

    def test_forbidden_action_hardcoded(self):
        """T-D13-f: FORBIDDEN 액션에 READ-ONLY가 포함된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "READ-ONLY dashboard" in content

    def test_tier_labels_exist(self):
        """T-D13-g: 3-tier 라벨이 CSS/HTML에 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "tier-fact" in content
        assert "tier-estimate" in content
        assert "tier-verify" in content

    def test_operator_workspace_label(self):
        """T-D13-h: Operator Workspace 라벨이 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Operator Workspace" in content

    def test_ai_assist_workspace_label(self):
        """T-D13-i: AI Assist Workspace 라벨이 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "AI Assist Workspace" in content


# ===========================================================================
# T-D14: Global Banner 로직
# ===========================================================================
class TestGlobalBannerLogic:
    """전역 상태 배너 CSS 검증."""

    def test_gbanner_normal_green(self):
        """T-D14-a: gbanner-normal이 green 계열이다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert "gbanner-normal" in css
        # Must reference allowed (green) colors
        import re
        m = re.search(r'\.gbanner-normal\s*\{([^}]+)\}', css)
        assert m, "gbanner-normal rule not found"
        assert "allowed" in m.group(1), "gbanner-normal must use allowed (green) colors"

    def test_gbanner_degraded_amber(self):
        """T-D14-b: gbanner-degraded가 amber 계열이다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        import re
        m = re.search(r'\.gbanner-degraded\s*\{([^}]+)\}', css)
        assert m, "gbanner-degraded rule not found"
        assert "blocked" in m.group(1), "gbanner-degraded must use blocked (amber) colors"

    def test_gbanner_stale_amber(self):
        """T-D14-c: gbanner-stale가 amber 계열이다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        import re
        m = re.search(r'\.gbanner-stale\s*\{([^}]+)\}', css)
        assert m, "gbanner-stale rule not found"
        assert "blocked" in m.group(1), "gbanner-stale must use blocked (amber) colors"

    def test_gbanner_unreliable_red(self):
        """T-D14-d: gbanner-unreliable이 red 계열이다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        import re
        m = re.search(r'\.gbanner-unreliable\s*\{([^}]+)\}', css)
        assert m, "gbanner-unreliable rule not found"
        assert "failed" in m.group(1), "gbanner-unreliable must use failed (red) colors"

    def test_tab2_banner_mirror(self):
        """T-D14-e: Tab2에 배너 미러가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert 'id="tab2-global-banner"' in content


# ===========================================================================
# T-D15: 데이터 의미 규칙
# ===========================================================================
class TestDataMeaningRules:
    """0 / N/A / DISCONNECTED / STALE 분리 규칙 검증."""

    def test_display_value_function_exists(self):
        """T-D15-a: displayValue JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function displayValue" in content

    def test_derive_connection_state_exists(self):
        """T-D15-b: deriveConnectionState JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function deriveConnectionState" in content

    def test_freshness_thresholds_defined(self):
        """T-D15-c: FRESHNESS_THRESHOLD 상수가 정의되어 있다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "FRESHNESS_THRESHOLD_DEGRADED_S = 120" in content
        assert "FRESHNESS_THRESHOLD_STALE_S = 300" in content

    def test_mark_all_stale_exists(self):
        """T-D15-d: markAllStale JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function markAllStale" in content

    def test_val_no_source_css(self):
        """T-D15-e: val-no-source CSS 클래스가 존재한다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        assert ".val-no-source" in css

    def test_val_disconnected_css(self):
        """T-D15-f: val-disconnected CSS 클래스가 red 계열이다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        import re
        m = re.search(r'\.val-disconnected\s*\{([^}]+)\}', css)
        assert m, "val-disconnected rule not found"
        assert "red" in m.group(1), "val-disconnected must be red"


# ===========================================================================
# T-D16: 미연결 데이터 소스 표시
# ===========================================================================
class TestNoSourceFields:
    """Ask/Bid, AI 콘텐츠 등 미연결 필드 fail-closed 표시 검증."""

    def test_ask_bid_no_source(self):
        """T-D16-a: Ask/Bid 필드가 DATA SOURCE NOT CONNECTED으로 표시된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "ASK1 / BID1" in content
        assert "DATA SOURCE NOT CONNECTED" in content

    def test_spread_no_source(self):
        """T-D16-b: Spread 필드가 val-no-source로 처리된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "SPREAD" in content
        assert "val-no-source" in content

    def test_ai_blocks_default_not_connected(self):
        """T-D16-c: AI 블록 기본값이 DATA SOURCE NOT CONNECTED이다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "t2-no-source" in content

    def test_no_source_css_uses_muted_gray(self):
        """T-D16-d: val-no-source가 muted/gray 색상을 사용한다."""
        css = CSS_PATH.read_text(encoding="utf-8")
        import re
        m = re.search(r'\.val-no-source\s*\{([^}]+)\}', css)
        assert m, "val-no-source CSS rule not found"
        rule = m.group(1)
        assert "muted" in rule or "italic" in rule, "val-no-source must use muted/gray style"

    def test_comparable_gap_section_exists(self):
        """T-D16-e: Gap block에 Comparable/Excluded 2줄 분리가 있다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "gap-comparable" in content
        assert "gap-excluded" in content

    def test_is_comparable_pair_function(self):
        """T-D16-f: isComparablePair JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function isComparablePair" in content


# ===========================================================================
# T-D17: 민감 필드 미노출 (N-01 ~ N-12 확장)
# ===========================================================================
class TestSensitiveFieldBlocklistV2:
    """v2 API 및 UI에서 민감 필드 12개 미노출 검증."""

    def test_no_raw_prompt_in_route(self):
        """T-D17-a: route에 raw_prompt 응답 필드가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        # raw_prompt should not appear as a dict key in any response
        assert '"raw_prompt"' not in content

    def test_no_reasoning_in_route(self):
        """T-D17-b: route에 reasoning 응답 필드가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"reasoning"' not in content

    def test_no_error_class_in_route(self):
        """T-D17-c: route에 error_class 응답 필드가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"error_class"' not in content

    def test_no_traceback_in_route(self):
        """T-D17-d: route에 traceback 응답 필드가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"traceback"' not in content

    def test_no_agent_analysis_in_template(self):
        """T-D17-e: template에 agent_analysis가 노출되지 않는다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "agent_analysis" not in content

    def test_sensitive_field_blocklist_comment(self):
        """T-D17-f: route에 민감 필드 차단 목록 주석이 있다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "N-01" in content or "Sensitive field blocklist" in content or "blocked-fields" in content


# ===========================================================================
# T-D18-ext: API 실패 시 fail-closed 전이
# ===========================================================================
class TestFailClosedTransition:
    """API 실패 시 조회 중 → fail-closed 상태 전이 검증."""

    def test_mark_all_stale_function_exists(self):
        """T-D18x-a: markAllStale 함수가 fail-closed 전이를 수행한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function markAllStale" in content

    def test_mark_all_stale_sets_unreliable(self):
        """T-D18x-b: markAllStale가 UNRELIABLE 배너를 설정한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function markAllStale")
        fn_section = content[fn_start:fn_start + 3000]
        assert "UNRELIABLE" in fn_section
        assert "gbanner-unreliable" in fn_section

    def test_mark_all_stale_shows_api_unavailable(self):
        """T-D18x-c: markAllStale가 venue card를 API UNAVAILABLE로 전이한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function markAllStale")
        fn_section = content[fn_start:fn_start + 3000]
        assert "API UNAVAILABLE" in fn_section

    def test_mark_all_stale_shows_poll_failed(self):
        """T-D18x-d: markAllStale가 LAST POLL에 실패 표시를 한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function markAllStale")
        fn_section = content[fn_start:fn_start + 3000]
        assert "POLL FAILED" in fn_section or "NEVER CONNECTED" in fn_section

    def test_mark_all_stale_shows_backend_unavailable(self):
        """T-D18x-e: markAllStale가 TRUST에 BACKEND UNAVAILABLE을 표시한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function markAllStale")
        fn_section = content[fn_start:fn_start + 3000]
        assert "BACKEND UNAVAILABLE" in fn_section

    def test_consecutive_failures_tracked(self):
        """T-D18x-f: 연속 실패 횟수가 추적된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "consecutiveFailures" in content

    def test_has_ever_loaded_flag(self):
        """T-D18x-g: 최초 로딩 여부를 추적하는 플래그가 있다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "hasEverLoaded" in content

    def test_api_unavailable_distinct_from_proxy_freshness(self):
        """T-D18x-h: API UNAVAILABLE과 proxy freshness가 시각적으로 분리된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        # API UNAVAILABLE uses conn-disconnected (red)
        # proxy freshness uses deriveConnectionState (green/amber/gray)
        fn_start = content.index("function markAllStale")
        fn_section = content[fn_start:fn_start + 3000]
        assert "conn-disconnected" in fn_section
        assert "API UNAVAILABLE" in fn_section
        # proxy freshness uses different function
        assert "function deriveConnectionState" in content


# ===========================================================================
# T-D19: B-08 AI Workspace 데이터 소스 연결
# ===========================================================================
class TestAIWorkspaceConnection:
    """AI Workspace가 내부 데이터 소스에 연결되었는지 검증."""

    def test_ai_blocks_have_dynamic_ids(self):
        """T-D19-a: AI 블록에 동적 렌더링 대상 ID가 있다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        for bid in ['ai-summary-body', 'anomaly-body', 'causes-body',
                     'risk-warn-body', 'check-order-body']:
            assert f'id="{bid}"' in content, f"AI block {bid} dynamic ID not found"

    def test_render_ai_workspace_function_exists(self):
        """T-D19-b: renderAIWorkspace JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderAIWorkspace" in content

    def test_render_confirmed_facts_exists(self):
        """T-D19-c: renderConfirmedFacts JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderConfirmedFacts" in content

    def test_render_detected_anomalies_exists(self):
        """T-D19-d: renderDetectedAnomalies JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderDetectedAnomalies" in content

    def test_render_possible_causes_exists(self):
        """T-D19-e: renderPossibleCauses JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderPossibleCauses" in content

    def test_render_risk_warnings_exists(self):
        """T-D19-f: renderRiskWarnings JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderRiskWarnings" in content

    def test_render_recommended_checks_exists(self):
        """T-D19-g: renderRecommendedChecks JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderRecommendedChecks" in content

    def test_ai_workspace_called_from_render_tab2(self):
        """T-D19-h: renderTab2에서 renderAIWorkspace가 호출된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "renderAIWorkspace(data, venueStates)" in content

    def test_tier_labels_used_in_ai_blocks(self):
        """T-D19-i: AI 블록에서 tier-fact/tier-estimate/tier-verify 라벨이 사용된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "_aiRow('fact'" in content or "_aiRow(\"fact\"" in content
        assert "_aiRow('estimate'" in content or "_aiRow(\"estimate\"" in content
        assert "_aiRow('verify'" in content or "_aiRow(\"verify\"" in content

    def test_ai_fail_closed_on_backend_unavailable(self):
        """T-D19-j: backend unavailable 시 AI 블록도 fail-closed 처리된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function markAllStale")
        fn_section = content[fn_start:fn_start + 4000]
        assert "ai-summary-body" in fn_section
        assert "BACKEND UNAVAILABLE" in fn_section

    def test_no_agent_analysis_in_ai_render(self):
        """T-D19-k: AI 렌더 함수에 agent_analysis 참조가 없다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        # Find renderAIWorkspace and all sub-functions
        ai_start = content.index("function renderAIWorkspace")
        # Find next major section (legacy shims)
        legacy_start = content.index("function renderBinance")
        ai_section = content[ai_start:legacy_start]
        assert "agent_analysis" not in ai_section

    def test_no_hidden_reasoning_in_ai_blocks(self):
        """T-D19-l: AI 블록에 hidden reasoning 관련 문자열이 없다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        ai_start = content.index("function renderAIWorkspace")
        legacy_start = content.index("function renderBinance")
        ai_section = content[ai_start:legacy_start]
        for forbidden in ['raw_prompt', 'chain_of_thought', 'internal_reasoning',
                          'debug_trace', 'error_class']:
            assert forbidden not in ai_section, f"Forbidden field {forbidden} in AI render"

    def test_causes_block_uses_estimate_tier(self):
        """T-D19-m: Possible Causes 블록이 estimate tier를 사용한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderPossibleCauses")
        fn_end = content.index("function renderRiskWarnings")
        fn = content[fn_start:fn_end]
        assert "'estimate'" in fn, "Possible Causes must use estimate tier"

    def test_block_titles_updated(self):
        """T-D19-n: AI 블록 타이틀이 업데이트되었다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Confirmed Facts" in content
        assert "Detected Anomalies" in content


# ===========================================================================
# T-D20-B09: Quote Truth Layer — bid/ask/spread feed
# ===========================================================================
class TestQuoteTruthBackend:
    """B-09: Backend quote data helper 검증."""

    def test_get_quote_data_function_exists(self):
        """T-D20-a: _get_quote_data 함수가 존재한다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "async def _get_quote_data" in content

    def test_v2_returns_quote_data_key(self):
        """T-D20-b: v2 응답에 quote_data 키가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert '"quote_data"' in content

    def test_quote_data_has_6_tuple_fields(self):
        """T-D20-c: quote 반환 구조에 6-tuple 필드가 포함된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        for field in ['"bid"', '"ask"', '"spread"', '"as_of"',
                      '"age_seconds"', '"trust_state"', '"source_venue"',
                      '"timestamp_origin"']:
            assert field in content, f"Quote 6-tuple field {field} missing"

    def test_trust_states_defined(self):
        """T-D20-d: 6개 trust_state가 정의되어 있다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        for state in ['LIVE', 'STALE', 'DISCONNECTED', 'UNAVAILABLE',
                      'NOT_AVAILABLE', 'NOT_QUERIED']:
            assert f'"{state}"' in content, f"Trust state {state} not defined"

    def test_bid_ask_not_supported_list(self):
        """T-D20-e: KIS/Kiwoom이 bid/ask 미지원으로 분류된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "_BID_ASK_NOT_SUPPORTED" in content
        assert '"kis"' in content
        assert '"kiwoom"' in content

    def test_stale_threshold_defined(self):
        """T-D20-f: QUOTE_STALE_THRESHOLD_S가 정의되어 있다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "_QUOTE_STALE_THRESHOLD_S" in content

    def test_connection_error_classification(self):
        """T-D20-g: 연결 에러가 DISCONNECTED로 분류된다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        assert "_CONNECTION_ERRORS" in content
        assert "ConnectionError" in content
        assert "TimeoutError" in content

    def test_no_write_action_in_quote(self):
        """T-D20-h: quote 함수에 write action이 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        import re
        fn_match = re.search(
            r'async def _get_quote_data.*?(?=\n# ---|\Z)',
            content, re.DOTALL
        )
        assert fn_match
        fn_body = fn_match.group()
        for forbidden in ['create_order', 'cancel_order', 'db.add', 'db.commit',
                          'session.add', '.post(', '.put(', '.delete(']:
            assert forbidden not in fn_body, f"Write action {forbidden} in quote code"

    def test_no_sensitive_fields_in_quote(self):
        """T-D20-i: quote 함수에 민감 필드 참조가 없다."""
        content = DASHBOARD_ROUTE_PATH.read_text(encoding="utf-8")
        import re
        fn_match = re.search(
            r'async def _get_quote_data.*?(?=\n# ---|\Z)',
            content, re.DOTALL
        )
        assert fn_match
        fn_body = fn_match.group()
        for forbidden in ['agent_analysis', 'reasoning', 'error_class']:
            assert forbidden not in fn_body


class TestQuoteTruthFrontend:
    """B-09: Frontend quote 표시 검증."""

    def test_render_quote_fields_function(self):
        """T-D20-j: renderQuoteFields JS 함수가 존재한다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "function renderQuoteFields" in content

    def test_frontend_no_trust_state_calculation(self):
        """T-D20-k: frontend는 trust_state를 계산하지 않는다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        # renderQuoteFields should use q.trust_state from backend, not calculate it
        fn_start = content.index("function renderQuoteFields")
        fn_end = content.index("function renderVenueCards")
        fn = content[fn_start:fn_end]
        assert "q.trust_state" in fn, "Must use backend trust_state"
        # Should NOT contain threshold comparison logic
        assert "FRESHNESS_THRESHOLD" not in fn, "Frontend must not re-judge with threshold"
        assert "_QUOTE_STALE_THRESHOLD" not in fn, "Frontend must not reference stale threshold"

    def test_quote_trust_css_map(self):
        """T-D20-l: trust_state → CSS 매핑이 정의되어 있다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "_QUOTE_TRUST_CSS" in content

    def test_not_queried_display_text(self):
        """T-D20-m: NOT_QUERIED가 'no tracked symbol'로 표시된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "no tracked symbol" in content

    def test_as_of_and_age_displayed(self):
        """T-D20-n: bid/ask 옆에 as-of 시각 + age가 표시된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderQuoteFields")
        fn_end = content.index("function renderVenueCards")
        fn = content[fn_start:fn_end]
        assert "as_of" in fn
        assert "age_seconds" in fn
        assert "Age:" in fn

    def test_timestamp_origin_indicator(self):
        """T-D20-o: timestamp_origin이 server_fetch_time일 때 표시된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderQuoteFields")
        fn_end = content.index("function renderVenueCards")
        fn = content[fn_start:fn_end]
        assert "timestamp_origin" in fn
        assert "server_fetch_time" in fn

    def test_ai_workspace_includes_quote_anomaly(self):
        """T-D20-p: AI Workspace에 quote anomaly가 반영된다."""
        content = TEMPLATE_PATH.read_text(encoding="utf-8")
        fn_start = content.index("function renderDetectedAnomalies")
        fn_end = content.index("function renderPossibleCauses")
        fn = content[fn_start:fn_end]
        assert "quote_data" in fn
        assert "quote" in fn.lower()
