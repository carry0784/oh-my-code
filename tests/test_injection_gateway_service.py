"""Tests for Injection Gateway validation logic.

CR-048 Stage 1 L3: Gateway 7-step validation + forbidden route blocking.
Tests verify design_strategy_registry.md §S-01~S-05 contracts.

All tests use mock DB — no real database required.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.injection_gateway import (
    InjectionGateway,
    GatewayVerdict,
    GatewayResult,
    FORBIDDEN_BROKERS,
    FORBIDDEN_SECTORS,
)
from app.core.constitution import (
    FORBIDDEN_BROKERS as CONST_FORBIDDEN_BROKERS,
    ALLOWED_BROKERS,
    FORBIDDEN_SECTOR_VALUES,
)
from app.models.feature_pack import FeaturePackStatus


# ── Fixtures ─────────────────────────────────────────────────────────


def _mock_db(fp_result=None, ind_result=None):
    """Create a mock AsyncSession that returns given results for queries."""
    db = AsyncMock()

    async def mock_execute(query):
        result = MagicMock()
        # Determine what entity is being queried based on query string repr
        query_str = str(query)
        if "feature_packs" in query_str:
            result.scalar_one_or_none.return_value = fp_result
        elif "indicators" in query_str:
            result.scalar_one_or_none.return_value = ind_result
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db.execute = mock_execute
    return db


def _valid_strategy_data(**overrides) -> dict:
    """Return minimal valid strategy data."""
    base = {
        "name": "test_strategy_v1",
        "version": "1.0.0",
        "feature_pack_id": "fp-001",
        "compute_module": "strategies.test",
        "asset_classes": json.dumps(["CRYPTO"]),
        "exchanges": json.dumps(["BINANCE"]),
        "sectors": json.dumps(["LAYER1"]),
        "timeframes": json.dumps(["1h"]),
    }
    base.update(overrides)
    return base


def _mock_feature_pack(status="ACTIVE"):
    """Create a mock FeaturePack."""
    fp = MagicMock()
    fp.id = "fp-001"
    fp.status = status
    return fp


# ── Test Class: Gateway 7-Step Validation ────────────────────────────


class TestGateway7StepValidation:
    """Tests for the 7-step Gateway validation (S-01)."""

    @pytest.mark.asyncio
    async def test_valid_strategy_approved(self):
        """A valid strategy should pass all 7 checks."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        result = await gw.validate_strategy(_valid_strategy_data())
        assert result.verdict == GatewayVerdict.APPROVED
        assert result.violations == []
        assert result.blocked_code is None

    @pytest.mark.asyncio
    async def test_gateway_has_seven_steps(self):
        """Gateway check steps should be 7 as per design card."""
        assert len(InjectionGateway.GATEWAY_CHECK_STEPS) == 7
        assert InjectionGateway.GATEWAY_CHECK_STEPS[0] == "forbidden_broker"
        assert InjectionGateway.GATEWAY_CHECK_STEPS[1] == "forbidden_sector"
        assert InjectionGateway.GATEWAY_CHECK_STEPS[2] == "dependency_verification"
        assert InjectionGateway.GATEWAY_CHECK_STEPS[3] == "version_checksum"
        assert InjectionGateway.GATEWAY_CHECK_STEPS[4] == "manifest_signature"
        assert InjectionGateway.GATEWAY_CHECK_STEPS[5] == "market_matrix_compatibility"
        assert InjectionGateway.GATEWAY_CHECK_STEPS[6] == "feature_pack_status"


# ── Test Class: Forbidden Broker Blocking ────────────────────────────


