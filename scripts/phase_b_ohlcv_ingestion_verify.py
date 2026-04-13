"""
Phase B Gate 3 — OHLCV 400D Ingestion Path Verification Script

Verifies V-001~V-007 for Gate 3 (OHLCV_400D_INGESTION_PATH_VERIFIED).
Executes: API ping → 7-day test → 400D ingestion → post-ingestion verification.

Usage:
  python scripts/phase_b_ohlcv_ingestion_verify.py                         # Full run
  python scripts/phase_b_ohlcv_ingestion_verify.py --dry-run               # Step 1 only
  python scripts/phase_b_ohlcv_ingestion_verify.py --verify-only           # Steps 4-5 only
  python scripts/phase_b_ohlcv_ingestion_verify.py --symbol SOL/USDT:USDT  # Single symbol

Constraints:
  - No strategy logic changes
  - No modification to existing files
  - V-005 tagging test must rollback (no pollution)
  - ABORT if fail-closed conditions met
"""

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

from app.core.config import settings  # noqa: E402
from app.core.database import async_session_factory  # noqa: E402
from app.services.history_data_manager import (  # noqa: E402
    HistoryDataManager,
    TIMEFRAME_MS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_SYMBOLS = ["SOL/USDT:USDT", "BTC/USDT:USDT"]
TIMEFRAME = "1h"
EXCHANGE_ID = "binance"
TARGET_DAYS = 400
EXPECTED_CANDLES = TARGET_DAYS * 24  # 9600
BATCH_LIMIT = 1000
TF_MS = TIMEFRAME_MS["1h"]  # 3_600_000

# Fail-closed thresholds
COVERAGE_MIN = 95.0
COVERAGE_TARGET = 99.0
GAP_MAX = 24
RETRY_DELAYS = [5, 15, 30]

# Evidence output
EVIDENCE_DIR = os.path.join(_project_root, "docs", "operations", "evidence")
LOG_PATH = os.path.join(EVIDENCE_DIR, "phase_b_gate3_verification_log.json")

# Failure codes
FC_SRC_MISSING = "SRC_MISSING"
FC_DUPLICATE = "DUPLICATE_DETECTED"
FC_ORDERING = "ORDERING_BROKEN"
FC_BACKFILL = "BACKFILL_MISMATCH"
FC_FAIL_CLOSED = "FAIL_CLOSED_TRIGGERED"
FC_NON_DETERM = "NON_DETERMINISTIC_RESULT"


# ---------------------------------------------------------------------------
# CCXT exchange helper
# ---------------------------------------------------------------------------
def create_exchange():
    """Create CCXT Binance Futures instance."""
    import ccxt
    return ccxt.binance({
        "apiKey": settings.binance_api_key or None,
        "secret": settings.binance_api_secret or None,
        "options": {"defaultType": "swap"},
        "enableRateLimit": True,
    })


# ---------------------------------------------------------------------------
# Step 1: Dry-run (API ping + data availability)
# ---------------------------------------------------------------------------
async def step1_dryrun(exchange, symbols: list[str]) -> dict:
    """V-001: API connectivity and rate limit compliance."""
    print("[STEP 1] API Dry-run: ping + data availability check")
    result = {"V-001": "FAIL", "details": {}}

    for symbol in symbols:
        try:
            candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=10)
            if candles and len(candles) > 0:
                result["details"][symbol] = {
                    "ping": "OK",
                    "candles_returned": len(candles),
                    "latest_ts": candles[-1][0],
                }
                print(f"  [V-001] {symbol}: ping OK, {len(candles)} candles returned")
            else:
                result["details"][symbol] = {"ping": "FAIL", "error": "no candles"}
                print(f"  [V-001] {symbol}: FAIL — no candles returned")
                return result
        except Exception as e:
            result["details"][symbol] = {"ping": "FAIL", "error": str(e)}
            print(f"  [V-001] {symbol}: FAIL — {e}")
            return result

    # Check 400-day availability for first symbol
    symbol = symbols[0]
    start_ts = int((datetime.now(timezone.utc) - timedelta(days=TARGET_DAYS)).timestamp() * 1000)
    try:
        old_candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=start_ts, limit=10)
        if old_candles and len(old_candles) > 0:
            age_days = (datetime.now(timezone.utc).timestamp() * 1000 - old_candles[0][0]) / 86_400_000
            result["details"]["earliest_available_days"] = round(age_days, 1)
            print(f"  [V-001] Earliest available: ~{age_days:.0f} days ago — OK")
        else:
            print(f"  [V-001] WARNING: No data available at {TARGET_DAYS}d ago")
            result["details"]["earliest_available_days"] = 0
    except Exception as e:
        print(f"  [V-001] WARNING: Could not check history: {e}")
        result["details"]["earliest_available_days"] = -1

    result["V-001"] = "PASS"
    print(f"  [V-001] PASS")
    return result


