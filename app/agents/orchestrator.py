from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.signal_validator import SignalValidatorAgent
from app.agents.risk_manager import RiskManagerAgent
from app.schemas.agent import AgentTask, AgentResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.signal_validator = SignalValidatorAgent()
        self.risk_manager = RiskManagerAgent()

    async def analyze(self, task: AgentTask) -> AgentResponse:
        context = task.context.copy()
        context["symbol"] = task.symbol
        context["exchange"] = task.exchange

        if task.task_type == "validate_signal":
            result = await self.signal_validator.execute(context)
        elif task.task_type == "risk_assessment":
            result = await self.risk_manager.execute(context)
        else:
            result = {"error": f"Unknown task type: {task.task_type}"}

        return AgentResponse(
            success="error" not in result,
            task_type=task.task_type,
            result=result,
            reasoning=result.get("reasoning"),
            confidence=result.get("confidence", 0.0),
        )

    async def execute(self, task: AgentTask) -> AgentResponse:
        # Full execution pipeline: validate -> risk check -> execute
        context = task.context.copy()

        # Step 1: Validate signal if present
        if task.signal_id:
            from app.services.signal_service import SignalService
            signal_service = SignalService(self.db)
            signal = await signal_service.get_signal(task.signal_id)
            if signal:
                validation = await self.signal_validator.validate(signal)
                if not validation.get("approved"):
                    return AgentResponse(
                        success=False,
                        task_type="execute",
                        result={"stage": "validation", "validation": validation},
                        reasoning=validation.get("reasoning"),
                        confidence=validation.get("confidence", 0.0),
                    )
                context["signal"] = signal

        # Step 2: Risk assessment
        risk_result = await self.risk_manager.execute(context)
        if not risk_result.get("approved"):
            return AgentResponse(
                success=False,
                task_type="execute",
                result={"stage": "risk_assessment", "risk": risk_result},
                reasoning=risk_result.get("reasoning"),
                confidence=0.0,
            )

        # Step 3: Would execute order here
        logger.info("Execution pipeline approved", task=task.task_type)
        return AgentResponse(
            success=True,
            task_type="execute",
            result={
                "stage": "ready",
                "adjusted_size": risk_result.get("position_size"),
            },
            reasoning="Signal validated and risk approved",
            confidence=risk_result.get("confidence", 0.8),
        )
