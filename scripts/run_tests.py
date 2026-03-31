#!/usr/bin/env python3
"""
K-Dexter AutoFix Loop — Step 1: Run Tests

테스트를 실행하고 결과를 구조화된 JSON으로 출력한다.
failure-analyzer의 입력 데이터를 생성한다.

Usage:
    python scripts/run_tests.py                    # 전체 테스트
    python scripts/run_tests.py --scope governance  # 거버넌스만
    python scripts/run_tests.py --scope dashboard   # 대시보드만
    python scripts/run_tests.py --scope monitor     # G-MON만
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is cwd for pytest path resolution
_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)

# ── Test scopes (K-Dexter 우선순위순) ────────────────────────────────────── #

SCOPES = {
    "governance": [
        "tests/test_agent_governance.py",
        "tests/test_governance_monitor.py",
    ],
    "constitution": [
        "tests/test_a01_constitution_audit.py",
    ],
    "dashboard": [
        "tests/test_dashboard.py",
        "tests/test_market_feed.py",
    ],
    "monitor": [
        "tests/test_governance_monitor.py",
        "tests/test_ops_checks.py",
    ],
    "agents": [
        "tests/test_agent_governance.py",
    ],
    "all": ["tests/"],
}

# ── Changed-files → scope mapping ────────────────────────────────────────── #
# Maps file path prefixes to test scopes for auto-detection.

_PATH_TO_SCOPE: list[tuple[str, str]] = [
    ("app/agents/governance_gate", "governance"),
    ("app/agents/", "agents"),
    ("app/core/governance_monitor", "monitor"),
    ("app/core/market_feed", "dashboard"),
    ("app/core/constitution_check", "monitor"),
    ("app/api/routes/dashboard", "dashboard"),
    ("app/templates/dashboard", "dashboard"),
    ("app/schemas/market_feed", "dashboard"),
    ("workers/tasks/governance_monitor", "monitor"),
    ("workers/celery_app", "monitor"),
    ("docs/aos-constitution/", "constitution"),
    ("scripts/verify_constitution", "constitution"),
    ("tests/test_agent_governance", "governance"),
    ("tests/test_governance_monitor", "governance"),
    ("tests/test_dashboard", "dashboard"),
    ("tests/test_market_feed", "dashboard"),
    ("tests/test_ops_checks", "monitor"),
]


def detect_scope_from_changed_files() -> str | None:
    """Detect test scope from git changed files. Returns highest-priority scope."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        # Also check staged
        result2 = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True, text=True, timeout=10,
        )
        changed.extend(f.strip() for f in result2.stdout.splitlines() if f.strip())

        if not changed:
            return None

        # Priority: governance > monitor > dashboard > constitution > agents
        scope_priority = ["governance", "monitor", "dashboard", "constitution", "agents"]
        detected: set[str] = set()

        for f in changed:
            f_norm = f.replace("\\", "/")
            for prefix, scope in _PATH_TO_SCOPE:
                if f_norm.startswith(prefix):
                    detected.add(scope)
                    break

        if not detected:
            return None

        for s in scope_priority:
            if s in detected:
                return s
        return None

    except Exception:
        return None


def run_tests(scope: str, verbose: bool = False) -> dict:
    """Run pytest for given scope and return structured result."""
    paths = SCOPES.get(scope, SCOPES["all"])

    # Filter to existing paths only
    existing = [p for p in paths if Path(p).exists()]
    if not existing:
        return {
            "scope": scope,
            "status": "SKIP",
            "reason": f"No test files found for scope '{scope}'",
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "total": 0,
        }

    cmd = [
        sys.executable, "-m", "pytest",
        *existing,
        "--tb=short",
        "-q",
        "--no-header",
    ]
    if verbose:
        cmd.append("-v")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    # Parse pytest output
    output = result.stdout + result.stderr
    passed = 0
    failed = 0
    errors = 0

    for line in output.splitlines():
        line = line.strip()
        if "passed" in line or "failed" in line or "error" in line:
            # Parse "X passed, Y failed, Z error" line
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if "passed" in part:
                    try:
                        passed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                if "failed" in part:
                    try:
                        failed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
                if "error" in part:
                    try:
                        errors = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass

    total = passed + failed + errors

    # Collect failure details
    failures = []
    current_failure = None
    for line in output.splitlines():
        if line.startswith("FAILED "):
            test_id = line.replace("FAILED ", "").strip()
            current_failure = {"test_id": test_id, "detail": ""}
            failures.append(current_failure)
        elif current_failure and line.startswith("E "):
            current_failure["detail"] += line + "\n"

    status = "PASS" if result.returncode == 0 else "FAIL"

    return {
        "scope": scope,
        "status": status,
        "returncode": result.returncode,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": total,
        "failures": failures[:10],  # top 10
        "stdout_tail": output[-500:] if len(output) > 500 else output,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="K-Dexter Test Runner")
    parser.add_argument("--scope", default=None, choices=list(SCOPES.keys()),
                        help="Test scope to run (default: auto-detect from changed files)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON file path")
    args = parser.parse_args()

    # Auto-detect scope from changed files if not specified
    scope = args.scope
    if scope is None:
        scope = detect_scope_from_changed_files()
        if scope:
            print(f"[AUTO] Detected scope from changed files: {scope}")
        else:
            scope = "all"
            print(f"[AUTO] No scope detected, running all tests")

    result = run_tests(scope, args.verbose)

    # Always print summary to stdout
    icon = {"PASS": "[OK]", "FAIL": "[XX]", "SKIP": "[--]"}[result["status"]]
    print(f"{icon} {result['scope']}: {result['passed']} passed, "
          f"{result['failed']} failed, {result['errors']} errors "
          f"(total {result['total']})")

    if result["failures"]:
        print("\nFailures:")
        for f in result["failures"]:
            print(f"  - {f['test_id']}")

    # Write JSON output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nResult written to: {args.output}")
    else:
        # Default output location
        out_path = Path("data/test_results.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(result["returncode"] if result["status"] != "SKIP" else 0)


if __name__ == "__main__":
    main()