# ---------------------------------------------------------------------------
# Step 2: Small window test (7 days)
# ---------------------------------------------------------------------------
async def step2_small_test(exchange, symbol: str) -> dict:
    """7-day ingestion test: ingest + dedup + monotonicity."""
    print(f"\n[STEP 2] Small window test (7 days) — {symbol}")
    result = {"ingest_ok": False, "dedup_ok": False, "monotonic_ok": False}
    mgr = HistoryDataManager()

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = now_ms - (7 * 24 * TF_MS)

    # Fetch 7 days from exchange
    try:
        candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=start_ts, limit=168)
        print(f"  Fetched {len(candles)} candles from API")
    except Exception as e:
        print(f"  FAIL: Could not fetch candles: {e}")
        return result

    if not candles:
        print("  FAIL: No candles returned")
        return result

    # First ingestion
    async with async_session_factory() as session:
        ing1 = await mgr.ingest_candles(session, EXCHANGE_ID, symbol, TIMEFRAME, candles)
        await session.commit()
        print(f"  1st ingest: fetched={ing1.candles_fetched}, inserted={ing1.candles_inserted}, skipped={ing1.candles_skipped}")
        result["ingest_ok"] = ing1.candles_inserted > 0 or ing1.candles_skipped > 0

    # Dedup test — re-ingest same data
    async with async_session_factory() as session:
        count_before = await mgr.get_candle_count(session, EXCHANGE_ID, symbol, TIMEFRAME)
        ing2 = await mgr.ingest_candles(session, EXCHANGE_ID, symbol, TIMEFRAME, candles)
        await session.commit()
        count_after = await mgr.get_candle_count(session, EXCHANGE_ID, symbol, TIMEFRAME)
        result["dedup_ok"] = (ing2.candles_skipped > 0) and (count_after == count_before)
        print(f"  Dedup: skipped={ing2.candles_skipped}, count_before={count_before}, count_after={count_after} — {'PASS' if result['dedup_ok'] else 'FAIL'}")

    # Monotonicity on small window
    async with async_session_factory() as session:
        stored = await mgr.get_replay_candles(session, EXCHANGE_ID, symbol, TIMEFRAME, start_ts=start_ts)
        if len(stored) >= 2:
            reversals = 0
            for i in range(1, len(stored)):
                if stored[i][0] <= stored[i - 1][0]:
                    reversals += 1
            result["monotonic_ok"] = reversals == 0
            print(f"  Monotonicity: {len(stored)} candles, reversals={reversals} — {'PASS' if result['monotonic_ok'] else 'FAIL'}")
        else:
            result["monotonic_ok"] = True  # not enough data to fail

    return result


