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
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is cwd for data file resolution
_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)


def load_json(path: str) -> dict | None:
    """Load JSON file, return None if missing."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def evaluate(test_data: dict | None, validation_data: dict | None) -> dict:
    """Produce unified evaluation report."""
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
        validation_summary = {
            "status": validation_data.get("overall", "UNKNOWN"),
            "passed": validation_data.get("passed", 0),
            "failed": validation_data.get("failed", 0),
            "total": validation_data.get("total", 0),
            "failures": [
                {"name": c["name"], "detail": c["detail"]} for c in val_failures
            ],
        }
    else:
        validation_summary = {"status": "NOT_RUN", "reason": "data/validation_results.json not found"}

    # Overall assessment
    test_ok = test_summary.get("status") == "PASS"
    val_ok = validation_summary.get("status") == "PASS"

    if test_ok and val_ok:
        overall = "GREEN"
        action = "No action required. System healthy."
    elif test_ok and not val_ok:
        overall = "YELLOW"
        action = "Tests pass but system validation has issues. Review validation failures."
    elif not test_ok and val_ok:
        overall = "YELLOW"
        action = "System structure OK but tests failing. Run failure-analyzer → autofix-agent."
    else:
        overall = "RED"
        action = "Both tests and validation failing. Prioritize: validation fixes first, then test fixes."

    # Next steps
    next_steps = []
    if not test_ok:
        next_steps.append("Run: python scripts/run_tests.py --scope governance")
        next_steps.append("Analyze failures with failure-analyzer agent")
    if not val_ok:
        for f in validation_summary.get("failures", [])[:3]:
            next_steps.append(f"Fix validation: {f['name']} — {f['detail']}")
    if test_ok and val_ok:
        next_steps.append("System healthy. Continue monitoring via G-MON.")

    return {
        "evaluation_timestamp": now,
        "overall_status": overall,
        "recommended_action": action,
        "test_summary": test_summary,
        "validation_summary": validation_summary,
        "next_steps": next_steps[:5],
    }


def format_markdown(report: dict) -> str:
    """Format as human-readable markdown."""
    icon = {"GREEN": "OK", "YELLOW": "!!", "RED": "XX"}
    overall = report["overall_status"]

    lines = [
        f"# K-Dexter Evaluation Report",
        f"",
        f"**Time**: {report['evaluation_timestamp'][:19]}Z",
        f"**Overall**: [{icon.get(overall, '??')}] {overall}",
        f"**Action**: {report['recommended_action']}",
        f"",
        f"## Test Results",
    ]

    ts = report["test_summary"]
    if ts.get("status") == "NOT_RUN":
        lines.append(f"- Not run: {ts.get('reason', '')}")
    else:
        lines.append(f"- Status: {ts['status']}")
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
        lines.append(f"- Passed: {vs.get('passed', 0)} / Failed: {vs.get('failed', 0)}")
        if vs.get("failures"):
            for f in vs["failures"]:
                lines.append(f"  - [{f['name']}] {f['detail']}")

    lines.append(f"")
    lines.append(f"## Next Steps")
    for i, step in enumerate(report.get("next_steps", []), 1):
        lines.append(f"{i}. {step}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="K-Dexter Result Evaluator")
    parser.add_argument("--format", default="text", choices=["text", "markdown", "json"])
    parser.add_argument("--test-input", default="data/test_results.json")
    parser.add_argument("--validation-input", default="data/validation_results.json")
    args = parser.parse_args()

    test_data = load_json(args.test_input)
    validation_data = load_json(args.validation_input)

    report = evaluate(test_data, validation_data)

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

    # Exit code based on overall status
    code = {"GREEN": 0, "YELLOW": 0, "RED": 1}.get(report["overall_status"], 1)
    sys.exit(code)


if __name__ == "__main__":
    main()
