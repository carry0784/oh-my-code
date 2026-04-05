"""RI-2B-1 + RI-2B-2a: Shadow Write Receipt Tests.

RI-2B-1 (SEALED tests — do not modify):
  - Model: fields, tablename, UNIQUE constraints, import
  - Verdict: 7-step decision table (step order, each verdict)
  - Dedupe: semantic dedupe_key computation + uniqueness
  - Idempotency: duplicate receipt_id / dedupe_key handling
  - Proof fields: dry_run=True, executed=False, business_write_count=0
  - Forbidden targets: OUT_OF_SCOPE, FORBIDDEN_TARGET
  - Failure isolation: flush/add failure → None
  - Append-only: no update/delete methods
  - Business table write: 0

RI-2B-2a (new tests):
  - EXECUTION_ENABLED=False enforcement
  - execute_bounded_write 10-step flow (all blocked by Step 1)
  - rollback_bounded_write blocked
  - Prior receipt checks, consumed, TOCTOU, CAS, post-write
  - Proof fields for execution verdicts
  - SEALED code protection
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.exc import IntegrityError

from app.models.asset import AssetClass, AssetSector
from app.models.shadow_write_receipt import ShadowWriteReceipt
from app.services.data_provider import DataQuality, MarketDataSnapshot, BacktestReadiness
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ShadowRunResult,
    run_shadow_pipeline,
)
from app.services.shadow_readthrough import (
    ExistingResultSource,
    ReadthroughComparisonResult,
)
from app.services.shadow_write_service import (
    ALLOWED_TARGETS,
    EXECUTION_ENABLED,
    FORBIDDEN_TARGETS,
    BlockReasonCode,
    ExecutionVerdict,
    RollbackFailedError,
    WriteVerdict,
    compute_dedupe_key,
    evaluate_shadow_write,
    evaluate_verdict,
    execute_bounded_write,
    rollback_bounded_write,
)


# ── Fixtures ──────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)


def _make_market(symbol="SOL/USDT") -> MarketDataSnapshot:
    return MarketDataSnapshot(
        symbol=symbol,
        timestamp=_NOW,
        price_usd=150.0,
        market_cap_usd=50e9,
        avg_daily_volume_usd=500_000_000.0,
        spread_pct=0.05,
        atr_pct=5.0,
        adx=30.0,
        price_vs_200ma=1.05,
        quality=DataQuality.HIGH,
    )


def _make_backtest(symbol="SOL/USDT") -> BacktestReadiness:
    return BacktestReadiness(
        symbol=symbol,
        available_bars=1000,
        sharpe_ratio=1.5,
        missing_data_pct=1.0,
        quality=DataQuality.HIGH,
    )


def _shadow_qualified(symbol="SOL/USDT") -> ShadowRunResult:
    return run_shadow_pipeline(
        _make_market(symbol=symbol),
        _make_backtest(symbol=symbol),
        AssetClass.CRYPTO,
        AssetSector.LAYER1,
        now_utc=_NOW,
    )


def _shadow_screen_failed(symbol="SOL/USDT") -> ShadowRunResult:
    """Create a shadow result that fails at screening (low volume)."""
    market = MarketDataSnapshot(
        symbol=symbol,
        timestamp=_NOW,
        price_usd=0.01,
        market_cap_usd=1e6,
        avg_daily_volume_usd=100.0,
        spread_pct=50.0,
        atr_pct=0.1,
        adx=5.0,
        price_vs_200ma=0.5,
        quality=DataQuality.STALE,
    )
    bt = BacktestReadiness(
        symbol=symbol,
        available_bars=10,
        sharpe_ratio=-1.0,
        missing_data_pct=90.0,
        quality=DataQuality.STALE,
    )
    return run_shadow_pipeline(market, bt, AssetClass.CRYPTO, AssetSector.LAYER1, now_utc=_NOW)


def _make_readthrough(symbol="SOL/USDT", shadow_result=None) -> ReadthroughComparisonResult:
    if shadow_result is None:
        shadow_result = _shadow_qualified(symbol)
    source = ExistingResultSource(
        screening_result_id="sr-001",
        qualification_result_id="qr-001",
        failure_code=None,
    )
    return ReadthroughComparisonResult(
        symbol=symbol,
        shadow_result=shadow_result,
        comparison_verdict=ComparisonVerdict.MATCH,
        reason_comparison=None,
        existing_source=source,
    )


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


def _uid():
    return str(uuid.uuid4())


# ── TestShadowWriteReceiptModel ──────────────────────────────────


class TestShadowWriteReceiptModel:
    def test_tablename(self):
        assert ShadowWriteReceipt.__tablename__ == "shadow_write_receipt"

    def test_required_fields(self):
        cols = {c.name for c in ShadowWriteReceipt.__table__.columns}
        required = {
            "id",
            "receipt_id",
            "dedupe_key",
            "symbol",
            "target_table",
            "target_field",
            "intended_value",
            "would_change_summary",
            "transition_reason",
            "input_fingerprint",
            "dry_run",
            "executed",
            "business_write_count",
            "verdict",
            "created_at",
        }
        assert required.issubset(cols)

    def test_nullable_fields(self):
        col_map = {c.name: c for c in ShadowWriteReceipt.__table__.columns}
        nullable_fields = ["current_value", "block_reason_code", "shadow_observation_id"]
        for name in nullable_fields:
            assert col_map[name].nullable is True, f"{name} should be nullable"

    def test_unique_constraints(self):
        col_map = {c.name: c for c in ShadowWriteReceipt.__table__.columns}
        assert col_map["receipt_id"].unique is True
        assert col_map["dedupe_key"].unique is True

    def test_import_from_models_init(self):
        from app.models import ShadowWriteReceipt as Imported

        assert Imported is ShadowWriteReceipt


# ── TestVerdictDecisionTable ─────────────────────────────────────


class TestVerdictDecisionTable:
    """Verify 7-step verdict decision table order."""

    def test_step1_out_of_scope(self):
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "unknown_table",
            "unknown_field",
            "unchecked",
            _shadow_qualified(),
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.OUT_OF_SCOPE.value

    def test_step2_forbidden_target_symbols_status(self):
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "status",
            "WATCH",
            _shadow_qualified(),
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.FORBIDDEN_TARGET.value

    def test_step2_forbidden_target_strategies(self):
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "strategies",
            "status",
            "DRAFT",
            _shadow_qualified(),
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.FORBIDDEN_TARGET.value

    def test_step3_null_shadow_result(self):
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            None,
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.INPUT_INVALID.value

    def test_step3_null_readthrough_result(self):
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            _shadow_qualified(),
            None,
        )
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.INPUT_INVALID.value

    def test_step4_already_matched(self):
        verdict, reason, intended, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "pass",
            _shadow_qualified(),
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.WOULD_SKIP
        assert reason is None

    def test_step5_precondition_failed(self):
        """Transition from 'pass' to 'fail' is not in allowed transitions."""
        shadow = _shadow_screen_failed()
        # Manually create a shadow that would produce 'fail' intended value
        # but from current_value='pass' which is not allowed
        # For this we need a qualify_failed shadow
        # Let's use a different approach: test with current_value='pass'
        # and a shadow that produces 'fail'
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "fail",
            _shadow_qualified(),
            _make_readthrough(),
        )
        # current=fail, intended=pass -> (fail, pass) not in allowed transitions
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.PRECONDITION_FAILED.value

    def test_step6_would_skip_screen_failed(self):
        shadow = _shadow_screen_failed()
        readthrough = _make_readthrough(shadow_result=shadow)
        verdict, reason, intended, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            shadow,
            readthrough,
        )
        assert verdict == WriteVerdict.WOULD_SKIP
        assert intended is None

    def test_step7_would_write_qualified(self):
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)
        verdict, reason, intended, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            shadow,
            readthrough,
        )
        assert verdict == WriteVerdict.WOULD_WRITE
        assert reason is None
        assert intended == "pass"

    def test_forbidden_before_business_logic(self):
        """Step 1-2 (forbidden) must block before Step 4-7 (business logic)."""
        # Even with valid shadow result, forbidden target is blocked first
        verdict, reason, _, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "promotion_eligibility_status",
            "unchecked",
            _shadow_qualified(),
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.BLOCKED
        assert reason == BlockReasonCode.FORBIDDEN_TARGET.value


# ── TestDedupeKey ────────────────────────────────────────────────


class TestDedupeKey:
    def test_deterministic(self):
        k1 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        k2 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        assert k1 == k2

    def test_different_symbol_different_key(self):
        k1 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        k2 = compute_dedupe_key(
            "BTC/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        assert k1 != k2

    def test_different_intended_different_key(self):
        k1 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        k2 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "fail", "fp1"
        )
        assert k1 != k2

    def test_none_current_value_uses_null(self):
        k1 = compute_dedupe_key("SOL/USDT", "symbols", "qualification_status", None, "pass", "fp1")
        k2 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "NULL", "pass", "fp1"
        )
        assert k1 == k2

    def test_sha256_hex_length(self):
        k = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)

    def test_verdict_8th_param_default_empty(self):
        """Default verdict="" preserves backward compat — no-arg calls are stable."""
        k1 = compute_dedupe_key(
            "SOL/USDT", "symbols", "qualification_status", "unchecked", "pass", "fp1"
        )
        k2 = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            verdict="",
        )
        assert k1 == k2

    def test_executed_vs_rolled_back_differ(self):
        """CR-048 RI-2B-2d Finding #1 regression: EXECUTED ≠ ROLLED_BACK dedupe."""
        k_exec = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        k_rb = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="rolled_back",
        )
        assert k_exec != k_rb

    def test_same_verdict_same_key(self):
        """Same verdict produces deterministic hash."""
        k1 = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        k2 = compute_dedupe_key(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            "pass",
            "fp1",
            dry_run=False,
            verdict="executed",
        )
        assert k1 == k2


