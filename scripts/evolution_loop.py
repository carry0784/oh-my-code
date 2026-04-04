#!/usr/bin/env python3
"""
K-Dexter Evolution Loop -- Self-Improving System Engine

Analyzes accumulated failure patterns and system performance to propose
and validate structural improvements.

Sits above AutoFix Loop:
  AutoFix  = reactive (fix what's broken)
  Evolution = proactive (improve what's inefficient)

Phases:
  1. ANALYZE   -- scan patterns, grade history, loop performance
  2. DIAGNOSE  -- identify inefficiencies and recurring weaknesses
  3. PROPOSE   -- generate improvement candidates
  4. VALIDATE  -- governance + safety check of proposal
  5. RECORD    -- record proposal + evidence for human review

Constraints:
  - Max 1 proposal per run
  - Proposals are NEVER auto-applied (human review required)
  - All proposals must pass governance pre-check
  - Evolution is read-only analysis + proposal generation
  - No direct code modification

Usage:
    python scripts/evolution_loop.py
    python scripts/evolution_loop.py --json
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_REPO_ROOT)


# ── Data Loaders ──────────────────────────────────────────────────────────── #

def _load_json(path: str) -> dict | list | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_patterns() -> list[dict]:
    data = _load_json("data/failure_patterns.json")
    return data if isinstance(data, list) else []


def _load_grade_history() -> list[dict]:
    data = _load_json("data/grade_history.json")
    return data if isinstance(data, list) else []


def _load_loop_report() -> dict | None:
    return _load_json("data/autofix_loop_report.json")


def _load_evolution_history() -> list[dict]:
    data = _load_json("data/evolution_history.json")
    return data if isinstance(data, list) else []


# ── Phase 1: ANALYZE ─────────────────────────────────────────────────────── #

def analyze(patterns: list[dict], grades: list[dict],
            loop_report: dict | None) -> dict:
    """Analyze system state for improvement opportunities."""
    analysis = {
        "pattern_count": len(patterns),
        "grade_count": len(grades),
        "loop_available": loop_report is not None,
    }

    # Failure type distribution
    type_counts = Counter(p.get("failure_type", "unknown") for p in patterns)
    analysis["failure_type_distribution"] = dict(type_counts.most_common(10))

    # Recurrence distribution
    rec_counts = Counter(p.get("recurrence", "FIRST") for p in patterns)
    analysis["recurrence_distribution"] = dict(rec_counts)

    # Grade trend
    if len(grades) >= 3:
        recent = grades[-5:]
        grade_rank = {"GREEN": 0, "YELLOW": 1, "RED": 2}
        scores = [grade_rank.get(g.get("grade", "RED"), 2) for g in recent]
        avg_score = sum(scores) / len(scores)

        if avg_score <= 0.3:
            analysis["health_trend"] = "HEALTHY"
        elif avg_score <= 1.0:
            analysis["health_trend"] = "DEGRADING"
        else:
            analysis["health_trend"] = "CRITICAL"

        analysis["recent_risk_scores"] = [g.get("risk_score", 0) for g in recent]
    else:
        analysis["health_trend"] = "INSUFFICIENT_DATA"

    # Loop performance
    if loop_report:
        analysis["last_loop_grade"] = loop_report.get("final_grade")
        analysis["last_loop_iterations"] = loop_report.get("iterations_run")
        analysis["last_loop_duration"] = loop_report.get("duration_seconds")
        analysis["last_loop_reason"] = loop_report.get("exit_reason")

    # Pattern hotspots (files with most failures)
    path_counts: Counter = Counter()
    for p in patterns:
        for ap in p.get("affected_paths", []):
            path_counts[ap] += 1
    analysis["hotspot_files"] = dict(path_counts.most_common(5))

    # Fix success rates by type
    fix_rates: dict[str, dict] = {}
    for ftype in type_counts:
        matching = [p for p in patterns
                    if p.get("failure_type") == ftype and p.get("fix_attempted")]
        if matching:
            succeeded = sum(1 for p in matching if p.get("fix_succeeded"))
            fix_rates[ftype] = {
                "attempted": len(matching),
                "succeeded": succeeded,
                "rate": round(succeeded / len(matching), 2),
            }
    analysis["fix_success_rates"] = fix_rates

    return analysis


# ── Phase 2: DIAGNOSE ────────────────────────────────────────────────────── #

def diagnose(analysis: dict) -> list[dict]:
    """Identify inefficiencies and recurring weaknesses."""
    diagnoses = []

    # D1: Recurring failure types
    type_dist = analysis.get("failure_type_distribution", {})
    for ftype, count in type_dist.items():
        if count >= 3:
            diagnoses.append({
                "id": f"D-TYPE-{ftype}",
                "severity": "HIGH" if count >= 5 else "MEDIUM",
                "category": "recurring_failure",
                "description": f"{ftype} has occurred {count} times",
                "failure_type": ftype,
                "count": count,
            })

    # D2: PATTERN recurrence accumulation
    rec_dist = analysis.get("recurrence_distribution", {})
    pattern_count = rec_dist.get("PATTERN", 0)
    if pattern_count >= 3:
        diagnoses.append({
            "id": "D-PATTERN-ACCUMULATION",
            "severity": "HIGH",
            "category": "pattern_accumulation",
            "description": f"{pattern_count} failures classified as PATTERN (structural recurring)",
            "count": pattern_count,
        })

    # D3: Health trend degradation
    trend = analysis.get("health_trend")
    if trend == "DEGRADING":
        diagnoses.append({
            "id": "D-TREND-DEGRADING",
            "severity": "MEDIUM",
            "category": "trend_degradation",
            "description": "System health trend is degrading based on recent grades",
        })
    elif trend == "CRITICAL":
        diagnoses.append({
            "id": "D-TREND-CRITICAL",
            "severity": "HIGH",
            "category": "trend_critical",
            "description": "System health is in critical state",
        })

    # D4: File hotspots
    hotspots = analysis.get("hotspot_files", {})
    for filepath, count in hotspots.items():
        if count >= 3:
            diagnoses.append({
                "id": f"D-HOTSPOT-{Path(filepath).stem}",
                "severity": "MEDIUM",
                "category": "file_hotspot",
                "description": f"{filepath} involved in {count} failures",
                "file": filepath,
                "count": count,
            })

    # D5: Loop efficiency
    last_iters = analysis.get("last_loop_iterations")
    if last_iters and last_iters >= 3:
        diagnoses.append({
            "id": "D-LOOP-MAXITER",
            "severity": "MEDIUM",
            "category": "loop_inefficiency",
            "description": f"AutoFix loop used all {last_iters} iterations without full GREEN",
        })

    # D6: Low fix success rate
    fix_rates = analysis.get("fix_success_rates", {})
    for ftype, rates in fix_rates.items():
        if rates["attempted"] >= 3 and rates["rate"] < 0.5:
            diagnoses.append({
                "id": f"D-LOWFIX-{ftype}",
                "severity": "HIGH",
                "category": "low_fix_rate",
                "description": f"{ftype} fix success rate is {rates['rate']:.0%} ({rates['succeeded']}/{rates['attempted']})",
                "failure_type": ftype,
                "rate": rates["rate"],
            })

    # Sort by severity
    sev_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    diagnoses.sort(key=lambda d: sev_order.get(d["severity"], 9))

    return diagnoses


# ── Phase 3: PROPOSE ─────────────────────────────────────────────────────── #

_PROPOSAL_TEMPLATES = {
    "recurring_failure": {
        "action": "Add dedicated fix handler for {failure_type}",
        "strategy": "Create specialized autofix rule targeting root cause pattern",
        "risk": "LOW",
    },
    "pattern_accumulation": {
        "action": "Escalate pattern failures to permanent monitoring",
        "strategy": "Add {count} pattern entries to G-MON watch list",
        "risk": "LOW",
    },
    "trend_degradation": {
        "action": "Increase test coverage for degrading area",
        "strategy": "Add regression tests targeting recent YELLOW/RED causes",
        "risk": "LOW",
    },
    "trend_critical": {
        "action": "Emergency stabilization review required",
        "strategy": "Freeze non-essential changes, focus on GREEN restoration",
        "risk": "MEDIUM",
    },
    "file_hotspot": {
        "action": "Refactor hotspot file {file}",
        "strategy": "Extract fragile logic, add targeted tests, reduce coupling",
        "risk": "MEDIUM",
    },
    "loop_inefficiency": {
        "action": "Improve autofix accuracy for common failure types",
        "strategy": "Add fix_pattern field to failure_patterns.json for known fixes",
        "risk": "LOW",
    },
    "low_fix_rate": {
        "action": "Redesign fix strategy for {failure_type}",
        "strategy": "Current fix success rate {rate:.0%} is too low - investigate root cause",
        "risk": "MEDIUM",
    },
}


# Cooldown: same category cannot be re-proposed within this window
PROPOSAL_COOLDOWN_HOURS = 24


def _is_on_cooldown(category: str, existing_proposals: list[dict]) -> bool:
    """Check if a category is on cooldown (proposed within PROPOSAL_COOLDOWN_HOURS)."""
    now = datetime.now(timezone.utc)
    for p in reversed(existing_proposals):
        if p.get("category") != category:
            continue
        created = p.get("created_at", "")
        if not created:
            continue
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if hasattr(created_dt, "tzinfo") and created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            hours_ago = (now - created_dt).total_seconds() / 3600
            if hours_ago < PROPOSAL_COOLDOWN_HOURS:
                return True
        except (ValueError, TypeError):
            continue
    return False


def propose(diagnoses: list[dict], existing_proposals: list[dict]) -> dict | None:
    """Generate a single improvement proposal from top diagnosis."""
    if not diagnoses:
        return None

    # Skip already-proposed diagnoses
    proposed_ids = {p.get("diagnosis_id") for p in existing_proposals}

    for diag in diagnoses:
        if diag["id"] in proposed_ids:
            continue

        # Cooldown check: skip if same category was proposed recently
        if _is_on_cooldown(diag["category"], existing_proposals):
            continue

        template = _PROPOSAL_TEMPLATES.get(diag["category"], {
            "action": "Review and address: {description}",
            "strategy": "Manual analysis required",
            "risk": "MEDIUM",
        })

        action = template["action"].format(**{**diag, "description": diag["description"]})
        strategy = template["strategy"].format(**{**diag, "description": diag["description"]})

        proposal = {
            "proposal_id": f"EVO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "diagnosis_id": diag["id"],
            "severity": diag["severity"],
            "category": diag["category"],
            "action": action,
            "strategy": strategy,
            "risk": template["risk"],
            "status": "PROPOSED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "applied_at": None,
            "approved_by": None,
        }
        return proposal

    return None


def score_proposal(proposal: dict, analysis: dict) -> int:
    """Compute proposal priority score (0-100). Higher = more urgent."""
    score = 0

    # Severity weight
    sev_scores = {"HIGH": 40, "MEDIUM": 25, "LOW": 10}
    score += sev_scores.get(proposal.get("severity", "LOW"), 10)

    # Risk weight (lower risk = higher score, safer to do)
    risk_scores = {"LOW": 20, "MEDIUM": 10, "HIGH": 0}
    score += risk_scores.get(proposal.get("risk", "HIGH"), 0)

    # Pattern count weight
    pattern_count = analysis.get("pattern_count", 0)
    score += min(pattern_count * 3, 20)

    # Health trend weight
    trend_scores = {"CRITICAL": 20, "DEGRADING": 10, "HEALTHY": 0, "INSUFFICIENT_DATA": 5}
    score += trend_scores.get(analysis.get("health_trend", ""), 0)

    return min(score, 100)


# ── Phase 4: VALIDATE ────────────────────────────────────────────────────── #

def validate_proposal(proposal: dict) -> dict:
    """Validate proposal safety (governance + risk check)."""
    validation = {
        "proposal_id": proposal["proposal_id"],
        "checks": [],
        "passed": True,
    }

    # Check 1: Risk level
    if proposal["risk"] in ("LOW", "MEDIUM"):
        validation["checks"].append({"name": "risk_level", "status": "OK",
                                      "detail": f"Risk: {proposal['risk']}"})
    else:
        validation["checks"].append({"name": "risk_level", "status": "WARN",
                                      "detail": "High risk proposal"})

    # Check 2: Not touching governance-protected area
    governance_keywords = ["governance_gate", "governance_check", "constitution"]
    action_lower = (proposal["action"] + proposal["strategy"]).lower()
    touches_governance = any(kw in action_lower for kw in governance_keywords)
    if touches_governance:
        validation["checks"].append({"name": "governance_proximity", "status": "BLOCK",
                                      "detail": "Proposal touches governance-protected area"})
        validation["passed"] = False
    else:
        validation["checks"].append({"name": "governance_proximity", "status": "OK",
                                      "detail": "No governance area impact"})

    # Check 3: Category safety
    safe_categories = {"recurring_failure", "pattern_accumulation",
                       "trend_degradation", "loop_inefficiency"}
    if proposal["category"] in safe_categories:
        validation["checks"].append({"name": "category_safety", "status": "OK",
                                      "detail": f"Category '{proposal['category']}' is safe"})
    else:
        validation["checks"].append({"name": "category_safety", "status": "WARN",
                                      "detail": f"Category '{proposal['category']}' needs human review"})

    return validation


# ── Phase 5: RECORD ──────────────────────────────────────────────────────── #

def record_evolution(proposal: dict | None, validation: dict | None,
                     analysis: dict, diagnoses: list[dict]) -> dict:
    """Record evolution result."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_summary": {
            "pattern_count": analysis.get("pattern_count", 0),
            "health_trend": analysis.get("health_trend", "UNKNOWN"),
            "diagnoses_count": len(diagnoses),
            "fix_success_rates": analysis.get("fix_success_rates", {}),
        },
        "proposal": proposal,
        "validation": validation,
        "diagnoses": diagnoses[:5],
    }

    history = _load_evolution_history()
    history.append(entry)
    if len(history) > 50:
        history = history[-50:]

    out = Path("data/evolution_history.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    return entry


# ── Main ──────────────────────────────────────────────────────────────────── #

def evolution_loop() -> dict:
    """Run one cycle of the evolution loop."""
    print("\n" + "#" * 60)
    print("  K-Dexter Evolution Loop")
    print("#" * 60)

    # Phase 1: ANALYZE
    print("\n[1/5] ANALYZE")
    patterns = _load_patterns()
    grades = _load_grade_history()
    loop_report = _load_loop_report()
    analysis = analyze(patterns, grades, loop_report)
    print(f"  Patterns: {analysis['pattern_count']}")
    print(f"  Grades: {analysis['grade_count']}")
    print(f"  Health trend: {analysis.get('health_trend', 'N/A')}")
    if analysis.get("failure_type_distribution"):
        print(f"  Top failure types: {analysis['failure_type_distribution']}")
    if analysis.get("fix_success_rates"):
        print(f"  Fix success rates: {analysis['fix_success_rates']}")

    # Phase 2: DIAGNOSE
    print("\n[2/5] DIAGNOSE")
    diagnoses = diagnose(analysis)
    if diagnoses:
        for d in diagnoses[:5]:
            print(f"  [{d['severity']}] {d['id']}: {d['description']}")
    else:
        print("  No issues diagnosed. System is healthy.")

    # Phase 3: PROPOSE
    print("\n[3/5] PROPOSE")
    existing = _load_evolution_history()
    existing_proposals = [e.get("proposal", {}) for e in existing
                          if e.get("proposal")]
    proposal = propose(diagnoses, existing_proposals)

    if proposal:
        proposal["score"] = score_proposal(proposal, analysis)

    if proposal:
        print(f"  Proposal: {proposal['proposal_id']}")
        print(f"  Action: {proposal['action']}")
        print(f"  Strategy: {proposal['strategy']}")
        print(f"  Risk: {proposal['risk']}")
    else:
        print("  No new proposals needed")

    # Phase 4: VALIDATE
    print("\n[4/5] VALIDATE")
    if proposal:
        validation = validate_proposal(proposal)
        for c in validation["checks"]:
            icon = {"OK": "[OK]", "WARN": "[!!]", "BLOCK": "[XX]"}[c["status"]]
            print(f"  {icon} {c['name']}: {c['detail']}")
        if not validation["passed"]:
            proposal["status"] = "BLOCKED"
            print(f"\n  [XX] Proposal BLOCKED by validation")
    else:
        validation = None

    # Phase 5: RECORD
    print("\n[5/5] RECORD")
    entry = record_evolution(proposal, validation, analysis, diagnoses)
    print(f"  Recorded to data/evolution_history.json")

    # Summary
    print("\n" + "#" * 60)
    print("  Evolution Loop Complete")
    print(f"  Diagnoses: {len(diagnoses)}")
    print(f"  Proposal: {proposal['proposal_id'] if proposal else 'None (healthy)'}")
    if proposal:
        print(f"  Status: {proposal['status']}")
    print("#" * 60)

    return {
        "loop_type": "evolution",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis": analysis,
        "diagnoses_count": len(diagnoses),
        "proposal": proposal,
        "validation": validation,
    }


def _cmd_list():
    """List all proposals with their status."""
    history = _load_evolution_history()
    proposals = [e.get("proposal") for e in history if e.get("proposal")]
    if not proposals:
        print("No proposals found.")
        return

    print(f"{'ID':<25} {'Score':>5} {'Severity':<8} {'Status':<10} {'Category':<20} {'Action'}")
    print("-" * 100)
    for p in proposals:
        print(f"{p.get('proposal_id', '?'):<25} {p.get('score', '?'):>5} "
              f"{p.get('severity', '?'):<8} {p.get('status', '?'):<10} "
              f"{p.get('category', '?'):<20} {p.get('action', '?')[:40]}")


def _cmd_board():
    """Show proposal board grouped by status (PENDING / APPROVED / REJECTED / APPLIED)."""
    history = _load_evolution_history()
    proposals = [e.get("proposal") for e in history if e.get("proposal")]
    if not proposals:
        print("No proposals found.")
        return

    buckets = {
        "PENDING (PROPOSED)": [p for p in proposals if p.get("status") == "PROPOSED"],
        "APPROVED": [p for p in proposals if p.get("status") == "APPROVED"],
        "REJECTED": [p for p in proposals if p.get("status") == "REJECTED"],
        "APPLIED": [p for p in proposals if p.get("status") == "APPLIED"],
        "BLOCKED": [p for p in proposals if p.get("status") == "BLOCKED"],
    }

    print("=" * 80)
    print("  Evolution Proposal Board")
    print("=" * 80)

    for label, items in buckets.items():
        print(f"\n[{label}] ({len(items)})")
        if not items:
            print("  (none)")
            continue
        print(f"  {'ID':<25} {'Score':>5} {'Severity':<8} {'Category':<20} {'Action'}")
        print("  " + "-" * 75)
        for p in items:
            print(f"  {p.get('proposal_id', '?'):<25} {p.get('score', '?'):>5} "
                  f"{p.get('severity', '?'):<8} "
                  f"{p.get('category', '?'):<20} {p.get('action', '?')[:35]}")

    print(f"\n{'=' * 80}")
    total = len(proposals)
    pending = len(buckets["PENDING (PROPOSED)"])
    approved = len(buckets["APPROVED"])
    print(f"  Total: {total}  |  Pending: {pending}  |  Approved: {approved}  |  "
          f"Rejected: {len(buckets['REJECTED'])}  |  Applied: {len(buckets['APPLIED'])}  |  "
          f"Blocked: {len(buckets['BLOCKED'])}")
    print("=" * 80)


def _cmd_approve(proposal_id: str):
    """Approve a proposal."""
    history = _load_evolution_history()
    found = False
    for entry in history:
        p = entry.get("proposal")
        if p and p.get("proposal_id") == proposal_id:
            if p["status"] == "PROPOSED":
                p["status"] = "APPROVED"
                p["approved_by"] = "operator"
                p["approved_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                print(f"[OK] Approved: {proposal_id}")
            else:
                print(f"[!!] Cannot approve: status is {p['status']}")
                return
            break

    if not found:
        print(f"[XX] Proposal not found: {proposal_id}")
        return

    out = Path("data/evolution_history.json")
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _cmd_reject(proposal_id: str):
    """Reject a proposal."""
    history = _load_evolution_history()
    found = False
    for entry in history:
        p = entry.get("proposal")
        if p and p.get("proposal_id") == proposal_id:
            if p["status"] in ("PROPOSED", "APPROVED"):
                p["status"] = "REJECTED"
                p["rejected_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                print(f"[OK] Rejected: {proposal_id}")
            else:
                print(f"[!!] Cannot reject: status is {p['status']}")
                return
            break

    if not found:
        print(f"[XX] Proposal not found: {proposal_id}")
        return

    out = Path("data/evolution_history.json")
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_guard_check(proposal_id: str, commit_hash: str) -> tuple[bool, list[str]]:
    """Pre-apply safety checks. Returns (passed, messages)."""
    messages = []
    passed = True

    # Guard 1: Receipt existence check
    receipt_dir = Path("docs/operations/evidence")
    receipt_found = False
    if receipt_dir.exists():
        for f in receipt_dir.iterdir():
            if f.suffix == ".md" and proposal_id.lower() in f.read_text(encoding="utf-8", errors="replace").lower():
                receipt_found = True
                break
    if receipt_found:
        messages.append("[OK] RECEIPT: Change approval receipt found")
    else:
        messages.append("[!!] RECEIPT: No change_approval_receipt referencing this proposal found")
        messages.append("     Create receipt from docs/operations/templates/change_approval_receipt.md")
        passed = False

    # Guard 2: Test results check
    eval_path = Path("data/evaluation_report.json")
    if eval_path.exists():
        try:
            report = json.loads(eval_path.read_text(encoding="utf-8"))
            grade = report.get("final_grade", "UNKNOWN")
            if grade in ("GREEN", "YELLOW"):
                messages.append(f"[OK] TESTS: Last evaluation grade is {grade}")
            else:
                messages.append(f"[!!] TESTS: Last evaluation grade is {grade} (should be GREEN or YELLOW)")
                passed = False
        except Exception:
            messages.append("[!!] TESTS: Cannot read evaluation_report.json")
            passed = False
    else:
        messages.append("[!!] TESTS: evaluation_report.json not found -- run evaluate_results.py first")
        passed = False

    # Guard 3: Governance check
    gov_path = Path("data/governance_check_result.json")
    if gov_path.exists():
        try:
            gov = json.loads(gov_path.read_text(encoding="utf-8"))
            judgment = gov.get("judgment", "UNKNOWN")
            if judgment == "BLOCK":
                messages.append(f"[XX] GOVERNANCE: judgment is BLOCK -- apply prohibited")
                passed = False
            else:
                messages.append(f"[OK] GOVERNANCE: judgment is {judgment}")
        except Exception:
            messages.append("[!!] GOVERNANCE: Cannot read governance_check_result.json")
    else:
        messages.append("[--] GOVERNANCE: governance_check_result.json not found (skipped)")

    # Guard 4: Commit hash provided
    if commit_hash:
        messages.append(f"[OK] COMMIT: {commit_hash}")
    else:
        messages.append("[!!] COMMIT: No commit hash provided (use --commit)")
        passed = False

    return passed, messages


def _cmd_apply(proposal_id: str, commit_hash: str = "", force: bool = False):
    """Mark a proposal as APPLIED (after human has implemented the change)."""
    # Apply Guard -- pre-apply safety checks
    guard_passed, guard_messages = _apply_guard_check(proposal_id, commit_hash)
    print("\n  Apply Guard Checks:")
    for msg in guard_messages:
        print(f"  {msg}")
    print()

    if not guard_passed and not force:
        print("[XX] Apply blocked by guard checks. Fix issues above or use --force to override.")
        print("     WARNING: --force bypasses safety checks. Use only in emergencies.")
        return

    if not guard_passed and force:
        print("[!!] FORCE OVERRIDE: Applying despite guard failures. This will be recorded.")

    history = _load_evolution_history()
    found = False
    for entry in history:
        p = entry.get("proposal")
        if p and p.get("proposal_id") == proposal_id:
            if p["status"] == "APPROVED":
                p["status"] = "APPLIED"
                p["applied_at"] = datetime.now(timezone.utc).isoformat()
                p["applied_commit"] = commit_hash or None
                p["apply_guard_passed"] = guard_passed
                p["apply_forced"] = force and not guard_passed
                found = True
                print(f"[OK] Applied: {proposal_id}")
                if commit_hash:
                    print(f"     Commit: {commit_hash}")
                if not guard_passed:
                    print(f"     [!!] FORCED: Guard checks were bypassed")
            else:
                print(f"[!!] Cannot apply: status is {p['status']} (must be APPROVED)")
                return
            break

    if not found:
        print(f"[XX] Proposal not found: {proposal_id}")
        return

    out = Path("data/evolution_history.json")
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _cmd_block(proposal_id: str, reason: str = ""):
    """Block a proposal (governance/safety concern)."""
    history = _load_evolution_history()
    found = False
    for entry in history:
        p = entry.get("proposal")
        if p and p.get("proposal_id") == proposal_id:
            if p["status"] in ("PROPOSED", "APPROVED"):
                p["status"] = "BLOCKED"
                p["blocked_at"] = datetime.now(timezone.utc).isoformat()
                p["blocked_reason"] = reason or "Governance/safety concern"
                found = True
                print(f"[OK] Blocked: {proposal_id}")
                print(f"     Reason: {p['blocked_reason']}")
            else:
                print(f"[!!] Cannot block: status is {p['status']}")
                return
            break

    if not found:
        print(f"[XX] Proposal not found: {proposal_id}")
        return

    out = Path("data/evolution_history.json")
    out.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="K-Dexter Evolution Loop")
    sub = parser.add_subparsers(dest="command", help="Commands")

    # Default: run evolution
    run_parser = sub.add_parser("run", help="Run evolution loop")
    run_parser.add_argument("--json", action="store_true")

    # List pending proposals
    sub.add_parser("list", help="List pending proposals")

    # Board view (grouped by status)
    sub.add_parser("board", help="Show proposal board grouped by status")

    # Approve a proposal
    approve_parser = sub.add_parser("approve", help="Approve a proposal")
    approve_parser.add_argument("proposal_id", help="Proposal ID to approve")

    # Reject a proposal
    reject_parser = sub.add_parser("reject", help="Reject a proposal")
    reject_parser.add_argument("proposal_id", help="Proposal ID to reject")

    # Apply a proposal (after human implementation)
    apply_parser = sub.add_parser("apply", help="Mark proposal as applied")
    apply_parser.add_argument("proposal_id", help="Proposal ID to mark as applied")
    apply_parser.add_argument("--commit", default="", help="Commit hash of the applied change")
    apply_parser.add_argument("--force", action="store_true", help="Force apply despite guard failures")

    # Block a proposal (governance/safety)
    block_parser = sub.add_parser("block", help="Block a proposal")
    block_parser.add_argument("proposal_id", help="Proposal ID to block")
    block_parser.add_argument("--reason", default="", help="Reason for blocking")

    args = parser.parse_args()

    if args.command == "list":
        _cmd_list()
    elif args.command == "board":
        _cmd_board()
    elif args.command == "approve":
        _cmd_approve(args.proposal_id)
    elif args.command == "reject":
        _cmd_reject(args.proposal_id)
    elif args.command == "apply":
        _cmd_apply(args.proposal_id, args.commit, args.force)
    elif args.command == "block":
        _cmd_block(args.proposal_id, args.reason)
    else:
        # Default: run
        result = evolution_loop()
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
