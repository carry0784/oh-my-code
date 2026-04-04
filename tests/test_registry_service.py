"""Tests for Registry Service CRUD operations.

CR-048 Stage 1 L3: Registry CRUD + Gateway integration.
Tests verify Create/Read/Retire for Indicator/FeaturePack/Strategy/PromotionEvent.

Rules verified:
- Strategy creation requires Gateway validation
- PromotionEvent is append-only (no update/delete)
- Hard delete is prohibited (retire/disable only)
- Promotion execution is outside scope (recording only)

All tests use mock DB — no real database required.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from app.services.registry_service import (
    RegistryService,
    GatewayRejectionError,
    NotFoundError,
    InvalidOperationError,
)
from app.services.injection_gateway import GatewayVerdict, GatewayResult
from app.models.indicator_registry import IndicatorStatus
from app.models.feature_pack import FeaturePackStatus
from app.models.strategy_registry import PromotionStatus


# ── Fixtures ─────────────────────────────────────────────────────────


def _mock_db():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _mock_indicator(**overrides):
    """Create a mock Indicator with defaults."""
    ind = MagicMock()
    ind.id = overrides.get("id", "ind-001")
    ind.name = overrides.get("name", "RSI")
    ind.version = overrides.get("version", "1.0.0")
    ind.status = overrides.get("status", IndicatorStatus.ACTIVE.value)
    ind.compute_module = overrides.get("compute_module", "app.indicators.rsi")
    return ind


def _mock_feature_pack(**overrides):
    fp = MagicMock()
    fp.id = overrides.get("id", "fp-001")
    fp.name = overrides.get("name", "trend_pack_v1")
    fp.version = overrides.get("version", "1.0.0")
    fp.status = overrides.get("status", FeaturePackStatus.ACTIVE.value)
    return fp


def _mock_strategy(**overrides):
    strat = MagicMock()
    strat.id = overrides.get("id", "strat-001")
    strat.name = overrides.get("name", "momentum_v1")
    strat.version = overrides.get("version", "1.0.0")
    strat.status = overrides.get("status", PromotionStatus.REGISTERED.value)
    return strat


# ── Test Class: Indicator CRUD ───────────────────────────────────────


class TestIndicatorCRUD:
    """Indicator create/read/retire tests."""

    @pytest.mark.asyncio
    async def test_create_indicator_calls_gateway(self):
        """Indicator creation should validate through gateway."""
        db = _mock_db()
        svc = RegistryService(db)

        # Mock gateway to approve
        svc.gateway.validate_indicator = AsyncMock(
            return_value=GatewayResult(verdict=GatewayVerdict.APPROVED)
        )

        indicator = await svc.create_indicator(
            {
                "name": "RSI",
                "version": "1.0.0",
                "compute_module": "app.indicators.rsi",
            }
        )

        svc.gateway.validate_indicator.assert_called_once()
        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_indicator_gateway_rejected(self):
        """Gateway rejection should raise GatewayRejectionError."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_indicator = AsyncMock(
            return_value=GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=["Missing name"],
            )
        )

        with pytest.raises(GatewayRejectionError):
            await svc.create_indicator({"version": "1.0.0", "compute_module": "x"})

    @pytest.mark.asyncio
    async def test_get_indicator_found(self):
        """get_indicator should return indicator if found."""
        db = _mock_db()
        ind = _mock_indicator()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = ind
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        found = await svc.get_indicator("ind-001")
        assert found.id == "ind-001"

    @pytest.mark.asyncio
    async def test_get_indicator_not_found(self):
        """get_indicator should raise NotFoundError if not found."""
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        with pytest.raises(NotFoundError):
            await svc.get_indicator("nonexistent")

    @pytest.mark.asyncio
    async def test_retire_indicator(self):
        """retire_indicator should set status to DEPRECATED."""
        db = _mock_db()
        ind = _mock_indicator(status=IndicatorStatus.ACTIVE.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = ind
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        retired = await svc.retire_indicator("ind-001", reason="obsolete")
        assert retired.status == IndicatorStatus.DEPRECATED.value

    @pytest.mark.asyncio
    async def test_retire_blocked_indicator_fails(self):
        """Cannot retire a BLOCKED indicator."""
        db = _mock_db()
        ind = _mock_indicator(status=IndicatorStatus.BLOCKED.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = ind
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        with pytest.raises(InvalidOperationError):
            await svc.retire_indicator("ind-001")

    @pytest.mark.asyncio
    async def test_no_hard_delete_indicator(self):
        """RegistryService should not have delete_indicator method."""
        assert not hasattr(RegistryService, "delete_indicator")


# ── Test Class: Feature Pack CRUD ────────────────────────────────────


class TestFeaturePackCRUD:
    """Feature pack create/read/retire tests."""

    @pytest.mark.asyncio
    async def test_create_feature_pack_calls_gateway(self):
        """Feature pack creation should validate through gateway."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_feature_pack = AsyncMock(
            return_value=GatewayResult(verdict=GatewayVerdict.APPROVED)
        )

        fp = await svc.create_feature_pack(
            {
                "name": "trend_pack_v1",
                "version": "1.0.0",
                "indicator_ids": json.dumps(["ind-001"]),
            }
        )

        svc.gateway.validate_feature_pack.assert_called_once()
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_feature_pack_gateway_rejected(self):
        """Gateway rejection should raise GatewayRejectionError."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_feature_pack = AsyncMock(
            return_value=GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=["No indicators"],
                blocked_code="MISSING_DEPENDENCY",
            )
        )

        with pytest.raises(GatewayRejectionError) as exc_info:
            await svc.create_feature_pack(
                {
                    "name": "bad_fp",
                    "version": "1.0.0",
                    "indicator_ids": "[]",
                }
            )
        assert exc_info.value.code == "MISSING_DEPENDENCY"

    @pytest.mark.asyncio
    async def test_get_feature_pack_not_found(self):
        """get_feature_pack should raise NotFoundError if not found."""
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        with pytest.raises(NotFoundError):
            await svc.get_feature_pack("nonexistent")

    @pytest.mark.asyncio
    async def test_retire_feature_pack(self):
        """retire_feature_pack should set status to DEPRECATED."""
        db = _mock_db()
        fp = _mock_feature_pack(status=FeaturePackStatus.ACTIVE.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fp
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        retired = await svc.retire_feature_pack("fp-001", reason="replaced")
        assert retired.status == FeaturePackStatus.DEPRECATED.value

    @pytest.mark.asyncio
    async def test_retire_blocked_feature_pack_fails(self):
        """Cannot retire a BLOCKED feature pack."""
        db = _mock_db()
        fp = _mock_feature_pack(status=FeaturePackStatus.BLOCKED.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = fp
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        with pytest.raises(InvalidOperationError):
            await svc.retire_feature_pack("fp-001")

    @pytest.mark.asyncio
    async def test_no_hard_delete_feature_pack(self):
        """RegistryService should not have delete_feature_pack method."""
        assert not hasattr(RegistryService, "delete_feature_pack")


# ── Test Class: Strategy CRUD ────────────────────────────────────────


class TestStrategyCRUD:
    """Strategy create/read/retire tests."""

    @pytest.mark.asyncio
    async def test_create_strategy_calls_gateway(self):
        """Strategy creation must go through Gateway validation."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_strategy = AsyncMock(
            return_value=GatewayResult(verdict=GatewayVerdict.APPROVED)
        )

        strategy, event = await svc.create_strategy(
            {
                "name": "momentum_v1",
                "version": "1.0.0",
                "feature_pack_id": "fp-001",
                "compute_module": "strategies.momentum",
                "asset_classes": json.dumps(["CRYPTO"]),
                "exchanges": json.dumps(["BINANCE"]),
                "timeframes": json.dumps(["1h"]),
            }
        )

        svc.gateway.validate_strategy.assert_called_once()
        # Strategy + PromotionEvent = 2 adds
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_create_strategy_sets_registered_status(self):
        """Newly created strategy should be REGISTERED."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_strategy = AsyncMock(
            return_value=GatewayResult(verdict=GatewayVerdict.APPROVED)
        )

        strategy, event = await svc.create_strategy(
            {
                "name": "momentum_v1",
                "version": "1.0.0",
                "feature_pack_id": "fp-001",
                "compute_module": "strategies.momentum",
                "asset_classes": json.dumps(["CRYPTO"]),
                "exchanges": json.dumps(["BINANCE"]),
                "timeframes": json.dumps(["1h"]),
            }
        )

        assert strategy.status == PromotionStatus.REGISTERED.value

    @pytest.mark.asyncio
    async def test_create_strategy_records_initial_event(self):
        """Strategy creation should record DRAFT→REGISTERED event."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_strategy = AsyncMock(
            return_value=GatewayResult(verdict=GatewayVerdict.APPROVED)
        )

        strategy, event = await svc.create_strategy(
            {
                "name": "test_v1",
                "version": "1.0.0",
                "feature_pack_id": "fp-001",
                "compute_module": "strategies.test",
                "asset_classes": json.dumps(["CRYPTO"]),
                "exchanges": json.dumps(["BINANCE"]),
                "timeframes": json.dumps(["1h"]),
            }
        )

        assert event.from_status == PromotionStatus.DRAFT.value
        assert event.to_status == PromotionStatus.REGISTERED.value

    @pytest.mark.asyncio
    async def test_create_strategy_forbidden_broker_rejected(self):
        """Strategy with forbidden broker should be rejected by gateway."""
        db = _mock_db()
        svc = RegistryService(db)

        svc.gateway.validate_strategy = AsyncMock(
            return_value=GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=["Forbidden broker: ALPACA"],
                blocked_code="FORBIDDEN_BROKER",
            )
        )

        with pytest.raises(GatewayRejectionError) as exc_info:
            await svc.create_strategy(
                {
                    "name": "bad_v1",
                    "version": "1.0.0",
                    "feature_pack_id": "fp-001",
                    "compute_module": "strategies.bad",
                    "asset_classes": json.dumps(["CRYPTO"]),
                    "exchanges": json.dumps(["ALPACA"]),
                    "timeframes": json.dumps(["1h"]),
                }
            )
        assert exc_info.value.code == "FORBIDDEN_BROKER"

    @pytest.mark.asyncio
    async def test_retire_strategy(self):
        """retire_strategy should set status to RETIRED + record event."""
        db = _mock_db()
        strat = _mock_strategy(status=PromotionStatus.REGISTERED.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = strat
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        retired, event = await svc.retire_strategy(
            "strat-001", reason="no longer needed", retired_by="operator"
        )
        assert retired.status == PromotionStatus.RETIRED.value
        assert event.to_status == PromotionStatus.RETIRED.value

    @pytest.mark.asyncio
    async def test_retire_blocked_strategy_fails(self):
        """Cannot retire a BLOCKED strategy."""
        db = _mock_db()
        strat = _mock_strategy(status=PromotionStatus.BLOCKED.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = strat
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        with pytest.raises(InvalidOperationError):
            await svc.retire_strategy("strat-001")

    @pytest.mark.asyncio
    async def test_retire_already_retired_fails(self):
        """Cannot retire an already retired strategy."""
        db = _mock_db()
        strat = _mock_strategy(status=PromotionStatus.RETIRED.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = strat
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)
        with pytest.raises(InvalidOperationError):
            await svc.retire_strategy("strat-001")

    @pytest.mark.asyncio
    async def test_no_hard_delete_strategy(self):
        """RegistryService should not have delete_strategy method."""
        assert not hasattr(RegistryService, "delete_strategy")


# ── Test Class: Promotion Event (append-only) ────────────────────────


class TestPromotionEventAppendOnly:
    """PromotionEvent should be append-only."""

    @pytest.mark.asyncio
    async def test_record_promotion_event(self):
        """Should create a promotion event record."""
        db = _mock_db()
        svc = RegistryService(db)

        event = await svc.record_promotion_event(
            strategy_id="strat-001",
            from_status="DRAFT",
            to_status="REGISTERED",
            reason="test",
            triggered_by="system",
        )

        db.add.assert_called_once()
        assert event.from_status == "DRAFT"
        assert event.to_status == "REGISTERED"

    @pytest.mark.asyncio
    async def test_record_event_does_not_change_strategy_status(self):
        """Recording an event should NOT change strategy.status.

        Promotion execution is outside Stage 1 scope.
        """
        db = _mock_db()
        strat = _mock_strategy(status=PromotionStatus.REGISTERED.value)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = strat
        db.execute = AsyncMock(return_value=result_mock)

        svc = RegistryService(db)

        # Record a REGISTERED→BACKTEST_PASS event
        event = await svc.record_promotion_event(
            strategy_id="strat-001",
            from_status="REGISTERED",
            to_status="BACKTEST_PASS",
            reason="test",
            triggered_by="system",
        )

        # Strategy status should NOT have changed
        strategy = await svc.get_strategy("strat-001")
        assert strategy.status == PromotionStatus.REGISTERED.value

    def test_no_update_promotion_event(self):
        """RegistryService should not have update_promotion_event method."""
        assert not hasattr(RegistryService, "update_promotion_event")

    def test_no_delete_promotion_event(self):
        """RegistryService should not have delete_promotion_event method."""
        assert not hasattr(RegistryService, "delete_promotion_event")

    @pytest.mark.asyncio
    async def test_record_event_with_evidence(self):
        """Event can include evidence JSON and approved_by."""
        db = _mock_db()
        svc = RegistryService(db)

        event = await svc.record_promotion_event(
            strategy_id="strat-001",
            from_status="REGISTERED",
            to_status="BACKTEST_PASS",
            reason="9-step pass",
            triggered_by="system",
            evidence='{"sharpe": 1.2, "mdd": 0.08}',
            approved_by="operator_a",
        )

        assert event.evidence == '{"sharpe": 1.2, "mdd": 0.08}'
        assert event.approved_by == "operator_a"


# ── Test Class: No Prohibited Methods ────────────────────────────────


class TestNoProhibitedMethods:
    """Verify RegistryService does not expose prohibited operations."""

    def test_no_execute_methods(self):
        """No execute/activate/promote methods should exist."""
        prohibited = [
            "execute_strategy",
            "activate_strategy",
            "promote_strategy",
            "activate_runtime",
            "connect_broker",
            "dispatch_task",
            "register_beat",
        ]
        for method in prohibited:
            assert not hasattr(RegistryService, method), f"Prohibited method found: {method}"

    def test_no_delete_methods(self):
        """No hard delete methods should exist."""
        delete_methods = [
            "delete_indicator",
            "delete_feature_pack",
            "delete_strategy",
            "delete_promotion_event",
        ]
        for method in delete_methods:
            assert not hasattr(RegistryService, method), f"Hard delete found: {method}"
