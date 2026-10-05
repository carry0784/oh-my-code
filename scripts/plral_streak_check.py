#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PLRAL Streak Check (offline analyzer)
=====================================

운영자 해석 보조 도구 — 연속 N회 판정 streak 분석.
NOT part of TRCC. NOT part of runtime.

User rule (2026-04-14):
    "연속 3회 판정 기준 — 1회=관측, 2회=원인확인, 3회=구조이슈"
    "runtime 변경이 아니라 해석용 운영 기준"

Coupling discipline (DP-1 preserved):
    - Reads  : logs/preeval/rhl.jsonl, logs/preeval/iwl.jsonl (PLRAL)
    - Writes : NONE (stdout only; never touches PLRAL or any runtime file)
    - Called by: 운영자가 수동 실행. TRCC (health_check.py) 는 이 파일을 호출하지 않음.
    - Called on: nothing. 이 스크립트도 외부에서 호출되지 않는 단발성 도구.

Usage:
    python scripts/plral_streak_check.py
    python scripts/plral_streak_check.py --window 10    # last N RHL entries
    python scripts/plral_streak_check.py --json         # machine-readable output

Interpretation rules (per user direction):
    * N=1 : "관측" (observation)          — 단발, 판정 보류
    * N=2 : "원인확인" (cause check)      — 패턴화 가능성, VRL 기록 권장
    * N>=3: "구조이슈" (structural issue) — 운영자 개입 대상, TRCC 폐기 전 조치 검토

Output (ASCII card, 3판정 surface stays uncoupled — this tool does NOT re-emit
verdicts, only streak metadata).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
PLRAL_DIR = REPO_ROOT / "logs" / "preeval"
RHL_PATH = PLRAL_DIR / "rhl.jsonl"
IWL_PATH = PLRAL_DIR / "iwl.jsonl"

STREAK_N1_LABEL = "관측"
STREAK_N2_LABEL = "원인확인"
STREAK_N3PLUS_LABEL = "구조이슈"

# Mirror of health_check.py REASON_CODE_BUCKETS — duplicated by design
# (offline analyzer must stand alone, no cross-module import).
# If health_check.py extends, keep this in sync manually. v3 schema adds
# reason_code_buckets directly in RHL entries, so this is also fallback.
REASON_CODE_BUCKETS = {
    "PID_STALE_OR_UNKNOWN":            "REGISTRY",
    "OBSERVED_CELERY_MATCHES":         "REGISTRY",
    "OBSERVED_CELERY_ABSENT":          "REGISTRY",
    "FLOWER_UI_OK_API_AUTH_REQUIRED":  "PROBE",
    "FLOWER_UNREACHABLE":              "PROBE",
    "DB_OK_BUT_RUNTIME_UNCONFIRMED":   "DATA",
    "OBSERVATION_SOURCE_EMPTY":        "DATA",
    "OBSERVATION_SOURCE_STALE":        "DATA",
    "OBSERVATION_QUERY_MISSING_TABLE": "DATA",
    "OK_FULL":                         "POSITIVE",
}
BUCKET_ORDER = ("REGISTRY", "PROBE", "DATA", "POSITIVE", "OTHER")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read .jsonl, skipping empty and malformed lines. NEVER raises."""
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(json.loads(raw))
                except Exception:
                    # tolerate malformed lines (append-only ledger can have
                    # partial writes from crash-interrupted append — rare)
                    continue
    except Exception:
        return []
    return out


def extract_verdict_series(rhl: List[Dict[str, Any]],
                           window: Optional[int] = None
                           ) -> List[Dict[str, Any]]:
    """Return list of {ts, verdict, reason_codes} from RHL, newest-last order."""
    series = []
    for e in rhl:
        series.append({
            "ts": e.get("ts"),
            "verdict": e.get("card_verdict"),
            "reason_codes": e.get("reason_codes") or [],
        })
    if window and len(series) > window:
        series = series[-window:]
    return series


def compute_verdict_streaks(series: List[Dict[str, Any]]
                            ) -> List[Dict[str, Any]]:
    """
    Sequence of (verdict, run_length, start_ts, end_ts) from consecutive same
    verdicts. Length == number of consecutive RHL entries with identical
    verdict.
    """
    if not series:
        return []
    streaks: List[Dict[str, Any]] = []
    cur_verdict = series[0]["verdict"]
    cur_start = series[0]["ts"]
    cur_end = series[0]["ts"]
    cur_len = 1
    for e in series[1:]:
        if e["verdict"] == cur_verdict:
            cur_len += 1
            cur_end = e["ts"]
        else:
            streaks.append({"verdict": cur_verdict, "length": cur_len,
                            "start_ts": cur_start, "end_ts": cur_end})
            cur_verdict = e["verdict"]
            cur_start = e["ts"]
            cur_end = e["ts"]
            cur_len = 1
    streaks.append({"verdict": cur_verdict, "length": cur_len,
                    "start_ts": cur_start, "end_ts": cur_end})
    return streaks


def compute_reason_code_streaks(series: List[Dict[str, Any]]
                                ) -> Dict[str, Dict[str, Any]]:
    """
    For each reason_code, return the current trailing streak length.
    'trailing' = counting backward from the most recent entry, how many
    consecutive RHL entries contained this code.
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not series:
        return result
    # Collect all codes ever seen
    all_codes = set()
    for e in series:
        for c in (e.get("reason_codes") or []):
            all_codes.add(c)
    for code in all_codes:
        trailing = 0
        first_ts: Optional[str] = None
        last_ts: Optional[str] = None
        for e in reversed(series):
            if code in (e.get("reason_codes") or []):
                trailing += 1
                if last_ts is None:
                    last_ts = e["ts"]
                first_ts = e["ts"]  # earliest in trailing window
            else:
                break
        if trailing > 0:
            result[code] = {
                "trailing_streak": trailing,
                "first_ts_in_streak": first_ts,
                "last_ts_in_streak": last_ts,
                "interpretation": (
                    STREAK_N3PLUS_LABEL if trailing >= 3
                    else (STREAK_N2_LABEL if trailing == 2
                          else STREAK_N1_LABEL)
                ),
            }
    return result