# ── TestEvaluateShadowWrite ──────────────────────────────────────


class TestEvaluateShadowWrite:
    @pytest.mark.asyncio
    async def test_would_write_returns_receipt(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result is not None
        assert isinstance(result, ShadowWriteReceipt)
        assert result.verdict == "would_write"
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_blocked_returns_receipt(self):
        db = _mock_db()

        result = await evaluate_shadow_write(
            db,
            _uid(),
            None,
            None,
            "SOL/USDT",
            "unchecked",
        )

        assert result is not None
        assert result.verdict == "blocked"
        assert result.block_reason_code == "INPUT_INVALID"

    @pytest.mark.asyncio
    async def test_would_skip_returns_receipt(self):
        db = _mock_db()
        shadow = _shadow_screen_failed()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result is not None
        assert result.verdict == "would_skip"

    @pytest.mark.asyncio
    async def test_would_change_summary_populated(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert "qualification_status" in result.would_change_summary
        assert "unchecked" in result.would_change_summary
        assert "pass" in result.would_change_summary


# ── TestProofFields ──────────────────────────────────────────────


class TestProofFields:
    @pytest.mark.asyncio
    async def test_dry_run_always_true(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result.dry_run is True

    @pytest.mark.asyncio
    async def test_executed_always_false(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result.executed is False

    @pytest.mark.asyncio
    async def test_business_write_count_always_zero(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result.business_write_count == 0


# ── TestForbiddenTargets ─────────────────────────────────────────


class TestForbiddenTargets:
    @pytest.mark.asyncio
    async def test_symbols_status_blocked(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "WATCH",
            target_table="symbols",
            target_field="status",
        )

        assert result.verdict == "blocked"
        assert result.block_reason_code == "FORBIDDEN_TARGET"

    @pytest.mark.asyncio
    async def test_promotion_eligibility_blocked(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
            target_table="symbols",
            target_field="promotion_eligibility_status",
        )

        assert result.verdict == "blocked"
        assert result.block_reason_code == "FORBIDDEN_TARGET"

    @pytest.mark.asyncio
    async def test_strategies_status_blocked(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "DRAFT",
            target_table="strategies",
            target_field="status",
        )

        assert result.verdict == "blocked"
        assert result.block_reason_code == "FORBIDDEN_TARGET"

    @pytest.mark.asyncio
    async def test_unknown_table_out_of_scope(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "x",
            target_table="orders",
            target_field="status",
        )

        assert result.verdict == "blocked"
        assert result.block_reason_code == "OUT_OF_SCOPE"


# ── TestAppendOnlyGuarantee ──────────────────────────────────────


class TestAppendOnlyGuarantee:
    @pytest.mark.asyncio
    async def test_only_add_called(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_merge_called(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        db.merge.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_delete_called(self):
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        db.delete.assert_not_called()

    def test_service_has_no_update_delete_methods(self):
        """RI-2B-1 append-only: no raw update/delete/remove methods.
        RI-2B-2a adds execute_bounded_write and rollback_bounded_write (allowed by design).
        """
        import app.services.shadow_write_service as svc

        public_funcs = [
            name for name in dir(svc) if not name.startswith("_") and callable(getattr(svc, name))
        ]
        # RI-2B-2a allowed names + sqlalchemy imports
        ri2b2_allowed = {
            "execute_bounded_write",
            "rollback_bounded_write",
            "update",
            "text",
            "select",
        }
        for name in public_funcs:
            if name in ri2b2_allowed:
                continue
            assert "update" not in name.lower(), f"Found update method: {name}"
            assert "delete" not in name.lower(), f"Found delete method: {name}"
            assert "remove" not in name.lower(), f"Found remove method: {name}"
            assert "execute" not in name.lower() or name == "evaluate_shadow_write", (
                f"Found execute method: {name}"
            )
            assert "apply" not in name.lower(), f"Found apply method: {name}"


# ── TestFailureIsolation ─────────────────────────────────────────


class TestFailureIsolation:
    @pytest.mark.asyncio
    async def test_flush_failure_returns_none(self):
        db = _mock_db()
        db.flush = AsyncMock(side_effect=Exception("DB down"))
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_add_failure_returns_none(self):
        db = _mock_db()
        db.add = MagicMock(side_effect=Exception("Constraint"))
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self):
        db = _mock_db()
        db.flush = AsyncMock(side_effect=RuntimeError("Unexpected"))
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )
        assert result is None


# ── TestIdempotency ──────────────────────────────────────────────


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_dedupe_key_returns_existing(self):
        """When IntegrityError occurs (dedupe_key collision), return existing receipt."""
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        existing_receipt = ShadowWriteReceipt(
            receipt_id="existing-id",
            dedupe_key="existing-key",
            symbol="SOL/USDT",
            target_table="symbols",
            target_field="qualification_status",
            intended_value="pass",
            would_change_summary="test",
            transition_reason="test",
            input_fingerprint="fp",
            dry_run=True,
            executed=False,
            business_write_count=0,
            verdict="would_write",
        )

        # First flush raises IntegrityError, then execute returns existing
        db.flush = AsyncMock(side_effect=IntegrityError("dup", {}, Exception()))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_receipt
        db.execute = AsyncMock(return_value=mock_result)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        assert result is existing_receipt
        db.rollback.assert_awaited_once()


# ── TestBusinessTableWriteZero ───────────────────────────────────


class TestBusinessTableWriteZero:
    """Verify no business tables are modified."""

    @pytest.mark.asyncio
    async def test_symbols_table_not_touched(self):
        """evaluate_shadow_write does not write to symbols table."""
        db = _mock_db()
        shadow = _shadow_qualified()
        readthrough = _make_readthrough(shadow_result=shadow)

        result = await evaluate_shadow_write(
            db,
            _uid(),
            shadow,
            readthrough,
            "SOL/USDT",
            "unchecked",
        )

        # Only one add call, and it's for ShadowWriteReceipt, not Symbol
        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, ShadowWriteReceipt)

    def test_allowed_targets_is_readonly(self):
        assert isinstance(ALLOWED_TARGETS, frozenset)

    def test_forbidden_targets_is_readonly(self):
        assert isinstance(FORBIDDEN_TARGETS, frozenset)

    def test_no_symbol_model_import_in_service(self):
        """shadow_write_service should not import Symbol model (no business write)."""
        import app.services.shadow_write_service as svc
        import inspect

        source = inspect.getsource(svc)
        assert "from app.models.asset import Symbol" not in source
        assert "Symbol(" not in source


# ══════════════════════════════════════════════════════════════════
# RI-2B-2a Tests — Code + Contract, EXECUTION_ENABLED=False
# ══════════════════════════════════════════════════════════════════


def _make_shadow_receipt(
    receipt_id="shadow-001",
    symbol="SOL/USDT",
    verdict="would_write",
    current_value="unchecked",
    intended_value="pass",
) -> ShadowWriteReceipt:
    return ShadowWriteReceipt(
        receipt_id=receipt_id,
        dedupe_key=compute_dedupe_key(
            symbol,
            "symbols",
            "qualification_status",
            current_value,
            intended_value,
            "fp1",
            dry_run=True,
        ),
        symbol=symbol,
        target_table="symbols",
        target_field="qualification_status",
        current_value=current_value,
        intended_value=intended_value,
        would_change_summary=f"symbols.qualification_status: {current_value} → {intended_value}",
        transition_reason="shadow_qualified",
        block_reason_code=None,
        shadow_observation_id=1,
        input_fingerprint="fp1",
        dry_run=True,
        executed=False,
        business_write_count=0,
        verdict=verdict,
    )


def _mock_db_with_receipt(shadow_receipt):
    """Mock DB that returns shadow_receipt on SELECT, accepts add/flush."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = shadow_receipt

    # Default: first execute returns the receipt, subsequent return empty lists
    call_count = {"n": 0}
    original_shadow = shadow_receipt

    async def mock_execute(stmt, params=None):
        call_count["n"] += 1
        m = MagicMock()
        # First call = shadow receipt lookup
        if call_count["n"] == 1:
            m.scalar_one_or_none.return_value = original_shadow
            return m
        # Second call = all_receipts for consumed check (empty list)
        if call_count["n"] == 2:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = []
            m.scalars.return_value = scalars_mock
            return m
        # Third call = SELECT FOR UPDATE (current value)
        if call_count["n"] == 3:
            m.fetchone.return_value = ("unchecked",)
            return m
        # Fourth call = CAS UPDATE
        if call_count["n"] == 4:
            m.rowcount = 1
            return m
        # Fifth call = post-write verify
        if call_count["n"] == 5:
            intended = original_shadow.intended_value if original_shadow else "pass"
            m.fetchone.return_value = (intended,)
            return m
        return m

    db.execute = AsyncMock(side_effect=mock_execute)
    return db


# ── TestExecutionEnabledFlag ────────────────────────────────────


class TestExecutionEnabledFlag:
    """Verify EXECUTION_ENABLED=False is hardcoded in RI-2B-2a."""

    def test_execution_enabled_is_true(self):
        assert EXECUTION_ENABLED is True

    def test_execution_enabled_is_module_constant(self):
        import app.services.shadow_write_service as svc

        assert hasattr(svc, "EXECUTION_ENABLED")
        assert svc.EXECUTION_ENABLED is True

    def test_execution_enabled_hardcoded_in_source(self):
        import app.services.shadow_write_service as svc
        import inspect

        source = inspect.getsource(svc)
        assert "EXECUTION_ENABLED: bool = True" in source


# ── TestExecuteBoundedWriteBlocked ──────────────────────────────


class TestExecuteBoundedWriteBlocked:
    """With EXECUTION_ENABLED=False, all calls are BLOCKED at Step 1.

    Module-level flag is True after RI-2B-2b B3' activation; these tests
    force False locally via @patch to preserve the disabled-mode contract.
    """

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", False)
    async def test_blocked_execution_disabled(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _make_shadow_receipt()
        db.execute = AsyncMock(return_value=mock_result)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.EXECUTION_DISABLED.value
        assert result.dry_run is True
        assert result.executed is False
        assert result.business_write_count == 0

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", False)
    async def test_blocked_execution_disabled_no_shadow(self):
        """Even without prior receipt, EXECUTION_DISABLED is returned."""
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await execute_bounded_write(
            db,
            _uid(),
            "nonexistent",
            "SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.EXECUTION_DISABLED.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", False)
    async def test_transition_reason_contains_shadow_id(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _make_shadow_receipt()
        db.execute = AsyncMock(return_value=mock_result)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert "exec_of:shadow-001" in result.transition_reason


# ── TestExecuteBoundedWriteWithEnabled ──────────────────────────


class TestExecuteBoundedWriteWithEnabled:
    """Test execution flow with EXECUTION_ENABLED patched to True (mock only)."""

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_no_prior_receipt(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await execute_bounded_write(
            db,
            _uid(),
            "nonexistent",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.NO_PRIOR_RECEIPT.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_prior_receipt_wrong_verdict(self):
        db = _mock_db()
        receipt = _make_shadow_receipt(verdict="blocked")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = receipt
        db.execute = AsyncMock(return_value=mock_result)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.NO_PRIOR_RECEIPT.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_receipt_already_consumed(self):
        shadow = _make_shadow_receipt()
        consumed_exec = _make_shadow_receipt(
            receipt_id="exec-001",
            verdict="executed",
        )
        consumed_exec.transition_reason = "exec_of:shadow-001"

        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = [consumed_exec]
                m.scalars.return_value = scalars_mock
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_stale_precondition_db_value_changed(self):
        shadow = _make_shadow_receipt(current_value="unchecked")
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                # DB now says 'pass' instead of 'unchecked'
                m.fetchone.return_value = ("pass",)
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.STALE_PRECONDITION.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_receipt_current_value_mismatch(self):
        """receipt.current_value != DB current value → STALE_PRECONDITION."""
        shadow = _make_shadow_receipt(current_value="fail")  # receipt says 'fail'
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("unchecked",)  # DB says 'unchecked'
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.STALE_PRECONDITION.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_cas_mismatch_zero_rows(self):
        shadow = _make_shadow_receipt()
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("unchecked",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 0  # CAS fails
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.CAS_MISMATCH.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_success_executed(self):
        shadow = _make_shadow_receipt()
        db = _mock_db_with_receipt(shadow)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.EXECUTED.value
        assert result.dry_run is False
        assert result.executed is True
        assert result.business_write_count == 1

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_success_fail_transition(self):
        shadow = _make_shadow_receipt(intended_value="fail")
        db = _mock_db_with_receipt(shadow)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.EXECUTED.value
        assert result.business_write_count == 1

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_post_write_verify_failure(self):
        shadow = _make_shadow_receipt()
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("unchecked",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 1
                return m
            if call_count["n"] == 5:
                # Post-write verify: wrong value
                m.fetchone.return_value = ("unchecked",)  # Should be 'pass' but isn't
                return m
            if call_count["n"] == 6:
                # Rollback UPDATE
                m.rowcount = 1
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.EXECUTION_FAILED.value
        assert result.executed is False
        assert result.business_write_count == 0

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_write_failure_consumed_false(self):
        """CAS mismatch → consumed stays False (receipt reusable)."""
        shadow = _make_shadow_receipt()
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("unchecked",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 0  # CAS fails
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        # BLOCKED verdict = consumed stays False
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        # The shadow receipt itself is not marked consumed
        # (no EXECUTED receipt linked to shadow-001)

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_post_write_fail_consumed_false(self):
        """Post-write verify failure → consumed stays False."""
        shadow = _make_shadow_receipt()
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("unchecked",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 1
                return m
            if call_count["n"] == 5:
                m.fetchone.return_value = ("unchecked",)  # Verify fail
                return m
            if call_count["n"] == 6:
                m.rowcount = 1  # Rollback
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        # EXECUTION_FAILED = not consumed
        assert result.verdict == ExecutionVerdict.EXECUTION_FAILED.value


# ── TestRollbackBoundedWrite ────────────────────────────────────


class TestRollbackBoundedWrite:
    """Rollback tests — verify both disabled-mode block and enabled-mode paths.

    Module-level flag is True after RI-2B-2b B3' activation; the disabled-mode
    test forces False locally via @patch to preserve the disabled-mode contract.
    """

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", False)
    async def test_rollback_blocked_execution_disabled(self):
        db = _mock_db()

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.EXECUTION_DISABLED.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_no_execution_receipt(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "nonexistent",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.NO_PRIOR_RECEIPT.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_wrong_verdict(self):
        """Can only rollback EXECUTED receipts."""
        exec_receipt = _make_shadow_receipt(receipt_id="exec-001", verdict="blocked")
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = exec_receipt
        db.execute = AsyncMock(return_value=mock_result)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.PRECONDITION_FAILED.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_already_rolled_back(self):
        exec_receipt = _make_shadow_receipt(receipt_id="exec-001", verdict="executed")
        existing_rollback = _make_shadow_receipt(receipt_id="rb-001", verdict="rolled_back")
        existing_rollback.transition_reason = "rollback_of:exec-001"

        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = exec_receipt
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = [existing_rollback]
                m.scalars.return_value = scalars_mock
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_stale_db_value(self):
        """DB value doesn't match intended_value → can't rollback."""
        exec_receipt = _make_shadow_receipt(
            receipt_id="exec-001",
            verdict="executed",
            intended_value="pass",
        )
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = exec_receipt
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("fail",)  # DB says 'fail', not 'pass'
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.STALE_PRECONDITION.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_success(self):
        exec_receipt = _make_shadow_receipt(
            receipt_id="exec-001",
            verdict="executed",
            current_value="unchecked",
            intended_value="pass",
        )
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = exec_receipt
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("pass",)  # Current = intended
                return m
            if call_count["n"] == 4:
                m.rowcount = 1  # CAS rollback
                return m
            if call_count["n"] == 5:
                m.fetchone.return_value = ("unchecked",)  # Post-rollback verify
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        # Mock SAVEPOINT (begin_nested)
        nested_mock = AsyncMock()
        nested_mock.commit = AsyncMock()
        nested_mock.rollback = AsyncMock()
        db.begin_nested = AsyncMock(return_value=nested_mock)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.ROLLED_BACK.value
        assert result.business_write_count == -1
        assert "rollback_of:exec-001" in result.transition_reason

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_receipt_linked_to_execution(self):
        exec_receipt = _make_shadow_receipt(
            receipt_id="exec-001",
            verdict="executed",
            current_value="unchecked",
            intended_value="pass",
        )
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = exec_receipt
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("pass",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 1
                return m
            if call_count["n"] == 5:
                m.fetchone.return_value = ("unchecked",)
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        # Mock SAVEPOINT (begin_nested)
        nested_mock = AsyncMock()
        nested_mock.commit = AsyncMock()
        nested_mock.rollback = AsyncMock()
        db.begin_nested = AsyncMock(return_value=nested_mock)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        assert result.transition_reason == "rollback_of:exec-001"


# ── TestRI2B2dRollbackRemediation ──────────────────────────────


class TestRI2B2dRollbackRemediation:
    """CR-048 RI-2B-2d regression tests for the 3 drill findings."""

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_savepoint_receipt_failure_returns_orphan(self):
        """Finding #2 regression: receipt INSERT failure must NOT undo business revert.

        When Step 8 INSERT fails inside SAVEPOINT, the CAS UPDATE from Step 6
        must remain intact, and the function returns ROLLBACK_ORPHAN (not None).
        """
        exec_receipt = _make_shadow_receipt(
            receipt_id="exec-001",
            verdict="executed",
            current_value="unchecked",
            intended_value="pass",
        )
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = exec_receipt
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("pass",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 1
                return m
            if call_count["n"] == 5:
                m.fetchone.return_value = ("unchecked",)
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        # SAVEPOINT commit raises IntegrityError (simulating dedupe collision)
        nested_mock = AsyncMock()
        nested_mock.commit = AsyncMock(side_effect=IntegrityError("dedupe", {}, Exception()))
        nested_mock.rollback = AsyncMock()
        db.begin_nested = AsyncMock(return_value=nested_mock)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        # Business revert happened (flush was called before SAVEPOINT)
        assert db.flush.call_count >= 1
        # Returns ROLLBACK_ORPHAN, not None
        assert result is not None
        assert result.verdict == ExecutionVerdict.ROLLBACK_ORPHAN.value
        assert result.business_write_count == -1

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_rollback_orphan_not_persisted(self):
        """ROLLBACK_ORPHAN receipt must not be db.add()-ed."""
        exec_receipt = _make_shadow_receipt(
            receipt_id="exec-001",
            verdict="executed",
            current_value="unchecked",
            intended_value="pass",
        )
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = exec_receipt
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            if call_count["n"] == 3:
                m.fetchone.return_value = ("pass",)
                return m
            if call_count["n"] == 4:
                m.rowcount = 1
                return m
            if call_count["n"] == 5:
                m.fetchone.return_value = ("unchecked",)
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        nested_mock = AsyncMock()
        nested_mock.commit = AsyncMock(side_effect=IntegrityError("dedupe", {}, Exception()))
        nested_mock.rollback = AsyncMock()
        db.begin_nested = AsyncMock(return_value=nested_mock)

        result = await rollback_bounded_write(
            db,
            _uid(),
            "exec-001",
            "SOL/USDT",
        )

        # The orphan receipt is built in-memory only — db.add is called once
        # (for the Step 8 attempt inside SAVEPOINT) but SAVEPOINT was rolled back.
        # The orphan returned is NOT added again.
        assert result.verdict == ExecutionVerdict.ROLLBACK_ORPHAN.value
        assert nested_mock.rollback.call_count == 1

    def test_rollback_failed_error_attributes(self):
        """RollbackFailedError carries diagnostic fields."""
        err = RollbackFailedError(
            symbol="SOL/USDT",
            execution_receipt_id="exec-001",
            phase="business_revert",
            cause=RuntimeError("test"),
        )
        assert err.symbol == "SOL/USDT"
        assert err.execution_receipt_id == "exec-001"
        assert err.phase == "business_revert"
        assert isinstance(err.cause, RuntimeError)
        assert "SOL/USDT" in str(err)

    def test_execution_verdict_has_rollback_orphan(self):
        """ROLLBACK_ORPHAN is a valid ExecutionVerdict member."""
        assert hasattr(ExecutionVerdict, "ROLLBACK_ORPHAN")
        assert ExecutionVerdict.ROLLBACK_ORPHAN.value == "rollback_orphan"


# ── TestRI2B2aSealedProtection ──────────────────────────────────


class TestRI2B2aSealedProtection:
    """Verify RI-2B-1 sealed code is untouched."""

    def test_evaluate_verdict_unchanged(self):
        """evaluate_verdict still works as RI-2B-1 defined it."""
        verdict, reason, intended, _ = evaluate_verdict(
            "SOL/USDT",
            "symbols",
            "qualification_status",
            "unchecked",
            _shadow_qualified(),
            _make_readthrough(),
        )
        assert verdict == WriteVerdict.WOULD_WRITE
        assert intended == "pass"

    def test_evaluate_shadow_write_exists(self):
        assert callable(evaluate_shadow_write)

    def test_compute_dedupe_key_exists(self):
        assert callable(compute_dedupe_key)

    def test_write_verdict_has_three_values(self):
        assert len(WriteVerdict) == 3

    def test_original_block_reason_codes_present(self):
        original = {
            "OUT_OF_SCOPE",
            "FORBIDDEN_TARGET",
            "INPUT_INVALID",
            "ALREADY_MATCHED",
            "PRECONDITION_FAILED",
        }
        for code in original:
            assert hasattr(BlockReasonCode, code)

    def test_model_schema_unchanged(self):
        cols = {c.name for c in ShadowWriteReceipt.__table__.columns}
        assert len(cols) == 18  # RI-2B-1 defined 18 columns


# ── TestExecutionFailureIsolation ───────────────────────────────


class TestExecutionFailureIsolation:
    """Verify exception behavior for execute/rollback.

    execute_bounded_write: returns None on failure (unchanged).
    rollback_bounded_write: raises RollbackFailedError on failure (RI-2B-2d).
    """

    @pytest.mark.asyncio
    async def test_execute_exception_returns_none(self):
        db = _mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("DB exploded"))

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_rollback_exception_raises_rollback_failed_error(self):
        db = _mock_db()
        db.execute = AsyncMock(side_effect=RuntimeError("DB exploded"))
        db.add = MagicMock(side_effect=RuntimeError("add exploded"))

        with pytest.raises(RollbackFailedError) as exc_info:
            await rollback_bounded_write(
                db,
                _uid(),
                "exec-001",
                "SOL/USDT",
            )

        assert exc_info.value.symbol == "SOL/USDT"
        assert exc_info.value.phase == "unknown"


# ── TestForbiddenTargetExecution ────────────────────────────────


class TestForbiddenTargetExecution:
    """Forbidden targets blocked even with EXECUTION_ENABLED=True."""

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", True)
    async def test_forbidden_target_blocked(self):
        shadow = _make_shadow_receipt()
        db = _mock_db()
        call_count = {"n": 0}

        async def mock_execute(stmt, params=None):
            call_count["n"] += 1
            m = MagicMock()
            if call_count["n"] == 1:
                m.scalar_one_or_none.return_value = shadow
                return m
            if call_count["n"] == 2:
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = []
                m.scalars.return_value = scalars_mock
                return m
            return m

        db.execute = AsyncMock(side_effect=mock_execute)

        result = await execute_bounded_write(
            db,
            _uid(),
            "shadow-001",
            "SOL/USDT",
            target_table="symbols",
            target_field="status",
        )

        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.FORBIDDEN_TARGET.value
