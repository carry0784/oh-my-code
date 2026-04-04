"""Tests for PortfolioConstructor — CR-043 Phase 6."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt", "ccxt.async_support", "aiohttp", "celery", "redis",
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm", "sqlalchemy.pool", "sqlalchemy.engine",
    "app.core.database", "app.core.config", "structlog",
]
for name in _STUB_MODULES:
    if name not in sys.modules:
        sys.modules[name] = MagicMock()
_fake_base = type("FakeBase", (), {"__tablename__": "", "metadata": MagicMock()})
sys.modules["app.core.database"].Base = _fake_base
sys.modules["app.core.database"].engine = MagicMock()
sys.modules["app.core.database"].async_session_factory = MagicMock()
sys.modules["app.core.config"].settings = MagicMock()

import pytest
from app.services.portfolio_constructor import PortfolioConstructor


CAPITAL = 10_000.0


@pytest.fixture
def constructor():
    return PortfolioConstructor()


def _equity(n=100, step=10.0):
    return [10_000.0 + i * step for i in range(n)]


# Three strategy equity curves with different growth rates
_EQUITY_CURVES = {
    "s1": _equity(100, step=10.0),
    "s2": _equity(100, step=20.0),
    "s3": _equity(100, step=5.0),
}


# ---------------------------------------------------------------------------
# test_construct_returns_result
# ---------------------------------------------------------------------------

def test_construct_returns_result(constructor):
    """construct() returns a fully populated PortfolioConstructionResult."""
    result = constructor.construct(_EQUITY_CURVES, capital=CAPITAL)

    assert result.allocations is not None and len(result.allocations) > 0
    assert result.correlation is not None
    assert result.risk_budget is not None
    assert result.performance is not None
    assert result.strategy_count == len(_EQUITY_CURVES)
    assert result.total_capital == CAPITAL


# ---------------------------------------------------------------------------
# test_construct_risk_parity
# ---------------------------------------------------------------------------

def test_construct_risk_parity(constructor):
    """method='risk_parity' is recorded in optimization_method field."""
    result = constructor.construct(_EQUITY_CURVES, capital=CAPITAL, method="risk_parity")

    assert result.optimization_method == "risk_parity"
    assert result.strategy_count > 0


# ---------------------------------------------------------------------------
# test_construct_min_variance
# ---------------------------------------------------------------------------

def test_construct_min_variance(constructor):
    """method='min_variance' is recorded in optimization_method field."""
    result = constructor.construct(_EQUITY_CURVES, capital=CAPITAL, method="min_variance")

    assert result.optimization_method == "min_variance"
    assert result.strategy_count > 0


# ---------------------------------------------------------------------------
# test_construct_equal_weight
# ---------------------------------------------------------------------------

def test_construct_equal_weight(constructor):
    """method='equal_weight' produces equal weights across all strategies."""
    result = constructor.construct(_EQUITY_CURVES, capital=CAPITAL, method="equal_weight")

    assert result.optimization_method == "equal_weight"
    weights = {a.genome_id: a.weight for a in result.allocations}
    expected = 1.0 / len(_EQUITY_CURVES)
    for w in weights.values():
        assert w == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# test_rebalance_check_triggers
# ---------------------------------------------------------------------------

def test_rebalance_check_triggers(constructor):
    """Drift exceeding the threshold triggers a rebalance."""
    target  = {"s1": 0.50, "s2": 0.30, "s3": 0.20}
    current = {"s1": 0.40, "s2": 0.35, "s3": 0.25}  # s1 drifted 10 pct points

    triggered = constructor.rebalance_check(target, current, threshold_pct=5.0)

    assert triggered is True


# ---------------------------------------------------------------------------
# test_rebalance_check_no_trigger
# ---------------------------------------------------------------------------

def test_rebalance_check_no_trigger(constructor):
    """Drift within the threshold does not trigger a rebalance."""
    target  = {"s1": 0.50, "s2": 0.30, "s3": 0.20}
    current = {"s1": 0.52, "s2": 0.29, "s3": 0.19}  # max drift = 2 pct points

    triggered = constructor.rebalance_check(target, current, threshold_pct=5.0)

    assert triggered is False
