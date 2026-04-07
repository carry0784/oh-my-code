"""FT-1 ~ FT-5: execute_bounded_write / rollback_bounded_write integration tests.

These tests run against a real SQLite database (via conftest.py db_session)
to verify the 10-step CAS logic end-to-end, NOT against mocks.

Coverage:
  FT-1  execute_bounded_write full 10-step CAS (happy path)
  FT-2  rollback_bounded_write after successful execution
  FT-3  CAS 0-row edge case (concurrent mutation / stale precondition)
  FT-4  Exception behavior — receipt consumed / already-rolled-back guards
  FT-5  Behavioral contract tests (replaces inspect.getsource approach)

Governance: ops_state.json future_tracking FT-1~FT-5.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetClass, AssetSector, AssetTheme, Symbol, SymbolStatus
from app.models.shadow_write_receipt import ShadowWriteReceipt
from app.services.shadow_write_service import (
    ALLOWED_TRANSITIONS,
    BlockReasonCode,
    ExecutionVerdict,
    RollbackFailedError,
    WriteVerdict,
    compute_dedupe_key,
    execute_bounded_write,
    rollback_bounded_write,
)


# ── Helpers ─────────────────────────────────────────────────────────


def _uid() -> str:
    return str(uuid.uuid4())


def _make_symbol(
    symbol: str = "SOL/USDT",
    qualification_status: str = "unchecked",
) -> Symbol:
    """Create a Symbol instance with minimal required fields."""
    return Symbol(
        id=_uid(),
        symbol=symbol,
        name=f"Test {symbol}",
        asset_class=AssetClass.CRYPTO,
        sector=AssetSector.LAYER1,
        theme=AssetTheme.NONE,
        exchanges='["binance"]',
        status=SymbolStatus.WATCH,
        qualification_status=qualification_status,
    )


def _make_shadow_receipt(
    receipt_id: str | None = None,
    symbol: str = "SOL/USDT",
    current_value: str = "unchecked",
    intended_value: str = "pass",
    verdict: str = "would_write",
) -> ShadowWriteReceipt:
    """Create a shadow receipt (RI-2B-1 dry-run) to seed as prior receipt."""
    rid = receipt_id or _uid()
    return ShadowWriteReceipt(
        receipt_id=rid,
        dedupe_key=compute_dedupe_key(
            symbol,
            "symbols",
            "qualification_status",
            current_value,
            intended_value,
            "fp-integration-test",
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
        shadow_observation_id=None,
        input_fingerprint="fp-integration-test",
        dry_run=True,
        executed=False,
        business_write_count=0,
        verdict=verdict,
    )


async def _read_qualification_status(db: AsyncSession, symbol: str) -> str | None:
    """Read current qualification_status from symbols table."""
    result = await db.execute(
        text("SELECT qualification_status FROM symbols WHERE symbol = :s"),
        {"s": symbol},
    )
    row = result.fetchone()
    return row[0] if row else None


# ── FT-1: Full 10-step CAS happy path ──────────────────────────────


class TestFT1ExecuteBoundedWrite:
    """FT-1: execute_bounded_write integration test (10-step CAS)."""

    @pytest.mark.asyncio
    async def test_happy_path_unchecked_to_pass(self, db_session: AsyncSession) -> None:
        """Seed unchecked symbol + WOULD_WRITE receipt → EXECUTED, DB = 'pass'."""
        sym = _make_symbol(symbol="SOL/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            symbol="SOL/USDT",
            current_value="unchecked",
            intended_value="pass",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        exec_receipt_id = _uid()
        result = await execute_bounded_write(
            db=db_session,
            receipt_id=exec_receipt_id,
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.EXECUTED.value
        assert result.executed is True
        assert result.business_write_count == 1
        assert result.dry_run is False
        assert result.transition_reason == f"exec_of:{shadow_receipt.receipt_id}"

        # Verify DB state changed
        actual = await _read_qualification_status(db_session, "SOL/USDT")
        assert actual == "pass"

    @pytest.mark.asyncio
    async def test_happy_path_unchecked_to_fail(self, db_session: AsyncSession) -> None:
        """unchecked → fail is also an allowed transition."""
        sym = _make_symbol(symbol="BTC/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="BTC/USDT",
            current_value="unchecked",
            intended_value="fail",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="BTC/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.EXECUTED.value

        actual = await _read_qualification_status(db_session, "BTC/USDT")
        assert actual == "fail"


# ── FT-2: rollback_bounded_write after execution ───────────────────


class TestFT2RollbackBoundedWrite:
    """FT-2: rollback_bounded_write integration test."""

    @pytest.mark.asyncio
    async def test_rollback_after_successful_execution(
        self, db_session: AsyncSession
    ) -> None:
        """Execute unchecked→pass, then rollback pass→unchecked."""
        # Setup: symbol + shadow receipt
        sym = _make_symbol(symbol="SOL/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(symbol="SOL/USDT")
        db_session.add(shadow_receipt)
        await db_session.flush()

        # Step 1: Execute
        exec_id = _uid()
        exec_result = await execute_bounded_write(
            db=db_session,
            receipt_id=exec_id,
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="SOL/USDT",
        )
        assert exec_result is not None
        assert exec_result.verdict == ExecutionVerdict.EXECUTED.value

        # Confirm DB = 'pass'
        assert await _read_qualification_status(db_session, "SOL/USDT") == "pass"

        # Step 2: Rollback
        rb_id = _uid()
        rb_result = await rollback_bounded_write(
            db=db_session,
            receipt_id=rb_id,
            execution_receipt_id=exec_id,
            symbol="SOL/USDT",
        )

        assert rb_result is not None
        assert rb_result.verdict == ExecutionVerdict.ROLLED_BACK.value
        assert rb_result.business_write_count == -1
        assert rb_result.transition_reason == f"rollback_of:{exec_id}"

        # Confirm DB reverted to 'unchecked'
        assert await _read_qualification_status(db_session, "SOL/USDT") == "unchecked"


# ── FT-3: CAS 0-row edge cases ────────────────────────────────────


class TestFT3CASEdgeCases:
    """FT-3: CAS 0-row / stale precondition edge case tests."""

    @pytest.mark.asyncio
    async def test_stale_precondition_already_pass(
        self, db_session: AsyncSession
    ) -> None:
        """Symbol already 'pass' but receipt says current='unchecked' → BLOCKED."""
        sym = _make_symbol(symbol="ETH/USDT", qualification_status="pass")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="ETH/USDT",
            current_value="unchecked",
            intended_value="pass",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="ETH/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.STALE_PRECONDITION.value
        assert result.executed is False

        # DB unchanged
        assert await _read_qualification_status(db_session, "ETH/USDT") == "pass"

    @pytest.mark.asyncio
    async def test_symbol_not_found_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """No symbol row in DB → BLOCKED (current_db_value is None)."""
        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="PHANTOM/USDT",
            current_value="unchecked",
            intended_value="pass",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="PHANTOM/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.STALE_PRECONDITION.value

    @pytest.mark.asyncio
    async def test_disallowed_transition_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """Transition unchecked→invalid should be BLOCKED (not in ALLOWED_TRANSITIONS)."""
        sym = _make_symbol(symbol="AVAX/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="AVAX/USDT",
            current_value="unchecked",
            intended_value="invalid_value",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="AVAX/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.PRECONDITION_FAILED.value

        # DB unchanged
        assert await _read_qualification_status(db_session, "AVAX/USDT") == "unchecked"


# ── FT-4: Exception / guard behavior ──────────────────────────────


class TestFT4GuardBehavior:
    """FT-4: Receipt consumed / already-rolled-back / exception guards."""

    @pytest.mark.asyncio
    async def test_receipt_already_consumed_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """Same shadow_receipt_id used twice → 2nd call BLOCKED."""
        sym = _make_symbol(symbol="DOT/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="DOT/USDT",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        # First execution — should succeed
        exec1_id = _uid()
        result1 = await execute_bounded_write(
            db=db_session,
            receipt_id=exec1_id,
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="DOT/USDT",
        )
        assert result1 is not None
        assert result1.verdict == ExecutionVerdict.EXECUTED.value

        # Second execution with same shadow_receipt_id — should BLOCK
        result2 = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="DOT/USDT",
        )
        assert result2 is not None
        assert result2.verdict == ExecutionVerdict.BLOCKED.value
        assert result2.block_reason_code == BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value

    @pytest.mark.asyncio
    async def test_double_rollback_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """Rollback same execution twice → 2nd call BLOCKED."""
        sym = _make_symbol(symbol="LINK/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="LINK/USDT",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        # Execute
        exec_id = _uid()
        exec_result = await execute_bounded_write(
            db=db_session,
            receipt_id=exec_id,
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="LINK/USDT",
        )
        assert exec_result is not None
        assert exec_result.verdict == ExecutionVerdict.EXECUTED.value

        # First rollback — should succeed
        rb1_id = _uid()
        rb1 = await rollback_bounded_write(
            db=db_session,
            receipt_id=rb1_id,
            execution_receipt_id=exec_id,
            symbol="LINK/USDT",
        )
        assert rb1 is not None
        assert rb1.verdict == ExecutionVerdict.ROLLED_BACK.value

        # Second rollback — should BLOCK (already rolled back)
        rb2_id = _uid()
        rb2 = await rollback_bounded_write(
            db=db_session,
            receipt_id=rb2_id,
            execution_receipt_id=exec_id,
            symbol="LINK/USDT",
        )
        assert rb2 is not None
        assert rb2.verdict == ExecutionVerdict.BLOCKED.value
        assert rb2.block_reason_code == BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value

    @pytest.mark.asyncio
    async def test_no_prior_shadow_receipt_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """execute_bounded_write with nonexistent shadow_receipt_id → BLOCKED."""
        sym = _make_symbol(symbol="ATOM/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id="nonexistent-shadow-id",
            symbol="ATOM/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.NO_PRIOR_RECEIPT.value

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_execution_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """rollback_bounded_write with nonexistent execution_receipt_id → BLOCKED."""
        result = await rollback_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            execution_receipt_id="nonexistent-exec-id",
            symbol="SOL/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.NO_PRIOR_RECEIPT.value

    @pytest.mark.asyncio
    @patch("app.services.shadow_write_service.EXECUTION_ENABLED", False)
    async def test_execution_disabled_blocks(
        self, db_session: AsyncSession
    ) -> None:
        """EXECUTION_ENABLED=False → BLOCKED."""
        sym = _make_symbol(symbol="ADA/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="ADA/USDT",
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="ADA/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value
        assert result.block_reason_code == BlockReasonCode.EXECUTION_DISABLED.value

        # DB unchanged
        assert await _read_qualification_status(db_session, "ADA/USDT") == "unchecked"

    @pytest.mark.asyncio
    async def test_would_skip_receipt_blocks_execution(
        self, db_session: AsyncSession
    ) -> None:
        """Shadow receipt with verdict=WOULD_SKIP → BLOCKED (not WOULD_WRITE)."""
        sym = _make_symbol(symbol="XRP/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        shadow_receipt = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="XRP/USDT",
            verdict=WriteVerdict.WOULD_SKIP.value,
        )
        db_session.add(shadow_receipt)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=shadow_receipt.receipt_id,
            symbol="XRP/USDT",
        )

        assert result is not None
        assert result.verdict == ExecutionVerdict.BLOCKED.value

        # DB unchanged
        assert await _read_qualification_status(db_session, "XRP/USDT") == "unchecked"


# ── FT-5: Behavioral contract tests ───────────────────────────────


class TestFT5BehavioralContracts:
    """FT-5: Behavioral tests replacing inspect.getsource approach.

    Validates contracts through observable behavior, not code inspection.
    """

    @pytest.mark.asyncio
    async def test_allowed_transitions_contract(
        self, db_session: AsyncSession
    ) -> None:
        """Only ALLOWED_TRANSITIONS keys succeed. Verify by behavior."""
        # Verify allowed: unchecked→pass
        sym = _make_symbol(symbol="SOL-CONTRACT/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        sr = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="SOL-CONTRACT/USDT",
            current_value="unchecked",
            intended_value="pass",
        )
        db_session.add(sr)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=sr.receipt_id,
            symbol="SOL-CONTRACT/USDT",
        )
        assert result is not None
        assert result.verdict == ExecutionVerdict.EXECUTED.value

    @pytest.mark.asyncio
    async def test_forbidden_transition_pass_to_unchecked(
        self, db_session: AsyncSession
    ) -> None:
        """pass→unchecked is NOT in ALLOWED_TRANSITIONS → BLOCKED."""
        sym = _make_symbol(symbol="FORBIDDEN/USDT", qualification_status="pass")
        db_session.add(sym)
        await db_session.flush()

        sr = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="FORBIDDEN/USDT",
            current_value="pass",
            intended_value="unchecked",
        )
        db_session.add(sr)
        await db_session.flush()

        result = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=sr.receipt_id,
            symbol="FORBIDDEN/USDT",
        )
        assert result is not None
        # Blocked at step 6: STALE_PRECONDITION (db=pass != receipt=pass? no, db==receipt)
        # But step 6b: current != "unchecked" → BLOCKED
        assert result.verdict == ExecutionVerdict.BLOCKED.value

    @pytest.mark.asyncio
    async def test_receipt_append_only_contract(
        self, db_session: AsyncSession
    ) -> None:
        """Every execute/rollback adds a receipt. Receipt count only grows."""
        sym = _make_symbol(symbol="APPEND/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        sr = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="APPEND/USDT",
        )
        db_session.add(sr)
        await db_session.flush()

        # Count before
        before_count = await _receipt_count(db_session, "APPEND/USDT")

        # Execute
        exec_id = _uid()
        await execute_bounded_write(
            db=db_session,
            receipt_id=exec_id,
            shadow_receipt_id=sr.receipt_id,
            symbol="APPEND/USDT",
        )

        after_exec = await _receipt_count(db_session, "APPEND/USDT")
        assert after_exec > before_count  # new receipt added

        # Rollback
        rb_id = _uid()
        await rollback_bounded_write(
            db=db_session,
            receipt_id=rb_id,
            execution_receipt_id=exec_id,
            symbol="APPEND/USDT",
        )

        after_rb = await _receipt_count(db_session, "APPEND/USDT")
        assert after_rb > after_exec  # another receipt added

    @pytest.mark.asyncio
    async def test_execute_rollback_roundtrip_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        """Execute + rollback = original state."""
        sym = _make_symbol(symbol="ROUNDTRIP/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        original = await _read_qualification_status(db_session, "ROUNDTRIP/USDT")
        assert original == "unchecked"

        sr = _make_shadow_receipt(
            receipt_id=_uid(),
            symbol="ROUNDTRIP/USDT",
        )
        db_session.add(sr)
        await db_session.flush()

        # Execute: unchecked → pass
        exec_id = _uid()
        exec_r = await execute_bounded_write(
            db=db_session,
            receipt_id=exec_id,
            shadow_receipt_id=sr.receipt_id,
            symbol="ROUNDTRIP/USDT",
        )
        assert exec_r is not None
        assert exec_r.verdict == ExecutionVerdict.EXECUTED.value
        assert await _read_qualification_status(db_session, "ROUNDTRIP/USDT") == "pass"

        # Rollback: pass → unchecked
        rb_r = await rollback_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            execution_receipt_id=exec_id,
            symbol="ROUNDTRIP/USDT",
        )
        assert rb_r is not None
        assert rb_r.verdict == ExecutionVerdict.ROLLED_BACK.value

        # Final state == original
        final = await _read_qualification_status(db_session, "ROUNDTRIP/USDT")
        assert final == original

    @pytest.mark.asyncio
    async def test_one_to_one_binding_enforced(
        self, db_session: AsyncSession
    ) -> None:
        """Each shadow receipt can only be executed exactly once (1:1 binding)."""
        sym = _make_symbol(symbol="BINDING/USDT", qualification_status="unchecked")
        db_session.add(sym)
        await db_session.flush()

        sr = _make_shadow_receipt(receipt_id=_uid(), symbol="BINDING/USDT")
        db_session.add(sr)
        await db_session.flush()

        # First execute: success
        exec1_id = _uid()
        r1 = await execute_bounded_write(
            db=db_session,
            receipt_id=exec1_id,
            shadow_receipt_id=sr.receipt_id,
            symbol="BINDING/USDT",
        )
        assert r1 is not None
        assert r1.verdict == ExecutionVerdict.EXECUTED.value

        # Rollback to reset DB state
        await rollback_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            execution_receipt_id=exec1_id,
            symbol="BINDING/USDT",
        )

        # Second execute with SAME shadow receipt: BLOCKED (consumed)
        r2 = await execute_bounded_write(
            db=db_session,
            receipt_id=_uid(),
            shadow_receipt_id=sr.receipt_id,
            symbol="BINDING/USDT",
        )
        assert r2 is not None
        assert r2.verdict == ExecutionVerdict.BLOCKED.value
        assert r2.block_reason_code == BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value


async def _receipt_count(db: AsyncSession, symbol: str) -> int:
    """Count receipts for a symbol."""
    result = await db.execute(
        select(ShadowWriteReceipt).where(ShadowWriteReceipt.symbol == symbol)
    )
    return len(list(result.scalars().all()))
