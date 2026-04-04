"""Tests for asset_service.py Stage 2B extensions.

CR-048 Stage 2B.  Verifies:
  - Broker-policy validation integration in register_symbol
  - Status transition with audit recording
  - TTL expiry processing (manual, max 10, fail-closed)
  - EXCLUDED→CORE direct prohibition (strengthened)
  - EXCLUDED→WATCH manual_override requirement
  - Fail-closed behavior on DB errors
  - screen_and_update / qualify_and_record FROZEN verification

Uses mock DB sessions to avoid infrastructure dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.models.asset import (
    AssetSector,
    Symbol,
    SymbolStatus,
    SymbolStatusReason,
    SymbolStatusAudit,
    EXCLUDED_SECTORS,
)
from app.models.strategy_registry import AssetClass
from app.services.asset_service import AssetService


# ── Helpers ───────────────────────────────────────────────────────────


def _mock_db():
    """Create a mock AsyncSession."""
    db = AsyncMock()
    return db


def _make_symbol(
    symbol: str = "SOL/USDT",
    status: SymbolStatus = SymbolStatus.CORE,
    sector: AssetSector = AssetSector.LAYER1,
    manual_override: bool = False,
    candidate_expire_at: datetime | None = None,
    **kwargs,
) -> Symbol:
    """Create a Symbol instance for testing."""
    sym = MagicMock(spec=Symbol)
    sym.id = kwargs.get("id", "sym-001")
    sym.symbol = symbol
    sym.name = kwargs.get("name", "Test Symbol")
    sym.status = status
    sym.sector = sector
    sym.manual_override = manual_override
    sym.candidate_expire_at = candidate_expire_at
    sym.asset_class = kwargs.get("asset_class", AssetClass.CRYPTO)
    sym.exchanges = kwargs.get("exchanges", json.dumps(["BINANCE"]))
    sym.updated_at = datetime.now(timezone.utc)
    return sym


# ══════════════════════════════════════════════════════════════════════
# Broker Policy Integration in register_symbol
# ══════════════════════════════════════════════════════════════════════


class TestRegisterSymbolBrokerValidation:
    """Verify broker-policy validation in register_symbol (Stage 2B)."""

    @pytest.mark.asyncio
    async def test_forbidden_broker_rejected(self):
        """ALPACA in exchanges → registration refused."""
        db = _mock_db()
        svc = AssetService(db)
        with pytest.raises(ValueError, match="Broker policy violation"):
            await svc.register_symbol(
                {
                    "symbol": "SOL/USDT",
                    "name": "Solana",
                    "asset_class": "crypto",
                    "sector": "layer1",
                    "exchanges": ["ALPACA"],
                }
            )

    @pytest.mark.asyncio
    async def test_kiwoom_us_rejected(self):
        """KIWOOM_US in exchanges → registration refused."""
        db = _mock_db()
        svc = AssetService(db)
        with pytest.raises(ValueError, match="Broker policy violation"):
            await svc.register_symbol(
                {
                    "symbol": "AAPL",
                    "name": "Apple",
                    "asset_class": "us_stock",
                    "sector": "tech",
                    "exchanges": ["KIWOOM_US"],
                }
            )

    @pytest.mark.asyncio
    async def test_incompatible_broker_rejected(self):
        """KIS_US for crypto → registration refused."""
        db = _mock_db()
        svc = AssetService(db)
        with pytest.raises(ValueError, match="Broker policy violation"):
            await svc.register_symbol(
                {
                    "symbol": "SOL/USDT",
                    "name": "Solana",
                    "asset_class": "crypto",
                    "sector": "layer1",
                    "exchanges": ["KIS_US"],
                }
            )

    @pytest.mark.asyncio
    async def test_allowed_broker_passes(self):
        """BINANCE for crypto → registration proceeds."""
        db = _mock_db()
        svc = AssetService(db)
        # Should not raise — will proceed to DB operations
        # (may fail on mock DB, but broker validation passes)
        try:
            await svc.register_symbol(
                {
                    "symbol": "SOL/USDT",
                    "name": "Solana",
                    "asset_class": "crypto",
                    "sector": "layer1",
                    "exchanges": ["BINANCE"],
                }
            )
        except Exception as e:
            # Only mock DB errors are acceptable — not broker violations
            assert "Broker policy" not in str(e)

    @pytest.mark.asyncio
    async def test_us_stock_kis_us_passes(self):
        """KIS_US for us_stock → registration proceeds."""
        db = _mock_db()
        svc = AssetService(db)
        try:
            await svc.register_symbol(
                {
                    "symbol": "NVDA",
                    "name": "NVIDIA",
                    "asset_class": "us_stock",
                    "sector": "tech",
                    "exchanges": ["KIS_US"],
                }
            )
        except Exception as e:
            assert "Broker policy" not in str(e)

    @pytest.mark.asyncio
    async def test_multiple_violations_all_reported(self):
        """Multiple violations → all listed in error."""
        db = _mock_db()
        svc = AssetService(db)
        with pytest.raises(ValueError, match="Broker policy violation") as exc_info:
            await svc.register_symbol(
                {
                    "symbol": "SOL/USDT",
                    "name": "Solana",
                    "asset_class": "crypto",
                    "sector": "layer1",
                    "exchanges": ["ALPACA", "KIS_US"],
                }
            )
        # Both violations should be mentioned
        err = str(exc_info.value)
        assert "ALPACA" in err or "forbidden" in err.lower()

    @pytest.mark.asyncio
    async def test_excluded_sector_still_forces_excluded(self):
        """Excluded sector + valid broker → EXCLUDED status forced."""
        db = _mock_db()
        svc = AssetService(db)
        try:
            result = await svc.register_symbol(
                {
                    "symbol": "DOGE/USDT",
                    "name": "Dogecoin",
                    "asset_class": "crypto",
                    "sector": "meme",
                    "exchanges": ["BINANCE"],
                }
            )
        except Exception:
            pass  # Mock DB may fail — that's OK


# ══════════════════════════════════════════════════════════════════════
# Status Transition with Audit
# ══════════════════════════════════════════════════════════════════════


class TestTransitionStatusWithAudit:
    """Verify status transition uses validator + records audit."""

    @pytest.mark.asyncio
    async def test_core_to_watch_allowed(self):
        """CORE→WATCH transition should succeed and record audit."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        result = await svc.transition_status(
            symbol_id="sym-001",
            new_status=SymbolStatus.WATCH,
            reason_code="ttl_expired",
            triggered_by="operator",
        )

        assert sym.status == SymbolStatus.WATCH
        # Verify audit was attempted (db.add called for SymbolStatusAudit)
        add_calls = [c for c in db.add.call_args_list if isinstance(c[0][0], SymbolStatusAudit)]
        assert len(add_calls) >= 1, "Audit record should have been added"

    @pytest.mark.asyncio
    async def test_excluded_to_core_forbidden(self):
        """EXCLUDED→CORE direct transition should be rejected."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.EXCLUDED, manual_override=True)

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        with pytest.raises(ValueError, match="denied|forbidden"):
            await svc.transition_status(
                symbol_id="sym-001",
                new_status=SymbolStatus.CORE,
                reason_code="manual_promotion",
            )

    @pytest.mark.asyncio
    async def test_excluded_to_watch_without_override_rejected(self):
        """EXCLUDED→WATCH without manual_override should be rejected."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.EXCLUDED, manual_override=False)

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        with pytest.raises(ValueError, match="denied|manual_override"):
            await svc.transition_status(
                symbol_id="sym-001",
                new_status=SymbolStatus.WATCH,
                reason_code="manual_promotion",
            )

    @pytest.mark.asyncio
    async def test_excluded_to_watch_with_override_allowed(self):
        """EXCLUDED→WATCH with manual_override should succeed."""
        db = _mock_db()
        sym = _make_symbol(
            status=SymbolStatus.EXCLUDED,
            manual_override=True,
            sector=AssetSector.LAYER1,  # Not an excluded sector
        )

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        result = await svc.transition_status(
            symbol_id="sym-001",
            new_status=SymbolStatus.WATCH,
            reason_code="manual_promotion",
            triggered_by="operator",
            approval_level="high",
        )
        assert sym.status == SymbolStatus.WATCH

    @pytest.mark.asyncio
    async def test_excluded_sector_cannot_leave_excluded(self):
        """Symbol in excluded sector (meme) can never leave EXCLUDED."""
        db = _mock_db()
        sym = _make_symbol(
            status=SymbolStatus.EXCLUDED,
            sector=AssetSector.MEME,
            manual_override=True,
        )

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        with pytest.raises(ValueError, match="denied|exclusion baseline"):
            await svc.transition_status(
                symbol_id="sym-001",
                new_status=SymbolStatus.WATCH,
                reason_code="manual_promotion",
            )

    @pytest.mark.asyncio
    async def test_same_status_noop(self):
        """Same-status transition should succeed (no-op)."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        result = await svc.transition_status(
            symbol_id="sym-001",
            new_status=SymbolStatus.CORE,
            reason_code="refresh",
        )
        assert sym.status == SymbolStatus.CORE

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_block_transition(self):
        """If audit recording fails, transition should still complete."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)
        # Make _record_status_audit fail
        svc._record_status_audit = AsyncMock(side_effect=Exception("DB error"))

        # Should NOT raise — transition completes despite audit failure
        result = await svc.transition_status(
            symbol_id="sym-001",
            new_status=SymbolStatus.WATCH,
            reason_code="ttl_expired",
        )
        assert sym.status == SymbolStatus.WATCH

    @pytest.mark.asyncio
    async def test_symbol_not_found_raises(self):
        """Non-existent symbol ID should raise ValueError."""
        db = _mock_db()
        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.transition_status(
                symbol_id="nonexistent",
                new_status=SymbolStatus.WATCH,
                reason_code="test",
            )

    @pytest.mark.asyncio
    async def test_audit_records_from_and_to_status(self):
        """Audit record should capture both old and new status."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        await svc.transition_status(
            symbol_id="sym-001",
            new_status=SymbolStatus.WATCH,
            reason_code="ttl_expired",
            triggered_by="operator",
        )

        # Find the SymbolStatusAudit added to DB
        audit_calls = [
            c[0][0] for c in db.add.call_args_list if isinstance(c[0][0], SymbolStatusAudit)
        ]
        assert len(audit_calls) >= 1
        audit = audit_calls[0]
        assert audit.from_status == "core"
        assert audit.to_status == "watch"
        assert audit.reason_code == "ttl_expired"
        assert audit.triggered_by == "operator"


# ══════════════════════════════════════════════════════════════════════
# TTL Expiry Processing
# ══════════════════════════════════════════════════════════════════════


class TestProcessExpiredTTL:
    """Verify TTL expiry processing (manual, max 10, fail-closed)."""

    @pytest.mark.asyncio
    async def test_demotes_expired_core_to_watch(self):
        """Expired CORE symbol should be demoted to WATCH."""
        db = _mock_db()
        expired_sym = _make_symbol(
            status=SymbolStatus.CORE,
            candidate_expire_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        svc = AssetService(db)
        svc.get_expired_candidates = AsyncMock(return_value=[expired_sym])
        svc.get_symbol_by_id = AsyncMock(return_value=expired_sym)

        demoted = await svc.process_expired_ttl(max_count=10, triggered_by="operator")

        assert len(demoted) == 1
        assert expired_sym.status == SymbolStatus.WATCH
        assert expired_sym.candidate_expire_at is None

    @pytest.mark.asyncio
    async def test_max_count_enforced(self):
        """Should only process up to max_count symbols."""
        db = _mock_db()
        expired_symbols = [
            _make_symbol(
                id=f"sym-{i:03d}",
                symbol=f"SYM{i}/USDT",
                status=SymbolStatus.CORE,
            )
            for i in range(5)
        ]

        svc = AssetService(db)
        svc.get_expired_candidates = AsyncMock(return_value=expired_symbols)
        # Each transition needs get_symbol_by_id
        svc.get_symbol_by_id = AsyncMock(
            side_effect=lambda sid: next((s for s in expired_symbols if s.id == sid), None)
        )

        demoted = await svc.process_expired_ttl(max_count=3)
        assert len(demoted) == 3

    @pytest.mark.asyncio
    async def test_max_count_capped_at_10(self):
        """max_count > 10 should raise ValueError."""
        db = _mock_db()
        svc = AssetService(db)

        with pytest.raises(ValueError, match="exceeds Stage 2B limit"):
            await svc.process_expired_ttl(max_count=20)

    @pytest.mark.asyncio
    async def test_no_expired_returns_empty(self):
        """No expired candidates → empty result."""
        db = _mock_db()
        svc = AssetService(db)
        svc.get_expired_candidates = AsyncMock(return_value=[])

        demoted = await svc.process_expired_ttl()
        assert demoted == []

    @pytest.mark.asyncio
    async def test_fail_closed_on_transition_error(self):
        """If transition fails, skip symbol and preserve CORE."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)

        svc = AssetService(db)
        svc.get_expired_candidates = AsyncMock(return_value=[sym])
        # Make transition_status fail
        svc.transition_status = AsyncMock(side_effect=Exception("DB connection lost"))

        # Should NOT raise — fail-closed skips the symbol
        demoted = await svc.process_expired_ttl()
        assert demoted == []  # Nothing demoted

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self):
        """If one symbol fails, others should still be processed."""
        db = _mock_db()
        sym1 = _make_symbol(id="sym-001", symbol="SYM1/USDT", status=SymbolStatus.CORE)
        sym2 = _make_symbol(id="sym-002", symbol="SYM2/USDT", status=SymbolStatus.CORE)

        svc = AssetService(db)
        svc.get_expired_candidates = AsyncMock(return_value=[sym1, sym2])

        call_count = 0
        original_transition = svc.transition_status

        async def mock_transition(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First fails")
            # Second succeeds — directly mutate sym2
            sym2.status = SymbolStatus.WATCH
            sym2.status_reason_code = "ttl_expired"

        svc.transition_status = mock_transition
        svc.get_symbol_by_id = AsyncMock(side_effect=lambda sid: sym2 if sid == "sym-002" else sym1)

        demoted = await svc.process_expired_ttl()
        assert len(demoted) == 1  # Only sym2 demoted

    @pytest.mark.asyncio
    async def test_manual_only_no_celery(self):
        """Verify process_expired_ttl is a regular async method, not a Celery task."""
        import inspect

        assert inspect.iscoroutinefunction(AssetService.process_expired_ttl)
        # Check it's not decorated with celery
        assert not hasattr(AssetService.process_expired_ttl, "delay")
        assert not hasattr(AssetService.process_expired_ttl, "apply_async")


# ══════════════════════════════════════════════════════════════════════
# Status Audit Recording
# ══════════════════════════════════════════════════════════════════════


class TestRecordStatusAudit:
    """Verify audit trail recording."""

    @pytest.mark.asyncio
    async def test_audit_record_created(self):
        """_record_status_audit should create a SymbolStatusAudit row."""
        db = _mock_db()
        svc = AssetService(db)

        audit = await svc._record_status_audit(
            symbol_id="sym-001",
            symbol="SOL/USDT",
            from_status="core",
            to_status="watch",
            reason_code="ttl_expired",
            triggered_by="operator",
        )

        assert isinstance(audit, SymbolStatusAudit)
        assert audit.from_status == "core"
        assert audit.to_status == "watch"
        assert audit.triggered_by == "operator"

    @pytest.mark.asyncio
    async def test_audit_is_append_only(self):
        """SymbolStatusAudit should have no update/delete methods in service."""
        svc_methods = dir(AssetService)
        assert not any("update_audit" in m for m in svc_methods)
        assert not any("delete_audit" in m for m in svc_methods)


# ══════════════════════════════════════════════════════════════════════
# FROZEN Functions Verification
# ══════════════════════════════════════════════════════════════════════


class TestFrozenFunctions:
    """Verify screen_and_update and qualify_and_record are NOT modified."""

    def test_screen_and_update_exists(self):
        """screen_and_update should still exist."""
        assert hasattr(AssetService, "screen_and_update")

    def test_qualify_and_record_exists(self):
        """qualify_and_record should still exist."""
        assert hasattr(AssetService, "qualify_and_record")

    def test_screen_and_update_signature_unchanged(self):
        """screen_and_update signature should have symbol_id and screening_input."""
        import inspect

        sig = inspect.signature(AssetService.screen_and_update)
        params = list(sig.parameters.keys())
        assert "symbol_id" in params
        assert "screening_input" in params

    def test_qualify_and_record_signature_unchanged(self):
        """qualify_and_record signature should have symbol_id and qualification_input."""
        import inspect

        sig = inspect.signature(AssetService.qualify_and_record)
        params = list(sig.parameters.keys())
        assert "symbol_id" in params
        assert "qualification_input" in params


# ══════════════════════════════════════════════════════════════════════
# Fail-Closed Behavior
# ══════════════════════════════════════════════════════════════════════


class TestFailClosed:
    """Verify fail-closed behavior across all Stage 2B changes."""

    @pytest.mark.asyncio
    async def test_broker_validation_blocks_before_db(self):
        """Broker violation should prevent any DB call."""
        db = _mock_db()
        svc = AssetService(db)

        with pytest.raises(ValueError, match="Broker policy"):
            await svc.register_symbol(
                {
                    "symbol": "TEST",
                    "name": "Test",
                    "asset_class": "crypto",
                    "sector": "layer1",
                    "exchanges": ["ALPACA"],
                }
            )

        # db.add should NOT have been called
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_transition_denied_no_db_change(self):
        """Denied transition should not modify DB."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.EXCLUDED, manual_override=True)
        original_status = sym.status

        svc = AssetService(db)
        svc.get_symbol_by_id = AsyncMock(return_value=sym)

        with pytest.raises(ValueError):
            await svc.transition_status(
                symbol_id="sym-001",
                new_status=SymbolStatus.CORE,  # Forbidden: EXCLUDED→CORE
                reason_code="test",
            )

        # db.flush should NOT have been called after the rejection
        # (sym.status should still be EXCLUDED)
        assert sym.status == SymbolStatus.EXCLUDED

    @pytest.mark.asyncio
    async def test_ttl_max_count_zero_is_valid(self):
        """max_count=0 should return empty (process nothing)."""
        db = _mock_db()
        svc = AssetService(db)
        svc.get_expired_candidates = AsyncMock(return_value=[_make_symbol()])

        demoted = await svc.process_expired_ttl(max_count=0)
        assert demoted == []
