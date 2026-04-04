"""Tests for SystemHealthMonitor — CR-044 Phase 7."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt", "ccxt.async_support", "aiohttp", "celery", "redis",
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm", "sqlalchemy.pool", "sqlalchemy.engine",
    "app.core.database", "app.core.config",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()
_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()

from app.services.system_health import SystemHealthMonitor, SystemHealthReport


def test_healthy_system():
    """No warnings when all metrics are within limits."""
    monitor = SystemHealthMonitor()
    report = monitor.collect(
        registry_size=10,
        portfolio_sharpe=1.5,
        portfolio_drawdown_pct=10.0,
        governance_pending=2,
    )
    assert report.is_healthy is True
    assert len(report.warnings) == 0


def test_drawdown_warning():
    """High drawdown triggers a warning."""
    monitor = SystemHealthMonitor(max_drawdown_threshold=20.0)
    report = monitor.collect(
        registry_size=10,
        portfolio_drawdown_pct=25.0,
    )
    assert report.is_healthy is False
    assert any("drawdown" in w.lower() for w in report.warnings)


def test_registry_size_warning():
    """Low registry size triggers a warning."""
    monitor = SystemHealthMonitor(min_registry_size=5)
    report = monitor.collect(
        registry_size=2,
        portfolio_sharpe=1.0,
    )
    assert report.is_healthy is False
    assert any("registry" in w.lower() for w in report.warnings)


def test_governance_queue_warning():
    """Too many pending governance decisions triggers a warning."""
    monitor = SystemHealthMonitor(max_pending_governance=5)
    report = monitor.collect(
        registry_size=10,
        governance_pending=8,
    )
    assert report.is_healthy is False
    assert any("governance" in w.lower() for w in report.warnings)


def test_negative_sharpe_warning():
    """Negative portfolio Sharpe triggers a warning."""
    monitor = SystemHealthMonitor()
    report = monitor.collect(
        registry_size=10,
        portfolio_sharpe=-0.5,
    )
    assert report.is_healthy is False
    assert any("sharpe" in w.lower() for w in report.warnings)
