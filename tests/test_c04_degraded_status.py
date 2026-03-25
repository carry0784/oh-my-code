"""
Card C-04: Degraded Status Endpoint — Tests

검수 범위:
  C04-1: /status 엔드포인트 구조
  C04-2: 상태 모델 필드 검증
  C04-3: degraded 판정 로직
  C04-4: 기존 probe 비수정 확인
  C04-5: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
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
    "app.exchanges.okx",
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
# File path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PATH = PROJECT_ROOT / "app" / "main.py"


def _get_status_fn_body():
    content = MAIN_PATH.read_text(encoding="utf-8")
    fn_match = re.search(
        r'async def degraded_status.*?(?=\n@app\.|\Z)',
        content, re.DOTALL
    )
    assert fn_match, "degraded_status function not found"
    return fn_match.group()


# ===========================================================================
# C04-1: /status 엔드포인트 구조
# ===========================================================================
class TestC04StatusEndpoint:
    """/status 엔드포인트 존재 및 기본 구조 검증."""

    def test_status_endpoint_exists(self):
        """C04-1a: /status 엔드포인트가 main.py에 존재한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/status"' in content

    def test_status_function_exists(self):
        """C04-1b: degraded_status 함수가 존재한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "async def degraded_status" in content

    def test_status_is_get_method(self):
        """C04-1c: GET 메서드로 등록된다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        # Find the decorator line before degraded_status
        idx = content.index("async def degraded_status")
        preceding = content[max(0, idx - 100):idx]
        assert "@app.get" in preceding

    def test_status_returns_200_always(self):
        """C04-1d: /status는 항상 200을 반환한다 (liveness와 혼합 방지)."""
        fn_body = _get_status_fn_body()
        assert "status_code=200" in fn_body


# ===========================================================================
# C04-2: 상태 모델 필드 검증
# ===========================================================================
class TestC04StatusModel:
    """응답 모델에 필수 필드가 포함되는지 검증."""

    def test_has_overall_status(self):
        """C04-2a: overall_status 필드를 반환한다."""
        fn_body = _get_status_fn_body()
        assert '"overall_status"' in fn_body

    def test_has_liveness(self):
        """C04-2b: liveness 필드를 반환한다."""
        fn_body = _get_status_fn_body()
        assert '"liveness"' in fn_body

    def test_has_readiness(self):
        """C04-2c: readiness 필드를 반환한다."""
        fn_body = _get_status_fn_body()
        assert '"readiness"' in fn_body

    def test_has_startup(self):
        """C04-2d: startup 필드를 반환한다."""
        fn_body = _get_status_fn_body()
        assert '"startup"' in fn_body

    def test_has_degraded_reasons(self):
        """C04-2e: degraded_reasons 배열을 반환한다."""
        fn_body = _get_status_fn_body()
        assert '"degraded_reasons"' in fn_body

    def test_has_sources(self):
        """C04-2f: sources dict를 반환한다."""
        fn_body = _get_status_fn_body()
        assert '"sources"' in fn_body

    def test_overall_status_values(self):
        """C04-2g: overall_status가 4가지 값 중 하나이다."""
        fn_body = _get_status_fn_body()
        for val in ['"healthy"', '"ready"', '"degraded"', '"unavailable"']:
            assert val in fn_body, f"overall_status value {val} must be defined"