class TestForbiddenBrokerBlocking:
    """Step 1: Forbidden broker check (S-02)."""

    @pytest.mark.asyncio
    async def test_alpaca_rejected(self):
        """ALPACA broker should be rejected immediately."""
        db = _mock_db(fp_result=_mock_feature_pack())
        gw = InjectionGateway(db)

        data = _valid_strategy_data(exchanges=json.dumps(["ALPACA"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_BROKER"
        assert any("ALPACA" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_kiwoom_us_rejected(self):
        """KIWOOM_US broker should be rejected immediately."""
        db = _mock_db(fp_result=_mock_feature_pack())
        gw = InjectionGateway(db)

        data = _valid_strategy_data(exchanges=json.dumps(["KIWOOM_US"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_BROKER"
        assert any("KIWOOM_US" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_all_forbidden_brokers_covered(self):
        """All constitution-defined forbidden brokers should be blocked."""
        for broker in CONST_FORBIDDEN_BROKERS:
            db = _mock_db(fp_result=_mock_feature_pack())
            gw = InjectionGateway(db)
            data = _valid_strategy_data(exchanges=json.dumps([broker]))
            result = await gw.validate_strategy(data)
            assert result.verdict == GatewayVerdict.REJECTED, f"{broker} should be rejected"

    @pytest.mark.asyncio
    async def test_allowed_broker_accepted(self):
        """Allowed brokers should pass forbidden broker check."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            exchanges=json.dumps(["BINANCE"]),
            asset_classes=json.dumps(["CRYPTO"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Forbidden Sector Blocking ────────────────────────────


class TestForbiddenSectorBlocking:
    """Step 2: Forbidden sector check (S-03)."""

    @pytest.mark.asyncio
    async def test_meme_sector_rejected(self):
        """MEME sector should be rejected."""
        db = _mock_db(fp_result=_mock_feature_pack())
        gw = InjectionGateway(db)

        data = _valid_strategy_data(sectors=json.dumps(["MEME"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_SECTOR"

    @pytest.mark.asyncio
    async def test_gamefi_sector_rejected(self):
        """GAMEFI sector should be rejected."""
        db = _mock_db(fp_result=_mock_feature_pack())
        gw = InjectionGateway(db)

        data = _valid_strategy_data(sectors=json.dumps(["GAMEFI"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "FORBIDDEN_SECTOR"

    @pytest.mark.asyncio
    async def test_all_seven_forbidden_sectors_rejected(self):
        """All 7 forbidden sectors should be blocked."""
        for sector_val in FORBIDDEN_SECTOR_VALUES:
            db = _mock_db(fp_result=_mock_feature_pack())
            gw = InjectionGateway(db)
            data = _valid_strategy_data(sectors=json.dumps([sector_val.upper()]))
            result = await gw.validate_strategy(data)
            assert result.verdict == GatewayVerdict.REJECTED, (
                f"Sector {sector_val} should be rejected"
            )

    @pytest.mark.asyncio
    async def test_allowed_sector_accepted(self):
        """Allowed sectors should pass."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(sectors=json.dumps(["LAYER1"]))
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Dependency Verification ──────────────────────────────


class TestDependencyVerification:
    """Step 3: Feature pack dependency check (S-04)."""

    @pytest.mark.asyncio
    async def test_missing_feature_pack_rejected(self):
        """Strategy without valid feature pack should be rejected."""
        db = _mock_db(fp_result=None)  # FP not found
        gw = InjectionGateway(db)

        data = _valid_strategy_data(feature_pack_id="nonexistent-fp")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "MISSING_DEPENDENCY"

    @pytest.mark.asyncio
    async def test_missing_feature_pack_id_rejected(self):
        """Strategy without feature_pack_id should be rejected."""
        db = _mock_db()
        gw = InjectionGateway(db)

        data = _valid_strategy_data()
        del data["feature_pack_id"]
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "MISSING_DEPENDENCY"

    @pytest.mark.asyncio
    async def test_existing_feature_pack_accepted(self):
        """Strategy with existing active feature pack should pass."""
        fp = _mock_feature_pack(status="ACTIVE")
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        result = await gw.validate_strategy(_valid_strategy_data())
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Version Checksum ─────────────────────────────────────


class TestVersionChecksum:
    """Step 4: Version checksum verification."""

    @pytest.mark.asyncio
    async def test_checksum_mismatch_rejected(self):
        """Mismatched checksum should be rejected."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            checksum="abc123",
            expected_checksum="def456",
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "VERSION_MISMATCH"

    @pytest.mark.asyncio
    async def test_checksum_match_approved(self):
        """Matched checksum should pass."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            checksum="abc123",
            expected_checksum="abc123",
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED

    @pytest.mark.asyncio
    async def test_no_checksum_skipped(self):
        """No checksum provided should skip verification."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data()  # no checksum fields
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Manifest Signature ───────────────────────────────────


class TestManifestSignature:
    """Step 5: Manifest signature verification."""

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self):
        """Short/invalid signature should be rejected."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(manifest_signature="short")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "INVALID_SIGNATURE"

    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self):
        """Valid signature (8+ chars) should pass."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(manifest_signature="abcdef1234567890")
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED

    @pytest.mark.asyncio
    async def test_no_signature_skipped(self):
        """No signature provided should skip verification."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data()  # no manifest_signature
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Asset-Broker Compatibility ───────────────────────────


class TestAssetBrokerCompatibility:
    """Step 6: Market-matrix broker compatibility (S-05)."""

    @pytest.mark.asyncio
    async def test_crypto_with_kis_us_rejected(self):
        """CRYPTO + KIS_US should be rejected (incompatible)."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            asset_classes=json.dumps(["CRYPTO"]),
            exchanges=json.dumps(["KIS_US"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "ASSET_BROKER_INCOMPATIBLE"

    @pytest.mark.asyncio
    async def test_us_stock_with_binance_rejected(self):
        """US_STOCK + BINANCE should be rejected (incompatible)."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            asset_classes=json.dumps(["US_STOCK"]),
            exchanges=json.dumps(["BINANCE"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_kr_stock_with_upbit_rejected(self):
        """KR_STOCK + UPBIT should be rejected (incompatible)."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            asset_classes=json.dumps(["KR_STOCK"]),
            exchanges=json.dumps(["UPBIT"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_crypto_with_binance_accepted(self):
        """CRYPTO + BINANCE is compatible."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            asset_classes=json.dumps(["CRYPTO"]),
            exchanges=json.dumps(["BINANCE"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED

    @pytest.mark.asyncio
    async def test_us_stock_with_kis_us_accepted(self):
        """US_STOCK + KIS_US is compatible."""
        fp = _mock_feature_pack()
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            asset_classes=json.dumps(["US_STOCK"]),
            exchanges=json.dumps(["KIS_US"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Feature Pack Status Check ────────────────────────────


class TestFeaturePackStatusCheck:
    """Step 7: Feature pack status check."""

    @pytest.mark.asyncio
    async def test_blocked_feature_pack_rejected(self):
        """BLOCKED feature pack should reject strategy."""
        fp = _mock_feature_pack(status="BLOCKED")
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        result = await gw.validate_strategy(_valid_strategy_data())
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "DEPENDENCY_BLOCKED"

    @pytest.mark.asyncio
    async def test_deprecated_feature_pack_rejected(self):
        """DEPRECATED feature pack should reject strategy."""
        fp = _mock_feature_pack(status="DEPRECATED")
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        result = await gw.validate_strategy(_valid_strategy_data())
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "DEPENDENCY_DEPRECATED"

    @pytest.mark.asyncio
    async def test_active_feature_pack_accepted(self):
        """ACTIVE feature pack should be accepted."""
        fp = _mock_feature_pack(status="ACTIVE")
        db = _mock_db(fp_result=fp)
        gw = InjectionGateway(db)

        result = await gw.validate_strategy(_valid_strategy_data())
        assert result.verdict == GatewayVerdict.APPROVED


# ── Test Class: Indicator Validation ─────────────────────────────────


class TestIndicatorValidation:
    """Indicator validation tests."""

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

    @pytest.mark.asyncio
    async def test_missing_name_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_indicator(
            {
                "version": "1.0.0",
                "compute_module": "app.indicators.rsi",
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_missing_version_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_indicator(
            {
                "name": "RSI",
                "compute_module": "app.indicators.rsi",
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_missing_compute_module_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_indicator(
            {
                "name": "RSI",
                "version": "1.0.0",
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED


# ── Test Class: Feature Pack Validation ──────────────────────────────


class TestFeaturePackValidation:
    """Feature pack validation tests."""

    @pytest.mark.asyncio
    async def test_empty_indicator_ids_rejected(self):
        db = _mock_db()
        gw = InjectionGateway(db)
        result = await gw.validate_feature_pack(
            {
                "name": "test_fp",
                "version": "1.0.0",
                "indicator_ids": "[]",
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED

    @pytest.mark.asyncio
    async def test_nonexistent_indicator_rejected(self):
        db = _mock_db(ind_result=None)
        gw = InjectionGateway(db)
        result = await gw.validate_feature_pack(
            {
                "name": "test_fp",
                "version": "1.0.0",
                "indicator_ids": json.dumps(["nonexistent-id"]),
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED
        assert result.blocked_code == "MISSING_DEPENDENCY"

    @pytest.mark.asyncio
    async def test_blocked_indicator_rejected(self):
        ind = MagicMock()
        ind.status = "BLOCKED"
        db = _mock_db(ind_result=ind)
        gw = InjectionGateway(db)
        result = await gw.validate_feature_pack(
            {
                "name": "test_fp",
                "version": "1.0.0",
                "indicator_ids": json.dumps(["ind-001"]),
            }
        )
        assert result.verdict == GatewayVerdict.REJECTED


# ── Test Class: Multiple Violations ──────────────────────────────────


class TestMultipleViolations:
    """Tests that multiple violations are collected."""

    @pytest.mark.asyncio
    async def test_forbidden_broker_and_sector_together(self):
        """Both forbidden broker AND sector should be reported."""
        db = _mock_db(fp_result=_mock_feature_pack())
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            exchanges=json.dumps(["ALPACA"]),
            sectors=json.dumps(["MEME"]),
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert len(result.violations) >= 2
        assert any("ALPACA" in v for v in result.violations)
        assert any("MEME" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_three_violations_collected(self):
        """Forbidden broker + sector + incompatible asset-broker."""
        db = _mock_db(fp_result=_mock_feature_pack())
        gw = InjectionGateway(db)

        data = _valid_strategy_data(
            exchanges=json.dumps(["ALPACA", "BINANCE"]),
            sectors=json.dumps(["GAMEFI"]),
            asset_classes=json.dumps(["US_STOCK"]),  # BINANCE incompatible with US_STOCK
        )
        result = await gw.validate_strategy(data)
        assert result.verdict == GatewayVerdict.REJECTED
        assert len(result.violations) >= 3
