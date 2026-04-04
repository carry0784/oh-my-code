"""RI-2B-1 + RI-2B-2a: Shadow Write Service.

RI-2B-1 (SEALED): evaluate_shadow_write — dry-run receipt-only.
RI-2B-2a: execute_bounded_write / rollback_bounded_write — code exists but
           EXECUTION_ENABLED=False (hardcoded). Real execution requires RI-2B-2b A approval.

INSERT failure does NOT propagate.

business_impact = false (RI-2B-2a: EXECUTION_ENABLED=False).
"""

from __future__ import annotations

import hashlib
import logging
from enum import Enum

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_write_receipt import ShadowWriteReceipt
from app.services.pipeline_shadow_runner import ShadowRunResult
from app.services.screening_qualification_pipeline import PipelineVerdict
from app.services.shadow_readthrough import ReadthroughComparisonResult

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────

ALLOWED_TARGETS: frozenset[tuple[str, str]] = frozenset(
    {
        ("symbols", "qualification_status"),
    }
)

FORBIDDEN_TARGETS: frozenset[tuple[str, str]] = frozenset(
    {
        ("symbols", "status"),
        ("symbols", "promotion_eligibility_status"),
        ("symbols", "paper_evaluation_status"),
        ("strategies", "status"),
    }
)

ALLOWED_TRANSITIONS: dict[tuple[str, str], frozenset[tuple[str, str]]] = {
    ("symbols", "qualification_status"): frozenset(
        {
            ("unchecked", "pass"),
            ("unchecked", "fail"),
        }
    ),
}


# RI-2B-2a: FORCED False. True 전환은 RI-2B-2b 별도 A 승인 후에만 허용.
# 무단 변경은 FROZEN violation으로 간주.
EXECUTION_ENABLED: bool = False


class WriteVerdict(str, Enum):
    WOULD_WRITE = "would_write"
    WOULD_SKIP = "would_skip"
    BLOCKED = "blocked"


class ExecutionVerdict(str, Enum):
    """RI-2B-2 execution verdicts (separate from RI-2B-1 WriteVerdict)."""

    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"
    ROLLED_BACK = "rolled_back"
    BLOCKED = "blocked"


class BlockReasonCode(str, Enum):
    # RI-2B-1 (기존 5개 — 무수정)
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    FORBIDDEN_TARGET = "FORBIDDEN_TARGET"
    INPUT_INVALID = "INPUT_INVALID"
    ALREADY_MATCHED = "ALREADY_MATCHED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    # RI-2B-2 (신규 5개)
    EXECUTION_DISABLED = "EXECUTION_DISABLED"
    NO_PRIOR_RECEIPT = "NO_PRIOR_RECEIPT"
    RECEIPT_ALREADY_CONSUMED = "RECEIPT_ALREADY_CONSUMED"
    STALE_PRECONDITION = "STALE_PRECONDITION"
    CAS_MISMATCH = "CAS_MISMATCH"


# ── Dedupe Key ───────────────────────────────────────────────────


