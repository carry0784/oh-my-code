"""Tests for CorrelationAnalyzer — CR-043 Phase 6."""

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
from app.services.correlation_analyzer import CorrelationAnalyzer, CorrelationMatrix


@pytest.fixture
def analyzer():
    return CorrelationAnalyzer()


# ---------------------------------------------------------------------------
# test_single_strategy_identity
# ---------------------------------------------------------------------------

def test_single_strategy_identity(analyzer):
    """1 strategy returns a 1x1 identity matrix with avg_correlation=0.0."""
    returns = {"s1": [0.01, -0.005, 0.02, 0.003, -0.001]}
    result = analyzer.compute_from_returns(returns)

    assert result.genome_ids == ["s1"]
    assert result.matrix.shape == (1, 1)
    assert result.matrix[0, 0] == pytest.approx(1.0)
    assert result.avg_correlation == pytest.approx(0.0)
    assert result.diversification_ratio == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# test_identical_returns_perfect_correlation
# ---------------------------------------------------------------------------

def test_identical_returns_perfect_correlation(analyzer):
    """Two strategies with the same return series produce correlation = 1.0."""
    series = [0.01, -0.005, 0.02, 0.003, -0.01, 0.015, -0.002, 0.008]
    returns = {"s1": series[:], "s2": series[:]}

    result = analyzer.compute_from_returns(returns)

    # Off-diagonal element (and avg / max) should be 1.0
    assert result.matrix[0, 1] == pytest.approx(1.0, abs=1e-6)
    assert result.max_pairwise == pytest.approx(1.0, abs=1e-6)
    assert result.avg_correlation == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# test_uncorrelated_returns
# ---------------------------------------------------------------------------

def test_uncorrelated_returns(analyzer):
    """Strategies with opposite-sign returns yield negative/low correlation."""
    pos = [0.01, 0.02, 0.005, 0.015, 0.01, 0.03, 0.005, 0.02]
    neg = [-v for v in pos]
    returns = {"s1": pos, "s2": neg}

    result = analyzer.compute_from_returns(returns)

    # Perfectly anti-correlated series → correlation should be close to -1.0
    assert result.matrix[0, 1] < 0.0
    assert result.avg_correlation < 0.0


# ---------------------------------------------------------------------------
# test_compute_from_equity
# ---------------------------------------------------------------------------

def test_compute_from_equity(analyzer):
    """Equity curves are converted to returns before correlation is computed."""
    # Two identical steady-growth curves → perfect correlation
    curve = [10000 + i * 10 for i in range(50)]
    equity = {"s1": list(curve), "s2": list(curve)}

    result = analyzer.compute_from_equity(equity)

    assert len(result.genome_ids) == 2
    # Identical normalized growth → corr = 1.0
    assert result.matrix[0, 1] == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# test_identify_clusters_high_threshold
# ---------------------------------------------------------------------------

def test_identify_clusters_high_threshold(analyzer):
    """With threshold=0.99 anti-correlated strategies form no shared cluster."""
    pos = [0.01, 0.02, 0.005, 0.015, 0.01, 0.03, 0.005, 0.02]
    neg = [-v for v in pos]
    returns = {"s1": pos, "s2": neg}

    matrix = analyzer.compute_from_returns(returns)
    clusters = analyzer.identify_clusters(matrix, threshold=0.99)

    # Each strategy should be in its own singleton cluster
    assert len(clusters) == 2
    for cluster in clusters:
        assert len(cluster) == 1


# ---------------------------------------------------------------------------
# test_identify_clusters_groups_correlated
# ---------------------------------------------------------------------------

def test_identify_clusters_groups_correlated(analyzer):
    """Highly correlated strategies are placed in the same cluster."""
    series = [0.01, -0.005, 0.02, 0.003, -0.01, 0.015, -0.002, 0.008]
    # s1 and s2 are identical → corr 1.0; s3 is anti-correlated
    returns = {
        "s1": series[:],
        "s2": series[:],
        "s3": [-v for v in series],
    }

    matrix = analyzer.compute_from_returns(returns)
    clusters = analyzer.identify_clusters(matrix, threshold=0.9)

    # s1 and s2 should share a cluster
    cluster_sizes = sorted(len(c) for c in clusters)
    assert 2 in cluster_sizes  # at least one cluster of size 2
