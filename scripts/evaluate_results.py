#!/usr/bin/env python3
"""
K-Dexter AutoFix Loop — Step 3: Evaluate Results

테스트 + 검증 결과를 종합 평가하여 사람이 읽기 쉬운 요약을 생성한다.
eval-viewer 입력 호환 형식으로 출력한다.

Usage:
    python scripts/evaluate_results.py
    python scripts/evaluate_results.py --format markdown
    python scripts/evaluate_results.py --format json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is cwd for data file resolution
_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)


# ── Risk Score Table ──────────────────────────────────────────────────────── #
# Each failure type contributes to total risk score.
# GREEN: 0-2 | YELLOW: 3-7 | RED: 8+

RISK_TABLE = {
    "test_failed": 1,        # per test failure
    "test_error": 2,         # per test error
    "import_error": 3,       # import failure in validation
    "governance_violation": 5,  # governance-checker BLOCK
    "governance_warning": 2,   # governance-checker WARN
    "validation_fail": 2,     # per validation check failure
    "constitution_fail": 5,   # verify_constitution.py FAIL
    "live_path_touch": 3,     # live execution path modified
}

RECURRENCE_MULTIPLIER = {
    "FIRST": 1.0,
    "REPEAT": 1.5,
    "PATTERN": 2.0,
}

GREEN_THRESHOLD = 2
YELLOW_THRESHOLD = 7
# Above YELLOW = RED


def compute_risk_score(test_data: dict | None, validation_data: dict | None,
                       governance_data: dict | None = None,
                       failure_patterns: list[dict] | None = None) -> tuple[int, list[dict]]:
    """Compute total risk score with breakdown."""
    breakdown: list[dict] = []
    total = 0

    # Build lookup map from failure_patterns by test_id for O(1) access
    pattern_map: dict[str, str] = {}
    if failure_patterns:
        for p in failure_patterns:
            tid = p.get("test_id")
            if tid:
                pattern_map[tid] = p.get("recurrence", "FIRST")

    if test_data:
        failures = test_data.get("failures", [])
        failed = test_data.get("failed", 0)
        errors = test_data.get("errors", 0)
        if failed > 0:
            if failure_patterns is not None and failures:
                # Apply per-failure recurrence multiplier
                weighted = 0.0
                for f in failures:
                    recurrence = pattern_map.get(f.get("test_id", ""), "FIRST")
                    multiplier = RECURRENCE_MULTIPLIER.get(recurrence, 1.0)
                    weighted += RISK_TABLE["test_failed"] * multiplier
                # Remaining failures not listed individually keep base weight
                unlisted = max(0, failed - len(failures))
                weighted += unlisted * RISK_TABLE["test_failed"]
                score = int(math.ceil(weighted))
            else:
                score = failed * RISK_TABLE["test_failed"]
            breakdown.append({"type": "test_failed", "count": failed, "score": score})
            total += score
        if errors > 0:
            if failure_patterns is not None and failures:
                weighted = 0.0
                error_failures = [f for f in failures if f.get("kind") == "error"]
                for f in error_failures:
                    recurrence = pattern_map.get(f.get("test_id", ""), "FIRST")
                    multiplier = RECURRENCE_MULTIPLIER.get(recurrence, 1.0)
                    weighted += RISK_TABLE["test_error"] * multiplier
                unlisted = max(0, errors - len(error_failures))
                weighted += unlisted * RISK_TABLE["test_error"]
                score = int(math.ceil(weighted))
            else:
                score = errors * RISK_TABLE["test_error"]
            breakdown.append({"type": "test_error", "count": errors, "score": score})
            total += score

    if validation_data:
        checks = validation_data.get("checks", [])
        for c in checks:
            if c["status"] != "OK":
                if "import" in c.get("name", "").lower():
                    score = RISK_TABLE["import_error"]
                    breakdown.append({"type": "import_error", "name": c["name"], "score": score})
                elif "constitution" in c.get("name", "").lower():
                    score = RISK_TABLE["constitution_fail"]
                    breakdown.append({"type": "constitution_fail", "name": c["name"], "score": score})
                else:
                    score = RISK_TABLE["validation_fail"]
                    breakdown.append({"type": "validation_fail", "name": c["name"], "score": score})
                total += score

    if governance_data:
        violations = governance_data.get("violations", [])
        warnings = governance_data.get("warnings", [])
        if violations:
            score = len(violations) * RISK_TABLE["governance_violation"]
            breakdown.append({"type": "governance_violation", "count": len(violations), "score": score})
            total += score
        if warnings:
            score = len(warnings) * RISK_TABLE["governance_warning"]
            breakdown.append({"type": "governance_warning", "count": len(warnings), "score": score})
            total += score
        live = governance_data.get("live_path_touches", [])
        if live:
            score = len(live) * RISK_TABLE["live_path_touch"]
            breakdown.append({"type": "live_path_touch", "count": len(live), "score": score})
            total += score

    return total, breakdown


def score_to_grade(score: int) -> str:
    """Convert risk score to GREEN/YELLOW/RED."""
    if score <= GREEN_THRESHOLD:
        return "GREEN"
    if score <= YELLOW_THRESHOLD:
        return "YELLOW"
    return "RED"


def load_json(path: str) -> dict | None:
    """Load JSON file, return None if missing."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def evaluate(test_data: dict | None, validation_data: dict | None,
             governance_data: dict | None = None,
             failure_patterns: list[dict] | None = None) -> dict:
    """Produce unified evaluation report with risk-score-based grading."""
    now = datetime.now(timezone.utc).isoformat()

    # Test results summary
    if test_data:
        test_summary = {
            "scope": test_data.get("scope", "unknown"),
            "status": test_data.get("status", "UNKNOWN"),
            "passed": test_data.get("passed", 0),
            "failed": test_data.get("failed", 0),
            "errors": test_data.get("errors", 0),
            "total": test_data.get("total", 0),
            "failure_count": len(test_data.get("failures", [])),
            "top_failures": [
                f["test_id"] for f in test_data.get("failures", [])[:5]
            ],
        }
    else:
        test_summary = {"status": "NOT_RUN", "reason": "data/test_results.json not found"}

    # Validation results summary
    if validation_data:
        val_checks = validation_data.get("checks", [])
        val_failures = [c for c in val_checks if c["status"] != "OK"]
        import_errors = sum(1 for c in val_failures if "import" in c.get("name", "").lower())
        validation_summary = {
            "status": validation_data.get("overall", "UNKNOWN"),
            "passed": validation_data.get("passed", 0),
            "failed": validation_data.get("failed", 0),
            "total": validation_data.get("total", 0),
            "import_errors": import_errors,
            "failures": [
                {"name": c["name"], "detail": c["detail"]} for c in val_failures
            ],
        }
    else:
        validation_summary = {"status": "NOT_RUN", "reason": "data/validation_results.json not found"}

    # Governance check summary
    if governance_data:
        governance_summary = {
            "status": governance_data.get("judgment", "UNKNOWN"),
            "violations": len(governance_data.get("violations", [])),
            "warnings": len(governance_data.get("warnings", [])),
            "live_path_touches": len(governance_data.get("live_path_touches", [])),
            "total_risk_score": governance_data.get("total_risk_score", 0),
            "files_checked": len(governance_data.get("files_checked", [])),
        }
    else:
        governance_summary = {"status": "NOT_RUN", "reason": "data/governance_check_result.json not found"}

    # ── Risk-score-based grading ──────────────────────────────────────── #
    risk_score, risk_breakdown = compute_risk_score(
        test_data, validation_data, governance_data, failure_patterns
    )
    final_grade = score_to_grade(risk_score)

    # ── BLOCK override: governance BLOCK always forces RED ────────────── #
    blocked = False
    blocked_reason: str | None = None
    if governance_summary.get("status") == "BLOCK":
        final_grade = "RED"
        blocked = True
        blocked_reason = (
            "Governance judgment is BLOCK — all modifications halted. "
            "Manual review required before any further action."
        )

    # Recommended action based on grade + breakdown
    if blocked:
        action = f"GOVERNANCE BLOCK (score={risk_score}). All modifications halted. Manual review required."
    elif final_grade == "GREEN":
        action = "No action required. System healthy."
    elif final_grade == "YELLOW":
        # Identify dominant risk factor
        top_risk = max(risk_breakdown, key=lambda x: x["score"]) if risk_breakdown else {}
        action = f"Moderate risk (score={risk_score}). Primary factor: {top_risk.get('type', 'unknown')}. Review and fix."
    else:  # RED
        block_items = [r for r in risk_breakdown if r["type"] in ("governance_violation", "constitution_fail")]
        if block_items:
            action = f"CRITICAL (score={risk_score}). Governance violations detected — manual review required before any merge."
        else:
            action = f"High risk (score={risk_score}). Multiple failures across test/validation. Prioritize: validation fixes first."

    # Next steps
    next_steps = []
    gov_blocked = governance_summary.get("status") == "BLOCK"
    test_ok = test_summary.get("status") == "PASS"
    val_ok = validation_summary.get("status") == "PASS"

    if gov_blocked:
        next_steps.append("BLOCKED: Governance violation detected. Revert changes or fix violations first.")
    if not test_ok and test_summary.get("status") != "NOT_RUN":
        next_steps.append("Run: python scripts/run_tests.py --scope governance")
        next_steps.append("Analyze failures with failure-analyzer agent")
    if not val_ok and validation_summary.get("status") != "NOT_RUN":
        for f in validation_summary.get("failures", [])[:3]:
            next_steps.append(f"Fix validation: {f['name']} — {f['detail']}")
    if final_grade == "GREEN":
        next_steps.append("System healthy. Continue monitoring via G-MON.")

    # ── Pattern summary ───────────────────────────────────────────────── #
    patterns = failure_patterns or []
    pattern_summary = {
        "total": len(patterns),
        "first": sum(1 for p in patterns if p.get("recurrence", "FIRST") == "FIRST"),
        "repeat": sum(1 for p in patterns if p.get("recurrence") == "REPEAT"),
        "pattern": sum(1 for p in patterns if p.get("recurrence") == "PATTERN"),
    }

    # ── Standardized output schema ────────────────────────────────────── #
    return {
        "evaluation_timestamp": now,
        "scope": test_summary.get("scope", "unknown"),
        "final_grade": final_grade,
        "risk_score": risk_score,
        "risk_breakdown": risk_breakdown,
        "recommended_action": action,
        "blocked": blocked,
        "blocked_reason": blocked_reason,
        "test_summary": test_summary,
        "validation_summary": validation_summary,
        "governance_summary": governance_summary,
        "pattern_summary": pattern_summary,
        "next_steps": next_steps[:5],
        # Legacy compat
        "overall_status": final_grade,
    }


