from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.api.routes import router as api_router
from app.api.routes.dashboard import router as dashboard_router

logger = get_logger(__name__)


def _create_governance_gate():
    """
    Create GovernanceGate singleton for DI into orchestrators.
    Returns None if governance is disabled (non-production only).

    Dual guard (intentional 2-layer defense):
      Layer 1: This function checks GovernanceGate._instance before creation.
      Layer 2: GovernanceGate.__init__ enforces singleton under _creation_lock.
    """
    if not settings.governance_enabled:
        return None

    from kdexter.ledger.forbidden_ledger import ForbiddenLedger
    from kdexter.audit.evidence_store import EvidenceStore
    from kdexter.state_machine.security_state import SecurityStateContext
    from app.agents.governance_gate import GovernanceGate

    # Layer 1: duplicate lifespan call detection
    if GovernanceGate._instance is not None:
        raise RuntimeError(
            "GovernanceGate already created — duplicate lifespan call detected "
            f"(existing gate_id={GovernanceGate._instance.gate_id})"
        )

    ledger = ForbiddenLedger()

    # Evidence backend selection based on configuration
    if settings.evidence_db_path:
        from kdexter.audit.backends.sqlite import SQLiteBackend
        backend = SQLiteBackend(settings.evidence_db_path)
        evidence_mode = "SQLITE_PERSISTED"
    else:
        backend = None  # EvidenceStore defaults to InMemoryBackend
        evidence_mode = "IN_MEMORY"

    store = EvidenceStore(backend=backend)
    security_ctx = SecurityStateContext()

    logger.info(
        "evidence_store_initialized",
        evidence_mode=evidence_mode,
        evidence_db_path=settings.evidence_db_path or "(none)",
        durability="DURABLE" if evidence_mode == "SQLITE_PERSISTED" else "NOT_DURABLE",
    )

    return GovernanceGate(
        forbidden_ledger=ledger,
        evidence_store=store,
        security_ctx=security_ctx,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    from app.core.logging import log_mode
    logger.info(
        "Starting trading system",
        env=settings.app_env,
        log_mode=log_mode,
        log_file_path=settings.log_file_path or "(none)",
        log_level=settings.log_level,
    )

    # Production fail-fast: governance must be enabled
    if settings.is_production and not settings.governance_enabled:
        raise RuntimeError(
            "FATAL: governance_enabled=False is not permitted in production. "
            "Set GOVERNANCE_ENABLED=true or remove the override."
        )

    # Create governance gate singleton
    gate = _create_governance_gate()
    app.state.governance_gate = gate

    # C-01: Runtime data source slots for dashboard read-only access
    app.state.loop_monitor = None
    app.state.work_state_ctx = None
    app.state.trust_registry = {}
    app.state.doctrine_registry = None

    # C-17/C-19: Receipt store with optional file persistence
    from app.core.notification_receipt_store import ReceiptStore
    receipt_file_backend = None
    receipt_mode = "IN_MEMORY"
    if settings.receipt_file_path:
        try:
            from app.core.notification_receipt_file_backend import ReceiptFileBackend
            receipt_file_backend = ReceiptFileBackend(settings.receipt_file_path)
            receipt_mode = "FILE_PERSISTED"
        except Exception:
            receipt_file_backend = None  # fail-closed: fallback to memory-only
            receipt_mode = "IN_MEMORY (file backend init failed)"
    app.state.receipt_store = ReceiptStore(file_backend=receipt_file_backend)
    logger.info(
        "receipt_store_initialized",
        receipt_mode=receipt_mode,
        receipt_file_path=settings.receipt_file_path or "(none)",
    )

    # C-23: Flow execution log
    from app.core.notification_flow_log import FlowLog
    app.state.flow_log = FlowLog()

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

# Dashboard: read-only operations board (Track 4)
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
    name="static",
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# C-03: Readiness and Startup probes (read-only introspection)

@app.get("/ready")
async def readiness_probe():
    """
    Readiness probe — reports whether critical subsystems are initialized.
    Returns 200 with ready=true when all checks pass, 503 otherwise.
    Read-only: no state mutation, no runtime method calls.
    """
    from fastapi.responses import JSONResponse

    checks = {}

    # Check 1: GovernanceGate initialized
    gate = getattr(app.state, "governance_gate", None)
    checks["governance_gate"] = gate is not None

    # Check 2: Evidence store accessible (via gate)
    if gate is not None:
        store = getattr(gate, "evidence_store", None)
        checks["evidence_store"] = store is not None
    else:
        checks["evidence_store"] = False

    # Check 3: Security context accessible (via gate)
    if gate is not None:
        sec_ctx = getattr(gate, "security_ctx", None)
        checks["security_context"] = sec_ctx is not None
    else:
        checks["security_context"] = False

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "ready": all_ready,
            "checks": checks,
        },
    )


@app.get("/startup")
async def startup_probe():
    """
    Startup probe — reports whether the application has completed initialization.
    Returns 200 with started=true when lifespan has completed, 503 otherwise.
    Read-only: no state mutation, no runtime method calls.
    """
    from fastapi.responses import JSONResponse

    checks = {}

    # Check 1: GovernanceGate exists (lifespan completed)
    gate = getattr(app.state, "governance_gate", None)
    governance_enabled = True
    try:
        from app.core.config import settings as _settings
        governance_enabled = _settings.governance_enabled
    except Exception:
        pass

    if governance_enabled:
        checks["governance_initialized"] = gate is not None
    else:
        checks["governance_initialized"] = True  # disabled = not required

    # Check 2: app.state slots exist (C-01 lifespan completed)
    checks["state_slots_initialized"] = hasattr(app.state, "loop_monitor")

    all_started = all(checks.values())
    status_code = 200 if all_started else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "started": all_started,
            "checks": checks,
        },
    )


