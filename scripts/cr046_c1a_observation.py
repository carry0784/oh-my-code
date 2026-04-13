"""
CR-046 SOL C1-A Post-Merge Diagnostic Observation Script

Read-only observation of post-activation paper_trading_receipts to verify
that diagnostic fields (PR #92) are correctly populated.

Usage:
  python scripts/cr046_c1a_observation.py --window 3
  python scripts/cr046_c1a_observation.py --window 24
  python scripts/cr046_c1a_observation.py --window 24 --append-to-evidence

Constraints:
  - SELECT only (no INSERT/UPDATE/DELETE)
  - Runtime/business logic: no modification
  - Evidence: append-only (existing sections untouched)
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Ensure UTF-8 stdout on Windows (cp949 cannot encode em-dash etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# Project root on path (for config import)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_ID = "cr046_sol_paper_v1"

# --- bar 기준 (논리 시각) ---
CUTOFF_BAR_TS = 1775660400000  # 2026-04-08 15:00:00 UTC (old-code last bar)
FIRST_ELIGIBLE_BAR_TS = 1775664000000  # 2026-04-08 16:00:00 UTC (post-merge minimum)

# --- 관측/도착 기준 ---
ACTIVATION_TS_UTC = "2026-04-08T15:59:27+00:00"
FIRST_EXPECTED_RECEIPT_NOTE = "2026-04-08 16:50 UTC ± jitter"

BAR_INTERVAL_MS = 3_600_000  # 1H
DISPATCH_DELAY_MS = 50 * 60 * 1000  # :50 dispatch
JITTER_GRACE_MS = 10 * 60 * 1000  # ±10 min grace

# 24-bar thresholds (locked in design doc lines 321-328)
THRESHOLD_POPULATED_RATE = 0.95
THRESHOLD_VERSION = 1
THRESHOLD_VERSION_RATE = 1.00

EVIDENCE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "operations",
    "evidence",
    "cr046_sol_c1a_diagnostic_field_design.md",
)

# ---------------------------------------------------------------------------
# Verdict & Reason Codes
# ---------------------------------------------------------------------------

VERDICT_PRECEDENCE = ["FAIL", "UNVERIFIABLE", "IN_PROGRESS", "PASS"]

SMOKE_PASS = "PASS"
SMOKE_FAIL = "FAIL"
SMOKE_PENDING = "PENDING"
SMOKE_UNAVAILABLE = "UNAVAILABLE"


def aggregate_verdict(verdicts: list[str]) -> str:
    for v in VERDICT_PRECEDENCE:
        if v in verdicts:
            return v
    return "PASS"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DiagRecord:
    bar_index: int
    receipt_id: str
    bar_ts: int
    bar_ts_utc: str
    action: str
    created_at: str
    # diagnostic fields
    diagnostic_exists: bool = False
    populated: bool | None = None
    version: int | None = None
    diagnostic_only: bool | None = None
    smc_sig_raw: int | None = None
    smc_trend_raw: int | None = None
    wt_sig_raw: int | None = None
    wt1_val: float | None = None
    wt2_val: float | None = None
    wt_cross_distance: float | None = None
    close_price: float | None = None
    skip_reason_codes: list[str] = field(default_factory=list)
    near_miss_type: str | None = None
    is_error: bool = False
    # derived
    bottleneck_class: str = ""
    rule_check: str = ""


# ---------------------------------------------------------------------------
# Preflight sanity checks
# ---------------------------------------------------------------------------


def run_preflight(db_url: str, append_mode: bool) -> None:
    """Verify environment prerequisites before observation run.

    Checks:
      1. DB connectivity (SELECT 1)
      2. paper_trading_receipts table exists
      3. data column exists
      4. Evidence file writable (append mode only)

    Exits with code 1 on any failure.
    """
    # 1. DB ping
    try:
        conn = psycopg2.connect(db_url)
        conn.set_session(readonly=True)
    except Exception as e:
        print(f"[PREFLIGHT FAIL] DB_PING_FAILED: {e}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        print("[PREFLIGHT] DB ping: OK")

        # 2. Table exists
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'paper_trading_receipts'
                )
                """
            )
            if not cur.fetchone()[0]:
                print("[PREFLIGHT FAIL] TABLE_MISSING: paper_trading_receipts")
                sys.exit(1)
        print("[PREFLIGHT] Table exists: OK")

        # 3. Column 'data' exists
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT data_type FROM information_schema.columns
                WHERE table_name = 'paper_trading_receipts' AND column_name = 'data'
                """
            )
            row = cur.fetchone()
            if not row:
                print("[PREFLIGHT FAIL] COLUMN_MISSING: 'data'")
                sys.exit(1)
        print("[PREFLIGHT] Column 'data': OK")
    finally:
        conn.close()

    # 4. Evidence file (append mode only)
    if append_mode:
        if not os.path.isfile(EVIDENCE_PATH):
            print(f"[PREFLIGHT FAIL] EVIDENCE_FILE_INVALID: not found: {EVIDENCE_PATH}")
            sys.exit(1)
        if not os.access(EVIDENCE_PATH, os.W_OK):
            print(f"[PREFLIGHT FAIL] EVIDENCE_FILE_INVALID: not writable: {EVIDENCE_PATH}")
            sys.exit(1)
        print("[PREFLIGHT] Evidence file: OK")

    print("[PREFLIGHT] All checks passed")
    print()


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------


def fetch_observed_records(db_url: str) -> tuple[list[DiagRecord], int]:
    """Fetch post-cutoff receipts with duplicate canonical rule.

    Returns:
        (records, dup_count) — deduplicated records sorted by bar_ts ASC,
        and the number of duplicate receipts that were ignored.

    Duplicate Canonical Rule:
        When multiple receipts share the same bar_ts, only the canonical
        one is kept.  Selection criteria (deterministic tie-breaker):
          1st: latest created_at (DESC)
          2nd: receipt_id lexicographic maximum (DESC)
    """
    conn = psycopg2.connect(db_url)
    conn.set_session(readonly=True)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT receipt_id, bar_ts, action, created_at, data
                FROM paper_trading_receipts
                WHERE session_id = %s AND bar_ts > %s
                ORDER BY bar_ts ASC, created_at DESC, receipt_id DESC
                """,
                (SESSION_ID, CUTOFF_BAR_TS),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    # --- Duplicate canonical: raw row dedup before DiagRecord creation ---
    canonical_map: dict[int, dict] = {}  # bar_ts -> canonical raw row
    for row in rows:
        bar_ts = row["bar_ts"]
        existing = canonical_map.get(bar_ts)
        if existing is None:
            canonical_map[bar_ts] = row
        else:
            # Compare: 1st created_at DESC, 2nd receipt_id DESC
            existing_key = (str(existing["created_at"]), str(existing["receipt_id"]))
            row_key = (str(row["created_at"]), str(row["receipt_id"]))
            if row_key > existing_key:
                canonical_map[bar_ts] = row

    dup_count = len(rows) - len(canonical_map)
    if dup_count > 0:
        print(f"[DEDUP] {dup_count} duplicate receipts ignored")

    # Build DiagRecords from canonical rows only
    canonical_rows = sorted(canonical_map.values(), key=lambda r: r["bar_ts"])
    records: list[DiagRecord] = []
    for idx, row in enumerate(canonical_rows):
        data = row["data"] or {}
        diag = data.get("diagnostic") or {}
        diagnostic_exists = bool(diag)

        skip_codes_raw = diag.get("skip_reason_codes")
        if isinstance(skip_codes_raw, str):
            try:
                skip_codes_raw = json.loads(skip_codes_raw)
            except (json.JSONDecodeError, TypeError):
                skip_codes_raw = []
        if not isinstance(skip_codes_raw, list):
            skip_codes_raw = []

        smc = diag.get("smc_sig_raw")
        wt = diag.get("wt_sig_raw")
        nm = diag.get("near_miss_type")

        rec = DiagRecord(
            bar_index=idx + 1,
            receipt_id=row["receipt_id"],
            bar_ts=row["bar_ts"],
            bar_ts_utc=_ts_to_utc(row["bar_ts"]),
            action=row["action"],
            created_at=str(row["created_at"]),
            diagnostic_exists=diagnostic_exists,
            populated=diag.get("diagnostic_populated"),
            version=diag.get("diagnostic_version"),
            diagnostic_only=diag.get("diagnostic_only"),
            smc_sig_raw=smc,
            smc_trend_raw=diag.get("smc_trend_raw"),
            wt_sig_raw=wt,
            wt1_val=diag.get("wt1_val"),
            wt2_val=diag.get("wt2_val"),
            wt_cross_distance=diag.get("wt_cross_distance"),
            close_price=diag.get("close_price"),
            skip_reason_codes=skip_codes_raw,
            near_miss_type=nm,
            is_error=(row["action"] == "ERROR_FAIL_CLOSED"),
        )
        rec.bottleneck_class = _classify_bottleneck(rec.skip_reason_codes)
        rec.rule_check = _verify_near_miss(smc, wt, nm)
        records.append(rec)

    return records, dup_count


