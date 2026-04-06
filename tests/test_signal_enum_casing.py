"""
signalstatus Enum Casing Regression Tests

Verifies that SQLAlchemy sends lowercase enum values to PostgreSQL,
matching the DB-side enum type definition.

Root cause: SQLEnum(SignalStatus) defaults to .name (uppercase),
but PostgreSQL enum was created with .value (lowercase).
Fix: values_callable=lambda e: [x.value for x in e]
"""

from __future__ import annotations

import pathlib
import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Anti-pollution guard: other test files may stub celery modules as MagicMock,
# which poisons module-level attributes (e.g. Signal.__table__ becomes MagicMock).
# Purge polluted modules before importing application code.
# ---------------------------------------------------------------------------
_POLLUTED_MODULES = [
    "workers",
    "workers.celery_app",
    "workers.tasks",
    "workers.tasks.order_tasks",
    "workers.tasks.signal_tasks",
    "workers.tasks.market_tasks",
    "workers.tasks.snapshot_tasks",
    "workers.tasks.data_collection_tasks",
]

for _mod_name in _POLLUTED_MODULES:
    _mod = sys.modules.get(_mod_name)
    if _mod is not None and isinstance(_mod, MagicMock):
        del sys.modules[_mod_name]

from sqlalchemy import Enum as SQLEnum  # noqa: E402

from app.models.signal import Signal, SignalStatus, SignalType  # noqa: E402


def _signal_table_usable() -> bool:
    """Return True if Signal.__table__ is a real SQLAlchemy Table (not MagicMock)."""
    try:
        tbl = Signal.__table__
        return not isinstance(tbl, MagicMock) and hasattr(tbl, "columns")
    except Exception:
        return False


def _read_source_from_file() -> str:
    """Read signal.py source directly from disk (immune to MagicMock pollution)."""
    src = pathlib.Path(__file__).resolve().parent.parent / "app" / "models" / "signal.py"
    return src.read_text(encoding="utf-8")


_TABLE_SKIP_REASON = "Signal.__table__ is MagicMock due to celery stub pollution in full suite"


class TestSignalStatusEnumCasing:
    """Verify SignalStatus enum sends lowercase values to DB."""

    @pytest.mark.skipif(not _signal_table_usable(), reason=_TABLE_SKIP_REASON)
    def test_sqlalchemy_enum_values_are_lowercase(self):
        """SQLEnum must produce lowercase values matching PostgreSQL enum."""
        col = Signal.__table__.columns["status"]
        assert list(col.type.enums) == [
            "pending",
            "validated",
            "rejected",
            "executed",
            "expired",
        ]

    def test_pending_value_is_lowercase(self):
        """PENDING enum must resolve to 'pending' (lowercase)."""
        assert SignalStatus.PENDING.value == "pending"

    def test_validated_value_is_lowercase(self):
        assert SignalStatus.VALIDATED.value == "validated"

    def test_rejected_value_is_lowercase(self):
        assert SignalStatus.REJECTED.value == "rejected"

    def test_executed_value_is_lowercase(self):
        assert SignalStatus.EXECUTED.value == "executed"

    def test_expired_value_is_lowercase(self):
        assert SignalStatus.EXPIRED.value == "expired"

    @pytest.mark.skipif(not _signal_table_usable(), reason=_TABLE_SKIP_REASON)
    def test_no_uppercase_in_enum_values(self):
        """No enum value should contain uppercase letters."""
        col = Signal.__table__.columns["status"]
        for val in col.type.enums:
            assert val == val.lower(), f"Enum value '{val}' contains uppercase"


class TestSignalTypeEnumCasing:
    """Verify SignalType enum sends lowercase values to DB."""

    @pytest.mark.skipif(not _signal_table_usable(), reason=_TABLE_SKIP_REASON)
    def test_sqlalchemy_enum_values_are_lowercase(self):
        col = Signal.__table__.columns["signal_type"]
        assert list(col.type.enums) == ["long", "short", "close"]

    def test_long_value_is_lowercase(self):
        assert SignalType.LONG.value == "long"

    def test_short_value_is_lowercase(self):
        assert SignalType.SHORT.value == "short"

    def test_close_value_is_lowercase(self):
        assert SignalType.CLOSE.value == "close"

    @pytest.mark.skipif(not _signal_table_usable(), reason=_TABLE_SKIP_REASON)
    def test_no_uppercase_in_enum_values(self):
        col = Signal.__table__.columns["signal_type"]
        for val in col.type.enums:
            assert val == val.lower(), f"Enum value '{val}' contains uppercase"


class TestEnumDBAlignment:
    """Verify enum values match the PostgreSQL migration definition."""

    MIGRATION_STATUS_VALUES = ["pending", "validated", "rejected", "executed", "expired"]
    MIGRATION_TYPE_VALUES = ["long", "short", "close"]

    @pytest.mark.skipif(not _signal_table_usable(), reason=_TABLE_SKIP_REASON)
    def test_status_enum_matches_migration(self):
        """ORM enum values must match migration-defined PostgreSQL enum."""
        col = Signal.__table__.columns["status"]
        assert list(col.type.enums) == self.MIGRATION_STATUS_VALUES

    @pytest.mark.skipif(not _signal_table_usable(), reason=_TABLE_SKIP_REASON)
    def test_type_enum_matches_migration(self):
        col = Signal.__table__.columns["signal_type"]
        assert list(col.type.enums) == self.MIGRATION_TYPE_VALUES

    def test_values_callable_present_in_status(self):
        """status column must use values_callable for lowercase mapping."""
        source = _read_source_from_file()
        assert "values_callable" in source
