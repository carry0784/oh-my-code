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
    from app.agents.action_ledger import ActionLedger
    from app.services.execution_ledger import ExecutionLedger
    from app.services.submit_ledger import SubmitLedger
    from app.services.order_executor import OrderExecutor

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(
        self,
        db: AsyncSession,
        governance_gate: Optional[GovernanceGate] = None,
        action_ledger: Optional[ActionLedger] = None,
    ):
        self.db = db
        self.governance_gate = governance_gate
        self.action_ledger = action_ledger
        self.execution_ledger: Optional[ExecutionLedger] = None
        self.submit_ledger: Optional[SubmitLedger] = None
        self.order_executor: Optional[OrderExecutor] = None
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

            # Step 2.5: Agent Apply Guard (before execution commitment)
            _action_proposal = None
            if self.action_ledger is not None:
                _cost_ctrl = getattr(self.governance_gate, "_cost_controller", None) if self.governance_gate else None
                guard_passed, _action_proposal = self.action_ledger.propose_and_guard(
                    task_type=task.task_type,
                    symbol=task.symbol,
                    exchange=task.exchange,
                    risk_result=risk_result,
                    pre_evidence_id=self._pre_evidence_id,
                    cost_controller=_cost_ctrl,
                )
                if not guard_passed:
                    post_eid = self._governance_post_record(task, {
                        "stage": "agent_apply_guard",
                        "proposal_id": _action_proposal.proposal_id,
                        "guard_reasons": _action_proposal.guard_reasons,
                    })
                    return AgentResponse(
                        success=False,
                        task_type="execute",
                        result={"stage": "agent_apply_guard", "proposal": _action_proposal.to_dict()},
                        reasoning=f"Agent Apply Guard blocked: {_action_proposal.guard_reasons}",
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

            # Step 3.5: Record agent approval receipt
            if self.action_ledger is not None and _action_proposal is not None:
                self.action_ledger.record_receipt(
                    proposal=_action_proposal,
                    final_result=final_result,
                    post_evidence_id=post_eid,
                )

            # Step 4: Execution Guard (final boundary before execution_ready)
            _exec_proposal = None
            if self.execution_ledger is not None:
                _cost_ctrl = getattr(self.governance_gate, "cost_controller", None) if self.governance_gate else None
                _sec_ctx = getattr(self.governance_gate, "security_ctx", None) if self.governance_gate else None
                _agent_status = _action_proposal.status if _action_proposal else "UNKNOWN"
                _agent_pid = _action_proposal.proposal_id if _action_proposal else "NONE"

                exec_passed, _exec_proposal = self.execution_ledger.propose_and_guard(
                    task_type=task.task_type,
                    symbol=task.symbol,
                    exchange=task.exchange,
                    agent_proposal_id=_agent_pid,
                    agent_proposal_status=_agent_status,
                    risk_result={**risk_result, "adjusted_size": final_result.get("adjusted_size")},
                    pre_evidence_id=self._pre_evidence_id,
                    cost_controller=_cost_ctrl,
                    security_ctx=_sec_ctx,
                )
                if not exec_passed:
                    return AgentResponse(
                        success=False,
                        task_type="execute",
                        result={"stage": "execution_guard", "proposal": _exec_proposal.to_dict()},
                        reasoning=f"Execution Guard blocked: {_exec_proposal.guard_reasons}",
                        confidence=0.0,
                        governance_evidence_id=post_eid or self._pre_evidence_id,
                    )

                # Step 4.5: Record execution receipt (execution_ready becomes True)
                self.execution_ledger.record_receipt(
                    proposal=_exec_proposal,
                    final_result=final_result,
                    post_evidence_id=post_eid,
                )

            # Step 5: Submit Guard (final boundary before submit_ready)
            _submit_proposal = None
            if self.submit_ledger is not None:
                _exec_status = _exec_proposal.status if _exec_proposal else "UNKNOWN"
                _exec_pid = _exec_proposal.proposal_id if _exec_proposal else "NONE"
                _agent_pid = _action_proposal.proposal_id if _action_proposal else "NONE"

                submit_passed, _submit_proposal = self.submit_ledger.propose_and_guard(
                    task_type=task.task_type,
                    symbol=task.symbol,
                    exchange=task.exchange,
                    agent_proposal_id=_agent_pid,
                    execution_proposal_id=_exec_pid,
                    execution_proposal_status=_exec_status,
                    risk_result={**risk_result, "adjusted_size": final_result.get("adjusted_size")},
                    pre_evidence_id=self._pre_evidence_id,
                    cost_controller=_cost_ctrl,
                    security_ctx=_sec_ctx,
                )
                if not submit_passed:
                    return AgentResponse(
                        success=False,
                        task_type="execute",
                        result={"stage": "submit_guard", "proposal": _submit_proposal.to_dict()},
                        reasoning=f"Submit Guard blocked: {_submit_proposal.guard_reasons}",
                        confidence=0.0,
                        governance_evidence_id=post_eid or self._pre_evidence_id,
                    )

                # Step 5.5: Record submit receipt (submit_ready becomes True)
                self.submit_ledger.record_receipt(
                    proposal=_submit_proposal,
                    final_result=final_result,
                    post_evidence_id=post_eid,
                )

            # Step 6: Execute Order (optional, only if order_executor connected)
            _order_result = None
            if self.order_executor is not None and _submit_proposal is not None:
                _order_result = await self.order_executor.execute_order(
                    submit_proposal=_submit_proposal,
                    side=task.context.get("side", "buy"),
                    order_type=task.context.get("order_type", "market"),
                    price=task.context.get("price"),
                    dry_run=task.context.get("dry_run", True),  # default dry_run=True safety
                )

            return AgentResponse(
                success=True,
                task_type="execute",
                result={
                    **final_result,
                    "execution_ready": _exec_proposal.execution_ready if _exec_proposal else None,
                    "execution_proposal_id": _exec_proposal.proposal_id if _exec_proposal else None,
                    "submit_ready": _submit_proposal.submit_ready if _submit_proposal else None,
                    "submit_proposal_id": _submit_proposal.proposal_id if _submit_proposal else None,
                    "order_id": _order_result.order_id if _order_result else None,
                    "order_status": _order_result.status if _order_result else None,
                    "dry_run": _order_result.dry_run if _order_result else None,
                },
                reasoning="Signal validated, risk approved, execution guard passed, submit guard passed",
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
