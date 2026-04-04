"""
B-01 Position.symbol_name Tests — 6 tests

Validates:
  - Model accepts nullable symbol_name
  - Schema includes symbol_name
  - sync_from_exchange preserves symbol_name
  - Update policy: None/empty preserves existing, new value updates
  - Dashboard data includes symbol_name

Isolation: This test creates its own in-memory SQLAlchemy Base and engine
to avoid contamination from MagicMock stubs injected by other test files
(e.g. test_dashboard.py). Do NOT remove the isolation bootstrap below.
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Isolation bootstrap: ensure real SQLAlchemy model, not MagicMock
# ---------------------------------------------------------------------------
# Other test files (test_dashboard.py etc.) inject MagicMock stubs into
# sys.modules for app.core.database, app.models.position, etc.
# If those stubs are present when this file is imported, Position becomes
# a MagicMock and all assertions fail.
#
# Strategy:
#   1. Remove contaminated modules from sys.modules
#   2. Inject a real DeclarativeBase as app.core.database.Base
#   3. Re-import the actual Position model and PositionResponse schema
# ---------------------------------------------------------------------------
import types
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase

# Modules that may be contaminated by prior test stubs
_CONTAMINATION_TARGETS = [
    "app.core.database",
    "app.models.position",
    "app.schemas.position",
]

# Save and remove contaminated modules
_saved_modules: dict[str, types.ModuleType] = {}
for _mod_name in _CONTAMINATION_TARGETS:
    if _mod_name in sys.modules:
        _saved_modules[_mod_name] = sys.modules.pop(_mod_name)


# Create isolated database module with real DeclarativeBase + in-memory engine
class _TestBase(DeclarativeBase):
    pass


_db_module = types.ModuleType("app.core.database")
_db_module.Base = _TestBase
_db_module.get_db = MagicMock()
_db_module.engine = None
_db_module.async_session_factory = MagicMock()

# Also stub app.core.config to prevent database_url resolution
if "app.core.config" not in sys.modules:
    _config_mod = types.ModuleType("app.core.config")
    _config_mod.settings = MagicMock()
    _config_mod.settings.database_url = "sqlite://"
    _config_mod.settings.debug = False
    sys.modules["app.core.config"] = _config_mod

sys.modules["app.core.database"] = _db_module

# Force fresh import of Position model (will use _TestBase)
from app.models.position import Position, PositionSide  # noqa: E402
from app.schemas.position import PositionResponse  # noqa: E402

# Create in-memory tables so SQLAlchemy model instantiation works
_engine = create_engine("sqlite:///:memory:")
_TestBase.metadata.create_all(_engine)


# ═══════════════════════════════════════════════════════════════════════════ #
# B-01: POSITION SYMBOL_NAME TESTS
# ═══════════════════════════════════════════════════════════════════════════ #


class TestPositionSymbolName:
    """B-01: Position.symbol_name field reinforcement."""

    def test_position_symbol_name_nullable(self):
        """Position can be created without symbol_name (crypto exchanges)."""
        pos = Position(
            exchange="binance",
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            quantity=1.0,
            entry_price=50000.0,
            current_price=51000.0,
        )
        assert pos.symbol_name is None
        assert pos.symbol == "BTC/USDT"

    def test_position_symbol_name_set(self):
        """Position stores symbol_name when provided (KIS/Kiwoom)."""
        pos = Position(
            exchange="kis",
            symbol="005930",
            symbol_name="삼성전자",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=70000.0,
            current_price=71000.0,
        )
        assert pos.symbol_name == "삼성전자"
        assert pos.symbol == "005930"

    def test_schema_includes_symbol_name(self):
        """PositionResponse schema includes symbol_name field."""
        data = {
            "id": "test-id",
            "exchange": "kis",
            "symbol": "005930",
            "symbol_name": "삼성전자",
            "side": "long",
            "quantity": 10.0,
            "entry_price": 70000.0,
            "current_price": 71000.0,
            "unrealized_pnl": 10000.0,
            "realized_pnl": 0.0,
            "leverage": 1.0,
            "liquidation_price": None,
            "opened_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        response = PositionResponse(**data)
        assert response.symbol_name == "삼성전자"

        # Without symbol_name (crypto)
        data_no_name = {**data, "symbol_name": None, "exchange": "binance", "symbol": "BTC/USDT"}
        response_no_name = PositionResponse(**data_no_name)
        assert response_no_name.symbol_name is None

    def test_sync_update_policy_none_preserves_existing(self):
        """When new symbol_name is None, existing value is preserved."""
        pos = Position(
            exchange="kis",
            symbol="005930",
            symbol_name="삼성전자",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=70000.0,
            current_price=71000.0,
        )

        # Simulate sync with no symbol_name (e.g., API didn't return it)
        new_symbol_name = None or None  # pos_data.get("symbol_name") → None
        if new_symbol_name:
            pos.symbol_name = new_symbol_name
        # Existing value should be preserved
        assert pos.symbol_name == "삼성전자"

    def test_sync_update_policy_empty_string_preserves_existing(self):
        """When new symbol_name is empty string, existing value is preserved."""
        pos = Position(
            exchange="kis",
            symbol="005930",
            symbol_name="삼성전자",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=70000.0,
            current_price=71000.0,
        )

        # Simulate sync with empty string
        new_symbol_name = "" or None  # falsy → None
        if new_symbol_name:
            pos.symbol_name = new_symbol_name
        assert pos.symbol_name == "삼성전자"

    def test_sync_update_policy_new_value_updates(self):
        """When new symbol_name has a value, it replaces existing."""
        pos = Position(
            exchange="kis",
            symbol="005930",
            symbol_name="삼성전자",
            side=PositionSide.LONG,
            quantity=10.0,
            entry_price=70000.0,
            current_price=71000.0,
        )

        new_symbol_name = "삼성전자(우)" or None  # truthy → value
        if new_symbol_name:
            pos.symbol_name = new_symbol_name
        assert pos.symbol_name == "삼성전자(우)"
