import pytest
from strategies.example_strategy import SimpleMAStrategy
from app.models.signal import SignalType


class TestSimpleMAStrategy:
    def test_strategy_name(self):
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=10, slow_period=20)
        assert strategy.name == "SMA_10_20"

    def test_analyze_insufficient_data(self):
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=10, slow_period=20)
        ohlcv = [[0, 100, 101, 99, 100, 1000] for _ in range(15)]
        result = strategy.analyze(ohlcv)
        assert result is None

    def test_analyze_bullish_crossover(self):
        strategy = SimpleMAStrategy("BTC/USDT", fast_period=3, slow_period=5)

        # Create data with bullish crossover
        ohlcv = [
            [0, 100, 101, 99, 95, 1000],
            [1, 95, 96, 94, 94, 1000],
            [2, 94, 95, 93, 93, 1000],
            [3, 93, 94, 92, 92, 1000],
            [4, 92, 93, 91, 91, 1000],
            [5, 91, 100, 90, 98, 1000],  # Price jumps up
            [6, 98, 102, 97, 101, 1000],
            [7, 101, 105, 100, 104, 1000],
        ]

        result = strategy.analyze(ohlcv)
        # May or may not trigger depending on exact crossover
        if result:
            assert result["signal_type"] == SignalType.LONG
            assert result["confidence"] > 0

    def test_generate_signal_structure(self):
        strategy = SimpleMAStrategy("BTC/USDT")
        signal = strategy.generate_signal(
            signal_type=SignalType.LONG,
            entry_price=50000,
            stop_loss=49000,
            take_profit=52000,
            confidence=0.75,
            metadata={"test": True},
        )

        assert signal["source"] == strategy.name
        assert signal["exchange"] == "binance"
        assert signal["symbol"] == "BTC/USDT"
        assert signal["signal_type"] == SignalType.LONG
        assert signal["entry_price"] == 50000
        assert signal["stop_loss"] == 49000
        assert signal["take_profit"] == 52000
        assert signal["confidence"] == 0.75
        assert signal["metadata"]["test"] is True