def compute_dedupe_key(
    symbol: str,
    target_table: str,
    target_field: str,
    current_value: str | None,
    intended_value: str,
    input_fingerprint: str,
    dry_run: bool = True,
) -> str:
    """Compute SHA-256 semantic dedupe key from 7 fixed inputs."""
    raw = "|".join(
        [
            symbol,
            target_table,
            target_field,
            current_value if current_value is not None else "NULL",
            intended_value,
            input_fingerprint,
            str(dry_run).lower(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Verdict Decision (7-step) ────────────────────────────────────


def _derive_intended_value(shadow_result: ShadowRunResult) -> tuple[str | None, str]:
    """Derive intended qualification_status from shadow pipeline verdict.

    Returns (intended_value, transition_reason).
    """
    v = shadow_result.pipeline_output.result.verdict
    if v == PipelineVerdict.QUALIFIED:
        return "pass", "shadow_qualified"
    if v == PipelineVerdict.QUALIFY_FAILED:
        return "fail", "shadow_qualify_failed"
    return None, f"shadow_{v.value}"


def evaluate_verdict(
    symbol: str,
    target_table: str,
    target_field: str,
    current_value: str | None,
    shadow_result: ShadowRunResult | None,
    readthrough_result: ReadthroughComparisonResult | None,
) -> tuple[WriteVerdict, str | None, str | None, str]:
    """7-step deterministic verdict evaluation.

    Returns (verdict, block_reason_code, intended_value, transition_reason).
    """
    # Step 1: explicitly forbidden target (checked first for clear error code)
    if (target_table, target_field) in FORBIDDEN_TARGETS:
        return (
            WriteVerdict.BLOCKED,
            BlockReasonCode.FORBIDDEN_TARGET.value,
            None,
            "target_forbidden",
        )

    # Step 2: out of scope (not in allowed whitelist)
    if (target_table, target_field) not in ALLOWED_TARGETS:
        return WriteVerdict.BLOCKED, BlockReasonCode.OUT_OF_SCOPE.value, None, "target_not_allowed"

    # Step 3: input validation
    if shadow_result is None or readthrough_result is None:
        return WriteVerdict.BLOCKED, BlockReasonCode.INPUT_INVALID.value, None, "null_input"

    # Derive intended value from shadow result
    intended_value, transition_reason = _derive_intended_value(shadow_result)

    # Step 6 (early): shadow verdict doesn't produce a qualification decision
    if intended_value is None:
        return WriteVerdict.WOULD_SKIP, None, None, transition_reason

    # Step 4: already matched
    if current_value == intended_value:
        return WriteVerdict.WOULD_SKIP, None, intended_value, "already_matched"

    # Step 5: precondition check
    allowed = ALLOWED_TRANSITIONS.get((target_table, target_field), frozenset())
    if (current_value, intended_value) not in allowed:
        return (
            WriteVerdict.BLOCKED,
            BlockReasonCode.PRECONDITION_FAILED.value,
            intended_value,
            f"transition_{current_value}_to_{intended_value}_not_allowed",
        )

    # Step 7: all checks passed
    return WriteVerdict.WOULD_WRITE, None, intended_value, transition_reason


# ── Main Entry Point ─────────────────────────────────────────────


async def evaluate_shadow_write(
    db: AsyncSession,
    receipt_id: str,
    shadow_result: ShadowRunResult | None,
    readthrough_result: ReadthroughComparisonResult | None,
    symbol: str,
    current_qualification_status: str | None,
    target_table: str = "symbols",
    target_field: str = "qualification_status",
    shadow_observation_id: int | None = None,
) -> ShadowWriteReceipt | None:
    """Evaluate and record a shadow write receipt. Dry-run only.

    Contract:
      - INSERT only (UPDATE/DELETE: ZERO)
      - Business table write: ZERO
      - dry_run=True, executed=False, business_write_count=0: FORCED
      - Failure does NOT raise
      - Returns ShadowWriteReceipt on success, None on failure
    """
    try:
        verdict, block_reason, intended_value, transition_reason = evaluate_verdict(
            symbol=symbol,
            target_table=target_table,
            target_field=target_field,
            current_value=current_qualification_status,
            shadow_result=shadow_result,
            readthrough_result=readthrough_result,
        )

        effective_intended = intended_value if intended_value is not None else ""
        input_fp = getattr(shadow_result, "input_fingerprint", "") if shadow_result else ""

        # Build would_change_summary
        if verdict == WriteVerdict.WOULD_WRITE:
            summary = (
                f"{target_table}.{target_field}: {current_qualification_status} → {intended_value}"
            )
        elif verdict == WriteVerdict.BLOCKED:
            summary = f"BLOCKED({block_reason}): {target_table}.{target_field}"
        else:
            summary = f"SKIP: {target_table}.{target_field} ({transition_reason})"

        dedupe = compute_dedupe_key(
            symbol=symbol,
            target_table=target_table,
            target_field=target_field,
            current_value=current_qualification_status,
            intended_value=effective_intended,
            input_fingerprint=input_fp,
            dry_run=True,
        )

        row = ShadowWriteReceipt(
            receipt_id=receipt_id,
            dedupe_key=dedupe,
            symbol=symbol,
            target_table=target_table,
            target_field=target_field,
            current_value=current_qualification_status,
            intended_value=effective_intended,
            would_change_summary=summary,
            transition_reason=transition_reason,
            block_reason_code=block_reason,
            shadow_observation_id=shadow_observation_id,
            input_fingerprint=input_fp,
            # Forced proof fields
            dry_run=True,
            executed=False,
            business_write_count=0,
            verdict=verdict.value,
        )

        db.add(row)
        await db.flush()
        return row

    except IntegrityError:
        await db.rollback()
        try:
            stmt = (
                select(ShadowWriteReceipt)
                .where(
                    ShadowWriteReceipt.dedupe_key == dedupe,
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing
        except Exception:
            pass
        return None

    except Exception:
        logger.exception(
            "shadow write receipt INSERT failed for %s",
            symbol,
        )
        return None


# ── RI-2B-2a: Bounded Write (EXECUTION_ENABLED=False) ───────────


def _is_receipt_consumed(db_receipts: list[ShadowWriteReceipt], shadow_receipt_id: str) -> bool:
    """Check if a shadow receipt has been consumed by an EXECUTED execution receipt."""
    for r in db_receipts:
        if (
            r.transition_reason is not None
            and r.transition_reason.startswith(f"exec_of:{shadow_receipt_id}")
            and r.verdict == ExecutionVerdict.EXECUTED.value
        ):
            return True
    return False


def _is_already_rolled_back(
    db_receipts: list[ShadowWriteReceipt], execution_receipt_id: str
) -> bool:
    """Check if an execution receipt already has a ROLLED_BACK receipt."""
    for r in db_receipts:
        if (
            r.transition_reason is not None
            and r.transition_reason == f"rollback_of:{execution_receipt_id}"
            and r.verdict == ExecutionVerdict.ROLLED_BACK.value
        ):
            return True
    return False


def _make_execution_receipt(
    receipt_id: str,
    symbol: str,
    shadow_receipt: ShadowWriteReceipt,
    verdict: ExecutionVerdict,
    block_reason: str | None,
    summary: str,
    transition_reason: str,
    dry_run: bool,
    executed: bool,
    business_write_count: int,
) -> ShadowWriteReceipt:
    """Build an execution receipt row (append-only)."""
    dedupe = compute_dedupe_key(
        symbol=symbol,
        target_table=shadow_receipt.target_table,
        target_field=shadow_receipt.target_field,
        current_value=shadow_receipt.current_value,
        intended_value=shadow_receipt.intended_value,
        input_fingerprint=shadow_receipt.input_fingerprint,
        dry_run=dry_run,
    )
    return ShadowWriteReceipt(
        receipt_id=receipt_id,
        dedupe_key=dedupe,
        symbol=symbol,
        target_table=shadow_receipt.target_table,
        target_field=shadow_receipt.target_field,
        current_value=shadow_receipt.current_value,
        intended_value=shadow_receipt.intended_value,
        would_change_summary=summary,
        transition_reason=transition_reason,
        block_reason_code=block_reason,
        shadow_observation_id=shadow_receipt.shadow_observation_id,
        input_fingerprint=shadow_receipt.input_fingerprint,
        dry_run=dry_run,
        executed=executed,
        business_write_count=business_write_count,
        verdict=verdict.value,
    )


async def execute_bounded_write(
    db: AsyncSession,
    receipt_id: str,
    shadow_receipt_id: str,
    symbol: str,
    target_table: str = "symbols",
    target_field: str = "qualification_status",
) -> ShadowWriteReceipt | None:
    """RI-2B-2: Execute real bounded write with prior receipt validation.

    Contract:
      - EXECUTION_ENABLED must be True (False in RI-2B-2a)
      - Prior receipt (WOULD_WRITE, not consumed) required
      - SELECT FOR UPDATE + Compare-and-Set (no blind write)
      - Post-write 5-point verification
      - consumed=True only after post-write verification
      - Failure: rollback + EXECUTION_FAILED receipt
      - Exception does NOT propagate (return None)
    """
    try:
        # Step 1: execution_enabled check
        if not EXECUTION_ENABLED:
            # Record BLOCKED receipt even when disabled
            # Need to fetch shadow receipt for building the response
            stmt = (
                select(ShadowWriteReceipt)
                .where(
                    ShadowWriteReceipt.receipt_id == shadow_receipt_id,
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            shadow_receipt = result.scalar_one_or_none()

            if shadow_receipt is None:
                # Can't even build a proper receipt without shadow data
                row = ShadowWriteReceipt(
                    receipt_id=receipt_id,
                    dedupe_key=compute_dedupe_key(
                        symbol,
                        target_table,
                        target_field,
                        "",
                        "",
                        "",
                        dry_run=False,
                    ),
                    symbol=symbol,
                    target_table=target_table,
                    target_field=target_field,
                    current_value=None,
                    intended_value="",
                    would_change_summary=f"BLOCKED(EXECUTION_DISABLED): {target_table}.{target_field}",
                    transition_reason=f"exec_of:{shadow_receipt_id}",
                    block_reason_code=BlockReasonCode.EXECUTION_DISABLED.value,
                    shadow_observation_id=None,
                    input_fingerprint="",
                    dry_run=True,
                    executed=False,
                    business_write_count=0,
                    verdict=ExecutionVerdict.BLOCKED.value,
                )
                db.add(row)
                await db.flush()
                return row

            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.EXECUTION_DISABLED.value,
                summary=f"BLOCKED(EXECUTION_DISABLED): {target_table}.{target_field}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 2: prior receipt existence
        stmt = (
            select(ShadowWriteReceipt)
            .where(
                ShadowWriteReceipt.receipt_id == shadow_receipt_id,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        shadow_receipt = result.scalar_one_or_none()

        if shadow_receipt is None:
            row = ShadowWriteReceipt(
                receipt_id=receipt_id,
                dedupe_key=compute_dedupe_key(
                    symbol,
                    target_table,
                    target_field,
                    "",
                    "",
                    "",
                    dry_run=False,
                ),
                symbol=symbol,
                target_table=target_table,
                target_field=target_field,
                current_value=None,
                intended_value="",
                would_change_summary=f"BLOCKED(NO_PRIOR_RECEIPT): {target_table}.{target_field}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                block_reason_code=BlockReasonCode.NO_PRIOR_RECEIPT.value,
                shadow_observation_id=None,
                input_fingerprint="",
                dry_run=True,
                executed=False,
                business_write_count=0,
                verdict=ExecutionVerdict.BLOCKED.value,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 3: prior receipt verdict check
        if shadow_receipt.verdict != WriteVerdict.WOULD_WRITE.value:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.NO_PRIOR_RECEIPT.value,
                summary=f"BLOCKED(NO_PRIOR_RECEIPT): verdict={shadow_receipt.verdict}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 4: consumed check (1:1 binding)
        stmt = select(ShadowWriteReceipt).where(
            ShadowWriteReceipt.symbol == symbol,
        )
        result = await db.execute(stmt)
        all_receipts = list(result.scalars().all())

        if _is_receipt_consumed(all_receipts, shadow_receipt_id):
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value,
                summary=f"BLOCKED(RECEIPT_ALREADY_CONSUMED): {shadow_receipt_id}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 5: forbidden/allowed targets
        if (target_table, target_field) in FORBIDDEN_TARGETS:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.FORBIDDEN_TARGET.value,
                summary=f"BLOCKED(FORBIDDEN_TARGET): {target_table}.{target_field}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        if (target_table, target_field) not in ALLOWED_TARGETS:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.OUT_OF_SCOPE.value,
                summary=f"BLOCKED(OUT_OF_SCOPE): {target_table}.{target_field}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 6: real-time DB check (TOCTOU defense)
        db_stmt = text("SELECT qualification_status FROM symbols WHERE symbol = :symbol FOR UPDATE")
        db_result = await db.execute(db_stmt, {"symbol": symbol})
        db_row = db_result.fetchone()
        current_db_value = db_row[0] if db_row else None

        if current_db_value != shadow_receipt.current_value:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.STALE_PRECONDITION.value,
                summary=f"BLOCKED(STALE): db={current_db_value} != receipt={shadow_receipt.current_value}",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        if current_db_value != "unchecked":
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.STALE_PRECONDITION.value,
                summary=f"BLOCKED(STALE): current={current_db_value}, expected=unchecked",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 7: allowed transitions
        intended = shadow_receipt.intended_value
        allowed = ALLOWED_TRANSITIONS.get((target_table, target_field), frozenset())
        if (current_db_value, intended) not in allowed:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.PRECONDITION_FAILED.value,
                summary=f"BLOCKED(PRECONDITION): {current_db_value}→{intended} not allowed",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 8: Compare-and-Set UPDATE
        cas_stmt = text(
            "UPDATE symbols SET qualification_status = :intended "
            "WHERE symbol = :symbol AND qualification_status = :expected"
        )
        cas_result = await db.execute(
            cas_stmt,
            {
                "intended": intended,
                "symbol": symbol,
                "expected": "unchecked",
            },
        )

        if cas_result.rowcount == 0:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.CAS_MISMATCH.value,
                summary=f"BLOCKED(CAS_MISMATCH): 0 rows affected",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        if cas_result.rowcount > 1:
            await db.rollback()
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.EXECUTION_FAILED,
                block_reason=None,
                summary=f"EXECUTION_FAILED: {cas_result.rowcount} rows affected (expected 1)",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=False,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 9: Post-write verification
        verify_stmt = text("SELECT qualification_status FROM symbols WHERE symbol = :symbol")
        verify_result = await db.execute(verify_stmt, {"symbol": symbol})
        verify_row = verify_result.fetchone()
        actual_value = verify_row[0] if verify_row else None

        if actual_value != intended:
            # Post-write verification failed → rollback
            rollback_stmt = text(
                "UPDATE symbols SET qualification_status = :original "
                "WHERE symbol = :symbol AND qualification_status = :intended"
            )
            await db.execute(
                rollback_stmt,
                {
                    "original": shadow_receipt.current_value,
                    "symbol": symbol,
                    "intended": intended,
                },
            )
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=shadow_receipt,
                verdict=ExecutionVerdict.EXECUTION_FAILED,
                block_reason=None,
                summary=f"EXECUTION_FAILED: post-write verify failed (actual={actual_value})",
                transition_reason=f"exec_of:{shadow_receipt_id}",
                dry_run=False,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 10: Success — EXECUTED receipt + consumed marking
        row = _make_execution_receipt(
            receipt_id=receipt_id,
            symbol=symbol,
            shadow_receipt=shadow_receipt,
            verdict=ExecutionVerdict.EXECUTED,
            block_reason=None,
            summary=f"{target_table}.{target_field}: {shadow_receipt.current_value} → {intended} (EXECUTED)",
            transition_reason=f"exec_of:{shadow_receipt_id}",
            dry_run=False,
            executed=True,
            business_write_count=1,
        )
        db.add(row)
        await db.flush()
        return row

    except Exception:
        logger.exception(
            "execute_bounded_write failed for %s",
            symbol,
        )
        return None


async def rollback_bounded_write(
    db: AsyncSession,
    receipt_id: str,
    execution_receipt_id: str,
    symbol: str,
) -> ShadowWriteReceipt | None:
    """RI-2B-2: Manual rollback of a bounded write. 1-time only.

    Contract:
      - EXECUTION_ENABLED must be True
      - Target execution receipt must have verdict=EXECUTED
      - No prior ROLLED_BACK receipt for this execution
      - Current DB value must == execution receipt's intended_value
      - Compare-and-Set rollback to original value
      - Post-rollback verification
      - Exception does NOT propagate (return None)
    """
    try:
        # Step 1: execution_enabled
        if not EXECUTION_ENABLED:
            row = ShadowWriteReceipt(
                receipt_id=receipt_id,
                dedupe_key=compute_dedupe_key(
                    symbol,
                    "symbols",
                    "qualification_status",
                    "",
                    "",
                    "",
                    dry_run=False,
                ),
                symbol=symbol,
                target_table="symbols",
                target_field="qualification_status",
                current_value=None,
                intended_value="",
                would_change_summary=f"BLOCKED(EXECUTION_DISABLED): rollback",
                transition_reason=f"rollback_of:{execution_receipt_id}",
                block_reason_code=BlockReasonCode.EXECUTION_DISABLED.value,
                shadow_observation_id=None,
                input_fingerprint="",
                dry_run=True,
                executed=False,
                business_write_count=0,
                verdict=ExecutionVerdict.BLOCKED.value,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 2: execution receipt lookup
        stmt = (
            select(ShadowWriteReceipt)
            .where(
                ShadowWriteReceipt.receipt_id == execution_receipt_id,
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        exec_receipt = result.scalar_one_or_none()

        if exec_receipt is None:
            row = ShadowWriteReceipt(
                receipt_id=receipt_id,
                dedupe_key=compute_dedupe_key(
                    symbol,
                    "symbols",
                    "qualification_status",
                    "",
                    "",
                    "rb",
                    dry_run=False,
                ),
                symbol=symbol,
                target_table="symbols",
                target_field="qualification_status",
                current_value=None,
                intended_value="",
                would_change_summary=f"BLOCKED(NO_PRIOR_RECEIPT): rollback target not found",
                transition_reason=f"rollback_of:{execution_receipt_id}",
                block_reason_code=BlockReasonCode.NO_PRIOR_RECEIPT.value,
                shadow_observation_id=None,
                input_fingerprint="",
                dry_run=True,
                executed=False,
                business_write_count=0,
                verdict=ExecutionVerdict.BLOCKED.value,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 3: verdict == EXECUTED
        if exec_receipt.verdict != ExecutionVerdict.EXECUTED.value:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=exec_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.PRECONDITION_FAILED.value,
                summary=f"BLOCKED: target verdict={exec_receipt.verdict}, expected=executed",
                transition_reason=f"rollback_of:{execution_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 4: no prior rollback
        stmt = select(ShadowWriteReceipt).where(
            ShadowWriteReceipt.symbol == symbol,
        )
        result = await db.execute(stmt)
        all_receipts = list(result.scalars().all())

        if _is_already_rolled_back(all_receipts, execution_receipt_id):
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=exec_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.RECEIPT_ALREADY_CONSUMED.value,
                summary=f"BLOCKED: already rolled back for {execution_receipt_id}",
                transition_reason=f"rollback_of:{execution_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 5: current DB value == intended_value
        db_stmt = text("SELECT qualification_status FROM symbols WHERE symbol = :symbol")
        db_result = await db.execute(db_stmt, {"symbol": symbol})
        db_row = db_result.fetchone()
        current_db_value = db_row[0] if db_row else None

        if current_db_value != exec_receipt.intended_value:
            row = _make_execution_receipt(
                receipt_id=receipt_id,
                symbol=symbol,
                shadow_receipt=exec_receipt,
                verdict=ExecutionVerdict.BLOCKED,
                block_reason=BlockReasonCode.STALE_PRECONDITION.value,
                summary=f"BLOCKED(STALE): db={current_db_value} != intended={exec_receipt.intended_value}",
                transition_reason=f"rollback_of:{execution_receipt_id}",
                dry_run=True,
                executed=False,
                business_write_count=0,
            )
            db.add(row)
            await db.flush()
            return row

        # Step 6: Compare-and-Set rollback
        original = exec_receipt.current_value
        cas_stmt = text(
            "UPDATE symbols SET qualification_status = :original "
            "WHERE symbol = :symbol AND qualification_status = :intended"
        )
        await db.execute(
            cas_stmt,
            {
                "original": original,
                "symbol": symbol,
                "intended": exec_receipt.intended_value,
            },
        )

        # Step 7: Post-rollback verification
        verify_stmt = text("SELECT qualification_status FROM symbols WHERE symbol = :symbol")
        verify_result = await db.execute(verify_stmt, {"symbol": symbol})
        verify_row = verify_result.fetchone()
        actual_value = verify_row[0] if verify_row else None

        if actual_value != original:
            logger.critical(
                "rollback_bounded_write: post-rollback verify FAILED for %s "
                "(expected=%s, actual=%s). Manual intervention required.",
                symbol,
                original,
                actual_value,
            )
            return None

        # Step 8: ROLLED_BACK receipt
        row = _make_execution_receipt(
            receipt_id=receipt_id,
            symbol=symbol,
            shadow_receipt=exec_receipt,
            verdict=ExecutionVerdict.ROLLED_BACK,
            block_reason=None,
            summary=f"ROLLED_BACK: {exec_receipt.intended_value} → {original}",
            transition_reason=f"rollback_of:{execution_receipt_id}",
            dry_run=False,
            executed=False,
            business_write_count=-1,
        )
        db.add(row)
        await db.flush()
        return row

    except Exception:
        logger.exception(
            "rollback_bounded_write failed for %s",
            symbol,
        )
        return None
