from pydantic import BaseModel, Field


class AgentTask(BaseModel):
    task_type: str = Field(..., description="Type of task (analyze, validate, execute)")
    symbol: str | None = None
    exchange: str | None = None
    signal_id: str | None = None
    context: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    success: bool
    task_type: str
    result: dict
    reasoning: str | None = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    governance_evidence_id: str | None = None
    action_proposal_id: str | None = None
