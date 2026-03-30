#!/usr/bin/env python3
"""
K-Dexter AutoFix Loop — Step 2: Validate System Integrity

시스템 구조, import 정합성, 핵심 파일 존재, DB migration,
FastAPI 진입점, 워커, 대시보드, 거버넌스 컴포넌트를 점검한다.

Usage:
    python scripts/validate_system.py
    python scripts/validate_system.py --json
"""

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root and src/ are on sys.path for imports
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
os.chdir(_REPO_ROOT)


# ── Validation checks ────────────────────────────────────────────────────── #

def _check(name: str, fn) -> dict:
    """Run a single check, return structured result."""
    try:
        ok, detail = fn()
        return {
            "name": name,
            "status": "OK" if ok else "FAIL",
            "detail": detail,
        }
    except Exception as e:
        return {
            "name": name,
            "status": "ERROR",
            "detail": str(e),
        }


def check_core_imports() -> tuple[bool, str]:
    """Verify critical Python imports work."""
    modules = [
        "app.main",
        "app.core.config",
        "app.core.logging",
        "app.core.governance_monitor",
        "app.agents.governance_gate",
        "app.agents.orchestrator",
        "app.agents.base",
    ]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e}")

    if failed:
        return False, f"Import failures: {'; '.join(failed[:3])}"
    return True, f"{len(modules)} core modules imported OK"


def check_kdexter_imports() -> tuple[bool, str]:
    """Verify K-Dexter engine imports."""
    modules = [
        "kdexter.audit.evidence_store",
        "kdexter.engines.cost_controller",
        "kdexter.engines.failure_router",
        "kdexter.engines.loop_monitor",
        "kdexter.state_machine.security_state",
        "kdexter.state_machine.work_state",
        "kdexter.loops.main_loop",
        "kdexter.loops.evolution_loop",
        "kdexter.loops.self_improvement_loop",
    ]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e}")

    if failed:
        return False, f"Import failures: {'; '.join(failed[:3])}"
    return True, f"{len(modules)} K-Dexter modules imported OK"


def check_critical_files() -> tuple[bool, str]:
    """Verify critical files exist."""
    files = [
        "app/main.py",
        "app/agents/governance_gate.py",
        "app/core/governance_monitor.py",
        "app/core/config.py",
        "workers/celery_app.py",
        "scripts/verify_constitution.py",
        "src/kdexter/audit/evidence_store.py",
        "src/kdexter/engines/cost_controller.py",
        "src/kdexter/loops/main_loop.py",
    ]
    missing = [f for f in files if not Path(f).exists()]
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    return True, f"{len(files)} critical files present"


def check_alembic() -> tuple[bool, str]:
    """Check alembic migration setup exists."""
    if not Path("alembic.ini").exists():
        return False, "alembic.ini not found"
    if not Path("alembic/versions").exists():
        return False, "alembic/versions/ not found"
    versions = list(Path("alembic/versions").glob("*.py"))
    return True, f"Alembic OK, {len(versions)} migration(s)"


def check_fastapi_entry() -> tuple[bool, str]:
    """Check FastAPI app is importable and has expected attributes."""
    try:
        from app.main import app
        routes = [r.path for r in app.routes]
        has_health = any("/health" in r for r in routes)
        has_dashboard = any("/dashboard" in r or "/api" in r for r in routes)
        detail = f"{len(routes)} routes"
        if has_health:
            detail += ", /health OK"
        if has_dashboard:
            detail += ", dashboard OK"
        return True, detail
    except Exception as e:
        return False, f"FastAPI import failed: {e}"


def check_workers() -> tuple[bool, str]:
    """Check worker task files exist."""
    task_files = list(Path("workers/tasks").glob("*.py"))
    expected = {"order_tasks.py", "signal_tasks.py", "market_tasks.py",
                "check_tasks.py", "snapshot_tasks.py", "governance_monitor_tasks.py"}
    found = {f.name for f in task_files}
    missing = expected - found
    if missing:
        return False, f"Missing tasks: {', '.join(missing)}"
    return True, f"{len(found)} task files present"


def check_dashboard_templates() -> tuple[bool, str]:
    """Check dashboard template exists."""
    template = Path("app/templates/dashboard.html")
    if not template.exists():
        return False, "dashboard.html not found"
    size = template.stat().st_size
    return True, f"dashboard.html present ({size:,} bytes)"


def check_governance_components() -> tuple[bool, str]:
    """Check governance components are wired."""
    checks = []
    try:
        from app.agents.governance_gate import GovernanceGate
        checks.append("GovernanceGate")
    except Exception:
        pass
    try:
        from app.core.governance_monitor import run_governance_monitor
        checks.append("G-MON")
    except Exception:
        pass
    try:
        from kdexter.engines.cost_controller import CostController
        checks.append("CostController")
    except Exception:
        pass
    try:
        from kdexter.engines.failure_router import FailurePatternMemory
        checks.append("FailurePatternMemory")
    except Exception:
        pass

    if len(checks) >= 4:
        return True, f"All 4 governance components: {', '.join(checks)}"
    return False, f"Only {len(checks)}/4: {', '.join(checks)}"


def check_constitution() -> tuple[bool, str]:
    """Run verify_constitution.py."""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "scripts/verify_constitution.py"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return True, "verify_constitution.py PASS"
        return False, f"FAIL: {result.stdout[-200:]}"
    except Exception as e:
        return False, f"Error: {e}"


# ── Main ─────────────────────────────────────────────────────────────────── #

ALL_CHECKS = [
    ("core_imports", check_core_imports),
    ("kdexter_imports", check_kdexter_imports),
    ("critical_files", check_critical_files),
    ("alembic", check_alembic),
    ("fastapi_entry", check_fastapi_entry),
    ("workers", check_workers),
    ("dashboard_templates", check_dashboard_templates),
    ("governance_components", check_governance_components),
    ("constitution", check_constitution),
]


def main():
    parser = argparse.ArgumentParser(description="K-Dexter System Validation")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    results = [_check(name, fn) for name, fn in ALL_CHECKS]

    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] != "OK")
    total = len(results)
    overall = "PASS" if fail_count == 0 else "FAIL"

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "passed": ok_count,
        "failed": fail_count,
        "total": total,
        "checks": results,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"=== K-Dexter System Validation ===")
        print(f"Overall: {overall} ({ok_count}/{total})\n")
        for r in results:
            icon = {"OK": "[OK]", "FAIL": "[XX]", "ERROR": "[!!]"}[r["status"]]
            print(f"  {icon} {r['name']}: {r['detail']}")
        print()

    # Write JSON to data/
    out = Path("data/validation_results.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    sys.exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
