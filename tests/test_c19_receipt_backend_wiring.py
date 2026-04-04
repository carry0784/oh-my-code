"""
Card C-19: Receipt Backend Wiring / Runtime Activation — Tests

검수 범위:
  C19-1: config.py receipt_file_path 설정
  C19-2: main.py 런타임 wiring 로직
  C19-3: fail-closed fallback 동작
  C19-4: 기존 동작 보존
  C19-5: 금지 조항 확인

Sealed layers 미접촉. 기존 테스트 파일 미수정.
"""

import sys
import re
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
MAIN_PATH = PROJECT_ROOT / "app" / "main.py"
CONFIG_PATH = PROJECT_ROOT / "app" / "core" / "config.py"


# ===========================================================================
# C19-1: config.py receipt_file_path
# ===========================================================================
class TestC19Config:
    def test_receipt_file_path_setting_exists(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert "receipt_file_path" in content

    def test_receipt_file_path_default_empty(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert 'receipt_file_path: str = ""' in content

    def test_config_comment_explains_behavior(self):
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert "in-memory" in content.lower() or "IN_MEMORY" in content
        assert "JSONL" in content or "file backend" in content.lower()


# ===========================================================================
# C19-2: main.py wiring 로직
# ===========================================================================
class TestC19MainWiring:
    def test_receipt_store_initialized(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.receipt_store" in content

    def test_checks_receipt_file_path(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "receipt_file_path" in content

    def test_imports_file_backend_conditionally(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "ReceiptFileBackend" in content

    def test_passes_file_backend_to_store(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "file_backend=receipt_file_backend" in content

    def test_logs_receipt_mode(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "receipt_store_initialized" in content
        assert "receipt_mode" in content

    def test_two_modes_defined(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"IN_MEMORY"' in content
        assert '"FILE_PERSISTED"' in content


# ===========================================================================
# C19-3: fail-closed fallback
# ===========================================================================
class TestC19FailClosed:
    def test_exception_fallback_to_memory(self):
        """file backend init 실패 시 memory-only fallback."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        # Find the wiring section
        wiring_start = content.index("receipt_file_backend = None")
        wiring_section = content[wiring_start : wiring_start + 500]
        assert "except" in wiring_section
        assert "receipt_file_backend = None" in wiring_section

    def test_empty_path_stays_memory_only(self):
        """빈 경로 → IN_MEMORY 유지."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        wiring_start = content.index("receipt_file_backend = None")
        wiring_section = content[wiring_start : wiring_start + 500]
        assert "if settings.receipt_file_path" in wiring_section


# ===========================================================================
# C19-4: 기존 동작 보존
# ===========================================================================
class TestC19ExistingPreserved:
    def test_c01_slots_preserved(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.loop_monitor" in content
        assert "app.state.work_state_ctx" in content
        assert "app.state.trust_registry" in content
        assert "app.state.doctrine_registry" in content

    def test_governance_gate_preserved(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert "app.state.governance_gate" in content

    def test_health_endpoint_preserved(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/health"' in content

    def test_c03_probes_preserved(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        assert '"/ready"' in content
        assert '"/startup"' in content
        assert '"/status"' in content


# ===========================================================================
# C19-5: 금지 조항
# ===========================================================================
class TestC19Forbidden:
    def test_no_forbidden_strings(self):
        content = MAIN_PATH.read_text(encoding="utf-8")
        # Check only the wiring section
        wiring_start = content.index("receipt_file_backend = None")
        wiring_section = content[wiring_start : wiring_start + 600]
        forbidden = [
            "agent_analysis",
            "raw_prompt",
            "chain_of_thought",
            "internal_reasoning",
            "debug_trace",
            "error_class",
        ]
        for f in forbidden:
            assert f not in wiring_section, f"Forbidden string '{f}'"

    def test_no_forced_file_persistence(self):
        """파일 영속화가 강제되지 않는다 (선택적)."""
        content = MAIN_PATH.read_text(encoding="utf-8")
        wiring_start = content.index("receipt_file_backend = None")
        wiring_section = content[wiring_start : wiring_start + 500]
        # Default is None (memory-only), file only if path configured
        assert wiring_section.startswith("receipt_file_backend = None")
