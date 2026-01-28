from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent import AgentTask, AgentResponse
from app.agents.orchestrator import AgentOrchestrator

router = APIRouter()


@router.post("/analyze", response_model=AgentResponse)
async def analyze_market(
    task: AgentTask,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = AgentOrchestrator(db)
    return await orchestrator.analyze(task)


@router.post("/execute", response_model=AgentResponse)
async def execute_strategy(
    task: AgentTask,
    db: AsyncSession = Depends(get_db),
):
    orchestrator = AgentOrchestrator(db)
    return await orchestrator.execute(task)


@router.get("/status")
async def agent_status():
    return {
        "agents": ["signal_validator", "risk_manager", "executor"],
        "status": "ready",
    }