def compute_reason_code_cumulative(series: List[Dict[str, Any]]
                                   ) -> Dict[str, int]:
    """Total occurrences of each reason_code across the window."""
    counts: Dict[str, int] = defaultdict(int)
    for e in series:
        for c in (e.get("reason_codes") or []):
            counts[c] += 1
    return dict(counts)


def iwl_incident_summary(iwl: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count IWL incidents by category."""
    counts: Dict[str, int] = defaultdict(int)
    for e in iwl:
        cat = e.get("category", "unknown")
        counts[cat] += 1
    return dict(counts)


def compute_bucket_aggregation(series: List[Dict[str, Any]]
                               ) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate reason_codes by 3-bucket classification across the window.
    Returns per-bucket {count, codes: {code: count}, trailing_streak}.

    trailing_streak = how many consecutive most-recent RHL entries had
    ANY code in this bucket (backward from latest entry).
    """
    result: Dict[str, Dict[str, Any]] = {}
    for b in BUCKET_ORDER:
        result[b] = {"count": 0, "codes": {}, "trailing_streak": 0}
    if not series:
        return result
    # Per-entry bucket presence
    entry_buckets: List[set] = []
    for e in series:
        codes = e.get("reason_codes") or []
        buckets_here = set()
        for c in codes:
            b = REASON_CODE_BUCKETS.get(c, "OTHER")
            result[b]["count"] += 1
            result[b]["codes"][c] = result[b]["codes"].get(c, 0) + 1
            buckets_here.add(b)
        entry_buckets.append(buckets_here)
    # Trailing streak per bucket
    for b in BUCKET_ORDER:
        trailing = 0
        for eb in reversed(entry_buckets):
            if b in eb:
                trailing += 1
            else:
                break
        result[b]["trailing_streak"] = trailing
    return result


def compute_baseline_delta(series: List[Dict[str, Any]]
                           ) -> Optional[Dict[str, Any]]:
    """
    Operator 아이디어 2 (2026-04-14): baseline delta 1-line summary.
    Compare most recent RHL entry to previous entry.
    - added    = codes present now but not in previous
    - removed  = codes in previous but not now
    - unchanged= codes common to both
    - verdict_change = prev.verdict -> curr.verdict (may be same)

    This computation is EXPLICITLY confined to the offline analyzer.
    It is NOT implemented in TRCC (health_check.py) because that would
    require TRCC to read PLRAL, violating DP-1 unidirectional coupling.
    """
    if len(series) < 2:
        return None
    prev = series[-2]
    curr = series[-1]
    prev_codes = set(prev.get("reason_codes") or [])
    curr_codes = set(curr.get("reason_codes") or [])
    added = sorted(curr_codes - prev_codes)
    removed = sorted(prev_codes - curr_codes)
    unchanged = sorted(curr_codes & prev_codes)
    verdict_prev = prev.get("verdict")
    verdict_curr = curr.get("verdict")

    # Short 1-liner per operator proposal.
    parts = []
    if verdict_prev != verdict_curr:
        parts.append(f"verdict {verdict_prev}→{verdict_curr}")
    else:
        parts.append(f"verdict={verdict_curr}")
    if added:
        parts.append("+" + ",".join(added))
    if removed:
        parts.append("-" + ",".join(removed))
    if not added and not removed and verdict_prev == verdict_curr:
        parts.append("unchanged")
    one_liner = "  ".join(parts)

    return {
        "from_ts": prev.get("ts"),
        "to_ts": curr.get("ts"),
        "verdict_prev": verdict_prev,
        "verdict_curr": verdict_curr,
        "added_codes": added,
        "removed_codes": removed,
        "unchanged_codes": unchanged,
        "one_line": one_liner,
    }


def render_text(rhl_count: int, iwl_count: int,
                verdict_streaks: List[Dict[str, Any]],
                code_streaks: Dict[str, Dict[str, Any]],
                code_cumulative: Dict[str, int],
                iwl_cats: Dict[str, int],
                window_size: int,
                bucket_agg: Dict[str, Dict[str, Any]],
                baseline_delta: Optional[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("  PLRAL Streak Check (offline) — 해석용, runtime 변경 없음")
    lines.append("=" * 72)
    lines.append(f"  Source     : {RHL_PATH.name} ({rhl_count} lines) / "
                 f"{IWL_PATH.name} ({iwl_count} lines)")
    lines.append(f"  Window     : last {window_size} RHL entries")
    lines.append(f"  Generated  : {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append("-" * 72)
    # Verdict run streaks
    lines.append("  Verdict run streaks (consecutive same verdict):")
    if not verdict_streaks:
        lines.append("    (no data)")
    else:
        for s in verdict_streaks[-5:]:  # last few
            label = (STREAK_N3PLUS_LABEL if s["length"] >= 3
                     else (STREAK_N2_LABEL if s["length"] == 2
                           else STREAK_N1_LABEL))
            lines.append(
                f"    verdict={s['verdict']:<6} "
                f"len={s['length']:>2}  "
                f"[{s['start_ts']} .. {s['end_ts']}]  "
                f"→ {label}"
            )
    lines.append("-" * 72)
    # Trailing streaks per reason code
    lines.append("  Reason code trailing streaks (most recent → backward):")
    if not code_streaks:
        lines.append("    (no reason codes yet)")
    else:
        sorted_codes = sorted(code_streaks.items(),
                              key=lambda x: (-x[1]["trailing_streak"], x[0]))
        for code, info in sorted_codes:
            n = info["trailing_streak"]
            lines.append(
                f"    {code:<36} "
                f"n={n:>2}  "
                f"→ {info['interpretation']}  "
                f"[{info['first_ts_in_streak']} .. {info['last_ts_in_streak']}]"
            )
    lines.append("-" * 72)
    # Cumulative occurrence across window
    lines.append(f"  Cumulative occurrence (within window={window_size}):")
    if not code_cumulative:
        lines.append("    (no reason codes yet)")
    else:
        for code, n in sorted(code_cumulative.items(),
                              key=lambda x: (-x[1], x[0])):
            lines.append(f"    {code:<36} total={n}")
    lines.append("-" * 72)
    # IWL incidents by category
    lines.append("  IWL incidents by category (all-time):")
    if not iwl_cats:
        lines.append("    (no incidents)")
    else:
        for cat, n in sorted(iwl_cats.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"    {cat:<36} total={n}")
    lines.append("-" * 72)
    # 3-bucket aggregation (operator 아이디어 1)
    lines.append("  Reason code 3-bucket aggregation "
                 "(REGISTRY / PROBE / DATA / POSITIVE):")
    any_bucket = False
    for b in BUCKET_ORDER:
        info = bucket_agg.get(b, {"count": 0, "codes": {}, "trailing_streak": 0})
        if info["count"] == 0 and info["trailing_streak"] == 0:
            continue
        any_bucket = True
        code_list = sorted(info["codes"].items(), key=lambda x: (-x[1], x[0]))
        code_str = ", ".join(f"{k}×{v}" for k, v in code_list[:4]) or "-"
        lines.append(
            f"    {b:<10} count={info['count']:>3} "
            f"trailing_streak={info['trailing_streak']:>2}  "
            f"codes=[{code_str}]"
        )
    if not any_bucket:
        lines.append("    (no bucket data yet)")
    lines.append("-" * 72)
    # Baseline delta (operator 아이디어 2; offline-only per DP-1)
    lines.append("  Baseline delta (prev → current RHL, offline-only):")
    if baseline_delta is None:
        lines.append("    (need ≥2 RHL entries for delta)")
    else:
        lines.append(
            f"    {baseline_delta['from_ts']} → {baseline_delta['to_ts']}"
        )
        lines.append(f"    summary: {baseline_delta['one_line']}")
        if baseline_delta["added_codes"]:
            lines.append(
                f"    added   : {', '.join(baseline_delta['added_codes'])}"
            )
        if baseline_delta["removed_codes"]:
            lines.append(
                f"    removed : {', '.join(baseline_delta['removed_codes'])}"
            )
        if baseline_delta["unchanged_codes"]:
            lines.append(
                f"    persist : {', '.join(baseline_delta['unchanged_codes'])}"
            )
    lines.append("-" * 72)
    lines.append(
        "  해석 규칙 (operator interpretation, NOT runtime):"
    )
    lines.append(f"    n=1 → {STREAK_N1_LABEL} (단발, 판정 보류)")
    lines.append(f"    n=2 → {STREAK_N2_LABEL} (패턴화 가능성, VRL 기록 권장)")
    lines.append(f"    n≥3 → {STREAK_N3PLUS_LABEL} (운영자 개입 대상)")
    lines.append("-" * 72)
    lines.append(
        "  결합 규칙 : TRCC(health_check.py)는 이 스크립트를 호출하지 않음."
    )
    lines.append(
        "  파일 쓰기 : 없음. stdout only. PLRAL append-only 불변식 유지."
    )
    lines.append("=" * 72)
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Offline PLRAL streak analyzer (operator interpretive only)."
    )
    ap.add_argument("--window", type=int, default=50,
                    help="Max last-N RHL entries to consider (default 50).")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON instead of text card.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    rhl = read_jsonl(RHL_PATH)
    iwl = read_jsonl(IWL_PATH)
    series = extract_verdict_series(rhl, window=args.window)
    v_streaks = compute_verdict_streaks(series)
    c_streaks = compute_reason_code_streaks(series)
    c_cumul = compute_reason_code_cumulative(series)
    iwl_cats = iwl_incident_summary(iwl)
    bucket_agg = compute_bucket_aggregation(series)
    baseline_delta = compute_baseline_delta(series)

    if args.json:
        payload = {
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "source": {
                "rhl_lines": len(rhl),
                "iwl_lines": len(iwl),
            },
            "window_size": args.window,
            "verdict_streaks": v_streaks,
            "reason_code_trailing_streaks": c_streaks,
            "reason_code_cumulative": c_cumul,
            "reason_code_bucket_aggregation": bucket_agg,
            "baseline_delta": baseline_delta,
            "iwl_category_counts": iwl_cats,
            "interpretation_rules": {
                "n1": STREAK_N1_LABEL,
                "n2": STREAK_N2_LABEL,
                "n_ge_3": STREAK_N3PLUS_LABEL,
            },
            "coupling_discipline": {
                "reads": [str(RHL_PATH.relative_to(REPO_ROOT)),
                          str(IWL_PATH.relative_to(REPO_ROOT))],
                "writes": [],
                "trcc_coupling": "none",
                "dp1_note": (
                    "baseline_delta computed here (offline) rather than in "
                    "health_check.py to preserve DP-1 unidirectional coupling"
                ),
            },
        }
        try:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        except Exception:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    text = render_text(
        rhl_count=len(rhl), iwl_count=len(iwl),
        verdict_streaks=v_streaks, code_streaks=c_streaks,
        code_cumulative=c_cumul, iwl_cats=iwl_cats,
        window_size=args.window,
        bucket_agg=bucket_agg, baseline_delta=baseline_delta,
    )
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
