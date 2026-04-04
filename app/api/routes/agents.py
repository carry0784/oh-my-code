from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.agent import AgentTask, AgentResponse
from app.agents.orchestrator import AgentOrchestrator

router = APIRouter()


def _get_governance_gate(request: Request):
    """Retrieve GovernanceGate singleton from app state (created in lifespan)."""
    return getattr(request.app.state, "governance_gate", None)


@router.post("/analyze", response_model=AgentResponse)
async def analyze_market(
    task: AgentTask,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    gate = _get_governance_gate(request)
    orchestrator = AgentOrchestrator(db, governance_gate=gate)
    return await orchestrator.analyze(task)


@router.post("/execute", response_model=AgentResponse)
async def execute_strategy(
    task: AgentTask,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    gate = _get_governance_gate(request)
    orchestrator = AgentOrchestrator(db, governance_gate=gate)
    return await orchestrator.execute(task)


@router.get("/status")
async def agent_status():
    return {
        "agents": ["signal_validator", "risk_manager", "executor"],
        "status": "ready",
    }


# ── Debug-only governance evidence endpoint ────────────────────────────── #
# Registered only when debug=True AND non-production.
# In production this route does not exist → 404.

if settings.debug and not settings.is_production:

    @router.get("/governance/evidence")
    async def get_governance_evidence(
        request: Request,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        """
        Debug-only: list recent governance evidence bundles.
        No prompt/response/reasoning originals exposed — hash and status only.
        """
        gate = _get_governance_gate(request)
        if gate is None:
            return {"bundles": [], "orphan_count": 0, "total": 0}

        all_bundles = gate.evidence_store.list_all()
        recent = all_bundles[-limit:] if len(all_bundles) > limit else all_bundles

        # Collect pre evidence IDs and linked post/error IDs for orphan detection
        pre_ids: set[str] = set()
        linked_pre_ids: set[str] = set()

        sanitized = []
        for b in recent:
            entry: dict = {
                "evidence_id": b.bundle_id,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "actor": b.actor,
                "action": b.action,
            }

            # Extract structured fields from artifacts (first item)
            if b.artifacts:
                art = b.artifacts[0] if isinstance(b.artifacts, list) and b.artifacts else {}
                if isinstance(art, dict):
                    entry["phase_code"] = art.get("phase")
                    entry["decision_code"] = art.get("decision_code")
                    entry["reason_code"] = art.get("reason_code")
                    entry["coverage_summary"] = art.get("coverage_meta")

                    # Track pre/post linkage for orphan count
                    phase = art.get("phase")
                    if phase == "PRE":
                        pre_ids.add(b.bundle_id)
                    pre_link = art.get("pre_evidence_id")
                    if pre_link and phase in ("POST", "ERROR"):
                        linked_pre_ids.add(pre_link)

            sanitized.append(entry)

        # Orphan count: pre evidence with no corresponding post/error
        orphan_count = len(pre_ids - linked_pre_ids)

        return {
            "bundles": sanitized,
            "orphan_count": orphan_count,
            "total": len(all_bundles),
        }