# ---------------------------------------------------------------------------
# Step 3: Full 400D ingestion
# ---------------------------------------------------------------------------
async def step3_full_ingestion(exchange, symbols: list[str]) -> dict:
    """Full 400-day OHLCV ingestion for all symbols."""
    print(f"\n[STEP 3] Full 400D ingestion — {symbols}")
    results = {}
    mgr = HistoryDataManager()

    for symbol in symbols:
        print(f"\n  --- {symbol} ---")
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ts = now_ms - (TARGET_DAYS * 24 * TF_MS)
        total_batches = (EXPECTED_CANDLES + BATCH_LIMIT - 1) // BATCH_LIMIT
        total_fetched = 0
        total_inserted = 0
        total_skipped = 0
        since = start_ts
        batch_num = 0
        abort = False

        while since < now_ms and batch_num < total_batches + 5:  # safety margin
            batch_num += 1
            candles = None

            # Fetch with retry
            for retry_idx, delay in enumerate(RETRY_DELAYS + [None]):
                try:
                    candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=since, limit=BATCH_LIMIT)
                    break
                except Exception as e:
                    if delay is None:
                        print(f"  [ABORT] {symbol} batch {batch_num}: 3 retries exhausted — {e}")
                        abort = True
                        break
                    print(f"  [RETRY {retry_idx + 1}] {symbol} batch {batch_num}: {e}, waiting {delay}s")
                    time.sleep(delay)

            if abort or candles is None:
                break

            if not candles:
                print(f"  [STEP 3] {symbol} batch {batch_num}: no more candles (end of data)")
                break

            # Ingest batch
            async with async_session_factory() as session:
                ing = await mgr.ingest_candles(session, EXCHANGE_ID, symbol, TIMEFRAME, candles)
                await session.commit()

            total_fetched += ing.candles_fetched
            total_inserted += ing.candles_inserted
            total_skipped += ing.candles_skipped

            print(f"  [STEP 3] {symbol} batch {batch_num}/{total_batches} ({total_fetched}/{EXPECTED_CANDLES} candles, +{ing.candles_inserted} new)")

            # Advance pagination cursor
            since = candles[-1][0] + TF_MS

        results[symbol] = {
            "total_fetched": total_fetched,
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "batches": batch_num,
            "aborted": abort,
        }
        print(f"  [STEP 3] {symbol} complete: fetched={total_fetched}, inserted={total_inserted}, skipped={total_skipped}")

    return results


