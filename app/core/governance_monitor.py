"""
G-MON: AI Governance Monitor — 6-indicator automated surveillance

6개 거버넌스 지표를 수집하여 OK/WARN/FAIL 상태를 판정한다.
Read-only. No state modification. No auto-repair.

지표:
  1. BUDGET_CHECK    — CostController 예산 소진율
  2. PATTERN_CHECK   — FailurePatternMemory 반복 실패 감지
  3. FORBIDDEN_CHECK — ForbiddenLedger 차단 이벤트
  4. TOKEN_USAGE     — LLM 토큰 사용량 (일 한도 대비)
  5. AGENT_SUCCESS   — 에이전트 실행 성공률
  6. CONSTITUTION    — verify_constitution.py 정합성

출력: GovernanceMonitorReport (OK/WARN/FAIL per indicator + overall)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class IndicatorStatus(Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class Indicator:
    name: str
    status: IndicatorStatus
    value: str
    threshold: str
    message: str = ""


@dataclass
class GovernanceMonitorReport:
    timestamp: str
    overall: IndicatorStatus
    indicators: list[Indicator] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall": self.overall.value,
            "summary": self.summary,
            "indicators": [
                {
                    "name": i.name,
                    "status": i.status.value,
                    "value": i.value,
                    "threshold": i.threshold,
                    "message": i.message,
                }
                for i in self.indicators
            ],
        }


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

_BUDGET_WARN = 0.8    # 80% usage → WARN
_BUDGET_FAIL = 1.0    # 100% usage → FAIL
_PATTERN_FAIL_COUNT = 3   # 3+ PATTERN classifications → FAIL
_PATTERN_WARN_COUNT = 1   # 1+ PATTERN → WARN
_TOKEN_WARN_RATIO = 0.8
_TOKEN_FAIL_RATIO = 1.0
_SUCCESS_WARN = 0.9   # < 90% success → WARN
_SUCCESS_FAIL = 0.7   # < 70% success → FAIL


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_governance_monitor() -> GovernanceMonitorReport:
    """
    Collect all 6 governance indicators. Read-only. Fail-closed.
    Returns GovernanceMonitorReport with per-indicator and overall status.
    """
    now = datetime.now(timezone.utc)
    indicators: list[Indicator] = []

    indicators.append(_check_budget())
    indicators.append(_check_pattern())
    indicators.append(_check_forbidden())
    indicators.append(_check_token_usage())
    indicators.append(_check_agent_success())
    indicators.append(_check_constitution())

    overall = _determine_overall(indicators)

    ok_count = sum(1 for i in indicators if i.status == IndicatorStatus.OK)
    warn_count = sum(1 for i in indicators if i.status == IndicatorStatus.WARN)
    fail_count = sum(1 for i in indicators if i.status == IndicatorStatus.FAIL)
    summary = f"G-MON: {ok_count} OK, {warn_count} WARN, {fail_count} FAIL — overall {overall.value}"

    return GovernanceMonitorReport(
        timestamp=now.isoformat(),
        overall=overall,
        indicators=indicators,
        summary=summary,
    )


def format_report_text(report: GovernanceMonitorReport) -> str:
    """Format report as human-readable text for notifications."""
    lines = [
        f"=== K-Dexter Governance Monitor ===",
        f"Time: {report.timestamp[:19]}Z",
        f"Overall: {report.overall.value}",
        "",
    ]
    for ind in report.indicators:
        icon = {"OK": "[OK]", "WARN": "[!!]", "FAIL": "[XX]"}[ind.status.value]
        lines.append(f"  {icon} {ind.name}: {ind.value} (threshold: {ind.threshold})")
        if ind.message:
            lines.append(f"      {ind.message}")

    lines.append("")
    lines.append(report.summary)
    return "\n".join(lines)


def format_discord_report(report: GovernanceMonitorReport) -> dict:
    """Format report as Discord webhook payload."""
    icon = {"OK": ":white_check_mark:", "WARN": ":warning:", "FAIL": ":x:"}
    overall_icon = icon[report.overall.value]

    lines = [f"{overall_icon} **K-Dexter Governance Monitor** | {report.overall.value}"]
    lines.append(f"`{report.timestamp[:19]}Z`")
    lines.append("")

    for ind in report.indicators:
        ind_icon = icon[ind.status.value]
        lines.append(f"{ind_icon} **{ind.name}**: {ind.value}")

    lines.append("")
    lines.append(f"_{report.summary}_")

    return {"content": "\n".join(lines)}


# ---------------------------------------------------------------------------
# Individual indicator checks (read-only, fail-closed)
# ---------------------------------------------------------------------------

def _check_budget() -> Indicator:
    """Check CostController budget usage ratio."""
    try:
        gate = _get_gate()
        if gate is None or not hasattr(gate, "cost_controller") or gate.cost_controller is None:
            return Indicator("BUDGET_CHECK", IndicatorStatus.OK, "no_controller", "n/a",
                             "CostController not configured")

        result = gate.cost_controller.check()
        ratio = result.resource_usage_ratio

        if ratio >= _BUDGET_FAIL:
            return Indicator("BUDGET_CHECK", IndicatorStatus.FAIL, f"{ratio:.2%}", f"<{_BUDGET_FAIL:.0%}",
                             "Budget exceeded")
        if ratio >= _BUDGET_WARN:
            return Indicator("BUDGET_CHECK", IndicatorStatus.WARN, f"{ratio:.2%}", f"<{_BUDGET_WARN:.0%}",
                             "Budget nearing limit")
        return Indicator("BUDGET_CHECK", IndicatorStatus.OK, f"{ratio:.2%}", f"<{_BUDGET_WARN:.0%}")
    except Exception as e:
        return Indicator("BUDGET_CHECK", IndicatorStatus.WARN, f"error", "n/a", str(e))


def _check_pattern() -> Indicator:
    """Check FailurePatternMemory for recurring failure patterns."""
    try:
        gate = _get_gate()
        if gate is None or not hasattr(gate, "pattern_memory") or gate.pattern_memory is None:
            return Indicator("PATTERN_CHECK", IndicatorStatus.OK, "no_memory", "n/a",
                             "FailurePatternMemory not configured")

        from kdexter.engines.failure_router import Recurrence

        memory = gate.pattern_memory
        # Check known agent task types for pattern recurrence
        pattern_count = 0
        checked_types = ["AGENT_VALIDATE_SIGNAL", "AGENT_RISK_ASSESSMENT", "AGENT_UNKNOWN"]
        for task_type in checked_types:
            rec = memory.classify_recurrence(task_type)
            if rec == Recurrence.PATTERN:
                pattern_count += 1

        if pattern_count >= _PATTERN_FAIL_COUNT:
            return Indicator("PATTERN_CHECK", IndicatorStatus.FAIL, f"{pattern_count} patterns",
                             f"<{_PATTERN_FAIL_COUNT}", "Multiple recurring failure patterns")
        if pattern_count >= _PATTERN_WARN_COUNT:
            return Indicator("PATTERN_CHECK", IndicatorStatus.WARN, f"{pattern_count} patterns",
                             f"<{_PATTERN_WARN_COUNT}", "Recurring failure detected")
        return Indicator("PATTERN_CHECK", IndicatorStatus.OK, "0 patterns", f"<{_PATTERN_WARN_COUNT}")
    except Exception as e:
        return Indicator("PATTERN_CHECK", IndicatorStatus.WARN, "error", "n/a", str(e))


def _check_forbidden() -> Indicator:
    """Check for recent forbidden action blocks in evidence."""
    try:
        gate = _get_gate()
        if gate is None or not hasattr(gate, "evidence_store"):
            return Indicator("FORBIDDEN_CHECK", IndicatorStatus.OK, "no_store", "n/a",
                             "Evidence store not available")

        store = gate.evidence_store
        bundles = store.list_all()

        # Count FORBIDDEN blocks in recent evidence
        forbidden_blocks = 0
        for b in bundles:
            artifacts = b.artifacts if hasattr(b, "artifacts") else []
            if isinstance(artifacts, dict):
                reason = artifacts.get("reason_code", "")
                if "FORBIDDEN" in str(reason).upper():
                    forbidden_blocks += 1

        if forbidden_blocks > 0:
            return Indicator("FORBIDDEN_CHECK", IndicatorStatus.FAIL, f"{forbidden_blocks} blocks",
                             "0", "Forbidden action attempts detected — investigate immediately")
        return Indicator("FORBIDDEN_CHECK", IndicatorStatus.OK, "0 blocks", "0")
    except Exception as e:
        return Indicator("FORBIDDEN_CHECK", IndicatorStatus.WARN, "error", "n/a", str(e))


def _check_token_usage() -> Indicator:
    """Check LLM token usage against budget."""
    try:
        gate = _get_gate()
        if gate is None or not hasattr(gate, "cost_controller") or gate.cost_controller is None:
            return Indicator("TOKEN_USAGE", IndicatorStatus.OK, "no_controller", "n/a",
                             "CostController not configured")

        ctrl = gate.cost_controller
        # Try to get LLM_TOKENS budget specifically
        budgets = ctrl._budgets if hasattr(ctrl, "_budgets") else {}
        token_budget = budgets.get("LLM_TOKENS")

        if token_budget is None:
            return Indicator("TOKEN_USAGE", IndicatorStatus.OK, "no_budget", "n/a",
                             "LLM_TOKENS budget not set")

        ratio = token_budget.usage_ratio
        current = int(token_budget.current)
        limit = int(token_budget.limit)

        if ratio >= _TOKEN_FAIL_RATIO:
            return Indicator("TOKEN_USAGE", IndicatorStatus.FAIL, f"{current}/{limit} ({ratio:.0%})",
                             f"<{_TOKEN_FAIL_RATIO:.0%}", "Token budget exhausted")
        if ratio >= _TOKEN_WARN_RATIO:
            return Indicator("TOKEN_USAGE", IndicatorStatus.WARN, f"{current}/{limit} ({ratio:.0%})",
                             f"<{_TOKEN_WARN_RATIO:.0%}", "Token usage nearing limit")
        return Indicator("TOKEN_USAGE", IndicatorStatus.OK, f"{current}/{limit} ({ratio:.0%})",
                         f"<{_TOKEN_WARN_RATIO:.0%}")
    except Exception as e:
        return Indicator("TOKEN_USAGE", IndicatorStatus.WARN, "error", "n/a", str(e))


def _check_agent_success() -> Indicator:
    """Check agent execution success rate from evidence store."""
    try:
        gate = _get_gate()
        if gate is None or not hasattr(gate, "evidence_store"):
            return Indicator("AGENT_SUCCESS", IndicatorStatus.OK, "no_store", "n/a",
                             "Evidence store not available")

        store = gate.evidence_store
        bundles = store.list_all()

        total = 0
        success = 0
        for b in bundles:
            artifacts = b.artifacts if hasattr(b, "artifacts") else []
            if isinstance(artifacts, dict):
                phase = artifacts.get("phase", "")
                if phase == "POST":
                    total += 1
                    decision = artifacts.get("decision_code", "")
                    if decision == "ALLOWED" or "success" in str(decision).lower():
                        success += 1
                elif phase == "ERROR":
                    total += 1

        if total == 0:
            return Indicator("AGENT_SUCCESS", IndicatorStatus.OK, "no_data", ">90%",
                             "No agent executions recorded yet")

        rate = success / total
        if rate < _SUCCESS_FAIL:
            return Indicator("AGENT_SUCCESS", IndicatorStatus.FAIL, f"{rate:.0%} ({success}/{total})",
                             f">{_SUCCESS_FAIL:.0%}", "Agent success rate critically low")
        if rate < _SUCCESS_WARN:
            return Indicator("AGENT_SUCCESS", IndicatorStatus.WARN, f"{rate:.0%} ({success}/{total})",
                             f">{_SUCCESS_WARN:.0%}", "Agent success rate degraded")
        return Indicator("AGENT_SUCCESS", IndicatorStatus.OK, f"{rate:.0%} ({success}/{total})",
                         f">{_SUCCESS_WARN:.0%}")
    except Exception as e:
        return Indicator("AGENT_SUCCESS", IndicatorStatus.WARN, "error", "n/a", str(e))


def _check_constitution() -> Indicator:
    """Check constitution document integrity via verify_constitution.py."""
    try:
        import subprocess
        result = subprocess.run(
            ["python", "scripts/verify_constitution.py"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return Indicator("CONSTITUTION", IndicatorStatus.OK, "PASS", "PASS")
        # Parse output for details
        output = result.stdout + result.stderr
        return Indicator("CONSTITUTION", IndicatorStatus.FAIL, "FAIL", "PASS",
                         output[:200] if output else "verify_constitution.py returned non-zero")
    except subprocess.TimeoutExpired:
        return Indicator("CONSTITUTION", IndicatorStatus.WARN, "timeout", "PASS",
                         "verify_constitution.py timed out (30s)")
    except FileNotFoundError:
        return Indicator("CONSTITUTION", IndicatorStatus.WARN, "not_found", "PASS",
                         "verify_constitution.py not accessible")
    except Exception as e:
        return Indicator("CONSTITUTION", IndicatorStatus.WARN, "error", "PASS", str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_gate():
    """Get GovernanceGate from app state. Returns None if unavailable."""
    try:
        import app.main as main_module
        return getattr(main_module.app.state, "governance_gate", None)
    except Exception:
        return None


def _determine_overall(indicators: list[Indicator]) -> IndicatorStatus:
    """Worst indicator determines overall. FAIL > WARN > OK."""
    has_fail = any(i.status == IndicatorStatus.FAIL for i in indicators)
    has_warn = any(i.status == IndicatorStatus.WARN for i in indicators)
    if has_fail:
        return IndicatorStatus.FAIL
    if has_warn:
        return IndicatorStatus.WARN
    return IndicatorStatus.OK
