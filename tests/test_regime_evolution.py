"""Tests for RegimeEvolutionManager — CR-042 Phase 5."""

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

import pytest

from app.services.regime_evolution import RegimeEvolutionManager, RegimeSegment

# Small OHLCV dataset (100 bars)
_OHLCV = [[1_000_000 + i * 60_000, 100 + i * 0.1, 101 + i * 0.1,
           99 + i * 0.1, 100.5 + i * 0.1, 1000] for i in range(100)]


def test_regime_tags_list():
    """get_regime_tags returns exactly the 5 expected canonical regime labels."""
    mgr = RegimeEvolutionManager()
    tags = mgr.get_regime_tags()
    assert isinstance(tags, list)
    assert len(tags) == 5
    expected = {"bull_trend", "bear_trend", "high_volatility", "ranging", "crisis"}
    assert set(tags) == expected


def test_identify_regime_segments():
    """Contiguous runs of the same regime label are merged into one segment."""
    mgr = RegimeEvolutionManager()
    ohlcv = _OHLCV[:6]
    # Pattern: [A, A, A, B, B, C] → 3 segments
    regimes = ["bull_trend", "bull_trend", "bull_trend", "ranging", "ranging", "crisis"]
    segments = mgr.identify_regime_segments(ohlcv, regimes)

    assert len(segments) == 3

    seg0 = segments[0]
    assert seg0.regime == "bull_trend"
    assert seg0.start_idx == 0
    assert seg0.end_idx == 2
    assert len(seg0.bars) == 3

    seg1 = segments[1]
    assert seg1.regime == "ranging"
    assert seg1.start_idx == 3
    assert seg1.end_idx == 4
    assert len(seg1.bars) == 2

    seg2 = segments[2]
    assert seg2.regime == "crisis"
    assert seg2.start_idx == 5
    assert seg2.end_idx == 5
    assert len(seg2.bars) == 1


def test_identify_segments_single_regime():
    """When all bars share the same regime, exactly 1 segment is returned."""
    mgr = RegimeEvolutionManager()
    ohlcv = _OHLCV[:5]
    regimes = ["ranging"] * 5
    segments = mgr.identify_regime_segments(ohlcv, regimes)

    assert len(segments) == 1
    assert segments[0].regime == "ranging"
    assert segments[0].start_idx == 0
    assert segments[0].end_idx == 4
    assert len(segments[0].bars) == 5


def test_select_active_strategies_matching():
    """Returns the population assigned to the exact current regime."""
    mgr = RegimeEvolutionManager()

    bull_pop = ["strategy_A", "strategy_B"]
    bear_pop = ["strategy_C"]
    populations = {
        "bull_trend": bull_pop,
        "bear_trend": bear_pop,
    }

    result = mgr.select_active_strategies("bull_trend", populations)
    assert result == bull_pop


def test_select_active_strategies_fallback():
    """When no population matches the regime, all strategies are returned."""
    mgr = RegimeEvolutionManager()

    populations = {
        "bull_trend": ["A", "B"],
        "ranging": ["C"],
    }

    result = mgr.select_active_strategies("crisis", populations)
    # Fallback: union of all populations
    assert len(result) == 3
    assert set(result) == {"A", "B", "C"}