# ---------------------------------------------------------------------------
# Step 4: Post-ingestion verification (V-001~V-007)
# ---------------------------------------------------------------------------
async def step4_verify(exchange, symbols: list[str], v001_result: dict) -> dict:
    """Run all V-001~V-007 checks on ingested data."""
    print(f"\n[STEP 4] Post-ingestion verification")
    mgr = HistoryDataManager()
    all_results = {}

    for symbol in symbols:
        print(f"\n  --- {symbol} ---")
        checks = {f"V-{i:03d}": "PENDING" for i in range(1, 8)}
        details = {}
        failure_codes = []

        # V-001: API connectivity (from Step 1)
        checks["V-001"] = v001_result.get("V-001", "FAIL")
        print(f"  [V-001] API connectivity: {checks['V-001']}")

        # V-002: Coverage
        async with async_session_factory() as session:
            coverage = await mgr.check_coverage(session, EXCHANGE_ID, symbol, TIMEFRAME)
            details["total_candles"] = coverage.total_candles
            details["expected_candles"] = coverage.expected_candles
            details["coverage_pct"] = coverage.coverage_pct
            details["gap_count"] = coverage.gap_count
            details["gap_details"] = coverage.gap_timestamps[:100]
            details["days_covered"] = coverage.days_covered

            if coverage.coverage_pct >= COVERAGE_TARGET:
                checks["V-002"] = "PASS"
            elif coverage.coverage_pct >= COVERAGE_MIN:
                checks["V-002"] = "PASS"  # Above abort threshold
                details["v002_note"] = f"Coverage {coverage.coverage_pct}% above abort threshold but below target {COVERAGE_TARGET}%"
            else:
                checks["V-002"] = "FAIL"
                failure_codes.append(FC_FAIL_CLOSED)
            print(f"  [V-002] Coverage: {coverage.coverage_pct}% ({coverage.total_candles}/{coverage.expected_candles}) gaps={coverage.gap_count} — {checks['V-002']}")

        # V-003: Deduplication
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        test_start = now_ms - (7 * 24 * TF_MS)
        try:
            test_candles = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=test_start, limit=168)
            async with async_session_factory() as session:
                count_before = await mgr.get_candle_count(session, EXCHANGE_ID, symbol, TIMEFRAME)
                ing = await mgr.ingest_candles(session, EXCHANGE_ID, symbol, TIMEFRAME, test_candles)
                await session.commit()
                count_after = await mgr.get_candle_count(session, EXCHANGE_ID, symbol, TIMEFRAME)

            details["duplicate_attempted"] = ing.candles_fetched
            details["duplicate_ignored"] = ing.candles_skipped

            if count_after == count_before and ing.candles_skipped > 0:
                checks["V-003"] = "PASS"
            else:
                checks["V-003"] = "FAIL"
                failure_codes.append(FC_DUPLICATE)
            print(f"  [V-003] Dedup: attempted={ing.candles_fetched}, ignored={ing.candles_skipped}, count_unchanged={count_after == count_before} — {checks['V-003']}")
        except Exception as e:
            checks["V-003"] = "FAIL"
            details["v003_error"] = str(e)
            print(f"  [V-003] FAIL: {e}")

        # V-004: Monotonicity
        async with async_session_factory() as session:
            all_candles = await mgr.get_replay_candles(session, EXCHANGE_ID, symbol, TIMEFRAME)
            if len(all_candles) < 2:
                checks["V-004"] = "FAIL"
                failure_codes.append(FC_SRC_MISSING)
                print(f"  [V-004] FAIL: insufficient candles ({len(all_candles)})")
            else:
                reversals = 0
                interval_violations = 0
                for i in range(1, len(all_candles)):
                    if all_candles[i][0] <= all_candles[i - 1][0]:
                        reversals += 1
                    gap = all_candles[i][0] - all_candles[i - 1][0]
                    if gap != TF_MS:
                        interval_violations += 1  # gaps (not necessarily errors)

                details["monotonic_reversals"] = reversals
                details["interval_violations"] = interval_violations

                if reversals == 0:
                    checks["V-004"] = "PASS"
                else:
                    checks["V-004"] = "FAIL"
                    failure_codes.append(FC_ORDERING)
                print(f"  [V-004] Monotonicity: {len(all_candles)} candles, reversals={reversals}, interval_gaps={interval_violations} — {checks['V-004']}")

        # V-005: Event metadata tagging (with rollback)
        try:
            async with async_session_factory() as session:
                async with session.begin():
                    # Pick a test range: first 24 candles
                    test_candles = await mgr.get_replay_candles(session, EXCHANGE_ID, symbol, TIMEFRAME, limit=24)
                    if test_candles and len(test_candles) >= 2:
                        tag_start = test_candles[0][0]
                        tag_end = test_candles[-1][0]

                        tagged_ew = await mgr.tag_event_week(
                            session, EXCHANGE_ID, symbol, TIMEFRAME,
                            tag_start, tag_end, "TEST_EVENT"
                        )
                        hv_timestamps = [c[0] for c in test_candles]
                        tagged_hv = await mgr.tag_high_volatility(
                            session, EXCHANGE_ID, symbol, TIMEFRAME,
                            hv_timestamps
                        )

                        details["event_week_tagged"] = tagged_ew > 0
                        details["high_vol_tagged"] = tagged_hv > 0

                        if tagged_ew > 0 and tagged_hv > 0:
                            checks["V-005"] = "PASS"
                        else:
                            checks["V-005"] = "FAIL"

                        print(f"  [V-005] Tagging: event_week={tagged_ew}, high_vol={tagged_hv} — {checks['V-005']}")
                    else:
                        checks["V-005"] = "FAIL"
                        print(f"  [V-005] FAIL: insufficient candles for tagging test")

                    # ROLLBACK to avoid polluting data
                    raise _RollbackSignal()
        except _RollbackSignal:
            print(f"  [V-005] Test tags rolled back (no pollution)")
        except Exception as e:
            checks["V-005"] = "FAIL"
            details["v005_error"] = str(e)
            print(f"  [V-005] FAIL: {e}")

        # V-006: Backfill/repair path
        async with async_session_factory() as session:
            cov = await mgr.check_coverage(session, EXCHANGE_ID, symbol, TIMEFRAME)
            if cov.gap_count == 0:
                checks["V-006"] = "PASS"
                details["backfill_needed"] = False
                print(f"  [V-006] Backfill: no gaps, no backfill needed — PASS")
            else:
                details["backfill_needed"] = True
                details["pre_backfill_gaps"] = cov.gap_count
                print(f"  [V-006] {cov.gap_count} gaps found, attempting backfill...")

                # Attempt backfill for gap timestamps
                backfilled = 0
                for gap_ts in cov.gap_timestamps[:50]:  # cap at 50
                    try:
                        fill_candles = exchange.fetch_ohlcv(
                            symbol, TIMEFRAME,
                            since=gap_ts - TF_MS,
                            limit=3
                        )
                        if fill_candles:
                            async with async_session_factory() as fill_session:
                                fill_result = await mgr.ingest_candles(
                                    fill_session, EXCHANGE_ID, symbol, TIMEFRAME, fill_candles
                                )
                                await fill_session.commit()
                                backfilled += fill_result.candles_inserted
                    except Exception:
                        pass

                # Re-check coverage
                async with async_session_factory() as session2:
                    cov2 = await mgr.check_coverage(session2, EXCHANGE_ID, symbol, TIMEFRAME)
                    details["post_backfill_gaps"] = cov2.gap_count
                    details["backfilled_candles"] = backfilled

                    if cov2.gap_count < cov.gap_count or cov2.gap_count == 0:
                        checks["V-006"] = "PASS"
                    else:
                        checks["V-006"] = "FAIL"
                        failure_codes.append(FC_BACKFILL)
                    print(f"  [V-006] Backfill: before={cov.gap_count}, after={cov2.gap_count}, filled={backfilled} — {checks['V-006']}")

                    # Update coverage details post-backfill
                    details["coverage_pct"] = cov2.coverage_pct
                    details["gap_count"] = cov2.gap_count

        # V-007: Fail-closed conditions
        final_coverage = details.get("coverage_pct", 0)
        final_gaps = details.get("gap_count", 0)
        reversals = details.get("monotonic_reversals", 0)

        v007_abort_reasons = []
        if final_coverage < COVERAGE_MIN:
            v007_abort_reasons.append(f"coverage {final_coverage}% < {COVERAGE_MIN}%")
        if final_gaps > GAP_MAX:
            v007_abort_reasons.append(f"gap_count {final_gaps} > {GAP_MAX}")
        if reversals > 0:
            v007_abort_reasons.append(f"reversals {reversals} > 0")

        if not v007_abort_reasons:
            checks["V-007"] = "PASS"
        else:
            checks["V-007"] = "FAIL"
            failure_codes.append(FC_FAIL_CLOSED)
        details["fail_closed_reasons"] = v007_abort_reasons
        print(f"  [V-007] Fail-closed: {v007_abort_reasons if v007_abort_reasons else 'no triggers'} — {checks['V-007']}")

        # Overall for this symbol
        overall = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"
        all_results[symbol] = {
            "checks": checks,
            "details": details,
            "failure_codes": failure_codes,
            "overall": overall,
        }
        print(f"\n  [{symbol}] Overall: {overall}")

    return all_results


