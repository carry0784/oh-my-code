from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.signal_validator import SignalValidatorAgent
from app.agents.risk_manager import RiskManagerAgent
from app.schemas.agent import AgentTask, AgentResponse
from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.agents.governance_gate import GovernanceGate

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(
        self,
        db: AsyncSession,
        governance_gate: Optional[GovernanceGate] = None,
    ):
        self.db = db
        self.governance_gate = governance_gate
        self.signal_validator = SignalValidatorAgent()
        self.risk_manager = RiskManagerAgent()

        # governance_enabled=True + gate=None → immediate failure (not a warning)
        governance_enabled = getattr(settings, "governance_enabled", True)
        if governance_enabled and governance_gate is None:
            raise RuntimeError(
                "governance_enabled=True but governance_gate is None. "
                "GovernanceGate is a required dependency when governance is enabled."
            )

        if not governance_enabled and governance_gate is None:
            logger.warning(
                "governance_bypass_active",
                message="governance_enabled=False — GovernanceGate is not connected. "
                "Agent execution proceeds without governance checks.",
            )

    # ── Governance flow (shared by analyze & execute) ──────────────────── #

    def _governance_pre_check(self, task: AgentTask) -> Optional[AgentResponse]:
        """
        Run GovernanceGate.pre_check if gate is present.
        Returns AgentResponse on block, or None to proceed.
        Sets self._pre_evidence_id for post-record linkage.
        """
        self._pre_evidence_id: Optional[str] = None

        if self.governance_gate is None:
            return None

        passed, decision_code, reason_code, evidence_id = self.governance_gate.pre_check(task)
        self._pre_evidence_id = evidence_id

        if not passed:
            return AgentResponse(
                success=False,
                task_type=task.task_type,
                result={
                    "stage": "governance_pre_check",
                    "decision_code": decision_code,
                    "reason_code": reason_code,
                },
                reasoning=f"Governance pre-check blocked: {reason_code}",
                confidence=0.0,
                governance_evidence_id=evidence_id,
            )

        return None

    def _governance_post_record(
        self, task: AgentTask, result: dict[str, Any],
    ) -> Optional[str]:
        """Record post-execution evidence. Returns evidence_id or None."""
        if self.governance_gate is None or self._pre_evidence_id is None:
            return None
        return self.governance_gate.post_record(task, result, self._pre_evidence_id)

    def _governance_post_error(
        self, task: AgentTask, exc: Exception,
    ) -> Optional[str]:
        """Record error evidence. Returns evidence_id or None."""
        if self.governance_gate is None or self._pre_evidence_id is None:
            return None
        return self.governance_gate.post_record_error(task, exc, self._pre_evidence_id)

    # ── analyze ────────────────────────────────────────────────────────── #

    async def analyze(self, task: AgentTask) -> AgentResponse:
        # [1] Governance pre-check — LLM call blocked if this fails
        blocked = self._governance_pre_check(task)
        if blocked is not None:
            return blocked

        # [2] LLM agent execution
        try:
            context = task.context.copy()
            context["symbol"] = task.symbol
            context["exchange"] = task.exchange

            if task.task_type == "validate_signal":
                result = await self.signal_validator.execute(context)
                result["_llm_usage"] = getattr(self.signal_validator, "last_usage", {})
            elif task.task_type == "risk_assessment":
                result = await self.risk_manager.execute(context)
                result["_llm_usage"] = getattr(self.risk_manager, "last_usage", {})
            else:
                result = {"error": f"Unknown task type: {task.task_type}"}

            # [3] Governance post-record (success path)
            post_eid = self._governance_post_record(task, result)

            return AgentResponse(
                success="error" not in result,
                task_type=task.task_type,
                result=result,
                reasoning=result.get("reasoning"),
                confidence=result.get("confidence", 0.0),
                governance_evidence_id=post_eid or self._pre_evidence_id,
            )

        except Exception as exc:
            # [4] Governance post-record-error (exception path)
            error_eid = self._governance_post_error(task, exc)
            logger.error("analyze_llm_exception", exception=str(exc), task_type=task.task_type)

            return AgentResponse(
                success=False,
                task_type=task.task_type,
                result={"stage": "llm_execution", "error": str(exc)},
                reasoning=f"LLM execution failed: {type(exc).__name__}",
                confidence=0.0,
                governance_evidence_id=error_eid or self._pre_evidence_id,
            )

    # ── execute ────────────────────────────────────────────────────────── #

    async def execute(self, task: AgentTask) -> AgentResponse:
        # [1] Governance pre-check — LLM call blocked if this fails
        blocked = self._governance_pre_check(task)
        if blocked is not None:
            return blocked

        # [2] LLM agent execution
        try:
            context = task.context.copy()

            # Step 1: Validate signal if present
            if task.signal_id:
                from app.services.signal_service import SignalService
                signal_service = SignalService(self.db)
                signal = await signal_service.get_signal(task.signal_id)
                if signal:
                    validation = await self.signal_validator.validate(signal)
                    validation["_llm_usage"] = getattr(self.signal_validator, "last_usage", {})
                    if not validation.get("approved"):
                        post_eid = self._governance_post_record(task, validation)
                        return AgentResponse(
                            success=False,
                            task_type="execute",
                            result={"stage": "validation", "validation": validation},
                            reasoning=validation.get("reasoning"),
                            confidence=validation.get("confidence", 0.0),
                            governance_evidence_id=post_eid or self._pre_evidence_id,
                        )
                    context["signal"] = signal

            # Step 2: Risk assessment
            risk_result = await self.risk_manager.execute(context)
            risk_result["_llm_usage"] = getattr(self.risk_manager, "last_usage", {})
            if not risk_result.get("approved"):
                post_eid = self._governance_post_record(task, risk_result)
                return AgentResponse(
                    success=False,
                    task_type="execute",
                    result={"stage": "risk_assessment", "risk": risk_result},
                    reasoning=risk_result.get("reasoning"),
                    confidence=0.0,
                    governance_evidence_id=post_eid or self._pre_evidence_id,
                )

            # Step 3: Would execute order here
            logger.info("Execution pipeline approved", task=task.task_type)
            final_result = {
                "stage": "ready",
                "adjusted_size": risk_result.get("position_size"),
            }

            # [3] Governance post-record (success path)
            post_eid = self._governance_post_record(task, {**final_result, **risk_result})

            return AgentResponse(
                success=True,
                task_type="execute",
                result=final_result,
                reasoning="Signal validated and risk approved",
                confidence=risk_result.get("confidence", 0.8),
                governance_evidence_id=post_eid or self._pre_evidence_id,
            )

        except Exception as exc:
            # [4] Governance post-record-error (exception path)
            error_eid = self._governance_post_error(task, exc)
            logger.error("execute_llm_exception", exception=str(exc), task_type=task.task_type)

            return AgentResponse(
                success=False,
                task_type="execute",
                result={"stage": "llm_execution", "error": str(exc)},
                reasoning=f"LLM execution failed: {type(exc).__name__}",
                confidence=0.0,
                governance_evidence_id=error_eid or self._pre_evidence_id,
            )