# ===========================================================================
# C04-3: degraded 판정 로직
# ===========================================================================
class TestC04DegradedJudgment:
    """degraded 상태 판정 로직 검증."""

    def test_checks_loop_monitor(self):
        """C04-3a: loop_monitor 소스 가용성을 검사한다."""
        fn_body = _get_status_fn_body()
        assert "loop_monitor" in fn_body

    def test_checks_work_state(self):
        """C04-3b: work_state 소스 가용성을 검사한다."""
        fn_body = _get_status_fn_body()
        assert "work_state" in fn_body

    def test_checks_trust_state(self):
        """C04-3c: trust_state 소스 가용성을 검사한다."""
        fn_body = _get_status_fn_body()
        assert "trust_state" in fn_body or "trust_registry" in fn_body

    def test_checks_doctrine(self):
        """C04-3d: doctrine 소스 가용성을 검사한다."""
        fn_body = _get_status_fn_body()
        assert "doctrine" in fn_body

    def test_source_states_include_available(self):
        """C04-3e: source 상태에 available이 포함된다."""
        fn_body = _get_status_fn_body()
        assert '"available"' in fn_body

    def test_source_states_include_unavailable(self):
        """C04-3f: source 상태에 unavailable이 포함된다."""
        fn_body = _get_status_fn_body()
        assert '"unavailable"' in fn_body

    def test_source_states_include_warning(self):
        """C04-3g: source 상태에 warning이 포함된다."""
        fn_body = _get_status_fn_body()
        assert '"warning"' in fn_body

    def test_source_states_include_critical(self):
        """C04-3h: source 상태에 critical이 포함된다."""
        fn_body = _get_status_fn_body()
        assert '"critical"' in fn_body

    def test_degraded_reasons_populated_on_unavailable_source(self):
        """C04-3i: 소스 unavailable 시 degraded_reasons에 추가된다."""
        fn_body = _get_status_fn_body()
        assert "degraded_reasons.append(" in fn_body

    def test_uses_getattr_safe_access(self):
        """C04-3j: getattr 안전 접근을 사용한다."""
        fn_body = _get_status_fn_body()
        assert "getattr(app.state" in fn_body


# ===========================================================================
# C04-4: 기존 probe 비수정 확인
# ===========================================================================
class TestC04ExistingProbesPreserved:
    """기존 /health, /ready, /startup이 보존되는지 검증."""

    def test_health_preserved(self):
        """C04-4a: /health 엔드포인트가 보존된다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/health"' in content
        assert "async def health_check" in content

    def test_ready_preserved(self):
        """C04-4b: /ready 엔드포인트가 보존된다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/ready"' in content
        assert "async def readiness_probe" in content

    def test_startup_preserved(self):
        """C04-4c: /startup 엔드포인트가 보존된다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/startup"' in content
        assert "async def startup_probe" in content

    def test_c03_section_not_modified(self):
        """C04-4d: C-03 섹션 마커가 보존된다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "# C-03:" in content


# ===========================================================================
# C04-5: 금지 조항 확인
# ===========================================================================
class TestC04ForbiddenFields:
    """금지 문자열 및 런타임 변경 미포함 검증."""

    def test_no_forbidden_strings(self):
        """C04-5a: /status 함수에 금지 문자열이 없다."""
        fn_body = _get_status_fn_body()
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in fn_body, f"Forbidden string '{f}' in status endpoint"

    def test_no_runtime_mutation(self):
        """C04-5b: 런타임 상태를 변경하지 않는다."""
        fn_body = _get_status_fn_body()
        mutation_calls = ['.record_violation(', '.on_failure(', '.check(', '.ratify(']
        for mc in mutation_calls:
            assert mc not in fn_body, f"Mutation call '{mc}' found in status endpoint"

    def test_no_auto_recovery(self):
        """C04-5c: 자동 복구 로직이 없다 (관측과 판정만)."""
        fn_body = _get_status_fn_body()
        # Strip docstring and comments — check only executable code
        lines = fn_body.split("\n")
        in_docstring = False
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if in_docstring or stripped.startswith("#"):
                continue
            code_lines.append(stripped.lower())
        code_only = " ".join(code_lines)
        # Word-boundary check to avoid false positives (e.g. "health" matching "heal")
        import re as _re
        recovery_patterns = [r'\brecover\b', r'\brestart\b', r'\breset\b', r'\bretry\b', r'\bheal\b']
        for pattern in recovery_patterns:
            assert not _re.search(pattern, code_only), \
                f"Recovery term '{pattern}' found — /status should observe only"
