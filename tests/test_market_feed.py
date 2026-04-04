"""
B-09: Market Feed Tests — read-only best bid/ask/spread service
"""

import pytest


class TestMarketFeedSchema:
    def test_schema_imports(self):
        from app.schemas.market_feed_schema import (
            MarketFeedResponse, MarketFeedSummary, QuoteEntry, VenueFeedSummary,
        )
        assert MarketFeedResponse is not None

    def test_default_response(self):
        from app.schemas.market_feed_schema import MarketFeedResponse
        r = MarketFeedResponse()
        assert r.summary.venues_total == 3
        assert r.summary.stale_threshold_seconds == 120
        assert "Read-only" in r.feed_note

    def test_quote_entry_shape(self):
        from app.schemas.market_feed_schema import QuoteEntry
        q = QuoteEntry(exchange="binance", symbol="BTCUSDT", bid=50000.0, ask=50001.0,
                       spread=1.0, last=50000.5, trust_state="LIVE", is_stale=False)
        assert q.bid == 50000.0
        assert q.spread == 1.0
        assert q.trust_state == "LIVE"

    def test_venue_summary_shape(self):
        from app.schemas.market_feed_schema import VenueFeedSummary
        v = VenueFeedSummary(exchange="binance", trust_state="LIVE", live_count=3, total_symbols=3)
        assert v.supported is True

    def test_stale_flag(self):
        from app.schemas.market_feed_schema import QuoteEntry
        q = QuoteEntry(exchange="binance", symbol="BTC", age_seconds=200, is_stale=True)
        assert q.is_stale is True


class TestMarketFeedService:
    def test_build_from_empty(self):
        from app.core.market_feed_service import build_market_feed_from_quote_data
        r = build_market_feed_from_quote_data(None)
        assert r.summary.venues_connected == 0

    def test_build_from_quote_data(self):
        from app.core.market_feed_service import build_market_feed_from_quote_data
        mock_data = {
            "binance": {
                "_venue_summary": {"trust_state": "LIVE", "live_count": 1, "stale_count": 0},
                "symbols": {
                    "BTCUSDT": {
                        "bid": 50000, "ask": 50001, "spread": 1.0, "last": 50000.5,
                        "as_of": "2026-03-25T00:00:00Z", "age_seconds": 5, "trust_state": "LIVE",
                    },
                },
            },
        }
        r = build_market_feed_from_quote_data(mock_data)
        assert r.summary.venues_connected == 1
        assert r.summary.total_live == 1
        assert len(r.quotes) == 1
        assert r.quotes[0].exchange == "binance"
        assert r.quotes[0].trust_state == "LIVE"
        assert r.quotes[0].is_stale is False

    def test_stale_detection(self):
        from app.core.market_feed_service import build_market_feed_from_quote_data
        mock_data = {
            "upbit": {
                "_venue_summary": {"trust_state": "STALE", "live_count": 0, "stale_count": 1},
                "symbols": {
                    "ETHUSDT": {
                        "bid": 3000, "ask": 3001, "spread": 1.0, "last": 3000.5,
                        "as_of": "2026-03-25T00:00:00Z", "age_seconds": 200, "trust_state": "STALE",
                    },
                },
            },
        }
        r = build_market_feed_from_quote_data(mock_data)
        assert r.quotes[0].is_stale is True
        assert r.summary.total_stale == 1

    def test_empty_market_feed(self):
        from app.core.market_feed_service import build_empty_market_feed
        r = build_empty_market_feed()
        assert len(r.venues) == 3
        assert all(v.trust_state == "NOT_QUERIED" for v in r.venues)

    def test_worst_trust_aggregation(self):
        from app.core.market_feed_service import build_market_feed_from_quote_data
        mock = {
            "binance": {"_venue_summary": {"trust_state": "LIVE", "live_count": 1, "stale_count": 0}, "symbols": {}},
            "upbit": {"_venue_summary": {"trust_state": "DISCONNECTED", "live_count": 0, "stale_count": 0}, "symbols": {}},
        }
        r = build_market_feed_from_quote_data(mock)
        assert r.summary.worst_trust == "DISCONNECTED"


class TestReadOnlyProperty:
    def test_no_write_in_service(self):
        import inspect
        from app.core import market_feed_service
        src = inspect.getsource(market_feed_service)
        forbidden = ["db.add", "db.delete", "session.commit", "submit_order", "create_order"]
        for f in forbidden:
            assert f not in src

    def test_no_execution_in_schema(self):
        from app.schemas import market_feed_schema
        assert not hasattr(market_feed_schema, "execute_trade")
        assert not hasattr(market_feed_schema, "place_order")


class TestExcludedScope:
    def test_no_orderbook_field_in_schema(self):
        """Schema models should not have orderbook or depth fields."""
        from app.schemas.market_feed_schema import MarketFeedResponse, QuoteEntry
        assert "orderbook" not in MarketFeedResponse.model_fields
        assert "depth" not in QuoteEntry.model_fields

    def test_supported_exchanges_crypto_only(self):
        from app.core.market_feed_service import _SUPPORTED_EXCHANGES
        assert len(_SUPPORTED_EXCHANGES) == 3
        assert set(_SUPPORTED_EXCHANGES) == {"binance", "upbit", "bitget"}
        assert "kis" not in _SUPPORTED_EXCHANGES
        assert "kiwoom" not in _SUPPORTED_EXCHANGES
        assert "okx" not in _SUPPORTED_EXCHANGES


class TestSupportedExchangesSSOT:
    """SSOT: app.core.config defines the whitelist, all other modules reference it."""

    def test_ssot_crypto_list(self):
        from app.core.config import SUPPORTED_EXCHANGES_CRYPTO
        assert set(SUPPORTED_EXCHANGES_CRYPTO) == {"binance", "upbit", "bitget"}

    def test_ssot_stock_list(self):
        from app.core.config import SUPPORTED_EXCHANGES_STOCK
        assert set(SUPPORTED_EXCHANGES_STOCK) == {"kis", "kiwoom"}

    def test_ssot_all_list(self):
        from app.core.config import SUPPORTED_EXCHANGES_ALL
        assert set(SUPPORTED_EXCHANGES_ALL) == {"binance", "upbit", "bitget", "kis", "kiwoom"}

    def test_okx_not_in_any_list(self):
        from app.core.config import SUPPORTED_EXCHANGES_ALL
        assert "okx" not in SUPPORTED_EXCHANGES_ALL

    def test_factory_source_has_no_okx(self):
        """Factory source code must not contain okx as a supported exchange."""
        from pathlib import Path
        factory_path = Path(__file__).resolve().parent.parent / "exchanges" / "factory.py"
        content = factory_path.read_text(encoding="utf-8")
        assert "okx" not in content.lower(), "factory.py must not reference OKX"
        assert "binance" in content
        assert "upbit" in content
        assert "bitget" in content

    def test_factory_registry_no_okx(self):
        """Factory _FACTORY_REGISTRY must not contain okx."""
        from pathlib import Path
        factory_path = Path(__file__).resolve().parent.parent / "exchanges" / "factory.py"
        content = factory_path.read_text(encoding="utf-8")
        assert "okx" not in content.lower()
        assert "Unsupported exchange" in content


class TestV2Integration:
    def test_v2_references_market_feed(self):
        import inspect
        from app.api.routes.dashboard import dashboard_data_v2
        src = inspect.getsource(dashboard_data_v2)
        assert "market_feed" in src

    def test_market_feed_endpoint_exists(self):
        from app.api.routes.dashboard import market_feed
        assert market_feed is not None