def _ts_to_utc(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Bottleneck classification (bar-level, design doc 1-H-1)
# ---------------------------------------------------------------------------


def _classify_bottleneck(skip_codes: list[str]) -> str:
    if not skip_codes:
        return "CONSENSUS_PASS"
    has_smc = "SMC_ZERO" in skip_codes
    has_wt = "WT_ZERO" in skip_codes
    if has_smc and not has_wt:
        return "SMC_ZERO"
    if has_wt and not has_smc:
        return "WT_ZERO"
    if has_smc and has_wt:
        return "BOTH_ZERO"
    if "DIRECTION_MISMATCH" in skip_codes:
        return "DIR_MISMATCH"
    return "OTHER"


# ---------------------------------------------------------------------------
# Near-miss canonical rule (design doc Section B, lines 154-163)
# ---------------------------------------------------------------------------


def _compute_expected_near_miss(smc_sig: int, wt_sig: int) -> str | None:
    if smc_sig != 0 and wt_sig == 0:
        return "SMC_ONLY"
    if smc_sig == 0 and wt_sig != 0:
        return "WT_ONLY"
    if smc_sig != 0 and wt_sig != 0 and smc_sig != wt_sig:
        return "DIR_MISMATCH"
    return None


def _verify_near_miss(smc, wt, actual_nm) -> str:
    if smc is None or wt is None:
        return "UNVERIFIABLE"
    if not isinstance(smc, int) or not isinstance(wt, int):
        return "UNVERIFIABLE"
    expected = _compute_expected_near_miss(smc, wt)
    if actual_nm == expected:
        return "PASS"
    return f"FAIL(exp={expected},act={actual_nm})"


# ---------------------------------------------------------------------------
# Gap checks (3-tier: leading / internal / trailing overdue)
# ---------------------------------------------------------------------------


def check_leading_gap(observed: list[DiagRecord]) -> list[int]:
    if not observed:
        return []
    missing = []
    ts = FIRST_ELIGIBLE_BAR_TS
    while ts < observed[0].bar_ts:
        missing.append(ts)
        ts += BAR_INTERVAL_MS
    return missing


def check_internal_gaps(observed: list[DiagRecord]) -> list[int]:
    missing = []
    for i in range(1, len(observed)):
        expected_ts = observed[i - 1].bar_ts + BAR_INTERVAL_MS
        while expected_ts < observed[i].bar_ts:
            missing.append(expected_ts)
            expected_ts += BAR_INTERVAL_MS
    return missing


def check_trailing_overdue(observed: list[DiagRecord], now_ms: int) -> list[int]:
    if not observed:
        return []
    overdue = []
    ts = observed[-1].bar_ts + BAR_INTERVAL_MS
    while ts + BAR_INTERVAL_MS + DISPATCH_DELAY_MS + JITTER_GRACE_MS < now_ms:
        overdue.append(ts)
        ts += BAR_INTERVAL_MS
    return overdue


def check_empty_bootstrap_overdue(now_ms: int) -> list[int]:
    first_due = FIRST_ELIGIBLE_BAR_TS + BAR_INTERVAL_MS + DISPATCH_DELAY_MS + JITTER_GRACE_MS
    if now_ms > first_due:
        return [FIRST_ELIGIBLE_BAR_TS]
    return []


# ---------------------------------------------------------------------------
# Smoke window verification (design doc lines 330-336)
# ---------------------------------------------------------------------------


def verify_smoke(analysis: list[DiagRecord]) -> list[dict]:
    results = []

    # Bar 1
    if len(analysis) < 1:
        if not analysis:  # 0-bar
            results.append({"bar": 1, "status": SMOKE_UNAVAILABLE, "detail": "0 bars"})
        else:
            results.append({"bar": 1, "status": SMOKE_PENDING, "detail": "not collected"})
    else:
        r = analysis[0]
        checks = {
            "diagnostic_exists": r.diagnostic_exists,
            "populated": r.populated is True,
            "version_1": r.version == 1,
        }
        ok = all(checks.values())
        results.append(
            {
                "bar": 1,
                "status": SMOKE_PASS if ok else SMOKE_FAIL,
                "detail": checks,
            }
        )

    # Bar 2
    if len(analysis) < 2:
        results.append({"bar": 2, "status": SMOKE_PENDING, "detail": "not collected"})
    else:
        r = analysis[1]
        checks = {
            "populated_continuity": r.populated is True,
            "skip_codes_filled": len(r.skip_reason_codes) > 0,
            "version_1": r.version == 1,
        }
        ok = all(checks.values())
        results.append(
            {
                "bar": 2,
                "status": SMOKE_PASS if ok else SMOKE_FAIL,
                "detail": checks,
            }
        )

    # Bar 3
    if len(analysis) < 3:
        results.append({"bar": 3, "status": SMOKE_PENDING, "detail": "not collected"})
    else:
        r = analysis[2]
        rule = r.rule_check
        if rule == "UNVERIFIABLE":
            status = SMOKE_FAIL
        elif rule == "PASS":
            status = SMOKE_PASS
        else:
            status = SMOKE_FAIL
        results.append(
            {
                "bar": 3,
                "status": status,
                "detail": {"near_miss_rule": rule},
            }
        )

    return results


# ---------------------------------------------------------------------------
# 24-bar criteria (design doc lines 321-328)
# ---------------------------------------------------------------------------


def evaluate_criteria(
    analysis: list[DiagRecord],
    window: int,
    observed: list[DiagRecord],
    now_ms: int,
) -> tuple[list[dict], list[str]]:
    """Returns (criteria_results, verdict_reasons)."""
    n = len(analysis)
    reasons: list[str] = []
    criteria = []

    # 1. populated rate
    if n == 0:
        pop_rate = 0.0
    else:
        pop_rate = sum(1 for r in analysis if r.populated is True) / n
    pop_verdict = "PASS" if pop_rate >= THRESHOLD_POPULATED_RATE else "IN_PROGRESS"
    if n >= window and pop_rate < THRESHOLD_POPULATED_RATE:
        pop_verdict = "FAIL"
        reasons.append("POPULATED_RATE_BELOW_THRESHOLD")
    criteria.append(
        {
            "name": "diagnostic_populated=True rate",
            "threshold": f">= {THRESHOLD_POPULATED_RATE:.0%}",
            "observed": f"{pop_rate:.1%} ({sum(1 for r in analysis if r.populated is True)}/{n})",
            "verdict": pop_verdict,
        }
    )

    # 2. version=1 consistency
    if n == 0:
        ver_rate = 0.0
    else:
        ver_rate = sum(1 for r in analysis if r.version == THRESHOLD_VERSION) / n
    ver_verdict = "PASS" if ver_rate >= THRESHOLD_VERSION_RATE else "IN_PROGRESS"
    if n >= window and ver_rate < THRESHOLD_VERSION_RATE:
        ver_verdict = "FAIL"
        reasons.append("VERSION_INCONSISTENCY")
    criteria.append(
        {
            "name": "diagnostic_version=1 consistency",
            "threshold": "100%",
            "observed": f"{ver_rate:.1%} ({sum(1 for r in analysis if r.version == THRESHOLD_VERSION)}/{n})",
            "verdict": ver_verdict,
        }
    )

    # 3. receipt generation failure (internal gap) — analysis_records 기준
    internal_gaps = check_internal_gaps(analysis)
    gap_verdict = "PASS" if len(internal_gaps) == 0 else "FAIL"
    if gap_verdict == "FAIL":
        reasons.append("INTERNAL_GAP_DETECTED")
    criteria.append(
        {
            "name": "receipt 생성 실패 (internal gap)",
            "threshold": "0",
            "observed": f"{len(internal_gaps)}건",
            "verdict": gap_verdict,
        }
    )

    # 4. ERROR count
    err_count = sum(1 for r in analysis if r.is_error)
    err_verdict = "PASS" if err_count == 0 else "FAIL"
    if err_verdict == "FAIL":
        reasons.append("ERROR_ACTION_DETECTED")
    criteria.append(
        {
            "name": "ERROR count",
            "threshold": "0",
            "observed": f"{err_count}건",
            "verdict": err_verdict,
        }
    )

    # 5. bottleneck direction (SMC_ZERO >= WT_ZERO)
    smc_bars = sum(1 for r in analysis if "SMC_ZERO" in r.skip_reason_codes)
    wt_bars = sum(1 for r in analysis if "WT_ZERO" in r.skip_reason_codes)
    if n == 0:
        bn_verdict = "IN_PROGRESS"
    elif smc_bars >= wt_bars:
        bn_verdict = "PASS"
    else:
        bn_verdict = "FAIL"
        reasons.append("BOTTLENECK_DIRECTION_UNEXPECTED")
    criteria.append(
        {
            "name": "replay 대비 병목 방향",
            "threshold": "SMC_ZERO 우세",
            "observed": f"SMC:{smc_bars} WT:{wt_bars}",
            "verdict": bn_verdict,
        }
    )

    # liveness checks — observed_records 기준
    if len(observed) == 0:
        empty_overdue = check_empty_bootstrap_overdue(now_ms)
        if empty_overdue:
            reasons.append("NO_POST_ACTIVATION_RECEIPTS")
    else:
        leading = check_leading_gap(observed)
        if leading:
            reasons.append("LEADING_GAP_DETECTED")
        # trailing only for progress
        if len(observed) < window:
            trailing = check_trailing_overdue(observed, now_ms)
            if trailing:
                reasons.append("TRAILING_OVERDUE_DETECTED")

    # window completion
    if n < window:
        reasons.append("WINDOW_INCOMPLETE")

    # near_miss unverifiable
    unverifiable_count = sum(1 for r in analysis if r.rule_check == "UNVERIFIABLE")
    if unverifiable_count > 0:
        reasons.append("DIAGNOSTIC_FIELD_UNVERIFIABLE")

    # near_miss rule violation
    rule_fail_count = sum(1 for r in analysis if r.rule_check.startswith("FAIL"))
    if rule_fail_count > 0:
        reasons.append("NEAR_MISS_RULE_VIOLATION")

    return criteria, reasons


# ---------------------------------------------------------------------------
# Report generation (Korean markdown)
# ---------------------------------------------------------------------------


def generate_report(
    observed: list[DiagRecord],
    analysis: list[DiagRecord],
    window: int,
    smoke_results: list[dict],
    criteria: list[dict],
    reasons: list[str],
    now_utc: str,
    dup_count: int = 0,
) -> str:
    """Generate observation report in Korean markdown.

    Overall Verdict Folding Rule:
        FAIL > UNVERIFIABLE > IN_PROGRESS > PASS
        0 bars + overdue = FAIL (NO_POST_ACTIVATION_RECEIPTS)
        0 bars + not overdue = IN_PROGRESS (WINDOW_INCOMPLETE)
        0-bar is folded to explicit FAIL/UNAVAILABLE instead of silent empty success.
    """
    status = "final" if len(observed) >= window else "progress"
    verdicts_for_agg: list[str] = []

    # Collect verdicts from criteria
    for c in criteria:
        verdicts_for_agg.append(c["verdict"])
    # Special verdicts from reasons
    if "NO_POST_ACTIVATION_RECEIPTS" in reasons:
        verdicts_for_agg.append("FAIL")
    if "DIAGNOSTIC_FIELD_UNVERIFIABLE" in reasons:
        verdicts_for_agg.append("UNVERIFIABLE")
    if "NEAR_MISS_RULE_VIOLATION" in reasons:
        verdicts_for_agg.append("FAIL")
    if "WINDOW_INCOMPLETE" in reasons:
        verdicts_for_agg.append("IN_PROGRESS")

    final_verdict = aggregate_verdict(verdicts_for_agg)

    # Smoke verdict
    smoke_statuses = [s["status"] for s in smoke_results]
    if SMOKE_UNAVAILABLE in smoke_statuses:
        smoke_verdict = SMOKE_UNAVAILABLE
    elif SMOKE_FAIL in smoke_statuses:
        smoke_verdict = SMOKE_FAIL
    elif SMOKE_PENDING in smoke_statuses:
        smoke_verdict = SMOKE_PENDING
    else:
        smoke_verdict = SMOKE_PASS

    # Gap summary
    leading_gaps = check_leading_gap(observed) if observed else []
    internal_gaps = check_internal_gaps(analysis)
    if len(observed) >= window:
        trailing = []
    else:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        trailing = check_trailing_overdue(observed, now_ms) if observed else []

    bars_observed_total = len(observed)
    bars_analyzed = len(analysis)
    first_bar_ts = analysis[0].bar_ts_utc if analysis else "None"
    last_bar_ts = analysis[-1].bar_ts_utc if analysis else "None"

    # Build heading
    if status == "progress":
        heading = f"## C1-A {window}-Bar 관측 진행 현황 ({now_utc})"
    else:
        heading = f"## C1-A {window}-Bar 최종 관측 결과 ({now_utc})"

    lines = [heading, ""]

    # A. Summary
    lines.append("### 요약")
    lines.append("")
    lines.append(f"- **상태:** {final_verdict}")
    lines.append(f"- **분석 bars:** {bars_analyzed}/{window}")
    lines.append(f"- **총 수집 bars:** {bars_observed_total}")
    lines.append(f"- **smoke 판정:** {smoke_verdict}")
    lines.append(f"- **internal gap:** {len(internal_gaps)}건 (analysis 기준)")
    if len(observed) < window:
        lines.append(f"- **trailing overdue:** {len(trailing)}건 (observed 기준)")
    else:
        lines.append("- **trailing overdue:** N/A (final)")
    lines.append(f"- **leading gap:** {len(leading_gaps)}건")
    err_total = sum(1 for r in analysis if r.is_error)
    lines.append(f"- **error:** {err_total}건")
    lines.append(f"- **verdict_reasons:** `{reasons}`")
    lines.append("")

    # Empty Observation block (0-bar explicit folding)
    if bars_analyzed == 0:
        lines.append("### Empty Observation")
        lines.append("")
        lines.append("- **전체 판정:** FAIL")
        lines.append("- **smoke:** UNAVAILABLE")
        lines.append("- **이유:** NO_POST_ACTIVATION_RECEIPTS")
        lines.append("")
        lines.append("post-activation 기간에 수집된 receipt가 0건입니다.")
        lines.append("이 상태는 정상적인 치명 실패 산출물로 처리됩니다.")
        lines.append("")

    # B. Smoke Window
    lines.append("### Smoke Window 결과")
    lines.append("")
    lines.append("| bar | bar_ts (UTC) | 검증 항목 | 결과 |")
    lines.append("|-----|-------------|-----------|------|")
    smoke_labels = [
        "diagnostic 존재 + populated + version=1",
        "populated 연속성 + skip_reason_codes 채워짐",
        "near_miss_type 규칙 일관성",
    ]
    for i, sr in enumerate(smoke_results):
        bar_ts_str = analysis[i].bar_ts_utc if i < len(analysis) else "—"
        detail = str(sr["detail"]) if isinstance(sr["detail"], dict) else sr["detail"]
        lines.append(f"| {sr['bar']} | {bar_ts_str} | {smoke_labels[i]} | {sr['status']} |")
    lines.append("")

    # C. 24-Bar criteria
    lines.append(f"### {window}-Bar 기준 진행 현황 ({bars_analyzed}/{window} bars)")
    lines.append("")
    lines.append("| 항목 | 성공 기준 | 현재 관측값 | 판정 |")
    lines.append("|------|-----------|------------|------|")
    for c in criteria:
        lines.append(f"| `{c['name']}` | {c['threshold']} | {c['observed']} | {c['verdict']} |")
    lines.append("")

    # D. Gap analysis
    lines.append("### Gap 분석")
    lines.append("")
    lines.append("| gap 유형 | 건수 | 상세 |")
    lines.append("|----------|------|------|")
    leading_detail = ", ".join(_ts_to_utc(t) for t in leading_gaps[:5]) if leading_gaps else "—"
    lines.append(f"| leading | {len(leading_gaps)} | {leading_detail} |")
    internal_detail = ", ".join(_ts_to_utc(t) for t in internal_gaps[:5]) if internal_gaps else "—"
    lines.append(f"| internal | {len(internal_gaps)} | {internal_detail} |")
    if len(observed) < window:
        trailing_detail = ", ".join(_ts_to_utc(t) for t in trailing[:5]) if trailing else "—"
        lines.append(f"| trailing overdue | {len(trailing)} | {trailing_detail} |")
    else:
        lines.append("| trailing overdue | N/A | final — 범위 밖 검사 제외 |")
    lines.append("")

    # E. Raw table
    lines.append("### 진단 필드 원시값")
    lines.append("")
    lines.append(
        "| bar# | bar_ts (UTC) | action | smc_sig | wt_sig | skip_codes | near_miss | bottleneck | rule_check |"
    )
    lines.append(
        "|------|-------------|--------|---------|--------|------------|-----------|------------|------------|"
    )
    for r in analysis:
        codes_str = ",".join(r.skip_reason_codes) if r.skip_reason_codes else "—"
        nm_str = r.near_miss_type if r.near_miss_type is not None else "null"
        lines.append(
            f"| {r.bar_index} | {r.bar_ts_utc} | {r.action} | {r.smc_sig_raw} | {r.wt_sig_raw} "
            f"| {codes_str} | {nm_str} | {r.bottleneck_class} | {r.rule_check} |"
        )
    if not analysis:
        lines.append("| — | — | — | — | — | — | — | — | — |")
    lines.append("")

    # F. Fingerprint
    lines.append("### 관측 Fingerprint")
    lines.append("")
    lines.append(f"- generated_at: {now_utc}")
    lines.append(f"- window: {window}")
    lines.append(f"- bars_observed_total: {bars_observed_total}")
    lines.append(f"- bars_analyzed: {bars_analyzed}")
    lines.append(f"- first_bar_ts: {first_bar_ts}")
    lines.append(f"- last_bar_ts: {last_bar_ts}")
    lines.append(f"- duplicate_ignored: {dup_count}")
    lines.append("")

    # G. Final verdict
    lines.append("### 최종 판정")
    lines.append("")
    lines.append(f"**{final_verdict}** ({bars_analyzed}/{window} bars)")
    if reasons:
        lines.append(f"- verdict_reasons: {reasons}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Evidence append
# ---------------------------------------------------------------------------


def make_heading_anchor(window: int, status: str) -> str:
    if status == "progress":
        return f"## C1-A {window}-Bar 관측 진행 현황"
    return f"## C1-A {window}-Bar 최종 관측 결과"


def section_exists(filepath: str, heading_prefix: str) -> bool:
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith(heading_prefix):
                return True
    return False


LOCK_PATH = EVIDENCE_PATH + ".lock"


def _acquire_lock() -> bool:
    """Atomically create lock file. Returns True on success."""
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    """Remove lock file. Only FileNotFoundError is silenced."""
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass


def append_evidence(report: str, observed_count: int, window: int, reasons: list[str]):
    status = "final" if observed_count >= window else "progress"
    anchor = make_heading_anchor(window, status)

    # Acquire lock for atomic append
    if not _acquire_lock():
        print("[ABORT] Lock file exists -- concurrent append blocked")
        return False

    try:
        # Re-check heading under lock (double-check after acquire)
        if section_exists(EVIDENCE_PATH, anchor):
            print(f"[SKIP] 중복 섹션 존재: '{anchor}' -- append 거부")
            return False

        # Append conditions
        fatal_empty = observed_count == 0 and "NO_POST_ACTIVATION_RECEIPTS" in reasons
        if status == "progress" and observed_count < 3 and not fatal_empty:
            print(
                f"[SKIP] progress append 조건 미충족: bars={observed_count} < 3, fatal_empty=False"
            )
            return False
        if status == "final" and observed_count < window:
            print(f"[SKIP] final append 조건 미충족: bars={observed_count} < window={window}")
            return False

        with open(EVIDENCE_PATH, "a", encoding="utf-8") as f:
            f.write("\n\n---\n\n")
            f.write(report)

        print(f"[OK] Evidence appended ({status}): {EVIDENCE_PATH}")
        return True
    finally:
        _release_lock()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="CR-046 C1-A Diagnostic Observation (read-only)")
    parser.add_argument(
        "--window",
        type=int,
        default=3,
        choices=[3, 24, 168],
        help="Observation window (3=smoke, 24=24-bar, 168=7-day)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Postgres connection string",
    )
    parser.add_argument(
        "--append-to-evidence",
        action="store_true",
        help="Append report to sealed design document",
    )
    args = parser.parse_args()

    db_url = args.db_url or settings.database_url_sync
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    now_utc = now.strftime("%Y-%m-%d %H:%M UTC")

    print(f"=== CR-046 C1-A Diagnostic Observation ===")
    print(f"window={args.window}  session={SESSION_ID}  now={now_utc}")
    print()

    # Preflight
    run_preflight(db_url, args.append_to_evidence)

    # Fetch (returns deduplicated records + dup_count)
    observed_records, dup_count = fetch_observed_records(db_url)
    print(f"[DB] post-cutoff receipts: {len(observed_records)} (canonical)")

    # Slice
    analysis_count = min(len(observed_records), args.window)
    analysis_records = observed_records[:analysis_count]
    print(f"[SLICE] analysis_records: {len(analysis_records)}/{args.window}")
    print()

    # Smoke
    smoke_results = verify_smoke(analysis_records)

    # Criteria
    criteria, reasons = evaluate_criteria(
        analysis_records,
        args.window,
        observed_records,
        now_ms,
    )

    # Report
    report = generate_report(
        observed_records,
        analysis_records,
        args.window,
        smoke_results,
        criteria,
        reasons,
        now_utc,
        dup_count=dup_count,
    )

    print(report)

    # Evidence append
    if args.append_to_evidence:
        append_evidence(report, len(observed_records), args.window, reasons)


if __name__ == "__main__":
    main()