def format_markdown(report: dict) -> str:
    """Format as human-readable markdown."""
    icon = {"GREEN": "OK", "YELLOW": "!!", "RED": "XX"}
    grade = report.get("final_grade", report.get("overall_status", "??"))
    risk = report.get("risk_score", "?")

    lines = [
        f"# K-Dexter Evaluation Report",
        f"",
        f"**Time**: {report['evaluation_timestamp'][:19]}Z",
        f"**Grade**: [{icon.get(grade, '??')}] {grade}  (risk score: {risk})",
        f"**Action**: {report['recommended_action']}",
        f"",
    ]

    # BLOCK banner — shown prominently when governance status is BLOCK
    if report.get("blocked") or report.get("governance_summary", {}).get("status") == "BLOCK":
        lines += [
            f"## !! GOVERNANCE BLOCK !!",
            f"- Judgment: BLOCK",
            f"- All modifications halted. Manual review required.",
            f"",
        ]

    # Risk breakdown
    breakdown = report.get("risk_breakdown", [])
    if breakdown:
        lines.append(f"## Risk Breakdown")
        for item in breakdown:
            lines.append(f"  - {item['type']}: +{item['score']} pts")
        lines.append(f"")

    # Test results
    lines.append(f"## Test Results")
    ts = report["test_summary"]
    if ts.get("status") == "NOT_RUN":
        lines.append(f"- Not run: {ts.get('reason', '')}")
    else:
        lines.append(f"- Status: {ts['status']} | Scope: {ts.get('scope', '?')}")
        lines.append(f"- Passed: {ts.get('passed', 0)} / Failed: {ts.get('failed', 0)} / Errors: {ts.get('errors', 0)}")
        if ts.get("top_failures"):
            lines.append(f"- Top failures:")
            for f in ts["top_failures"]:
                lines.append(f"  - `{f}`")

    lines.append(f"")
    lines.append(f"## System Validation")

    vs = report["validation_summary"]
    if vs.get("status") == "NOT_RUN":
        lines.append(f"- Not run: {vs.get('reason', '')}")
    else:
        lines.append(f"- Status: {vs['status']}")
        lines.append(f"- Passed: {vs.get('passed', 0)} / Failed: {vs.get('failed', 0)} | Import errors: {vs.get('import_errors', 0)}")
        if vs.get("failures"):
            for f in vs["failures"]:
                lines.append(f"  - [{f['name']}] {f['detail']}")

    # Governance
    lines.append(f"")
    lines.append(f"## Governance Check")
    gs = report.get("governance_summary", {})
    if gs.get("status") == "NOT_RUN":
        lines.append(f"- Not run: {gs.get('reason', '')}")
    else:
        lines.append(f"- Judgment: {gs.get('status', '?')}")
        lines.append(f"- Violations: {gs.get('violations', 0)} | Warnings: {gs.get('warnings', 0)} | Live-path touches: {gs.get('live_path_touches', 0)}")

    lines.append(f"")
    lines.append(f"## Next Steps")
    for i, step in enumerate(report.get("next_steps", []), 1):
        lines.append(f"{i}. {step}")

    return "\n".join(lines)


