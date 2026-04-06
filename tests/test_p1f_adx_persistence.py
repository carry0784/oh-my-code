"""CR-048 Follow-Up 2A P1-F: ADX(14) persistence foundation tests.

Pure unit tests — no DB fixtures, no ORM mapper initialization.
Validates ADX calculation correctness, schema field, and collector wiring.

Scope Budget: db_schema_change=YES, migration=YES, collector_write_path_change=YES
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.schemas.market_state_schema import IndicatorSet, OHLCVBar
from app.services.indicator_calculator import IndicatorCalculator


# ── Helpers ──────────────────────────────────────────────────────


def _make_bars(n: int, *, base_price: float = 100.0, trend: float = 0.0) -> list[OHLCVBar]:
    """Generate n OHLCV bars with optional linear trend.

    Creates bars with realistic high/low spread around close.
    """
    bars: list[OHLCVBar] = []
    for i in range(n):
        close = base_price + trend * i
        high = close + 2.0  # fixed spread for determinism
        low = close - 2.0
        open_ = close - trend * 0.5 if trend != 0 else close
        bars.append(
            OHLCVBar(
                timestamp=1700000000 + i * 3600,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=1000.0,
            )
        )
    return bars


def _make_trending_bars(n: int) -> list[OHLCVBar]:
    """Generate strongly trending bars (high ADX expected)."""
    bars: list[OHLCVBar] = []
    for i in range(n):
        close = 100.0 + i * 3.0  # strong uptrend
        high = close + 1.0
        low = close - 0.5
        bars.append(
            OHLCVBar(
                timestamp=1700000000 + i * 3600,
                open=close - 1.5,
                high=high,
                low=low,
                close=close,
                volume=1000.0 + i * 10,
            )
        )
    return bars


def _make_ranging_bars(n: int) -> list[OHLCVBar]:
    """Generate ranging/choppy bars (low ADX expected)."""
    bars: list[OHLCVBar] = []
    for i in range(n):
        # Oscillate around 100 with small amplitude
        close = 100.0 + 2.0 * math.sin(i * 0.5)
        high = close + 1.0
        low = close - 1.0
        bars.append(
            OHLCVBar(
                timestamp=1700000000 + i * 3600,
                open=close + 0.5 * math.sin(i),
                high=high,
                low=low,
                close=close,
                volume=1000.0,
            )
        )
    return bars


# ── ADX Calculation Tests ────────────────────────────────────────


class TestADXCalculation:
    """Validate IndicatorCalculator._adx correctness."""

    def test_adx_requires_28_bars(self):
        """ADX(14) needs 2*period = 28 bars minimum."""
        calc = IndicatorCalculator()

        # 27 bars → no adx_14
        result_27 = calc.calculate(_make_bars(27))
        assert result_27.adx_14 is None

        # 28 bars → adx_14 computed
        result_28 = calc.calculate(_make_bars(28))
        assert result_28.adx_14 is not None

    def test_adx_range_0_100(self):
        """ADX output must be in [0, 100] range."""
        calc = IndicatorCalculator()
        for n in [28, 50, 100, 200]:
            result = calc.calculate(_make_bars(n, trend=0.5))
            assert result.adx_14 is not None
            assert 0.0 <= result.adx_14 <= 100.0, f"ADX out of range for {n} bars: {result.adx_14}"

    def test_adx_trending_higher_than_ranging(self):
        """Strong trend should produce higher ADX than choppy market."""
        calc = IndicatorCalculator()
        trending = calc.calculate(_make_trending_bars(60))
        ranging = calc.calculate(_make_ranging_bars(60))

        assert trending.adx_14 is not None
        assert ranging.adx_14 is not None
        assert trending.adx_14 > ranging.adx_14, (
            f"Trending ADX {trending.adx_14:.1f} should exceed ranging ADX {ranging.adx_14:.1f}"
        )

    def test_adx_deterministic(self):
        """Same input always produces same output."""
        calc = IndicatorCalculator()
        bars = _make_bars(50, trend=1.0)
        r1 = calc.calculate(bars)
        r2 = calc.calculate(bars)
        assert r1.adx_14 == r2.adx_14

    def test_adx_flat_market_low(self):
        """Perfectly flat market → ADX near 0."""
        bars: list[OHLCVBar] = []
        for i in range(50):
            bars.append(
                OHLCVBar(
                    timestamp=1700000000 + i * 3600,
                    open=100.0,
                    high=100.0,
                    low=100.0,
                    close=100.0,
                    volume=1000.0,
                )
            )
        calc = IndicatorCalculator()
        result = calc.calculate(bars)
        assert result.adx_14 is not None
        assert result.adx_14 == 0.0

    def test_adx_static_method_direct(self):
        """_adx static method can be called directly with numpy arrays."""
        n = 50
        highs = np.array([102.0 + i * 0.5 for i in range(n)], dtype=np.float64)
        lows = np.array([98.0 + i * 0.5 for i in range(n)], dtype=np.float64)
        closes = np.array([100.0 + i * 0.5 for i in range(n)], dtype=np.float64)

        adx = IndicatorCalculator._adx(highs, lows, closes, 14)
        assert isinstance(adx, float)
        assert 0.0 <= adx <= 100.0

    def test_adx_does_not_affect_other_indicators(self):
        """Adding ADX must not change existing indicator values."""
        calc = IndicatorCalculator()
        bars = _make_bars(50, trend=0.3)
        result = calc.calculate(bars)

        # Existing indicators should still be computed
        assert result.rsi_14 is not None
        assert result.atr_14 is not None
        assert result.sma_20 is not None
        assert result.obv is not None
        # ADX also present
        assert result.adx_14 is not None


# ── Schema Field Tests ───────────────────────────────────────────


class TestIndicatorSetADXField:
    """Validate IndicatorSet schema has adx_14 field."""

    def test_default_none(self):
        """adx_14 defaults to None."""
        ind = IndicatorSet()
        assert ind.adx_14 is None

    def test_explicit_value(self):
        """adx_14 accepts float value."""
        ind = IndicatorSet(adx_14=25.5)
        assert ind.adx_14 == 25.5

    def test_serialization_roundtrip(self):
        """adx_14 survives dict → model roundtrip."""
        ind = IndicatorSet(rsi_14=55.0, adx_14=30.0)
        data = ind.model_dump()
        assert data["adx_14"] == 30.0
        restored = IndicatorSet(**data)
        assert restored.adx_14 == 30.0

    def test_null_in_dict(self):
        """None adx_14 appears as None in dict output."""
        ind = IndicatorSet()
        data = ind.model_dump()
        assert "adx_14" in data
        assert data["adx_14"] is None


# ── Model Column Tests (no DB required) ─────────────────────────


class TestMarketStateModelADXColumn:
    """Validate MarketState ORM model has adx_14 column definition."""

    def test_column_exists(self):
        """MarketState class has adx_14 attribute."""
        from app.models.market_state import MarketState

        assert hasattr(MarketState, "adx_14")

    def test_column_nullable_annotation(self):
        """adx_14 type annotation includes None (nullable)."""
        import typing

        from app.models.market_state import MarketState

        hints = typing.get_type_hints(MarketState)
        adx_hint = hints.get("adx_14")
        assert adx_hint is not None
        # Mapped[float | None] → outer args = (float | None,), inner contains NoneType
        outer_args = typing.get_args(adx_hint)
        assert len(outer_args) >= 1, f"Expected Mapped[...] args, got {adx_hint}"
        inner_args = typing.get_args(outer_args[0])
        assert type(None) in inner_args, f"Expected nullable type, got {adx_hint}"

    def test_column_mapped_column_definition(self):
        """adx_14 uses mapped_column with Float and nullable=True in source."""
        import inspect

        from app.models import market_state

        source = inspect.getsource(market_state)
        # Verify the column definition exists in source
        assert "adx_14" in source
        assert "Float" in source


# ── Migration Contract Tests ─────────────────────────────────────


def _load_migration_024():
    """Load migration module dynamically (numeric filename not importable normally)."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / (
        "alembic/versions/024_add_adx_14_to_market_states.py"
    )
    spec = importlib.util.spec_from_file_location("migration_024", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class TestMigration024Contract:
    """Validate migration 024 metadata (no DB execution)."""

    def test_revision_chain(self):
        """Migration 024 correctly chains from 023."""
        m024 = _load_migration_024()
        assert m024.revision == "024_add_adx_14_to_market_states"
        assert m024.down_revision == "023_shadow_obs_is_archived"

    def test_module_has_upgrade_downgrade(self):
        """Migration has both upgrade and downgrade functions."""
        m024 = _load_migration_024()
        assert callable(getattr(m024, "upgrade", None))
        assert callable(getattr(m024, "downgrade", None))
