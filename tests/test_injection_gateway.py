"""
Tests for Injection Gateway — validates forbidden broker/sector enforcement,
dependency checks, and market matrix compatibility.

These tests use mocked DB sessions to avoid infrastructure dependencies.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.injection_gateway import (
    InjectionGateway,
    GatewayVerdict,
    FORBIDDEN_BROKERS,
    FORBIDDEN_SECTORS,
    ALLOWED_BROKERS,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_db():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    return db


def _strategy_data(**overrides) -> dict:
    """Create a valid strategy registration request."""
    base = {
        "name": "test_strategy",
        "version": "1.0.0",
        "feature_pack_id": "fp-001",
        "compute_module": "strategies.test",
        "asset_classes": json.dumps(["crypto"]),
        "exchanges": json.dumps(["BINANCE"]),
        "sectors": json.dumps(["LAYER1"]),
        "timeframes": json.dumps(["1h"]),
        "regimes": json.dumps(["trending_up"]),
        "max_symbols": 10,
    }
    base.update(overrides)
    return base


# ── Forbidden Broker Tests ────────────────────────────────────────────


class TestForbiddenBrokers:
    """Verify that forbidden brokers are rejected at the gateway."""

    @pytest.mark.asyncio
    async def test_alpaca_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(exchanges=json.dumps(["ALPACA"]), feature_pack_id="")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_BROKER"
        assert any("ALPACA" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_kiwoom_us_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(exchanges=json.dumps(["KIWOOM_US"]), feature_pack_id="")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_BROKER"
        assert any("KIWOOM_US" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_allowed_broker_passes(self):
        db = _mock_db()
        # Mock feature pack lookup to return a valid FP
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        db.execute.return_value = mock_result

        gw = InjectionGateway(db)
        data = _strategy_data(exchanges=json.dumps(["BINANCE"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED

    @pytest.mark.asyncio
    async def test_forbidden_brokers_constant_complete(self):
        """Ensure all known forbidden brokers are in the constant."""
        assert "ALPACA" in FORBIDDEN_BROKERS
        assert "KIWOOM_US" in FORBIDDEN_BROKERS


# ── Forbidden Sector Tests ────────────────────────────────────────────


class TestForbiddenSectors:
    """Verify that forbidden sectors are rejected at the gateway."""

    @pytest.mark.asyncio
    async def test_meme_sector_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(sectors=json.dumps(["MEME"]), feature_pack_id="")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_SECTOR"

    @pytest.mark.asyncio
    async def test_gamefi_sector_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(sectors=json.dumps(["GAMEFI"]), feature_pack_id="")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_SECTOR"

    @pytest.mark.asyncio
    async def test_allowed_sector_passes(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        db.execute.return_value = mock_result

        gw = InjectionGateway(db)
        data = _strategy_data(sectors=json.dumps(["LAYER1"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED

    @pytest.mark.asyncio
    async def test_all_forbidden_sectors_present(self):
        """Verify completeness of the forbidden sectors constant."""
        expected = {
            "MEME",
            "GAMEFI",
            "LOW_LIQUIDITY_NEW_TOKEN",
            "HIGH_VALUATION_PURE_SW",
            "WEAK_CONSUMER_BETA",
            "OIL_SENSITIVE",
            "LOW_LIQUIDITY_THEME",
        }
        assert expected == FORBIDDEN_SECTORS


# ── Market Matrix Compatibility ───────────────────────────────────────


class TestMarketMatrix:
    """Verify broker-asset class compatibility enforcement."""

    @pytest.mark.asyncio
    async def test_kis_us_not_allowed_for_crypto(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(
            asset_classes=json.dumps(["crypto"]),
            exchanges=json.dumps(["KIS_US"]),
            feature_pack_id="",
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert any("KIS_US" in v and "crypto" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_binance_not_allowed_for_us_stock(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(
            asset_classes=json.dumps(["us_stock"]),
            exchanges=json.dumps(["BINANCE"]),
            feature_pack_id="",
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_kis_us_allowed_for_us_stock(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        db.execute.return_value = mock_result

        gw = InjectionGateway(db)
        data = _strategy_data(
            asset_classes=json.dumps(["us_stock"]),
            exchanges=json.dumps(["KIS_US"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Dependency Check ──────────────────────────────────────────────────


class TestDependencyCheck:
    """Verify feature pack and indicator dependency enforcement."""

    @pytest.mark.asyncio
    async def test_missing_feature_pack_rejected(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # FP not found
        db.execute.return_value = mock_result

        gw = InjectionGateway(db)
        data = _strategy_data(feature_pack_id="nonexistent-fp")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "MISSING_DEPENDENCY"

    @pytest.mark.asyncio
    async def test_existing_feature_pack_approved(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # FP found
        db.execute.return_value = mock_result

        gw = InjectionGateway(db)
        data = _strategy_data()
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Checksum Verification ─────────────────────────────────────────────


class TestChecksumVerification:
    @pytest.mark.asyncio
    async def test_checksum_mismatch_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(
            checksum="abc123",
            expected_checksum="def456",
            feature_pack_id="",
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        # Step 3 (missing fp) fires before Step 4 (checksum), so first code is MISSING_DEPENDENCY.
        # Both violations should be present.
        assert any("checksum" in v.lower() for v in result.violations)
        assert result.blocked_code in ("MISSING_DEPENDENCY", "VERSION_MISMATCH")


# ── Indicator Validation ──────────────────────────────────────────────


class TestIndicatorValidation:
    @pytest.mark.asyncio
    async def test_missing_name_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_indicator({"version": "1.0", "compute_module": "x"})
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_valid_indicator_approved(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_indicator(
            {
                "name": "RSI",
                "version": "1.0.0",
                "compute_module": "app.indicators.rsi",
            }
        )
        assert result.verdict == GatewayVerdict.APPROVED


# ── Feature Pack Validation ───────────────────────────────────────────


class TestFeaturePackValidation:
    @pytest.mark.asyncio
    async def test_empty_indicators_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_feature_pack({"indicator_ids": "[]"})
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_missing_indicator_rejected(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Indicator not found
        db.execute.return_value = mock_result

        gw = InjectionGateway(db)
        result = await gw.validate_feature_pack(
            {
                "indicator_ids": json.dumps(["ind-001"]),
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "MISSING_DEPENDENCY"


# ── Multiple Violations ───────────────────────────────────────────────


class TestMultipleViolations:
    @pytest.mark.asyncio
    async def test_forbidden_broker_and_sector_both_caught(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        data = _strategy_data(
            exchanges=json.dumps(["ALPACA"]),
            sectors=json.dumps(["MEME"]),
            feature_pack_id="",
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert len(result.violations) >= 2
