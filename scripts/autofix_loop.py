#!/usr/bin/env python3
"""
K-Dexter AutoFix Loop -- Self-Healing Execution Engine

analyze -> fix -> test -> evaluate -> repeat (until GREEN or max iterations)

Rules:
  - Max 3 iterations (prevent infinite loop)
  - Max 3 files per fix (minimal invasive)
  - governance-checker BLOCK -> immediate abort (fail-closed)
  - Each iteration records to FailurePatternMemory via data/failure_patterns.json
  - Exit codes: 0 = GREEN, 1 = RED (unresolved), 2 = BLOCK (governance)

Usage:
    python scripts/autofix_loop.py                       # full loop
    python scripts/autofix_loop.py --scope governance    # specific scope
    python scripts/autofix_loop.py --max-iter 5          # more iterations
    python scripts/autofix_loop.py --dry-run             # analyze only, no fix
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)

# ── Constants ─────────────────────────────────────────────────────────────── #

MAX_ITERATIONS = 3
MAX_FILES_PER_FIX = 3
FAILURE_PATTERNS_FILE = Path("data/failure_patterns.json")

# Failure type classification (from failure-analyzer.md)
_FAILURE_TYPES = {
    "import": "F-IMPORT",
    "attribute": "F-IMPORT",
    "module": "F-IMPORT",
    "assert": "F-TEST",
    "test": "F-TEST",
    "migration": "F-MIGRATION",
    "alembic": "F-MIGRATION",
    "endpoint": "F-ENDPOINT",
    "route": "F-ENDPOINT",
    "governance": "F-GOVERNANCE",
    "constitution": "F-GOVERNANCE",
    "config": "F-CONFIG",
    "setting": "F-CONFIG",
    "worker": "F-WORKER",
    "celery": "F-WORKER",
    "lint": "F-LINT",
    "syntax": "F-LINT",
}

# ── AutoFix Policy Engine ─────────────────────────────────────────────── #
# Decides: ALLOW / DENY / MANUAL for each failure based on type + recurrence

AUTOFIX_POLICY = {
    # failure_type: {recurrence: decision}
    "F-IMPORT":     {"FIRST": "ALLOW", "REPEAT": "ALLOW", "PATTERN": "MANUAL"},
    "F-TEST":       {"FIRST": "ALLOW", "REPEAT": "ALLOW", "PATTERN": "MANUAL"},
    "F-LINT":       {"FIRST": "ALLOW", "REPEAT": "ALLOW", "PATTERN": "ALLOW"},
    "F-CONFIG":     {"FIRST": "ALLOW", "REPEAT": "MANUAL", "PATTERN": "DENY"},
    "F-MIGRATION":  {"FIRST": "MANUAL", "REPEAT": "DENY", "PATTERN": "DENY"},
    "F-ENDPOINT":   {"FIRST": "ALLOW", "REPEAT": "MANUAL", "PATTERN": "DENY"},
    "F-GOVERNANCE": {"FIRST": "DENY", "REPEAT": "DENY", "PATTERN": "DENY"},
    "F-WORKER":     {"FIRST": "ALLOW", "REPEAT": "MANUAL", "PATTERN": "DENY"},
}


# ── Pattern Escalation Rules ──────────────────────────────────────────── #
# When PATTERN count exceeds threshold, escalate actions

PATTERN_ESCALATION_THRESHOLD = 3   # 3+ PATTERN records for same failure_type
PATTERN_BAN_THRESHOLD = 5          # 5+ PATTERN records → permanent DENY


def _check_pattern_escalation(patterns: list[dict]) -> list[dict]:
    """Check if any failure_type needs escalation based on PATTERN count.

    Returns list of escalation alerts.
    """
    from collections import Counter

    pattern_entries = [p for p in patterns if p.get("recurrence") == "PATTERN"]
    type_counts = Counter(p.get("failure_type", "unknown") for p in pattern_entries)

    alerts = []
    for ftype, count in type_counts.items():
        if count >= PATTERN_BAN_THRESHOLD:
            alerts.append({
                "failure_type": ftype,
                "pattern_count": count,
                "escalation": "BAN",
                "message": f"{ftype} has {count} PATTERN records - autofix permanently banned",
            })
        elif count >= PATTERN_ESCALATION_THRESHOLD:
            alerts.append({
                "failure_type": ftype,
                "pattern_count": count,
                "escalation": "WARN",
                "message": f"{ftype} has {count} PATTERN records - escalating to G-MON alert",
            })
    return alerts


def _get_autofix_decision(failure_type: str, recurrence: str) -> tuple[str, str]:
    """Get autofix policy decision and reason code.

    Returns: (decision, reason_code) where decision is ALLOW/DENY/MANUAL
    """
    policy = AUTOFIX_POLICY.get(failure_type, {"FIRST": "MANUAL", "REPEAT": "DENY", "PATTERN": "DENY"})
    decision = policy.get(recurrence, "DENY")

    # Generate reason code
    ft_short = failure_type.replace("F-", "").upper()
    rec_short = recurrence[:3].upper()
    reason_code = f"{ft_short}_{rec_short}_{decision}"

    return decision, reason_code


# ── Failure Pattern Memory (file-based) ──────────────────────────────────── #

def _load_patterns() -> list[dict]:
    """Load failure patterns from JSON file."""
    if FAILURE_PATTERNS_FILE.exists():
        try:
            return json.loads(FAILURE_PATTERNS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_patterns(patterns: list[dict]) -> None:
    """Save failure patterns to JSON file."""
    FAILURE_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    FAILURE_PATTERNS_FILE.write_text(
        json.dumps(patterns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _classify_failure_type(failure_text: str) -> str:
    """Classify a failure into F-* type based on keywords."""
    lower = failure_text.lower()
    for keyword, ftype in _FAILURE_TYPES.items():
        if keyword in lower:
            return ftype
    return "F-TEST"  # default


def _record_failure_pattern(test_id: str, detail: str, iteration: int,
                            scope: str) -> dict:
    """Create a failure pattern record."""
    failure_type = _classify_failure_type(test_id + " " + detail)

    # Extract affected path from test_id
    # e.g., "tests/test_agent_governance.py::TestClass::test_method"
    affected_path = test_id.split("::")[0] if "::" in test_id else test_id

    record = {
        "failure_type": failure_type,
        "test_id": test_id,
        "root_cause": detail[:200] if detail else "unknown",
        "affected_paths": [affected_path],
        "fix_pattern": None,       # filled after successful fix
        "fix_attempted": False,    # whether autofix was attempted
        "fix_succeeded": None,     # True/False after attempt
        "fix_strategy": None,      # which strategy was used
        "success_rate": None,      # calculated from historical data
        "regression_risk": "unknown",
        "verified_by": None,
        "iteration": iteration,
        "scope": scope,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    return record


def _count_recurrence(patterns: list[dict], test_id: str) -> str:
    """Classify recurrence: FIRST / REPEAT / PATTERN."""
    matching = [p for p in patterns if p.get("test_id") == test_id]
    count = len(matching)
    if count == 0:
        return "FIRST"
    if count >= 3:
        return "PATTERN"
    return "REPEAT"


def _calculate_success_rate(patterns: list[dict], failure_type: str) -> float:
    """Calculate historical fix success rate for a failure type."""
    matching = [p for p in patterns
                if p.get("failure_type") == failure_type and p.get("fix_attempted")]
    if not matching:
        return 0.0
    succeeded = sum(1 for p in matching if p.get("fix_succeeded"))
    return succeeded / len(matching)


def _suggest_fix_strategy(patterns: list[dict], failure_type: str,
                          recurrence: str) -> str:
    """Suggest fix strategy based on historical success."""
    # Get previously successful strategies for this type
    successful = [p.get("fix_strategy") for p in patterns
                  if p.get("failure_type") == failure_type
                  and p.get("fix_succeeded")
                  and p.get("fix_strategy")]

    if successful:
        # Use most common successful strategy
        from collections import Counter
        most_common = Counter(successful).most_common(1)[0][0]
        return most_common

    # Default strategies by type
    defaults = {
        "F-IMPORT": "check_sys_path_and_reinstall",
        "F-TEST": "update_assertion_or_fix_logic",
        "F-LINT": "auto_format",
        "F-CONFIG": "restore_default_config",
        "F-MIGRATION": "manual_review_required",
        "F-ENDPOINT": "check_route_registration",
        "F-GOVERNANCE": "manual_review_required",
        "F-WORKER": "check_task_registration",
    }
    return defaults.get(failure_type, "generic_investigation")


def _update_pattern_fix_result(patterns: list[dict], test_id: str,
                                iteration: int, succeeded: bool,
                                strategy: str) -> None:
    """Update the most recent pattern entry for a test_id with fix results."""
    for p in reversed(patterns):
        if p.get("test_id") == test_id and p.get("iteration") == iteration:
            p["fix_attempted"] = True
            p["fix_succeeded"] = succeeded
            p["fix_strategy"] = strategy
            break


# ── Step Runners ──────────────────────────────────────────────────────────── #

def _run_step(cmd: list[str], label: str, timeout: int = 300) -> tuple[int, str]:
    """Run a subprocess step, return (exit_code, output)."""
    print(f"\n{'='*60}")
    print(f"  [{label}]")
    print(f"{'='*60}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        output = result.stdout + result.stderr
        print(output[-1000:] if len(output) > 1000 else output)
        return result.returncode, output
    except subprocess.TimeoutExpired:
        msg = f"TIMEOUT after {timeout}s"
        print(f"  [!!] {msg}")
        return -1, msg
    except Exception as e:
        msg = f"ERROR: {e}"
        print(f"  [XX] {msg}")
        return -1, msg


def run_governance_check(scope_files: list[str] | None = None) -> tuple[int, dict | None]:
    """Run governance checker. Returns (exit_code, parsed_data)."""
    cmd = [sys.executable, "scripts/governance_check.py", "--json"]
    if scope_files:
        cmd.extend(["--files"] + scope_files)

    code, output = _run_step(cmd, "Governance Check", timeout=30)

    # Parse JSON from output
    try:
        data = json.loads(output.strip())
        return code, data
    except Exception:
        return code, None


def run_tests(scope: str) -> tuple[int, dict | None]:
    """Run tests for scope. Returns (exit_code, parsed_data)."""
    cmd = [sys.executable, "scripts/run_tests.py", "--scope", scope]
    code, output = _run_step(cmd, f"Tests ({scope})", timeout=300)

    # Load from file
    try:
        data = json.loads(Path("data/test_results.json").read_text(encoding="utf-8"))
        return code, data
    except Exception:
        return code, None


def run_validation() -> tuple[int, dict | None]:
    """Run system validation. Returns (exit_code, parsed_data)."""
    cmd = [sys.executable, "scripts/validate_system.py"]
    code, output = _run_step(cmd, "System Validation", timeout=60)

    try:
        data = json.loads(Path("data/validation_results.json").read_text(encoding="utf-8"))
        return code, data
    except Exception:
        return code, None


def run_evaluation() -> tuple[int, dict | None]:
    """Run evaluation. Returns (exit_code, parsed_data)."""
    cmd = [sys.executable, "scripts/evaluate_results.py", "--format", "markdown"]
    code, output = _run_step(cmd, "Evaluation", timeout=30)

    try:
        data = json.loads(Path("data/evaluation_report.json").read_text(encoding="utf-8"))
        return code, data
    except Exception:
        return code, None


# ── Failure Analyzer ──────────────────────────────────────────────────────── #

def analyze_failures(test_data: dict, patterns: list[dict],
                     iteration: int, scope: str) -> list[dict]:
    """Analyze test failures, classify, record patterns. Returns analysis."""
    failures = test_data.get("failures", [])
    if not failures:
        return []

    analysis = []
    for f in failures[:MAX_FILES_PER_FIX]:  # limit to 3
        test_id = f.get("test_id", "unknown")
        detail = f.get("detail", "")
        recurrence = _count_recurrence(patterns, test_id)
        failure_type = _classify_failure_type(test_id + " " + detail)

        record = _record_failure_pattern(test_id, detail, iteration, scope)
        record["recurrence"] = recurrence
        patterns.append(record)

        # Priority based on type + recurrence
        if failure_type == "F-GOVERNANCE":
            priority = "CRITICAL"
        elif recurrence == "PATTERN":
            priority = "HIGH"
        elif failure_type in ("F-IMPORT", "F-CONFIG"):
            priority = "HIGH"
        else:
            priority = "MEDIUM"

        autofix_decision, reason_code = _get_autofix_decision(failure_type, recurrence)

        # BAN escalation override: if this failure_type has >= PATTERN_BAN_THRESHOLD
        # PATTERN records in the existing patterns list, force DENY regardless of policy
        ban_types = {
            a["failure_type"]
            for a in _check_pattern_escalation(patterns)
            if a["escalation"] == "BAN"
        }
        if failure_type in ban_types:
            autofix_decision = "DENY"
            reason_code = reason_code.rsplit("_", 1)[0] + "_DENY"

        success_rate = _calculate_success_rate(patterns, failure_type)
        suggested_strategy = _suggest_fix_strategy(patterns, failure_type, recurrence)

        analysis.append({
            "test_id": test_id,
            "failure_type": failure_type,
            "recurrence": recurrence,
            "priority": priority,
            "detail": detail[:300],
            "affected_path": test_id.split("::")[0] if "::" in test_id else test_id,
            "autofix_decision": autofix_decision,
            "reason_code": reason_code,
            "success_rate": round(success_rate, 2),
            "suggested_strategy": suggested_strategy,
        })

        icon = {"CRITICAL": "[!!]", "HIGH": "[XX]", "MEDIUM": "[--]", "LOW": "[  ]"}
        print(f"  {icon.get(priority, '[  ]')} {failure_type} {recurrence}: {test_id}")

    return analysis


# ── Main Loop ─────────────────────────────────────────────────────────────── #

def autofix_loop(scope: str, max_iter: int = MAX_ITERATIONS,
                 dry_run: bool = False) -> dict:
    """
    Execute the self-healing loop.

    Returns:
        Loop result dict with final_grade, iterations, patterns.
    """
    print(f"\n{'#'*60}")
    print(f"  K-Dexter AutoFix Loop")
    print(f"  Scope: {scope} | Max iterations: {max_iter} | Dry run: {dry_run}")
    print(f"{'#'*60}")

    patterns = _load_patterns()
    loop_start = datetime.now(timezone.utc)
    iterations: list[dict] = []
    final_grade = "RED"
    exit_reason = "max_iterations_reached"

    for i in range(1, max_iter + 1):
        print(f"\n{'*'*60}")
        print(f"  ITERATION {i}/{max_iter}")
        print(f"{'*'*60}")

        iter_start = datetime.now(timezone.utc)
        iter_result: dict = {"iteration": i, "started_at": iter_start.isoformat()}

        # ── Step 1: Run tests ──────────────────────────────────────── #
        test_code, test_data = run_tests(scope)
        iter_result["test_exit_code"] = test_code

        if test_data and test_data.get("status") == "PASS":
            # Tests pass -- run validation
            val_code, val_data = run_validation()
            iter_result["validation_exit_code"] = val_code

            # Run evaluation
            eval_code, eval_data = run_evaluation()
            iter_result["eval_exit_code"] = eval_code

            grade = eval_data.get("final_grade", "UNKNOWN") if eval_data else "UNKNOWN"
            iter_result["grade"] = grade

            if grade == "GREEN":
                final_grade = "GREEN"
                exit_reason = "all_pass"
                iterations.append(iter_result)
                print(f"\n  [OK] GREEN -- loop complete at iteration {i}")
                break
            elif grade == "YELLOW":
                final_grade = "YELLOW"
                # Continue to try to fix remaining issues
                print(f"\n  [!!] YELLOW -- attempting further fixes")
        else:
            iter_result["grade"] = "RED"

        # ── Step 2: Analyze failures ───────────────────────────────── #
        if test_data and test_data.get("failures"):
            print(f"\n  Analyzing {len(test_data['failures'])} failure(s)...")
            analysis = analyze_failures(test_data, patterns, i, scope)
            iter_result["analysis"] = analysis
            iter_result["failure_count"] = len(analysis)

            # Check for PATTERN recurrence (escalation)
            pattern_count = sum(1 for a in analysis if a["recurrence"] == "PATTERN")
            if pattern_count > 0:
                print(f"\n  [!!] {pattern_count} PATTERN recurrence(s) detected")
                print(f"       Consider escalation to FailureRouter")
                iter_result["pattern_escalation"] = True
        else:
            iter_result["analysis"] = []
            iter_result["failure_count"] = 0

        # ── Step 3: Governance pre-check ───────────────────────────── #
        gov_code, gov_data = run_governance_check()
        iter_result["governance_exit_code"] = gov_code

        if gov_data and gov_data.get("judgment") == "BLOCK":
            print(f"\n  [XX] GOVERNANCE BLOCK -- aborting loop")
            final_grade = "RED"
            exit_reason = "governance_block"
            iter_result["grade"] = "BLOCKED"
            iterations.append(iter_result)
            break

        # ── Step 4: AutoFix (if not dry-run) ───────────────────────── #
        if dry_run:
            print(f"\n  [--] DRY RUN -- skipping autofix")
            iter_result["autofix"] = "skipped (dry-run)"
        else:
            # In a full implementation, this would invoke the autofix-agent
            # via Claude Code. For now, we record what WOULD be fixed.
            if iter_result.get("analysis"):
                current_analysis = iter_result["analysis"]

                allow_items  = [a for a in current_analysis if a.get("autofix_decision") == "ALLOW"]
                manual_items = [a for a in current_analysis if a.get("autofix_decision") == "MANUAL"]
                deny_items   = [a for a in current_analysis if a.get("autofix_decision") == "DENY"]

                iter_result["autofix_allowed"] = len(allow_items)
                iter_result["autofix_manual"]  = len(manual_items)
                iter_result["autofix_denied"]  = len(deny_items)

                # Safety check: all failures are DENY -> abort
                if len(deny_items) == len(current_analysis):
                    print(f"\n  [XX] ALL failures are DENY -- autofix blocked entirely")
                    final_grade = "RED"
                    exit_reason = "all_failures_denied"
                    iter_result["autofix"] = "all_denied"
                    iterations.append(iter_result)
                    break

                if allow_items:
                    print(f"\n  [**] AutoFix ALLOW ({len(allow_items)} item(s)):")
                    for a in allow_items[:MAX_FILES_PER_FIX]:
                        print(f"       {a['priority']} {a['failure_type']}: {a['affected_path']}")
                    for a in allow_items[:MAX_FILES_PER_FIX]:
                        if a.get("suggested_strategy"):
                            print(f"         Strategy: {a['suggested_strategy']} (success rate: {a.get('success_rate', 0):.0%})")

                if manual_items:
                    print(f"\n  [>>] Needs human review -- MANUAL ({len(manual_items)} item(s)):")
                    for a in manual_items:
                        print(f"       {a['priority']} {a['failure_type']}: {a['affected_path']}")

                if deny_items:
                    print(f"\n  [XX] Autofix blocked -- DENY ({len(deny_items)} item(s)):")
                    for a in deny_items:
                        print(f"       {a['priority']} {a['failure_type']}: {a['affected_path']}")

                iter_result["autofix"] = "candidates_identified"
            else:
                iter_result["autofix_allowed"] = 0
                iter_result["autofix_manual"]  = 0
                iter_result["autofix_denied"]  = 0
                iter_result["autofix"] = "no_failures_to_fix"

        iterations.append(iter_result)

    # ── Pattern Escalation Check ──────────────────────────────────────── #
    escalations = _check_pattern_escalation(patterns)
    if escalations:
        print(f"\n  [!!] Pattern Escalation Alerts:")
        for alert in escalations:
            print(f"       {alert['escalation']}: {alert['message']}")

    # ── Finalize ──────────────────────────────────────────────────────── #
    loop_end = datetime.now(timezone.utc)

    # Save updated patterns
    _save_patterns(patterns)

    loop_report = {
        "loop_type": "autofix",
        "started_at": loop_start.isoformat(),
        "ended_at": loop_end.isoformat(),
        "duration_seconds": (loop_end - loop_start).total_seconds(),
        "scope": scope,
        "max_iterations": max_iter,
        "iterations_run": len(iterations),
        "final_grade": final_grade,
        "exit_reason": exit_reason,
        "dry_run": dry_run,
        "pattern_count": len(patterns),
        "pattern_escalations": escalations,
        "iterations": iterations,
    }

    # Save loop report
    out = Path("data/autofix_loop_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(loop_report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    print(f"\n{'#'*60}")
    print(f"  AutoFix Loop Complete")
    print(f"  Grade: {final_grade} | Reason: {exit_reason}")
    print(f"  Iterations: {len(iterations)}/{max_iter}")
    print(f"  Duration: {loop_report['duration_seconds']:.1f}s")
    print(f"  Patterns recorded: {len(patterns)}")
    print(f"  Report: {out}")
    print(f"{'#'*60}")

    return loop_report


# ── CLI ───────────────────────────────────────────────────────────────────── #

def main():
    parser = argparse.ArgumentParser(description="K-Dexter AutoFix Loop")
    parser.add_argument("--scope", default="governance",
                        choices=["governance", "constitution", "dashboard",
                                 "monitor", "agents", "all"])
    parser.add_argument("--max-iter", type=int, default=MAX_ITERATIONS,
                        help=f"Max iterations (default: {MAX_ITERATIONS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze only, no autofix")
    parser.add_argument("--json", action="store_true",
                        help="Print JSON report to stdout")
    args = parser.parse_args()

    report = autofix_loop(args.scope, args.max_iter, args.dry_run)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    # Exit code
    code = {"GREEN": 0, "YELLOW": 0, "RED": 1}.get(report["final_grade"], 1)
    if report["exit_reason"] == "governance_block":
        code = 2
    sys.exit(code)


if __name__ == "__main__":
    main()
