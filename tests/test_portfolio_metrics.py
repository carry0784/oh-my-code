"""Tests for PortfolioMetricsCalculator — CR-043 Phase 6."""

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
from app.services.portfolio_metrics import PortfolioMetricsCalculator


INITIAL = 10_000.0


@pytest.fixture
def calc():
    return PortfolioMetricsCalculator()


# Helper: build an equity curve that grows linearly with a given per-step increment.
def _curve(n=100, start=10_000.0, step=10.0):
    return [start + i * step for i in range(n)]


# ---------------------------------------------------------------------------
# test_portfolio_equity_weighted
# ---------------------------------------------------------------------------


def test_portfolio_equity_weighted(calc):
    """Combined portfolio equity reflects the weighted blend of components."""
    curve_a = _curve(50, start=10_000.0, step=20.0)  # grows faster
    curve_b = _curve(50, start=10_000.0, step=10.0)  # grows slower
    weights = {"sA": 0.5, "sB": 0.5}
    equity_curves = {"sA": curve_a, "sB": curve_b}

    portfolio = calc.calculate_portfolio_equity(weights, equity_curves, INITIAL)

    # Portfolio should start at INITIAL and end above INITIAL
    assert portfolio[0] == pytest.approx(INITIAL, abs=1e-6)
    assert portfolio[-1] > INITIAL


# ---------------------------------------------------------------------------
# test_portfolio_return_pct
# ---------------------------------------------------------------------------


def test_portfolio_return_pct(calc):
    """Return percentage is (end - start) / start * 100."""
    curve = _curve(101, start=10_000.0, step=10.0)  # ends at 11_000 → +10 %
    weights = {"s1": 1.0}
    equity_curves = {"s1": curve}

    report = calc.calculate(weights, equity_curves, INITIAL)

    assert report.portfolio_return_pct == pytest.approx(10.0, abs=0.01)


# ---------------------------------------------------------------------------
# test_portfolio_max_drawdown
# ---------------------------------------------------------------------------


def test_portfolio_max_drawdown(calc):
    """Max drawdown is detected when equity falls from a peak."""
    # Rises then falls: peak at index 50 = 10_500, trough at index 100 = 10_000
    # drawdown ≈ 500/10_500 * 100 ≈ 4.76 %
    rise = [10_000.0 + i * 10.0 for i in range(51)]  # 10_000 → 10_500
    fall = [10_500.0 - i * 10.0 for i in range(1, 51)]  # 10_490 → 10_010
    curve = rise + fall
    weights = {"s1": 1.0}
    equity_curves = {"s1": curve}

    report = calc.calculate(weights, equity_curves, INITIAL)

    assert report.portfolio_max_drawdown_pct > 0.0
    assert report.portfolio_max_drawdown_pct == pytest.approx(
        (10_500 - 10_010) / 10_500 * 100, abs=0.5
    )


# ---------------------------------------------------------------------------
# test_portfolio_sharpe_positive
# ---------------------------------------------------------------------------


def test_portfolio_sharpe_positive(calc):
    """A consistently profitable portfolio yields a positive Sharpe ratio."""
    # 200 steps of steady growth → essentially positive excess returns every day
    curve = _curve(200, start=10_000.0, step=10.0)
    weights = {"s1": 1.0}
    equity_curves = {"s1": curve}

    report = calc.calculate(weights, equity_curves, INITIAL)

    assert report.portfolio_sharpe > 0.0


# ---------------------------------------------------------------------------
# test_effective_n_equal_weights
# ---------------------------------------------------------------------------


def test_effective_n_equal_weights(calc):
    """Equal weights across N strategies yield effective_n_strategies = N."""
    n = 4
    curves = {f"s{i}": _curve(50, start=10_000.0, step=(i + 1) * 5.0) for i in range(n)}
    weights = {f"s{i}": 1.0 / n for i in range(n)}

    report = calc.calculate(weights, curves, INITIAL)

    assert report.effective_n_strategies == pytest.approx(float(n), abs=1e-9)


# ---------------------------------------------------------------------------
# test_diversification_benefit
# ---------------------------------------------------------------------------


def test_diversification_benefit(calc):
    """Diversification benefit > 0 when component correlations are below 1."""
    # s1 grows steadily; s2 alternates up/down — low correlation
    curve1 = _curve(100, start=10_000.0, step=10.0)
    curve2 = [10_000.0 + (10.0 if i % 2 == 0 else -5.0) * i for i in range(100)]
    weights = {"s1": 0.5, "s2": 0.5}
    equity_curves = {"s1": curve1, "s2": curve2}

    report = calc.calculate(weights, equity_curves, INITIAL)

    assert report.diversification_benefit_pct > 0.0
