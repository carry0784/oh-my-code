"""Tests for PortfolioOptimizer — CR-043 Phase 6."""

import sys
from unittest.mock import MagicMock

_STUB_MODULES = [
    "ccxt",
    "ccxt.async_support",
    "aiohttp",
    "celery",
    "redis",
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.orm",
    "sqlalchemy.pool",
    "sqlalchemy.engine",
    "app.core.database",
    "app.core.config",
    "structlog",
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
from app.services.portfolio_optimizer import PortfolioOptimizer, OptimizationConstraints


@pytest.fixture
def optimizer():
    return PortfolioOptimizer()


# Deterministic return series used across tests:
# s1: low volatility  (step 0.001)
# s2: high volatility (step 0.01)
_LOW_VOL = [0.001 * (1 if i % 2 == 0 else -1) for i in range(40)]
_HIGH_VOL = [0.010 * (1 if i % 2 == 0 else -1) for i in range(40)]
_RETURNS_2 = {"s1": _LOW_VOL, "s2": _HIGH_VOL}

# Three strategies with distinctly different but positive returns for max-Sharpe
_POS_A = [0.005] * 40
_POS_B = [0.003] * 40
_POS_C = [0.001] * 40
_RETURNS_3 = {"sA": _POS_A, "sB": _POS_B, "sC": _POS_C}


# ---------------------------------------------------------------------------
# test_equal_weight
# ---------------------------------------------------------------------------


def test_equal_weight(optimizer):
    """N strategies each receive weight 1/N."""
    returns = {"s1": _LOW_VOL, "s2": _HIGH_VOL, "s3": _POS_A}
    weights = optimizer.optimize_equal_weight(returns)

    assert set(weights.keys()) == {"s1", "s2", "s3"}
    for w in weights.values():
        assert w == pytest.approx(1.0 / 3, abs=1e-9)


# ---------------------------------------------------------------------------
# test_risk_parity_lower_vol_gets_more
# ---------------------------------------------------------------------------


def test_risk_parity_lower_vol_gets_more(optimizer):
    """In risk parity, the lower-volatility strategy receives a higher weight."""
    weights = optimizer.optimize_risk_parity(_RETURNS_2)

    assert weights["s1"] > weights["s2"]


# ---------------------------------------------------------------------------
# test_risk_parity_weights_sum_to_one
# ---------------------------------------------------------------------------


def test_risk_parity_weights_sum_to_one(optimizer):
    """Risk-parity weights must sum to 1.0 after constraint application."""
    weights = optimizer.optimize_risk_parity(_RETURNS_2)

    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# test_min_variance_weights_sum_to_one
# ---------------------------------------------------------------------------


def test_min_variance_weights_sum_to_one(optimizer):
    """Min-variance weights must sum to 1.0 after constraint application."""
    weights = optimizer.optimize_min_variance(_RETURNS_2)

    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# test_max_sharpe_weights_sum_to_one
# ---------------------------------------------------------------------------


def test_max_sharpe_weights_sum_to_one(optimizer):
    """Max-Sharpe weights must sum to 1.0 after constraint application."""
    weights = optimizer.optimize_max_sharpe(_RETURNS_3)

    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# test_constraints_cap_max_weight
# ---------------------------------------------------------------------------


def test_constraints_cap_max_weight(optimizer):
    """No individual weight may exceed max_weight after constraint application."""
    # With 3 strategies and max_weight=0.4, the dominant strategy must be capped.
    constraints = OptimizationConstraints(max_weight=0.4, min_weight=0.0)
    weights = optimizer.optimize_risk_parity(_RETURNS_3, constraints)

    for w in weights.values():
        assert w <= constraints.max_weight + 1e-9


# ---------------------------------------------------------------------------
# test_empty_returns_empty_weights
# ---------------------------------------------------------------------------


def test_empty_returns_empty_weights(optimizer):
    """An empty input dict returns an empty weight dict for all methods."""
    assert optimizer.optimize_equal_weight({}) == {}
    assert optimizer.optimize_risk_parity({}) == {}
    assert optimizer.optimize_min_variance({}) == {}
    assert optimizer.optimize_max_sharpe({}) == {}
