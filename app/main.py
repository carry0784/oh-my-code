from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.routes import router as api_router

logger = get_logger(__name__)


def _create_governance_gate():
    """
    Create GovernanceGate singleton for DI into orchestrators.
    Returns None if governance is disabled (non-production only).
    """
    if not settings.governance_enabled:
        return None

    from kdexter.ledger.forbidden_ledger import ForbiddenLedger
    from kdexter.audit.evidence_store import EvidenceStore
    from kdexter.state_machine.security_state import SecurityStateContext
    from app.agents.governance_gate import GovernanceGate

    ledger = ForbiddenLedger()
    store = EvidenceStore()
    security_ctx = SecurityStateContext()

    return GovernanceGate(
        forbidden_ledger=ledger,
        evidence_store=store,
        security_ctx=security_ctx,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting trading system", env=settings.app_env)

    # Production fail-fast: governance must be enabled
    if settings.is_production and not settings.governance_enabled:
        raise RuntimeError(
            "FATAL: governance_enabled=False is not permitted in production. "
            "Set GOVERNANCE_ENABLED=true or remove the override."
        )

    # Create governance gate singleton
    gate = _create_governance_gate()
    app.state.governance_gate = gate

    if gate is not None:
        logger.info("governance_gate_initialized", governance_enabled=True)
    else:
        logger.warning(
            "governance_gate_disabled",
            governance_enabled=False,
            env=settings.app_env,
        )

    yield
    logger.info("Shutting down trading system")


app = FastAPI(
    title="AI Trading System",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
