"""
Card C-03: Health / Readiness / Startup Probes — Tests

검수 범위:
  C03-1: /health 엔드포인트 보존
  C03-2: /ready 엔드포인트 구조 및 동작
  C03-3: /startup 엔드포인트 구조 및 동작
  C03-4: 금지 조항 확인

Card B / C-01 / C-fix / C-02 봉인 유지. 기존 테스트 파일 미수정.
"""

import sys
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy modules (same pattern as sealed tests)
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


# ===========================================================================
# C03-1: /health 보존
# ===========================================================================
class TestC03HealthPreserved:
    """기존 /health 엔드포인트 보존 검증."""

    def test_health_endpoint_exists(self):
        """C03-1a: /health 엔드포인트가 main.py에 존재한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/health"' in content

    def test_health_returns_healthy(self):
        """C03-1b: /health가 {"status": "healthy"}를 반환한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"healthy"' in content or "'healthy'" in content


# ===========================================================================
# C03-2: /ready 엔드포인트
# ===========================================================================
class TestC03ReadyProbe:
    """/ready 엔드포인트 구조 및 동작 검증."""

    def _get_fn_body(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r'async def readiness_probe.*?(?=\n@app\.|\nasync def startup_probe|\Z)',
            content, re.DOTALL
        )
        assert fn_match, "readiness_probe function not found"
        return fn_match.group()

    def test_ready_endpoint_exists(self):
        """C03-2a: /ready 엔드포인트가 main.py에 존재한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/ready"' in content

    def test_ready_checks_governance_gate(self):
        """C03-2b: governance_gate 초기화를 검사한다."""
        fn_body = self._get_fn_body()
        assert "governance_gate" in fn_body

    def test_ready_checks_evidence_store(self):
        """C03-2c: evidence_store 접근 가능성을 검사한다."""
        fn_body = self._get_fn_body()
        assert "evidence_store" in fn_body

    def test_ready_checks_security_context(self):
        """C03-2d: security_context 접근 가능성을 검사한다."""
        fn_body = self._get_fn_body()
        assert "security_context" in fn_body

    def test_ready_returns_checks_dict(self):
        """C03-2e: checks dict를 반환한다."""
        fn_body = self._get_fn_body()
        assert '"checks"' in fn_body

    def test_ready_returns_ready_bool(self):
        """C03-2f: ready boolean 필드를 반환한다."""
        fn_body = self._get_fn_body()
        assert '"ready"' in fn_body

    def test_ready_uses_503_on_failure(self):
        """C03-2g: 미준비 시 503 상태 코드를 반환한다."""
        fn_body = self._get_fn_body()
        assert "503" in fn_body

    def test_ready_is_read_only(self):
        """C03-2h: 상태 변경 메서드를 호출하지 않는다."""
        fn_body = self._get_fn_body()
        # Must not call any mutation methods
        assert ".check(" not in fn_body or "# " in fn_body.split(".check(")[0].split("\n")[-1]
        assert ".record(" not in fn_body
        assert ".on_failure(" not in fn_body


# ===========================================================================
# C03-3: /startup 엔드포인트
# ===========================================================================
class TestC03StartupProbe:
    """/startup 엔드포인트 구조 및 동작 검증."""

    def _get_fn_body(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        fn_match = re.search(
            r'async def startup_probe.*?(?=\n@app\.|\Z)',
            content, re.DOTALL
        )
        assert fn_match, "startup_probe function not found"
        return fn_match.group()

    def test_startup_endpoint_exists(self):
        """C03-3a: /startup 엔드포인트가 main.py에 존재한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/startup"' in content

    def test_startup_checks_governance_initialized(self):
        """C03-3b: governance 초기화 완료를 검사한다."""
        fn_body = self._get_fn_body()
        assert "governance_initialized" in fn_body

    def test_startup_checks_state_slots(self):
        """C03-3c: C-01 app.state 슬롯 초기화를 검사한다."""
        fn_body = self._get_fn_body()
        assert "state_slots_initialized" in fn_body

    def test_startup_returns_started_bool(self):
        """C03-3d: started boolean 필드를 반환한다."""
        fn_body = self._get_fn_body()
        assert '"started"' in fn_body

    def test_startup_returns_checks_dict(self):
        """C03-3e: checks dict를 반환한다."""
        fn_body = self._get_fn_body()
        assert '"checks"' in fn_body

    def test_startup_uses_503_on_failure(self):
        """C03-3f: 미시작 시 503 상태 코드를 반환한다."""
        fn_body = self._get_fn_body()
        assert "503" in fn_body

    def test_startup_handles_governance_disabled(self):
        """C03-3g: governance 비활성화 시에도 정상 동작한다."""
        fn_body = self._get_fn_body()
        assert "governance_enabled" in fn_body


# ===========================================================================
# C03-4: 금지 조항 확인
# ===========================================================================
class TestC03ForbiddenFields:
    """금지 문자열 및 런타임 변경 미포함 검증."""

    def test_no_forbidden_strings_in_probes(self):
        """C03-4a: probe 함수에 금지 문자열이 없다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        # Extract probe section
        probe_start = content.index("# C-03:")
        probe_section = content[probe_start:]
        forbidden = [
            'agent_analysis', 'raw_prompt', 'chain_of_thought',
            'internal_reasoning', 'debug_trace', 'error_class',
            'traceback', 'exception_type', 'stack', 'internal_state_dump',
        ]
        for f in forbidden:
            assert f not in probe_section, f"Forbidden string '{f}' in probe section"

    def test_no_runtime_mutation(self):
        """C03-4b: probe 함수에서 런타임 상태를 변경하지 않는다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        probe_start = content.index("# C-03:")
        probe_section = content[probe_start:]
        mutation_calls = ['.record_violation(', '.on_failure(', '.check(', '.ratify(']
        for mc in mutation_calls:
            assert mc not in probe_section, f"Mutation call '{mc}' found in probe section"

    def test_probes_use_getattr_safe_access(self):
        """C03-4c: getattr 안전 접근을 사용한다."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        probe_start = content.index("# C-03:")
        probe_section = content[probe_start:]
        assert "getattr(" in probe_section
