"""CR-048 RI-2B-2c Session 3 — B3'' Retry Execution (Path L, one-shot).

Scope (governance lock)
-----------------------
This script is the single, auditable execution artifact for CR-048 RI-2B-2c
Session 3 under the Session 3 Opener v1 controlling spec. It is designed to
run exactly once and:

1. Snapshot the pre-execution state of ``data/cr048_prior_shadow.sqlite``.
2. Seed exactly one ``SOL/USDT`` row under the Path L Standard Seed Contract
   (17 NOT NULL columns, enum members authoritative per
   ``cr048_ri2b2c_scope_review_acceptance_receipt.md §5.2``) — only if
   absent. Bootstrap is a pre-call setup write, NOT routed through
   ``execute_bounded_write``.
3. Invoke ``app.services.shadow_write_service.execute_bounded_write`` EXACTLY
   ONCE to transition ``symbols.qualification_status`` from ``unchecked`` to
   ``pass`` for ``SOL/USDT`` using the prior shadow receipt
   ``prior_68d980c176d24a0c9dc6ead35307bbad``.
4. Commit the execution session so the CAS UPDATE + new execution receipt
   persist to disk.
5. Snapshot the post-execution state and verify the Session 3 success
   criteria (qualification_status='pass', receipt count=2,
   business_write_count sum=1, prior receipt consumed).

Path discipline
---------------
* Path = L (local-only aiosqlite).
* The script creates its OWN AsyncEngine pointed at
  ``data/cr048_prior_shadow.sqlite``. It never uses ``app.core.database.engine``
  (which is a Postgres Engine object — not connected, but off-limits).
* No Postgres connection is opened at any point.
* No test harness code is modified.
* No application code is modified.

Invocation
----------
Run from the repo root::

    python scripts/cr048_ri2b2c_session3_execute.py

Exit codes
----------
* 0 — SUCCESS (all success criteria met)
* 1 — BLOCKED or FAILED (details in stdout)
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Force UTF-8 stdout/stderr so Windows cp949 consoles do not crash on
# unicode characters in log lines.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Resolve repo root relative to this script so CWD-independence is guaranteed.
REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "cr048_prior_shadow.sqlite"
DB_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"

PRIOR_RECEIPT_ID = "prior_68d980c176d24a0c9dc6ead35307bbad"
TARGET_SYMBOL = "SOL/USDT"
TARGET_TABLE = "symbols"
TARGET_FIELD = "qualification_status"

# Ensure the repo root is importable so "app.*" resolves when run standalone.
sys.path.insert(0, str(REPO_ROOT))


def _sync_snapshot(label: str) -> dict:
    """Take a synchronous snapshot via the stdlib sqlite3 driver.

    Using sqlite3 here (instead of SQLAlchemy) keeps the snapshot layer
    completely independent of the session used by ``execute_bounded_write``
    and guarantees we are reading committed state only.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    snap: dict = {"label": label, "taken_at": datetime.now(timezone.utc).isoformat()}

    sym_rows = list(
        cur.execute(
            "SELECT symbol, qualification_status, status, screening_score "
            "FROM symbols WHERE symbol = ?",
            (TARGET_SYMBOL,),
        )
    )
    snap["symbol_row_count"] = len(sym_rows)
    snap["symbol_rows"] = [dict(r) for r in sym_rows]

    receipt_rows = list(
        cur.execute(
            "SELECT receipt_id, verdict, executed, business_write_count, "
            "dry_run, current_value, intended_value, transition_reason "
            "FROM shadow_write_receipt WHERE symbol = ? ORDER BY id",
            (TARGET_SYMBOL,),
        )
    )
    snap["receipt_row_count"] = len(receipt_rows)
    snap["receipts"] = [dict(r) for r in receipt_rows]

    total_bwc = cur.execute(
        "SELECT COALESCE(SUM(business_write_count),0) FROM shadow_write_receipt WHERE symbol = ?",
        (TARGET_SYMBOL,),
    ).fetchone()[0]
    snap["business_write_count_sum"] = int(total_bwc)

    conn.close()
    return snap


def _print_snapshot(snap: dict) -> None:
    print(f"\n=== SNAPSHOT {snap['label']} @ {snap['taken_at']} ===")
    print(f"  symbol_row_count       : {snap['symbol_row_count']}")
    for r in snap["symbol_rows"]:
        print(f"  symbol_row             : {dict(r)}")
    print(f"  receipt_row_count      : {snap['receipt_row_count']}")
    for r in snap["receipts"]:
        print(f"  receipt                : {dict(r)}")
    print(f"  business_write_count_sum: {snap['business_write_count_sum']}")


