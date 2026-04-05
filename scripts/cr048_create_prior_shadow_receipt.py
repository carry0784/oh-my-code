"""CR-048 RI-2B-2b prior-shadow creation — one-off integration bring-up.

Purpose
-------
Create exactly ONE real `shadow_write_receipt` row by invoking
`app.services.shadow_write_service.evaluate_shadow_write()` against a
dedicated fresh SQLite database. Capture the generated `receipt_id` so
that A can paste it into the `P4.shadow_receipt_id` slot of
`cr048_ri2b2b_activation_go_receipt.md` during the signature session.

Scope and boundaries
--------------------
- Runs exactly ONE call to `evaluate_shadow_write()`.
- Writes exactly ONE row to `shadow_write_receipt` (INSERT only).
- ZERO writes to any business table (symbols.qualification_status is
  unchanged — the receipt's `dry_run=True, executed=False,
  business_write_count=0` proof fields are forced by the sealed
  RI-2B-1 function body).
- Uses a fresh dedicated SQLite file under `data/` (gitignored).
- Does NOT modify `shadow_write_service.py` (sealed RI-2B-1).
- Does NOT modify `shadow_write_receipt.py` model (sealed RI-2B-1).
- Does NOT modify `test_shadow_write_receipt.py` (sealed tests).
- Does NOT modify any alembic migration.
- Does NOT touch `cr048_ri2b2b_activation_go_receipt.md`.
- Does NOT exercise `execute_bounded_write` (that is B3'', a separate
  governance step blocked on signature).

Chain relationship
------------------
This script belongs to a SIBLING chain of the activation DRAFT.
Running it does NOT advance the Track A governance chain head
(`d999aed`). It only produces an artifact (receipt_id) that the
activation DRAFT's P4 slot can reference.

Usage
-----
    python scripts/cr048_create_prior_shadow_receipt.py

Output
------
Prints a structured summary to stdout and exits 0 on success.
On any internal error exits non-zero with a diagnostic message.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Force stdout to utf-8 so the report prints cleanly on Windows consoles
# whose default encoding is cp949.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


# ── sys.path + DB selection MUST happen before any app import ──

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DB_FILE = REPO_ROOT / "data" / "cr048_prior_shadow.sqlite"
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

# Use aiosqlite driver (same as tests/conftest.py) to avoid Postgres
# dependency for this one-off integration bring-up.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"
os.environ["DATABASE_URL_SYNC"] = f"sqlite:///{DB_FILE.as_posix()}"

# ── App imports (after env override) ─────────────────────────────

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.database import Base  # noqa: E402

# IMPORTANT: importing app.models registers all ORM classes on Base.metadata
# so that create_all creates every table including shadow_write_receipt.
import app.models  # noqa: E402,F401  -- side-effect import

from app.models.asset import AssetClass, AssetSector  # noqa: E402
from app.models.shadow_write_receipt import ShadowWriteReceipt  # noqa: E402
from app.services.data_provider import (  # noqa: E402
    BacktestReadiness,
    DataQuality,
    MarketDataSnapshot,
)
from app.services.pipeline_shadow_runner import (  # noqa: E402
    ComparisonVerdict,
    ShadowRunResult,
    run_shadow_pipeline,
)
from app.services.shadow_readthrough import (  # noqa: E402
    ExistingResultSource,
    ReadthroughComparisonResult,
)
from app.services.shadow_write_service import evaluate_shadow_write  # noqa: E402


# ── Fixture builders ─────────────────────────────────────────────

_NOW = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
SYMBOL = "SOL/USDT"


def _make_market() -> MarketDataSnapshot:
    """High-quality SOL/USDT snapshot that passes all screening stages."""
    return MarketDataSnapshot(
        symbol=SYMBOL,
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


def _make_backtest() -> BacktestReadiness:
    return BacktestReadiness(
        symbol=SYMBOL,
        available_bars=1000,
        sharpe_ratio=1.5,
        missing_data_pct=1.0,
        quality=DataQuality.HIGH,
    )


def _build_shadow_result() -> ShadowRunResult:
    return run_shadow_pipeline(
        _make_market(),
        _make_backtest(),
        AssetClass.CRYPTO,
        AssetSector.LAYER1,
        now_utc=_NOW,
    )


def _build_readthrough(shadow_result: ShadowRunResult) -> ReadthroughComparisonResult:
    return ReadthroughComparisonResult(
        symbol=SYMBOL,
        shadow_result=shadow_result,
        comparison_verdict=ComparisonVerdict.MATCH,
        reason_comparison=None,
        existing_source=ExistingResultSource(
            screening_result_id="sr-prior-001",
            qualification_result_id="qr-prior-001",
            failure_code=None,
        ),
    )


# ── Main ─────────────────────────────────────────────────────────


async def _main() -> int:
    print(f"[setup] DB file         : {DB_FILE}")
    print(f"[setup] DATABASE_URL    : {os.environ['DATABASE_URL']}")

    # Delete any previous file so we always start from a clean slate.
    if DB_FILE.exists():
        DB_FILE.unlink()
        print("[setup] removed previous DB file")

    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False,
    )

    # Create schema via ORM metadata (same pattern as tests/conftest.py).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[setup] Base.metadata.create_all -> OK")

    shadow_result = _build_shadow_result()
    readthrough = _build_readthrough(shadow_result)
    pipeline_verdict = shadow_result.pipeline_output.result.verdict
    print(f"[inputs] symbol         : {SYMBOL}")
    print(f"[inputs] pipeline verdict: {pipeline_verdict}")
    print(f"[inputs] input_fingerprint: {shadow_result.input_fingerprint}")
    print(f"[inputs] comparison      : {readthrough.comparison_verdict}")

    receipt_id = "prior_" + uuid.uuid4().hex
    print(f"[call]   receipt_id      : {receipt_id}")

    async with AsyncSession(engine, expire_on_commit=False) as session:
        receipt = await evaluate_shadow_write(
            db=session,
            receipt_id=receipt_id,
            shadow_result=shadow_result,
            readthrough_result=readthrough,
            symbol=SYMBOL,
            current_qualification_status="unchecked",
            target_table="symbols",
            target_field="qualification_status",
            shadow_observation_id=None,
        )

        if receipt is None:
            print("[ERROR]  evaluate_shadow_write returned None", file=sys.stderr)
            await engine.dispose()
            return 2

        await session.commit()

        # Verify row exists via fresh query.
        stmt = select(ShadowWriteReceipt).where(ShadowWriteReceipt.receipt_id == receipt_id)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            print("[ERROR]  row not found after commit", file=sys.stderr)
            await engine.dispose()
            return 3

        # Total row count (must be 1).
        count_stmt = select(ShadowWriteReceipt)
        count_result = await session.execute(count_stmt)
        all_rows = count_result.scalars().all()
        total_rows = len(all_rows)

    await engine.dispose()

    # ── Structured report ────────────────────────────────────────
    print()
    print("=" * 64)
    print("CR-048 RI-2B-2b PRIOR SHADOW RECEIPT — CREATION REPORT")
    print("=" * 64)
    print(f"receipt_id           : {row.receipt_id}")
    print(f"dedupe_key           : {row.dedupe_key}")
    print(f"symbol               : {row.symbol}")
    print(f"target_table         : {row.target_table}")
    print(f"target_field         : {row.target_field}")
    print(f"current_value        : {row.current_value}")
    print(f"intended_value       : {row.intended_value}")
    print(f"verdict              : {row.verdict}")
    print(f"transition_reason    : {row.transition_reason}")
    print(f"block_reason_code    : {row.block_reason_code}")
    print(f"would_change_summary : {row.would_change_summary}")
    print(f"input_fingerprint    : {row.input_fingerprint}")
    print(f"shadow_observation_id: {row.shadow_observation_id}")
    print(f"dry_run              : {row.dry_run}")
    print(f"executed             : {row.executed}")
    print(f"business_write_count : {row.business_write_count}")
    print(f"created_at           : {row.created_at}")
    print(f"total row count      : {total_rows}")
    print("=" * 64)

    # Forced-proof assertions (defensive — the sealed function already
    # guarantees these, but we verify post-hoc).
    assert row.dry_run is True, f"dry_run must be True, got {row.dry_run}"
    assert row.executed is False, f"executed must be False, got {row.executed}"
    assert row.business_write_count == 0, (
        f"business_write_count must be 0, got {row.business_write_count}"
    )
    assert total_rows == 1, f"expected exactly 1 row, got {total_rows}"

    print("[verify] dry_run=True, executed=False, business_write_count=0 -> OK")
    print("[verify] total rows == 1 -> OK")
    print("[done]   exit 0")
    return 0


if __name__ == "__main__":
    rc = asyncio.run(_main())
    sys.exit(rc)