def _append_grade_history(report: dict) -> None:
    """Append evaluation snapshot to grade history for time-series tracking."""
    history_path = Path("data/grade_history.json")
    history: list[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            history = []

    entry = {
        "timestamp": report.get("evaluation_timestamp"),
        "grade": report.get("final_grade"),
        "risk_score": report.get("risk_score", 0),
        "scope": report.get("scope", "unknown"),
        "tests_passed": report.get("test_summary", {}).get("passed", 0),
        "tests_failed": report.get("test_summary", {}).get("failed", 0),
        "validation_status": report.get("validation_summary", {}).get("status"),
        "governance_status": report.get("governance_summary", {}).get("status"),
        "pattern_total": report.get("pattern_summary", {}).get("total", 0),
    }
    history.append(entry)

    # Keep last 100 entries max
    if len(history) > 100:
        history = history[-100:]

    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="K-Dexter Result Evaluator")
    parser.add_argument("--format", default="text", choices=["text", "markdown", "json"])
    parser.add_argument("--test-input", default="data/test_results.json")
    parser.add_argument("--validation-input", default="data/validation_results.json")
    parser.add_argument("--governance-input", default="data/governance_check_result.json")
    args = parser.parse_args()

    test_data = load_json(args.test_input)
    validation_data = load_json(args.validation_input)
    governance_data = load_json(args.governance_input)
    failure_patterns_raw = load_json("data/failure_patterns.json")
    # failure_patterns.json may be a list or a dict with a "patterns" key
    if isinstance(failure_patterns_raw, list):
        failure_patterns = failure_patterns_raw
    elif isinstance(failure_patterns_raw, dict):
        failure_patterns = failure_patterns_raw.get("patterns", [])
    else:
        failure_patterns = None

    report = evaluate(test_data, validation_data, governance_data, failure_patterns)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.format == "markdown":
        print(format_markdown(report))
    else:
        md = format_markdown(report)
        print(md)

    # Write evaluation to data/
    out = Path("data/evaluation_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nEvaluation saved to: {out}")

    # Append to grade history (time-series)
    _append_grade_history(report)

    # Exit code: GREEN=0, YELLOW=0, RED=1
    grade = report.get("final_grade", report.get("overall_status", "RED"))
    code = {"GREEN": 0, "YELLOW": 0, "RED": 1}.get(grade, 1)
    sys.exit(code)


if __name__ == "__main__":
    main()
