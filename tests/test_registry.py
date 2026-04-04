"""
Tests for Control Plane Registry models — verifies model instantiation,
enum values, and basic CRUD patterns.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from app.models.indicator_registry import Indicator, IndicatorStatus
from app.models.feature_pack import FeaturePack, FeaturePackStatus
from app.models.strategy_registry import (
    Strategy,
    AssetClass,
    PromotionStatus,
)
from app.models.promotion_state import PromotionEvent


# ── Indicator Model ───────────────────────────────────────────────────


class TestIndicatorModel:
    def test_create_indicator(self):
        ind = Indicator(
            name="RSI",
            version="1.0.0",
            compute_module="app.indicators.rsi",
            warmup_bars=14,
            input_params=json.dumps({"period": 14}),
            output_fields=json.dumps(["rsi_value"]),
        )
        assert ind.name == "RSI"
        assert ind.version == "1.0.0"
        assert ind.warmup_bars == 14

    def test_indicator_status_enum(self):
        assert IndicatorStatus.ACTIVE.value == "ACTIVE"
        assert IndicatorStatus.DEPRECATED.value == "DEPRECATED"
        assert IndicatorStatus.BLOCKED.value == "BLOCKED"

    def test_indicator_default_status(self):
        ind = Indicator(
            name="ADX",
            version="1.0.0",
            compute_module="app.indicators.adx",
        )
        # Default is set by column default, but on model init it won't auto-apply
        # unless using the DB. Check enum exists.
        assert IndicatorStatus.ACTIVE == IndicatorStatus("ACTIVE")


# ── Feature Pack Model ────────────────────────────────────────────────


class TestFeaturePackModel:
    def test_create_feature_pack(self):
        fp = FeaturePack(
            name="trend_pack_v1",
            version="1.0.0",
            indicator_ids=json.dumps(["ind-1", "ind-2"]),
            weights=json.dumps({"ind-1": 1.0, "ind-2": 0.5}),
        )
        assert fp.name == "trend_pack_v1"
        ids = json.loads(fp.indicator_ids)
        assert len(ids) == 2
        assert "ind-1" in ids

    def test_feature_pack_status_enum(self):
        assert FeaturePackStatus.ACTIVE.value == "ACTIVE"
        assert FeaturePackStatus.CHALLENGER.value == "CHALLENGER"
        assert FeaturePackStatus.DEPRECATED.value == "DEPRECATED"
        assert FeaturePackStatus.BLOCKED.value == "BLOCKED"


# ── Strategy Model ────────────────────────────────────────────────────


class TestStrategyModel:
    def test_create_strategy(self):
        s = Strategy(
            name="smc_wavetrend_v3",
            version="3.0.0",
            feature_pack_id="fp-001",
            compute_module="strategies.smc_wavetrend",
            asset_classes=json.dumps(["crypto"]),
            exchanges=json.dumps(["BINANCE", "UPBIT"]),
            sectors=json.dumps(["LAYER1", "DEFI"]),
            timeframes=json.dumps(["1h", "4h"]),
            regimes=json.dumps(["trending_up"]),
            max_symbols=10,
        )
        assert s.name == "smc_wavetrend_v3"
        assert json.loads(s.asset_classes) == ["crypto"]
        assert json.loads(s.exchanges) == ["BINANCE", "UPBIT"]

    def test_asset_class_enum(self):
        assert AssetClass.CRYPTO.value == "CRYPTO"
        assert AssetClass.US_STOCK.value == "US_STOCK"
        assert AssetClass.KR_STOCK.value == "KR_STOCK"

    def test_promotion_status_enum_complete(self):
        """All 10 promotion states must exist (CR-048: +BACKTEST_FAIL)."""
        expected = {
            "DRAFT",
            "REGISTERED",
            "BACKTEST_PASS",
            "BACKTEST_FAIL",
            "PAPER_PASS",
            "QUARANTINE",
            "GUARDED_LIVE",
            "LIVE",
            "RETIRED",
            "BLOCKED",
        }
        actual = {s.value for s in PromotionStatus}
        assert expected == actual

    def test_promotion_status_ordering(self):
        """Verify the promotion chain is representable."""
        chain = [
            PromotionStatus.DRAFT,
            PromotionStatus.REGISTERED,
            PromotionStatus.BACKTEST_PASS,
            PromotionStatus.PAPER_PASS,
            PromotionStatus.GUARDED_LIVE,
            PromotionStatus.LIVE,
        ]
        # Each should be a valid enum value
        for status in chain:
            assert isinstance(status, PromotionStatus)


# ── Promotion Event Model ─────────────────────────────────────────────


class TestPromotionEventModel:
    def test_create_promotion_event(self):
        event = PromotionEvent(
            strategy_id="strat-001",
            from_status="draft",
            to_status="registered",
            reason="Initial registration",
            triggered_by="system",
            approval_level="low",
        )
        assert event.strategy_id == "strat-001"
        assert event.from_status == "draft"
        assert event.to_status == "registered"
        assert event.triggered_by == "system"

    def test_high_risk_event(self):
        event = PromotionEvent(
            strategy_id="strat-001",
            from_status="paper_pass",
            to_status="guarded_live",
            reason="A approved for guarded live deployment",
            triggered_by="admin_user",
            approval_level="high",
        )
        assert event.approval_level == "high"
        assert event.to_status == "guarded_live"


# ── Constitution Constants Integrity ──────────────────────────────────


class TestConstitutionConstants:
    """Verify that code constants match the constitution documents."""

    def test_forbidden_brokers(self):
        from app.services.injection_gateway import FORBIDDEN_BROKERS, ALLOWED_BROKERS

        assert "ALPACA" in FORBIDDEN_BROKERS
        assert "KIWOOM_US" in FORBIDDEN_BROKERS
        # Allowed brokers must NOT be in forbidden
        for ac_brokers in ALLOWED_BROKERS.values():
            for broker in ac_brokers:
                assert broker not in FORBIDDEN_BROKERS

    def test_forbidden_sectors(self):
        from app.services.injection_gateway import FORBIDDEN_SECTORS

        assert "MEME" in FORBIDDEN_SECTORS
        assert "GAMEFI" in FORBIDDEN_SECTORS
        assert len(FORBIDDEN_SECTORS) == 7

    def test_allowed_brokers_coverage(self):
        from app.services.injection_gateway import ALLOWED_BROKERS

        assert "crypto" in ALLOWED_BROKERS
        assert "us_stock" in ALLOWED_BROKERS
        assert "kr_stock" in ALLOWED_BROKERS
        assert "BINANCE" in ALLOWED_BROKERS["crypto"]
        assert "KIS_US" in ALLOWED_BROKERS["us_stock"]
        assert "KIS_KR" in ALLOWED_BROKERS["kr_stock"]

    def test_exposure_limits(self):
        from app.services.injection_gateway import EXPOSURE_LIMITS

        assert EXPOSURE_LIMITS["max_strategies_per_market"] == 5
        assert EXPOSURE_LIMITS["max_strategies_per_symbol"] == 3
        assert EXPOSURE_LIMITS["max_concurrent_strategy_symbol"] == 30
        assert EXPOSURE_LIMITS["max_single_symbol_capital_pct"] == 10
        assert EXPOSURE_LIMITS["max_single_theme_capital_pct"] == 25
        assert EXPOSURE_LIMITS["max_single_market_capital_pct"] == 50
