"""Tests for SentimentCollector — CR-038 Phase 1."""

import sys
from unittest.mock import MagicMock, patch

# Stub external dependencies before imports
_STUB_MODULES = [
    "ccxt", "ccxt.async_support",
    "celery", "redis", "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
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

from app.services.sentiment_collector import SentimentCollector


class _FakeResponse:
    def __init__(self, status=200, json_data=None):
        self.status = status
        self._json = json_data or {}

    async def json(self):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _FakeSession:
    """Fake aiohttp session that routes URLs to different responses."""

    def __init__(self, responses=None, default_response=None):
        self._responses = responses or {}
        self._default = default_response or _FakeResponse(status=404)

    def get(self, url):
        for key, resp in self._responses.items():
            if key in url:
                return resp
        return self._default

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestSentimentCollectorFearGreed:
    @pytest.mark.asyncio
    async def test_collect_fear_greed_success(self):
        responses = {
            "alternative.me": _FakeResponse(200, {
                "data": [{"value": "25", "value_classification": "Extreme Fear"}]
            }),
            "blockchain.info/stats": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.fear_greed_index == 25
        assert result.fear_greed_label == "Extreme Fear"
        assert result.collected_at is not None

    @pytest.mark.asyncio
    async def test_collect_fear_greed_greed(self):
        responses = {
            "alternative.me": _FakeResponse(200, {
                "data": [{"value": "75", "value_classification": "Greed"}]
            }),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.fear_greed_index == 75
        assert result.fear_greed_label == "Greed"

    @pytest.mark.asyncio
    async def test_fear_greed_http_error(self):
        responses = {
            "alternative.me": _FakeResponse(500),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.fear_greed_index is None

    @pytest.mark.asyncio
    async def test_collect_malformed_json(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": []}),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        # Empty data array causes IndexError → caught by except → returns None
        assert result.fear_greed_index is None


class TestSentimentCollectorBlockchain:
    @pytest.mark.asyncio
    async def test_blockchain_stats_collected(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": [{"value": "50"}]}),
            "blockchain.info/stats": _FakeResponse(200, {
                "hash_rate": 500_000_000_000_000,  # 500 TH/s after /1e9
                "difficulty": 83_000_000_000_000,
                "n_tx": 350000,
                "n_tx_unconfirmed": 12000,
                "blocks_size": 1500000,
            }),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.on_chain.hash_rate == pytest.approx(500000.0)
        assert result.on_chain.difficulty == 83_000_000_000_000
        assert result.on_chain.tx_count_24h == 350000
        assert result.on_chain.mempool_size == 12000

    @pytest.mark.asyncio
    async def test_blockchain_stats_failure_graceful(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": [{"value": "50"}]}),
            "blockchain.info": _FakeResponse(503),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.on_chain.hash_rate is None
        assert result.fear_greed_index == 50  # Other sources still work


class TestSentimentCollectorMempool:
    @pytest.mark.asyncio
    async def test_mempool_fees_collected(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": [{"value": "50"}]}),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {
                "fastestFee": 45,
                "halfHourFee": 30,
                "hourFee": 15,
            }),
            "mempool.space/api/mempool": _FakeResponse(200, {
                "vsize": 50_000_000,  # 50 MB
            }),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.on_chain.mempool_fee_fast == 45
        assert result.on_chain.mempool_fee_medium == 30
        assert result.on_chain.mempool_fee_slow == 15
        assert result.on_chain.mempool_vsize == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_mempool_failure_graceful(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": [{"value": "50"}]}),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space": _FakeResponse(503),
            "coingecko.com": _FakeResponse(200, {"data": {}}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.on_chain.mempool_fee_fast is None


class TestSentimentCollectorCoinGecko:
    @pytest.mark.asyncio
    async def test_coingecko_global_collected(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": [{"value": "50"}]}),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(200, {"data": {
                "market_cap_percentage": {"btc": 54.3},
                "total_market_cap": {"usd": 2_500_000_000_000},
                "total_volume": {"usd": 150_000_000_000},
            }}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.on_chain.btc_dominance == 54.3
        assert result.on_chain.total_market_cap_usd == 2_500_000_000_000
        assert result.on_chain.total_volume_24h_usd == 150_000_000_000

    @pytest.mark.asyncio
    async def test_coingecko_failure_graceful(self):
        responses = {
            "alternative.me": _FakeResponse(200, {"data": [{"value": "50"}]}),
            "blockchain.info": _FakeResponse(200, {}),
            "mempool.space/api/v1/fees": _FakeResponse(200, {}),
            "mempool.space/api/mempool": _FakeResponse(200, {}),
            "coingecko.com": _FakeResponse(429),  # Rate limited
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.on_chain.btc_dominance is None
        assert result.fear_greed_index == 50  # Other sources still work


class TestSentimentCollectorFullIntegration:
    @pytest.mark.asyncio
    async def test_all_sources_collected(self):
        responses = {
            "alternative.me": _FakeResponse(200, {
                "data": [{"value": "40", "value_classification": "Fear"}]
            }),
            "blockchain.info/stats": _FakeResponse(200, {
                "hash_rate": 600_000_000_000_000,
                "difficulty": 85_000_000_000_000,
                "n_tx": 400000,
                "n_tx_unconfirmed": 8000,
                "blocks_size": 1200000,
            }),
            "mempool.space/api/v1/fees": _FakeResponse(200, {
                "fastestFee": 35, "halfHourFee": 20, "hourFee": 10,
            }),
            "mempool.space/api/mempool": _FakeResponse(200, {"vsize": 30_000_000}),
            "coingecko.com": _FakeResponse(200, {"data": {
                "market_cap_percentage": {"btc": 55.1},
                "total_market_cap": {"usd": 2_800_000_000_000},
                "total_volume": {"usd": 180_000_000_000},
            }}),
        }
        fake_session = _FakeSession(responses)

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        # Sentiment
        assert result.fear_greed_index == 40
        assert result.fear_greed_label == "Fear"

        # On-chain
        assert result.on_chain.hash_rate == pytest.approx(600000.0)
        assert result.on_chain.tx_count_24h == 400000
        assert result.on_chain.mempool_fee_fast == 35
        assert result.on_chain.mempool_vsize == pytest.approx(30.0)
        assert result.on_chain.btc_dominance == 55.1
        assert result.on_chain.total_market_cap_usd == 2_800_000_000_000

        # Source composite
        assert "blockchain.com" in result.source
        assert "mempool.space" in result.source
        assert "coingecko" in result.source

    @pytest.mark.asyncio
    async def test_all_sources_fail_gracefully(self):
        """Even if all external APIs fail, collector returns valid result."""
        fake_session = _FakeSession({}, _FakeResponse(503))

        with patch.object(SentimentCollector, "_create_session", return_value=fake_session):
            collector = SentimentCollector()
            result = await collector.collect()

        assert result.fear_greed_index is None
        assert result.on_chain.hash_rate is None
        assert result.on_chain.btc_dominance is None
        assert result.collected_at is not None
