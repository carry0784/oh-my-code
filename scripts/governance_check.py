#!/usr/bin/env python3
"""
K-Dexter Governance Checker -Machine-Enforceable Rule Engine

governance-checker.md 규칙(GC-01~08)을 코드로 시행한다.
git diff 기반으로 변경 파일을 분석하고 PASS/WARN/BLOCK 판정.

Usage:
    python scripts/governance_check.py                    # staged changes
    python scripts/governance_check.py --diff HEAD~1      # last commit
    python scripts/governance_check.py --files a.py b.py  # specific files
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ── Protected Paths & Rules ─────────────────────────────────────────────── #


@dataclass
class Rule:
    code: str
    description: str
    severity: str  # BLOCK or WARN
    protected_patterns: list[str]
    forbidden_content: list[str] = field(default_factory=list)


RULES: list[Rule] = [
    Rule(
        code="GC-01",
        description="GovernanceGate.pre_check() 로직 우회 금지",
        severity="BLOCK",
        protected_patterns=["app/agents/governance_gate.py"],
        forbidden_content=["pre_check.*pass", "pre_check.*skip", "pre_check.*bypass"],
    ),
    Rule(
        code="GC-02",
        description="ForbiddenLedger 등록 행위 삭제 금지",
        severity="BLOCK",
        protected_patterns=["src/kdexter/ledger/forbidden_ledger.py"],
        forbidden_content=[],  # deletion check handled separately
    ),
    Rule(
        code="GC-03",
        description="EvidenceStore에 delete/update 메서드 추가 금지",
        severity="BLOCK",
        protected_patterns=["src/kdexter/audit/evidence_store.py"],
        forbidden_content=["def delete", "def update", "def remove", "def clear"],
    ),
    Rule(
        code="GC-04",
        description="SecurityStateContext 초기값 NORMAL 외 변경 금지",
        severity="BLOCK",
        protected_patterns=["src/kdexter/state_machine/security_state.py"],
        forbidden_content=[],
    ),
    Rule(
        code="GC-05",
        description="Dashboard read-only 영역에 write path 추가 금지",
        severity="BLOCK",
        protected_patterns=[
            "app/core/market_feed_service.py",
            "app/core/governance_summary_service.py",
            "app/core/constitution_check_runner.py",
            "app/core/governance_monitor.py",
        ],
        forbidden_content=["db.add", "db.delete", "session.commit", "submit_order", "create_order"],
    ),
    Rule(
        code="GC-06",
        description="헌법 문서 삭제 금지",
        severity="BLOCK",
        protected_patterns=["docs/aos-constitution/"],
        forbidden_content=[],
    ),
    Rule(
        code="GC-07",
        description="verify_constitution.py 기대값 임의 조정 금지 (실제 변경 없이)",
        severity="WARN",
        protected_patterns=["scripts/verify_constitution.py"],
        forbidden_content=[],
    ),
    Rule(
        code="GC-08",
        description="CostController/FailurePatternMemory DI 제거 금지",
        severity="BLOCK",
        protected_patterns=["app/main.py"],
        forbidden_content=["cost_controller=None", "pattern_memory=None"],
    ),
]

# Additional write-path protection for live execution
LIVE_EXECUTION_PATHS = [
    "app/services/order_service.py",
    "workers/tasks/order_tasks.py",
    "exchanges/binance.py",
    "exchanges/factory.py",
    "src/kdexter/strategy/execution_cell.py",
    "src/kdexter/tcl/commands.py",
]


# ── Risk Scoring ─────────────────────────────────────────────────────────── #

RISK_SCORES = {
    "BLOCK": 3,
    "WARN": 2,
    "INFO": 1,
}


@dataclass
class Violation:
    rule_code: str
    file: str
    severity: str
    description: str
    line: str = ""
    risk_score: int = 0


@dataclass
class CheckResult:
    judgment: str  # PASS / WARN / BLOCK
    total_risk_score: int
    violations: list[Violation]
    warnings: list[Violation]
    files_checked: list[str]
    live_path_touches: list[str]
    timestamp: str = ""


# ── Core Logic ───────────────────────────────────────────────────────────── #


def get_changed_files(
    diff_ref: str | None = None, explicit_files: list[str] | None = None
) -> list[str]:
    """Get list of changed files from git or explicit list."""
    if explicit_files:
        return explicit_files

    cmd = ["git", "diff", "--name-only"]
    if diff_ref:
        cmd.append(diff_ref)
    else:
        cmd.append("--cached")  # staged changes

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        return []


def get_diff_content(diff_ref: str | None = None) -> str:
    """Get unified diff content."""
    cmd = ["git", "diff"]
    if diff_ref:
        cmd.append(diff_ref)
    else:
        cmd.append("--cached")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout
    except Exception:
        return ""


def check_rules(changed_files: list[str], diff_content: str) -> CheckResult:
    """Apply all GC rules against changed files and diff content."""
    violations: list[Violation] = []
    warnings: list[Violation] = []
    live_touches: list[str] = []

    for f in changed_files:
        f_norm = f.replace("\\", "/")

        # Check live execution paths
        for lp in LIVE_EXECUTION_PATHS:
            if f_norm == lp or f_norm.startswith(lp):
                live_touches.append(f_norm)

        # Check each rule
        for rule in RULES:
            matched = False
            for pattern in rule.protected_patterns:
                if f_norm == pattern or f_norm.startswith(pattern):
                    matched = True
                    break

            if not matched:
                continue

            # File touches a protected path
            v = Violation(
                rule_code=rule.code,
                file=f_norm,
                severity=rule.severity,
                description=f"{rule.description} -file modified: {f_norm}",
                risk_score=RISK_SCORES.get(rule.severity, 1),
            )

            # Check forbidden content in diff
            if rule.forbidden_content:
                for forbidden in rule.forbidden_content:
                    # Search in added lines of the diff for this file
                    in_file_diff = False
                    for line in diff_content.splitlines():
                        if line.startswith("+++ b/" + f_norm):
                            in_file_diff = True
                        elif line.startswith("+++ b/") and in_file_diff:
                            in_file_diff = False
                        elif in_file_diff and line.startswith("+") and not line.startswith("+++"):
                            if re.search(forbidden, line, re.IGNORECASE):
                                v.line = line.strip()
                                v.description = f"{rule.description} -forbidden content: '{forbidden}' in {f_norm}"
                                break

            if rule.severity == "BLOCK":
                violations.append(v)
            else:
                warnings.append(v)

    # Check for constitution file deletions (GC-06)
    for f in changed_files:
        if f.startswith("docs/aos-constitution/"):
            # Check if file was deleted
            if "deleted file" in diff_content and f in diff_content:
                violations.append(
                    Violation(
                        rule_code="GC-06",
                        file=f,
                        severity="BLOCK",
                        description=f"헌법 문서 삭제 감지: {f}",
                        risk_score=3,
                    )
                )

    # Live execution path warning
    if live_touches:
        warnings.append(
            Violation(
                rule_code="LIVE-EXEC",
                file=", ".join(live_touches),
                severity="WARN",
                description=f"실거래 경로 수정 감지: {len(live_touches)} files -추가 검증 필수",
                risk_score=2,
            )
        )

    # Determine judgment
    total_risk = sum(v.risk_score for v in violations) + sum(w.risk_score for w in warnings)

    if violations:
        judgment = "BLOCK"
    elif warnings:
        judgment = "WARN"
    else:
        judgment = "PASS"

    return CheckResult(
        judgment=judgment,
        total_risk_score=total_risk,
        violations=violations,
        warnings=warnings,
        files_checked=changed_files,
        live_path_touches=live_touches,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def result_to_dict(result: CheckResult) -> dict:
    return {
        "checker": "governance-checker",
        "timestamp": result.timestamp,
        "judgment": result.judgment,
        "total_risk_score": result.total_risk_score,
        "files_checked": result.files_checked,
        "live_path_touches": result.live_path_touches,
        "violations": [
            {
                "rule_code": v.rule_code,
                "file": v.file,
                "severity": v.severity,
                "description": v.description,
                "line": v.line,
                "risk_score": v.risk_score,
            }
            for v in result.violations
        ],
        "warnings": [
            {
                "rule_code": w.rule_code,
                "file": w.file,
                "severity": w.severity,
                "description": w.description,
                "risk_score": w.risk_score,
            }
            for w in result.warnings
        ],
    }


# ── Main ─────────────────────────────────────────────────────────────────── #


def main():
    parser = argparse.ArgumentParser(description="K-Dexter Governance Checker")
    parser.add_argument("--diff", default=None, help="Git diff reference (e.g., HEAD~1)")
    parser.add_argument("--files", nargs="*", help="Explicit file list")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    changed = get_changed_files(args.diff, args.files)
    if not changed:
        print("[OK] PASS -No changed files detected")
        sys.exit(0)

    diff_content = get_diff_content(args.diff)
    result = check_rules(changed, diff_content)
    report = result_to_dict(result)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        icon = {"PASS": "[OK]", "WARN": "[!!]", "BLOCK": "[XX]"}[result.judgment]
        print(f"{icon} Governance Check: {result.judgment} (risk score: {result.total_risk_score})")
        print(f"    Files checked: {len(result.files_checked)}")

        if result.violations:
            print(f"\n  VIOLATIONS ({len(result.violations)}):")
            for v in result.violations:
                print(f"    [{v.rule_code}] {v.severity} -{v.description}")

        if result.warnings:
            print(f"\n  WARNINGS ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"    [{w.rule_code}] {w.severity} -{w.description}")

        if not result.violations and not result.warnings:
            print("    No governance issues found.")

    # Save result
    out = Path("data/governance_check_result.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    sys.exit(1 if result.judgment == "BLOCK" else 0)


if __name__ == "__main__":
    main()
