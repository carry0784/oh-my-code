from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.agent import AgentTask, AgentResponse
from app.agents.orchestrator import AgentOrchestrator
from exchanges.factory import ExchangeFactory

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_governance_gate(request: Request):
    """Retrieve GovernanceGate singleton from app state (created in lifespan)."""
    return getattr(request.app.state, "governance_gate", None)


# ── PPF Shadow Connect (SHADOW-CONNECT-001) ─────────────────────────── #


async def _build_ppf_gate_handler(
    symbol: str,
    exchange: str,
) -> Optional["PPFGateHandler"]:
    """Build PPFGateHandler for shadow mode.

    Authority: SHADOW-CONNECT-001
    Scope: route-level direct wiring (Method A)
    Manifest: SHADOW_MANIFEST (enforce_deny=False)
    Failure: returns None + warning log (supplementary gate fallback)

    S1 strategy: pre-fetch OHLCV via public API, wrap as sync closure.
    """
    try:
        from strategies.ppf.constants import MarketProfile
        from strategies.ppf.gate import PPFGate
        from strategies.ppf.parameters import PPFParameters
        from strategies.ppf.ppf_gate_handler import (
            PPFGateHandler,
            SHADOW_MANIFEST,
        )
        from strategies.ppf.session_ledger import (
            SessionBudgetConfig,
            SessionFailureBudgetLedger,
        )

        # 1. PPFParameters (defaults only, no tuning)
        params = PPFParameters(market_profile=MarketProfile.M1_CRYPTO_FUTURES)

        # 2. PPFGate
        asset_tag = f"{exchange}:{symbol}:1h"
        ppf_gate = PPFGate(params=params, asset_timeframe_tag=asset_tag)

        # 3. SessionFailureBudgetLedger
        session_ledger = SessionFailureBudgetLedger(config=SessionBudgetConfig())

        # 4. ohlcv_provider (S1: pre-fetch + closure)
        ohlcv_closure = await _build_ohlcv_closure(symbol, exchange)

        # 5. PPFGateHandler (SHADOW_MANIFEST default)
        handler = PPFGateHandler(
            ppf_gate=ppf_gate,
            session_ledger=session_ledger,
            ohlcv_provider=ohlcv_closure,
            manifest=SHADOW_MANIFEST,
        )
        return handler

    except Exception as exc:
        logger.warning(
            "ppf_shadow_connect_failed",
            extra={
                "symbol": symbol,
                "exchange": exchange,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return None


async def _build_ohlcv_closure(
    symbol: str,
    exchange: str,
):
    """Build sync ohlcv_provider closure via S1 pre-fetch strategy.

    Fetches OHLCV via public read-only API, converts to numpy arrays,
    and wraps as a sync callable returning cached data.

    On fetch failure: returns lambda: None (fail-closed -> DATA_MISSING path).
    """
    try:
        client = ExchangeFactory.create(exchange)
        raw_bars = await client.fetch_ohlcv(symbol, timeframe="1h", limit=100)

        if not raw_bars or len(raw_bars) == 0:
            return lambda: None

        # Convert to numpy arrays (closed bars only)
        highs = np.array([bar[2] for bar in raw_bars], dtype=np.float64)
        lows = np.array([bar[3] for bar in raw_bars], dtype=np.float64)
        closes = np.array([bar[4] for bar in raw_bars], dtype=np.float64)
        volumes = np.array([bar[5] for bar in raw_bars], dtype=np.float64)

        # Cached sync closure
        return lambda: (highs, lows, closes, volumes)

    except Exception as exc:
        logger.warning(
            "ppf_ohlcv_fetch_failed",
            extra={
                "symbol": symbol,
                "exchange": exchange,
                "error": str(exc),
            },
        )
        return lambda: None


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

    # PPF shadow connect (SHADOW-CONNECT-001): attribute injection
    handler = await _build_ppf_gate_handler(task.symbol, task.exchange)
    orchestrator.ppf_gate_handler = handler

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

    @router.get("/governance/monitor")
    async def get_governance_monitor():
        """
        G-MON: On-demand governance monitor report.
        Returns 6-indicator snapshot (OK/WARN/FAIL).
        Read-only. No state modification.
        """
        from app.core.governance_monitor import run_governance_monitor

        report = run_governance_monitor()
        return report.to_dict()

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