# C-04: Degraded status endpoint (observation + judgment only, no recovery)

@app.get("/status")
async def degraded_status():
    """
    Unified status endpoint — distinguishes degraded from healthy/ready/unavailable.
    Observation and judgment only. No auto-recovery. No state mutation.

    Returns:
      overall_status: "healthy" | "ready" | "degraded" | "unavailable"
      liveness: "ok" | "fail"
      readiness: "ready" | "not_ready"
      startup: "complete" | "incomplete"
      degraded_reasons: [...] (empty when healthy)
      sources: { source_name: "available" | "unavailable" | "warning" | "critical" }
    """
    from fastapi.responses import JSONResponse

    degraded_reasons = []
    sources = {}

    # --- Liveness (trivially ok if we're responding) ---
    liveness = "ok"

    # --- Startup check ---
    gate = getattr(app.state, "governance_gate", None)
    governance_enabled = True
    try:
        from app.core.config import settings as _settings
        governance_enabled = _settings.governance_enabled
    except Exception:
        pass

    if governance_enabled:
        startup_ok = gate is not None
    else:
        startup_ok = True
    startup_ok = startup_ok and hasattr(app.state, "loop_monitor")
    startup = "complete" if startup_ok else "incomplete"

    # --- Readiness check (mirrors /ready logic without modifying it) ---
    readiness_checks = []
    readiness_checks.append(gate is not None if governance_enabled else True)
    if gate is not None:
        readiness_checks.append(getattr(gate, "evidence_store", None) is not None)
        readiness_checks.append(getattr(gate, "security_ctx", None) is not None)
    else:
        if governance_enabled:
            readiness_checks.extend([False, False])
    readiness = "ready" if all(readiness_checks) else "not_ready"

    # --- Source availability (C-01 runtime data sources) ---

    # Loop Monitor
    loop_monitor = getattr(app.state, "loop_monitor", None)
    if loop_monitor is None:
        sources["loop_monitor"] = "unavailable"
        degraded_reasons.append("loop_monitor: source unavailable")
    else:
        last_result = getattr(loop_monitor, "last_result", None)
        if last_result is None:
            sources["loop_monitor"] = "unavailable"
            degraded_reasons.append("loop_monitor: no result available")
        else:
            overall_health = getattr(last_result, "overall_health", None)
            health_val = overall_health.value if hasattr(overall_health, "value") else str(overall_health) if overall_health else None
            if health_val == "EXCEEDED" or health_val == "CRITICAL":
                sources["loop_monitor"] = "critical"
                degraded_reasons.append("loop_monitor: " + health_val)
            elif health_val == "WARNING":
                sources["loop_monitor"] = "warning"
                degraded_reasons.append("loop_monitor: WARNING")
            else:
                sources["loop_monitor"] = "available"

    # Work State
    work_state_ctx = getattr(app.state, "work_state_ctx", None)
    if work_state_ctx is None:
        sources["work_state"] = "unavailable"
        degraded_reasons.append("work_state: source unavailable")
    else:
        current = getattr(work_state_ctx, "current", None)
        current_val = current.value if hasattr(current, "value") else str(current) if current else None
        if current_val in ("FAILED", "BLOCKED", "ISOLATED"):
            sources["work_state"] = "critical"
            degraded_reasons.append("work_state: " + current_val)
        else:
            sources["work_state"] = "available"

    # Trust Registry
    trust_registry = getattr(app.state, "trust_registry", None)
    if trust_registry is None or not isinstance(trust_registry, dict) or len(trust_registry) == 0:
        sources["trust_state"] = "unavailable"
        degraded_reasons.append("trust_state: source unavailable")
    else:
        non_exec = 0
        for ctx in trust_registry.values():
            current = getattr(ctx, "current", None)
            if current and hasattr(current, "allows_execution") and not current.allows_execution():
                non_exec += 1
        if non_exec > 0:
            sources["trust_state"] = "warning"
            degraded_reasons.append("trust_state: " + str(non_exec) + " component(s) non-executable")
        else:
            sources["trust_state"] = "available"

    # Doctrine Registry
    doctrine_registry = getattr(app.state, "doctrine_registry", None)
    if doctrine_registry is None:
        sources["doctrine"] = "unavailable"
        degraded_reasons.append("doctrine: source unavailable")
    else:
        violation_count = 0
        if hasattr(doctrine_registry, "violation_count"):
            violation_count = doctrine_registry.violation_count()
        if violation_count > 0:
            sources["doctrine"] = "warning"
            degraded_reasons.append("doctrine: " + str(violation_count) + " violation(s)")
        else:
            sources["doctrine"] = "available"

    # --- Overall status judgment ---
    if startup != "complete":
        overall_status = "unavailable"
    elif readiness != "ready":
        overall_status = "unavailable"
    elif len(degraded_reasons) > 0:
        has_critical = any(s == "critical" for s in sources.values())
        overall_status = "degraded" if not has_critical else "degraded"
    else:
        overall_status = "healthy"

    return JSONResponse(
        status_code=200,
        content={
            "overall_status": overall_status,
            "liveness": liveness,
            "readiness": readiness,
            "startup": startup,
            "degraded_reasons": degraded_reasons,
            "sources": sources,
        },
    )
