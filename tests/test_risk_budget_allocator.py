"""Tests for RiskBudgetAllocator — CR-043 Phase 6."""

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
from app.services.risk_budget_allocator import RiskBudgetAllocator, RiskBudget


TOTAL_RISK = 20.0


@pytest.fixture
def allocator():
    return RiskBudgetAllocator(total_risk_pct=TOTAL_RISK)


# ---------------------------------------------------------------------------
# test_simple_proportional
# ---------------------------------------------------------------------------


def test_simple_proportional(allocator):
    """Without volatilities, each strategy gets total_risk * weight."""
    weights = {"s1": 0.6, "s2": 0.4}
    budget = allocator.allocate(weights)

    assert budget.strategy_budgets["s1"] == pytest.approx(TOTAL_RISK * 0.6, abs=1e-9)
    assert budget.strategy_budgets["s2"] == pytest.approx(TOTAL_RISK * 0.4, abs=1e-9)


# ---------------------------------------------------------------------------
# test_vol_adjusted_allocation
# ---------------------------------------------------------------------------


def test_vol_adjusted_allocation(allocator):
    """Lower-volatility strategy receives a larger share of the risk budget."""
    weights = {"s_low": 0.5, "s_high": 0.5}
    volatilities = {"s_low": 0.01, "s_high": 0.05}

    budget = allocator.allocate(weights, volatilities)

    assert budget.strategy_budgets["s_low"] > budget.strategy_budgets["s_high"]


# ---------------------------------------------------------------------------
# test_budget_sums_to_total
# ---------------------------------------------------------------------------


def test_budget_sums_to_total(allocator):
    """All strategy budgets must sum to total_risk_pct."""
    weights = {"s1": 0.3, "s2": 0.5, "s3": 0.2}
    budget = allocator.allocate(weights)

    total = sum(budget.strategy_budgets.values())
    assert total == pytest.approx(TOTAL_RISK, abs=1e-9)


# ---------------------------------------------------------------------------
# test_check_breach_detects
# ---------------------------------------------------------------------------


def test_check_breach_detects(allocator):
    """A drawdown exceeding the allocated budget is reported as a breach."""
    weights = {"s1": 0.5, "s2": 0.5}
    budget = allocator.allocate(weights)
    # s1 budget = 10.0; set drawdown to 15.0 → breach
    current_drawdowns = {"s1": 15.0, "s2": 5.0}

    breached = allocator.check_breach(budget, current_drawdowns)

    assert "s1" in breached
    assert "s2" not in breached


# ---------------------------------------------------------------------------
# test_check_breach_no_breach
# ---------------------------------------------------------------------------


def test_check_breach_no_breach(allocator):
    """All drawdowns within budget produce an empty breach list."""
    weights = {"s1": 0.5, "s2": 0.5}
    budget = allocator.allocate(weights)
    # Both drawdowns well below their 10.0 budgets
    current_drawdowns = {"s1": 2.0, "s2": 3.0}

    breached = allocator.check_breach(budget, current_drawdowns)

    assert breached == []
