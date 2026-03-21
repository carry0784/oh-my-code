"""
Governance Gate — Agent Execution Control Boundary

GovernanceGate is NOT a decision maker. It is a control boundary.
Allowed: block/allow, check matrix recording, evidence creation, pre/post/error linkage.
Forbidden: trade decisions, prompt modification, risk calculations, orchestration.

Resolves:
  D-002: EvidenceBundle must be produced for every agent execution
  D-009: ForbiddenLedger must be checked before any agent execution
  VALIDATING: 10-check state classification required before execution
"""
from __future__ import annotations

import hashlib
import traceback
from enum import Enum
from typing import Any, Optional

from kdexter.audit.evidence_store import EvidenceBundle, EvidenceStore
from kdexter.ledger.forbidden_ledger import ForbiddenAction, ForbiddenLedger
from kdexter.state_machine.security_state import SecurityStateContext

from app.core.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────── #
# Code classification enums
# ─────────────────────────────────────────────────────────────────────────── #

class DecisionCode(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ReasonCode(str, Enum):
    NONE = "GOV-NONE"
    LOCKDOWN_BLOCK = "GOV-LOCKDOWN-BLOCK"
    QUARANTINE_BLOCK = "GOV-QUARANTINE-BLOCK"
    FORBIDDEN_ACTION = "GOV-FORBIDDEN-ACTION"
    MISSING_SYMBOL = "GOV-MISSING-SYMBOL"
    MISSING_EXCHANGE = "GOV-MISSING-EXCHANGE"
    COMPLIANCE_D002 = "GOV-COMPLIANCE-D002"
    COMPLIANCE_D009 = "GOV-COMPLIANCE-D009"
    POST_EXCEPTION = "GOV-POST-EXCEPTION"


class PhaseCode(str, Enum):
    PRE = "PRE"
    POST = "POST"
    ERROR = "ERROR"


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED = "deferred"
    UNIMPLEMENTED = "unimplemented"


# ─────────────────────────────────────────────────────────────────────────── #
# Pre-defined forbidden actions for agent scope
# ─────────────────────────────────────────────────────────────────────────── #

_AGENT_FORBIDDEN_ACTIONS = [
    ForbiddenAction(
        action_id="FA-AGENT-001",
        description="TCL bypass: direct exchange API call from agent",
        severity="LOCKDOWN",
        pattern="AGENT_DIRECT_EXCHANGE_CALL",
        registered_by="GovernanceGate",
    ),
    ForbiddenAction(
        action_id="FA-AGENT-002",
        description="Trade execution without risk check",
        severity="LOCKDOWN",
        pattern="AGENT_UNAPPROVED_EXECUTION",
        registered_by="GovernanceGate",
    ),
    ForbiddenAction(
        action_id="FA-AGENT-003",
        description="Position limit exceeded by agent approval",
        severity="BLOCKED",
        pattern="AGENT_EXCEED_POSITION_LIMIT*",
        registered_by="GovernanceGate",
    ),
    ForbiddenAction(
        action_id="FA-AGENT-004",
        description="Governance gate bypass attempt",
        severity="LOCKDOWN",
        pattern="AGENT_SKIP_GOVERNANCE*",
        registered_by="GovernanceGate",
    ),
]


# ─────────────────────────────────────────────────────────────────────────── #
# GovernanceGate
# ─────────────────────────────────────────────────────────────────────────── #

class GovernanceGate:
    """
    Control boundary for agent execution.

    Ensures:
      1. ForbiddenLedger is checked before any LLM agent call (D-009)
      2. EvidenceBundle is produced for every execution (D-002)
      3. VALIDATING 10-check state classification is recorded
    """

    def __init__(
        self,
        forbidden_ledger: ForbiddenLedger,
        evidence_store: EvidenceStore,
        security_ctx: SecurityStateContext,
    ) -> None:
        self.forbidden_ledger = forbidden_ledger
        self.evidence_store = evidence_store
        self.security_ctx = security_ctx

        # Register agent-scope forbidden actions (idempotent — register() overwrites by action_id)
        for fa in _AGENT_FORBIDDEN_ACTIONS:
            self.forbidden_ledger.register(fa)

    # ── Pre-check ──────────────────────────────────────────────────────── #

    def pre_check(self, task: Any) -> tuple[bool, str, str, str]:
        """
        Pre-execution governance check.

        Returns:
            (passed, decision_code, reason_code, evidence_id)
        """
        check_matrix: dict[str, dict[str, str]] = {}

        # ── Check 1: FORBIDDEN_CHECK ──
        # SecurityState gate — read-only, no writes to global state
        if self.security_ctx.is_locked_down():
            check_matrix["FORBIDDEN_CHECK"] = {
                "status": CheckStatus.FAILED.value,
                "detail": "Global SecurityState is LOCKDOWN",
            }
            return self._finalize_pre(
                task, False, DecisionCode.BLOCKED, ReasonCode.LOCKDOWN_BLOCK,
                check_matrix, "SecurityState LOCKDOWN — execution denied",
            )

        if self.security_ctx.sandbox_only():
            check_matrix["FORBIDDEN_CHECK"] = {
                "status": CheckStatus.FAILED.value,
                "detail": "Global SecurityState is QUARANTINED",
            }
            return self._finalize_pre(
                task, False, DecisionCode.BLOCKED, ReasonCode.QUARANTINE_BLOCK,
                check_matrix, "SecurityState QUARANTINED — execution denied",
            )

        # ForbiddenLedger check
        action_name = f"AGENT_{task.task_type.upper()}" if hasattr(task, "task_type") else "AGENT_UNKNOWN"
        forbidden_passed, forbidden_reason = self.forbidden_ledger.check_and_enforce(
            action_name=action_name,
            context={"task_type": getattr(task, "task_type", "unknown")},
            security_ctx=self.security_ctx,
            evidence_store=self.evidence_store,
        )

        if not forbidden_passed:
            check_matrix["FORBIDDEN_CHECK"] = {
                "status": CheckStatus.FAILED.value,
                "detail": forbidden_reason,
            }
            return self._finalize_pre(
                task, False, DecisionCode.BLOCKED, ReasonCode.FORBIDDEN_ACTION,
                check_matrix, forbidden_reason,
            )

        check_matrix["FORBIDDEN_CHECK"] = {
            "status": CheckStatus.PASSED.value,
            "detail": "No forbidden action detected",
        }

        # ── Check 2: MANDATORY_CHECK ──
        symbol = getattr(task, "symbol", None)
        exchange = getattr(task, "exchange", None)

        if not symbol:
            check_matrix["MANDATORY_CHECK"] = {
                "status": CheckStatus.FAILED.value,
                "detail": "symbol is required",
            }
            return self._finalize_pre(
                task, False, DecisionCode.BLOCKED, ReasonCode.MISSING_SYMBOL,
                check_matrix, "Mandatory field missing: symbol",
            )

        if not exchange:
            check_matrix["MANDATORY_CHECK"] = {
                "status": CheckStatus.FAILED.value,
                "detail": "exchange is required",
            }
            return self._finalize_pre(
                task, False, DecisionCode.BLOCKED, ReasonCode.MISSING_EXCHANGE,
                check_matrix, "Mandatory field missing: exchange",
            )

        check_matrix["MANDATORY_CHECK"] = {
            "status": CheckStatus.PASSED.value,
            "detail": f"symbol={symbol}, exchange={exchange}",
        }

        # ── Check 3: COMPLIANCE_CHECK ──
        # D-002: EvidenceBundle will be produced (this method guarantees it)
        # D-008: Audit trail completeness
        # D-009: ForbiddenLedger was checked (above)
        check_matrix["COMPLIANCE_CHECK"] = {
            "status": CheckStatus.PASSED.value,
            "detail": "D-002 evidence production guaranteed, D-008 audit trail, D-009 forbidden check executed",
        }

        # ── Checks 4-10: Scope-based classification ──
        check_matrix["DRIFT_CHECK"] = {
            "status": CheckStatus.NOT_APPLICABLE.value,
            "detail": "Single agent call scope — intent drift is MainLoop/L15 scope",
        }
        check_matrix["CONFLICT_CHECK"] = {
            "status": CheckStatus.NOT_APPLICABLE.value,
            "detail": "Agent calls do not modify rules — RuleLedger/L16 scope",
        }
        check_matrix["PATTERN_CHECK"] = {
            "status": CheckStatus.DEFERRED.value,
            "detail": "Failure pattern memory (L17) — deferred to priority 5+",
        }
        check_matrix["BUDGET_CHECK"] = {
            "status": CheckStatus.DEFERRED.value,
            "detail": "Cost control (L29) — deferred to priority 3 (M-08/G-22)",
        }
        check_matrix["TRUST_CHECK"] = {
            "status": CheckStatus.NOT_APPLICABLE.value,
            "detail": "Agent calls are not trust decay targets — TrustState/L19 scope",
        }
        check_matrix["LOOP_CHECK"] = {
            "status": CheckStatus.NOT_APPLICABLE.value,
            "detail": "Agent calls are not loop health targets — LoopMonitor/L28 scope",
        }
        check_matrix["LOCK_CHECK"] = {
            "status": CheckStatus.NOT_APPLICABLE.value,
            "detail": "Agent calls do not modify spec locks — SpecLock/L22 scope",
        }

        # All checks passed
        return self._finalize_pre(
            task, True, DecisionCode.ALLOWED, ReasonCode.NONE,
            check_matrix, "All pre-checks passed",
        )

    def _finalize_pre(
        self,
        task: Any,
        passed: bool,
        decision_code: DecisionCode,
        reason_code: ReasonCode,
        check_matrix: dict,
        detail: str,
    ) -> tuple[bool, str, str, str]:
        """Build coverage meta from check_matrix dynamically and store evidence."""
        coverage_meta = self._compute_coverage(check_matrix)

        bundle = EvidenceBundle(
            trigger="GovernanceGate.pre_check",
            actor="GovernanceGate",
            action=f"PRE_CHECK:{decision_code.value}",
            before_state=self.security_ctx.current.value,
            after_state=self.security_ctx.current.value,
            artifacts=[{
                "phase": PhaseCode.PRE.value,
                "decision_code": decision_code.value,
                "reason_code": reason_code.value,
                "detail": detail,
                "task_type": getattr(task, "task_type", "unknown"),
                "check_matrix": check_matrix,
                "coverage_meta": coverage_meta,
            }],
        )
        evidence_id = self.evidence_store.store(bundle)

        log_method = logger.warning if decision_code == DecisionCode.BLOCKED else logger.info
        if decision_code == DecisionCode.FAILED:
            log_method = logger.error
        log_method(
            "governance_pre_check",
            decision=decision_code.value,
            reason=reason_code.value,
            evidence_id=evidence_id,
            passed=passed,
        )

        return passed, decision_code.value, reason_code.value, evidence_id

    # ── Post-record ────────────────────────────────────────────────────── #

    def post_record(
        self,
        task: Any,
        result: dict[str, Any],
        pre_evidence_id: str,
    ) -> str:
        """
        Record post-execution evidence. Links to pre_evidence_id.

        Invariant: pre_evidence_id is required. Post without pre is forbidden.
        """
        if not pre_evidence_id:
            raise ValueError("post_record requires pre_evidence_id — post without pre is forbidden")

        prompt_hash = hashlib.sha256(
            str(result.get("reasoning", "")).encode()
        ).hexdigest()[:16]

        bundle = EvidenceBundle(
            trigger="GovernanceGate.post_record",
            actor="GovernanceGate",
            action=f"POST_RECORD:{DecisionCode.ALLOWED.value}",
            before_state=self.security_ctx.current.value,
            after_state=self.security_ctx.current.value,
            artifacts=[{
                "phase": PhaseCode.POST.value,
                "decision_code": DecisionCode.ALLOWED.value,
                "pre_evidence_id": pre_evidence_id,
                "task_type": getattr(task, "task_type", "unknown"),
                "prompt_hash": prompt_hash,
                "confidence": result.get("confidence", 0.0),
                "approved": result.get("approved", result.get("success", False)),
                "reasoning_hash": prompt_hash,
            }],
        )
        evidence_id = self.evidence_store.store(bundle)

        logger.info(
            "governance_post_record",
            decision=DecisionCode.ALLOWED.value,
            evidence_id=evidence_id,
            pre_evidence_id=pre_evidence_id,
        )

        return evidence_id

    # ── Post-record error ──────────────────────────────────────────────── #

    def post_record_error(
        self,
        task: Any,
        exception: Exception,
        pre_evidence_id: str,
    ) -> Optional[str]:
        """
        Record error evidence when LLM execution fails.
        FAILED decision_code with elevated severity for audit distinction.

        Invariant: pre_evidence_id is required.
        Fallback: if this method itself fails, logger.critical() ensures no silent failure.
        """
        if not pre_evidence_id:
            logger.critical(
                "governance_post_record_error_invariant_violation",
                error="pre_evidence_id is required but missing",
                exception_type=type(exception).__name__,
            )
            raise ValueError("post_record_error requires pre_evidence_id — post without pre is forbidden")

        try:
            bundle = EvidenceBundle(
                trigger="GovernanceGate.post_record_error",
                actor="GovernanceGate",
                action=f"POST_ERROR:{DecisionCode.FAILED.value}",
                before_state=self.security_ctx.current.value,
                after_state=self.security_ctx.current.value,
                artifacts=[{
                    "phase": PhaseCode.ERROR.value,
                    "decision_code": DecisionCode.FAILED.value,
                    "reason_code": ReasonCode.POST_EXCEPTION.value,
                    "error_severity": "CRITICAL",
                    "error_class": type(exception).__name__,
                    "pre_evidence_id": pre_evidence_id,
                    "task_type": getattr(task, "task_type", "unknown"),
                    "exception_message": str(exception),
                    "traceback_hash": hashlib.sha256(
                        traceback.format_exc().encode()
                    ).hexdigest()[:16],
                }],
            )
            evidence_id = self.evidence_store.store(bundle)

            logger.error(
                "governance_post_record_error",
                decision=DecisionCode.FAILED.value,
                reason=ReasonCode.POST_EXCEPTION.value,
                error_severity="CRITICAL",
                error_class=type(exception).__name__,
                evidence_id=evidence_id,
                pre_evidence_id=pre_evidence_id,
            )

            return evidence_id

        except Exception as fallback_exc:
            # Fallback: even if evidence storage fails, audit log must survive
            logger.critical(
                "governance_post_record_error_FALLBACK",
                original_exception=str(exception),
                fallback_exception=str(fallback_exc),
                pre_evidence_id=pre_evidence_id,
                task_type=getattr(task, "task_type", "unknown"),
                message="Evidence storage failed — this is the last audit line",
            )
            return None

    # ── Coverage computation ───────────────────────────────────────────── #

    @staticmethod
    def _compute_coverage(check_matrix: dict[str, dict[str, str]]) -> dict[str, int]:
        """Dynamically compute coverage meta from check_matrix. No hardcoding."""
        counts = {
            "total_checks": 0,
            "executed_checks": 0,
            "not_applicable_checks": 0,
            "deferred_checks": 0,
            "unimplemented_checks": 0,
        }
        for entry in check_matrix.values():
            counts["total_checks"] += 1
            status = entry.get("status", "")
            if status in (CheckStatus.PASSED.value, CheckStatus.FAILED.value):
                counts["executed_checks"] += 1
            elif status == CheckStatus.NOT_APPLICABLE.value:
                counts["not_applicable_checks"] += 1
            elif status == CheckStatus.DEFERRED.value:
                counts["deferred_checks"] += 1
            elif status == CheckStatus.UNIMPLEMENTED.value:
                counts["unimplemented_checks"] += 1
        return counts