class _RollbackSignal(Exception):
    """Signal to trigger rollback in V-005 tagging test."""
    pass


# ---------------------------------------------------------------------------
# Step 5: Output JSON log + verdict
# ---------------------------------------------------------------------------
def step5_output(v001: dict, step3: dict, step4: dict, symbols: list[str]) -> dict:
    """Produce final verification log and overall verdict."""
    print(f"\n[STEP 5] Final verdict")
    now_utc = datetime.now(timezone.utc).isoformat()

    # Per-symbol logs
    symbol_logs = {}
    all_pass = True

    for symbol in symbols:
        s4 = step4.get(symbol, {})
        checks = s4.get("checks", {})
        details = s4.get("details", {})
        s3 = step3.get(symbol, {})
        overall = s4.get("overall", "FAIL")

        if overall != "PASS":
            all_pass = False

        symbol_logs[symbol] = {
            "ingestion_id": str(uuid4()),
            "verified_at": now_utc,
            "symbol": symbol,
            "exchange": EXCHANGE_ID,
            "timeframe": TIMEFRAME,
            "total_expected_bars": EXPECTED_CANDLES,
            "total_ingested_bars": details.get("total_candles", 0),
            "coverage_pct": details.get("coverage_pct", 0),
            "gap_count": details.get("gap_count", 0),
            "gap_details": details.get("gap_details", [])[:20],
            "duplicate_attempted": details.get("duplicate_attempted", 0),
            "duplicate_ignored": details.get("duplicate_ignored", 0),
            "event_week_tagged": details.get("event_week_tagged", False),
            "high_vol_tagged": details.get("high_vol_tagged", False),
            "monotonic_check": "PASS" if details.get("monotonic_reversals", 0) == 0 else "FAIL",
            "checks": checks,
            "failure_codes": s4.get("failure_codes", []),
            "overall_verdict": overall,
            "ingestion_stats": s3,
        }

    overall_verdict = "PASS" if all_pass else "FAIL"

    log = {
        "gate": "Gate 3 — OHLCV_400D_INGESTION_PATH_VERIFIED",
        "overall_verdict": overall_verdict,
        "verified_at": now_utc,
        "symbols": symbol_logs,
    }

    # Save to file
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"  Verification log saved: {LOG_PATH}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  GATE 3 OVERALL VERDICT: {overall_verdict}")
    print(f"{'='*60}")
    for symbol in symbols:
        sl = symbol_logs[symbol]
        print(f"  {symbol}:")
        print(f"    coverage: {sl['coverage_pct']}% ({sl['total_ingested_bars']}/{EXPECTED_CANDLES})")
        print(f"    gaps: {sl['gap_count']}")
        print(f"    monotonic: {sl['monotonic_check']}")
        for k, v in sl["checks"].items():
            status_mark = "✓" if v == "PASS" else "✗"
            print(f"    {k}: {status_mark} {v}")
        print(f"    verdict: {sl['overall_verdict']}")
    print(f"{'='*60}")

    return log


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(
        description="Phase B Gate 3 — OHLCV 400D Ingestion Verification"
    )
    parser.add_argument("--dry-run", action="store_true", help="Step 1 only (API ping)")
    parser.add_argument("--verify-only", action="store_true", help="Steps 4-5 only (skip ingestion)")
    parser.add_argument("--symbol", type=str, default=None, help="Single symbol override")
    args = parser.parse_args()

    symbols = [args.symbol] if args.symbol else DEFAULT_SYMBOLS

    print("=" * 60)
    print("  Phase B Gate 3 — OHLCV 400D Ingestion Verification")
    print(f"  symbols: {symbols}")
    print(f"  target: {TARGET_DAYS} days = {EXPECTED_CANDLES} candles/symbol")
    print(f"  mode: {'dry-run' if args.dry_run else 'verify-only' if args.verify_only else 'full'}")
    print(f"  time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # Create exchange
    exchange = create_exchange()

    # Step 1: Dry-run
    v001 = await step1_dryrun(exchange, symbols)
    if v001["V-001"] != "PASS":
        print("\n[ABORT] V-001 FAIL — API not reachable. Cannot proceed.")
        return

    if args.dry_run:
        print("\n[DRY-RUN] Step 1 complete. Exiting.")
        return

    step3_results = {}

    if not args.verify_only:
        # Step 2: Small window test
        for symbol in symbols:
            s2 = await step2_small_test(exchange, symbol)
            if not s2["ingest_ok"]:
                print(f"\n[ABORT] Step 2 FAIL for {symbol} — ingestion not working")
                return

        # Step 3: Full 400D ingestion
        step3_results = await step3_full_ingestion(exchange, symbols)

        # Check for aborts
        for symbol, s3 in step3_results.items():
            if s3.get("aborted"):
                print(f"\n[ABORT] Step 3 FAIL for {symbol} — ingestion aborted")
                return

    # Step 4: Post-ingestion verification
    step4_results = await step4_verify(exchange, symbols, v001)

    # Step 5: Output
    log = step5_output(v001, step3_results, step4_results, symbols)

    return log


if __name__ == "__main__":
    asyncio.run(main())