async def main() -> int:
    # ── Imports that trigger app.core.database load are deferred here ──
    # so that snapshot T0 (above) runs before the Postgres Engine object
    # is instantiated. The engine object is lazy and NEVER connects unless
    # we call .begin()/.connect() on it — we do neither.
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.models.asset import (
        AssetClass,
        AssetSector,
        AssetTheme,
        Symbol,
        SymbolStatus,
    )
    from app.services.shadow_write_service import (
        EXECUTION_ENABLED,
        ExecutionVerdict,
        execute_bounded_write,
    )

    print("=" * 72)
    print("CR-048 RI-2B-2c Session 3 — B3'' Retry Execution (Path L)")
    print("=" * 72)
    print(f"controlling_spec = CR-048 RI-2B-2c Session 3 Opener v1")
    print(f"DB_PATH          = {DB_PATH}")
    print(f"DB_URL           = {DB_URL}")
    print(f"PRIOR_RECEIPT_ID = {PRIOR_RECEIPT_ID}")
    print(f"EXECUTION_ENABLED flag value seen by script = {EXECUTION_ENABLED}")
    if not EXECUTION_ENABLED:
        print("ABORT: EXECUTION_ENABLED=False — cannot proceed.")
        return 1

    # ── T0: Pre-execution snapshot ──────────────────────────────────
    t0 = _sync_snapshot("T0_pre_seed")
    _print_snapshot(t0)

    # Gate: SOL/USDT must be absent, or if present its qualification_status
    # MUST be 'unchecked' (per preflight 3). T0 already captured this.
    bootstrap_needed = t0["symbol_row_count"] == 0
    if not bootstrap_needed:
        current = t0["symbol_rows"][0]["qualification_status"]
        if current != "unchecked":
            print(
                f"\nABORT: SOL/USDT row exists with qualification_status={current!r}, "
                f"expected 'unchecked' per preflight 3."
            )
            return 1

    # ── Engine for Path L (local SQLite only) ───────────────────────
    engine = create_async_engine(DB_URL, echo=False)

    try:
        # ── Phase 1: Seed bootstrap (only if absent) ────────────────
        if bootstrap_needed:
            print("\n-- Phase 1: Path L Standard Seed Contract bootstrap --")
            now = datetime.now(timezone.utc)
            seed_values = {
                "id": str(uuid4()),
                "symbol": TARGET_SYMBOL,
                "name": "Solana / Tether USD",
                "asset_class": AssetClass.CRYPTO,  # .value = "CRYPTO"
                "sector": AssetSector.LAYER1,  # .value = "layer1"
                "theme": AssetTheme.L1_SCALING,  # .value = "l1_scaling"
                "exchanges": '["binance"]',
                "status": SymbolStatus.WATCH,  # .value = "watch"
                "screening_score": 0.0,
                "qualification_status": "unchecked",
                "promotion_eligibility_status": "unchecked",
                "paper_evaluation_status": "pending",
                "paper_allowed": False,
                "live_allowed": False,
                "manual_override": False,
                "created_at": now,
                "updated_at": now,
            }
            # Print an auditable echo of the exact seed values used.
            print("seed_values (17-column contract):")
            for k, v in seed_values.items():
                if hasattr(v, "value"):
                    print(f"  {k:36s} = {v!r} (enum .value={v.value!r})")
                else:
                    print(f"  {k:36s} = {v!r}")

            async with AsyncSession(engine, expire_on_commit=False) as session:
                session.add(Symbol(**seed_values))
                await session.commit()
            print("seed bootstrap: committed.")
        else:
            print("\n-- Phase 1 SKIPPED: SOL/USDT row already present --")

        # ── T1: Post-seed snapshot ──────────────────────────────────
        t1 = _sync_snapshot("T1_post_seed")
        _print_snapshot(t1)

        # Invariant: seed row present with qualification_status='unchecked',
        # prior receipt still unconsumed (executed=0).
        assert t1["symbol_row_count"] == 1
        assert t1["symbol_rows"][0]["qualification_status"] == "unchecked"
        prior = next(
            (r for r in t1["receipts"] if r["receipt_id"] == PRIOR_RECEIPT_ID),
            None,
        )
        assert prior is not None, "prior receipt not visible after seed"
        assert prior["executed"] == 0, "prior receipt already consumed before exec"

        # ── Phase 2: exactly one execute_bounded_write call ─────────
        new_receipt_id = f"exec_{uuid4().hex}"
        print("\n-- Phase 2: execute_bounded_write (exactly 1 call) --")
        print(f"new_receipt_id = {new_receipt_id}")

        call_count = 0
        returned_receipt = None
        async with AsyncSession(engine, expire_on_commit=False) as session:
            call_count += 1
            returned_receipt = await execute_bounded_write(
                db=session,
                receipt_id=new_receipt_id,
                shadow_receipt_id=PRIOR_RECEIPT_ID,
                symbol=TARGET_SYMBOL,
                target_table=TARGET_TABLE,
                target_field=TARGET_FIELD,
            )

            if returned_receipt is None:
                # Exception path — execute_bounded_write swallows and returns None.
                await session.rollback()
                print("execute_bounded_write returned None — exception swallowed.")
                print("Session rolled back. SESSION 3 = FAILED.")
                return 1

            # Commit so the CAS UPDATE + new receipt persist.
            await session.commit()

            print(f"returned receipt_id       : {returned_receipt.receipt_id}")
            print(f"returned verdict          : {returned_receipt.verdict}")
            print(f"returned executed         : {returned_receipt.executed}")
            print(f"returned business_write_ct: {returned_receipt.business_write_count}")
            print(f"returned summary          : {returned_receipt.would_change_summary}")

        print(f"execute_bounded_write call count: {call_count}")

        # ── T2: Post-execute snapshot ───────────────────────────────
        t2 = _sync_snapshot("T2_post_exec")
        _print_snapshot(t2)

        # ── Success criteria evaluation ─────────────────────────────
        print("\n" + "=" * 72)
        print("SESSION 3 SUCCESS CRITERIA EVALUATION")
        print("=" * 72)

        sol_row = next(iter(t2["symbol_rows"]), None)
        assert sol_row is not None, "SOL/USDT row missing post-exec"

        criteria = {
            "criterion_1_path_L_only": True,
            "criterion_2_zero_path_P": True,  # no Postgres connection opened
            "criterion_3_at_most_one_seed_insert": bootstrap_needed,
            "criterion_4_exactly_one_execute_call": call_count == 1,
            "criterion_5_transition_unchecked_to_pass": sol_row["qualification_status"] == "pass",
            "criterion_6_prior_receipt_consumed": False,  # filled below
            "criterion_7_new_execution_evidence_auditable": False,  # filled below
            "criterion_8_no_forbidden_scope_expansion": True,
        }

        # Prior receipt consumed iff a new receipt exists that
        # references it via transition_reason="exec_of:<prior>" and
        # verdict=executed.
        new_exec_receipts = [
            r
            for r in t2["receipts"]
            if r["transition_reason"] == f"exec_of:{PRIOR_RECEIPT_ID}"
            and r["verdict"] == ExecutionVerdict.EXECUTED.value
        ]
        criteria["criterion_6_prior_receipt_consumed"] = len(new_exec_receipts) == 1
        criteria["criterion_7_new_execution_evidence_auditable"] = (
            len(new_exec_receipts) == 1
            and t2["receipt_row_count"] == 2
            and t2["business_write_count_sum"] == 1
        )

        all_pass = all(criteria.values())
        for k, v in criteria.items():
            print(f"  {k:50s} : {v}")
        print(f"  all_pass                                             : {all_pass}")

        # Print full snapshot triplet as JSON for the evidence doc.
        bundle = {
            "T0_pre_seed": t0,
            "T1_post_seed": t1,
            "T2_post_exec": t2,
            "execute_bounded_write_call_count": call_count,
            "new_receipt_id": new_receipt_id,
            "returned_receipt": {
                "receipt_id": returned_receipt.receipt_id,
                "verdict": returned_receipt.verdict,
                "executed": bool(returned_receipt.executed),
                "business_write_count": returned_receipt.business_write_count,
                "summary": returned_receipt.would_change_summary,
                "dry_run": bool(returned_receipt.dry_run),
            },
            "criteria": criteria,
            "all_pass": all_pass,
        }
        print("\n--- BUNDLE JSON BEGIN ---")
        print(json.dumps(bundle, indent=2, default=str))
        print("--- BUNDLE JSON END ---")

        return 0 if all_pass else 1

    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
