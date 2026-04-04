"""
K-Dexter Operations Dashboard — Read-Only Monitoring Board
Track 4: L0/L1 운영 대시보드

Baseline: governance-go-baseline (7eb9ad8)
Rules:
  - NO write actions, NO trade execution, NO order submission
  - Read-only data retrieval from existing services
  - Missing data shown as "-" or "미연결", never faked as 0
  - No raw prompt/reasoning/error_class exposure
  - BLOCKED/FAILED/ALLOWED meaning preserved per Visualization Constitution
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.position import Position
from app.models.order import Order, OrderStatus
from app.models.trade import Trade
from app.models.signal import Signal, SignalStatus
from app.models.asset_snapshot import AssetSnapshot
from app.schemas.alert_schema import AlertSummaryResponse
from app.schemas.check_schema import CheckSummaryResponse
from app.schemas.preflight_schema import RecoveryPreflightResult, IncidentPlaybackResult
from app.schemas.execution_gate_schema import ExecutionGateResult
from app.schemas.operator_approval_schema import OperatorApprovalReceipt
from app.schemas.execution_policy_schema import ExecutionPolicyResult
from app.schemas.executor_schema import ExecutionReceipt
from app.schemas.executor_activation_schema import ActivationReceipt
from app.schemas.micro_executor_schema import DispatchReceipt
from app.schemas.ai_assist_schema import AIAssistSources
from app.schemas.market_feed_schema import MarketFeedResponse
from app.schemas.ops_aggregate_schema import OpsAggregateResponse, OpsHealth
from app.schemas.governance_summary_schema import GovernanceSummaryResponse, GovernanceHealth
from app.schemas.alert_summary_schema import AlertSummaryDetailResponse, AlertHealth
from app.core.constitution_alert_level import (
    convert_receipt_to_alert,
    convert_flow_entry_to_alert,
)
from app.schemas.ops_status import (
    OpsStatusResponse,
    GlobalStatusBar,
    IntegrityPanel,
    TradingSafetyPanel,
    IncidentEvidencePanel,
    SystemStatus,
    SystemStatusWord,
    DualLock,
    OpsScore,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Exchange registry — canonical names used across all dashboard endpoints
# ---------------------------------------------------------------------------
_EXCHANGES = ["binance", "upbit", "bitget", "kis", "kiwoom"]

router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    """Serve the operations dashboard HTML page."""
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "debug_mode": settings.debug and not settings.is_production,
        },
    )


@router.get("/api/data/v2", include_in_schema=False)
async def dashboard_data_v2(db: AsyncSession = Depends(get_db)):
    """
    Read-only v2 data endpoint for dual-dashboard.
    Includes all v1 data plus: recent_events, open_orders, signal_summary,
    venue_freshness.  No agent_analysis / blocked-fields / reasoning / error_class
    exposure (N-01 ~ N-12).
    """
    # Reuse all v1 data assembly
    exchange_data = {}
    for ex in _EXCHANGES:
        exchange_data[ex] = await _get_exchange_panel_data(db, ex)

    all_positions = []
    any_connected = False
    for exd in exchange_data.values():
        all_positions.extend(exd.get("positions", []))
        if exd["status"] == "connected":
            any_connected = True

    total_pnl = None
    total_value = None
    if any_connected:
        total_pnl = sum(p.get("unrealized_pnl", 0) or 0 for p in all_positions)
        total_value = sum(
            (p.get("entry_price", 0) or 0) * (p.get("quantity", 0) or 0) for p in all_positions
        )

    trade_count_result = await db.execute(select(func.count(Trade.id)))
    total_trade_count = trade_count_result.scalar() or 0

    governance_info = _get_governance_info()
    time_windows = await _get_time_window_stats(db)

    # v2-only data
    recent_events = await _get_recent_events(db)
    open_orders = await _get_open_orders_by_exchange(db)
    signal_summary = await _get_signal_summary(db)
    venue_freshness = await _get_venue_freshness(db)

    result = {}
    for ex in _EXCHANGES:
        result[ex] = exchange_data[ex]

    result["stats"] = {
        "total_value": total_value,
        "trade_count": total_trade_count,
        "unrealized_pnl": total_pnl,
        "windows": time_windows,
    }
    result["governance"] = governance_info
    result["recent_events"] = recent_events
    result["open_orders"] = open_orders
    result["signal_summary"] = signal_summary
    result["venue_freshness"] = venue_freshness
    result["quote_data"] = await _get_quote_data(exchange_data)

    # C-01: Runtime data sources for AI Workspace
    result["loop_monitor"] = _get_loop_monitor_info()
    result["work_state"] = _get_work_state_info()
    result["trust_state"] = _get_trust_state_info()
    result["doctrine"] = _get_doctrine_info()

    # C-08: Source freshness summary
    result["source_freshness"] = _get_source_freshness_summary(result)

    # B-08: AI Assist data sources (read-only, ops summary)
    try:
        from app.core.ai_assist_source import collect_ai_assist_sources

        ai_sources = collect_ai_assist_sources()
        # Enrich with async-only data from v2 payload
        sig = signal_summary or {}
        ai_sources.signal_pipeline.total_24h = sig.get("total", 0)
        ai_sources.signal_pipeline.validated = sig.get("validated", 0)
        ai_sources.signal_pipeline.rejected = sig.get("rejected", 0)
        ai_sources.signal_pipeline.executed = sig.get("executed", 0)
        ai_sources.signal_pipeline.pending = sig.get("pending", 0)
        total_sig = sig.get("total", 0)
        if total_sig > 0:
            ai_sources.signal_pipeline.rejection_rate = round(sig.get("rejected", 0) / total_sig, 4)
        ai_sources.position_overview.total_positions = len(all_positions)
        ai_sources.position_overview.total_value = total_value
        ai_sources.position_overview.unrealized_pnl = total_pnl
        ai_sources.position_overview.exchanges_connected = sum(
            1 for ex in _EXCHANGES if exchange_data.get(ex, {}).get("status") == "connected"
        )
        result["ai_assist_sources"] = ai_sources.model_dump()
    except Exception:
        result["ai_assist_sources"] = None

    # B-09: Market feed summary (read-only, from existing quote_data)
    try:
        from app.core.market_feed_service import build_market_feed_from_quote_data

        mf = build_market_feed_from_quote_data(result.get("quote_data"))
        result["market_feed"] = mf.model_dump()
    except Exception:
        result["market_feed"] = None

    # B-10: Ops health lightweight summary (4 fields only)
    try:
        from app.core.ops_aggregate_service import build_ops_health

        result["ops_health"] = build_ops_health().model_dump()
    except Exception:
        result["ops_health"] = None

    # B-11: Governance health lightweight summary
    try:
        from app.core.governance_summary_service import build_governance_health

        result["governance_health"] = build_governance_health().model_dump()
    except Exception:
        result["governance_health"] = None

    # B-13: Alert health lightweight summary
    try:
        from app.core.alert_summary_service import build_alert_health

        result["alert_health"] = build_alert_health().model_dump()
    except Exception:
        result["alert_health"] = None

    # C-09: Source provenance metadata
    result["provenance"] = _get_provenance_metadata(result)

    # 4-Tier Seal Chain Board (lightweight embed)
    try:
        import app.main as main_module
        from app.services.four_tier_board_service import build_four_tier_board

        app_inst = main_module.app
        board = build_four_tier_board(
            action_ledger=getattr(app_inst.state, "action_ledger", None),
            execution_ledger=getattr(app_inst.state, "execution_ledger", None),
            submit_ledger=getattr(app_inst.state, "submit_ledger", None),
            order_executor=getattr(app_inst.state, "order_executor", None),
        )
        result["four_tier_board"] = board.model_dump()
    except Exception:
        result["four_tier_board"] = None

    return result


# C-13: Export-friendly incident snapshot
@router.get("/api/snapshot", include_in_schema=False)
async def incident_snapshot(db: AsyncSession = Depends(get_db)):
    """
    Compact, export-friendly incident snapshot.
    Re-combines existing v2 data into a single summary suitable for
    alerts, logs, external handoff, or post-restart comparison.
    Read-only. No new queries beyond what v2 already performs.
    No hidden reasoning, no debug traces.
    """
    # Reuse v2 data assembly
    v2 = await dashboard_data_v2(db)
    snapshot = _build_incident_snapshot(v2)

    # C-14: Attach routing decision
    try:
        from app.core.alert_router import route_snapshot

        snapshot["routing"] = route_snapshot(snapshot)
    except Exception:
        snapshot["routing"] = {
            "channels": [],
            "severity_tier": "unknown",
            "reason": "router_unavailable",
        }

    return snapshot


# C-17: Receipt review endpoint
@router.get("/api/receipts", include_in_schema=False)
async def receipt_review(limit: int = 10):
    """
    Read-only receipt review endpoint.
    Returns recent notification receipts from in-memory store.
    No DB dependency. Fail-closed.
    """
    try:
        import app.main as main_module

        app_instance = main_module.app
        store = getattr(app_instance.state, "receipt_store", None)
        if store is None:
            return {"receipts": [], "total": 0, "available": False}
        return {
            "receipts": store.list_receipts(limit=min(limit, 50)),
            "total": store.count(),
            "available": True,
        }
    except Exception:
        return {"receipts": [], "total": 0, "available": False, "error": True}


# C-23: Flow log review endpoint
@router.get("/api/flow-log", include_in_schema=False)
async def flow_log_review(limit: int = 10):
    """
    Read-only notification flow execution log.
    Returns recent flow results from in-memory log.
    No DB dependency. Fail-closed.
    """
    try:
        import app.main as main_module

        app_instance = main_module.app
        flow_log = getattr(app_instance.state, "flow_log", None)
        if flow_log is None:
            return {"entries": [], "total": 0, "available": False}
        return {
            "entries": flow_log.list_entries(limit=min(limit, 50)),
            "total": flow_log.count(),
            "available": True,
        }
    except Exception:
        return {"entries": [], "total": 0, "available": False, "error": True}


# C-24: Notification audit export bundle
@router.get("/api/audit-export", include_in_schema=False)
async def audit_export(limit: int = 20):
    """
    Compact audit export bundle combining recent flow executions and receipts.
    Suitable for external handoff, post-incident review, or audit archival.
    Read-only. No DB dependency. Fail-closed.
    No hidden reasoning, no debug traces.
    """
    now = datetime.now(timezone.utc)

    bundle = {
        "bundle_version": "C-24",
        "generated_at": now.isoformat(),
        "flow_log": {"entries": [], "total": 0, "available": False},
        "receipts": {"entries": [], "total": 0, "available": False},
        "summary": {
            "total_flows": 0,
            "total_receipts": 0,
            "sent_count": 0,
            "suppressed_count": 0,
            "escalated_count": 0,
            "failed_count": 0,
            "top_severity": "clear",
        },
    }

    try:
        import app.main as main_module

        app_instance = main_module.app

        # Flow log
        flow_log = getattr(app_instance.state, "flow_log", None)
        if flow_log is not None:
            entries = flow_log.list_entries(limit=min(limit, 50))
            bundle["flow_log"] = {
                "entries": entries,
                "total": flow_log.count(),
                "available": True,
            }
            bundle["summary"]["total_flows"] = flow_log.count()

            # Compute summary from entries
            severity_order = {"critical": 0, "high": 1, "low": 2, "clear": 3}
            top_sev = "clear"
            for e in entries:
                action = e.get("policy_action", "")
                if action == "send":
                    bundle["summary"]["sent_count"] += 1
                elif action == "suppress":
                    bundle["summary"]["suppressed_count"] += 1
                elif action == "escalate":
                    bundle["summary"]["escalated_count"] += 1
                if e.get("error_count", 0) > 0:
                    bundle["summary"]["failed_count"] += 1
                # Track top severity from routing
                sev = e.get("severity_tier", "clear") if hasattr(e, "get") else "clear"
                # Use policy_urgent as proxy for critical
                if e.get("policy_urgent"):
                    sev = "critical"
                if severity_order.get(sev, 9) < severity_order.get(top_sev, 9):
                    top_sev = sev
            bundle["summary"]["top_severity"] = top_sev

        # Receipts
        receipt_store = getattr(app_instance.state, "receipt_store", None)
        if receipt_store is not None:
            receipts = receipt_store.list_receipts(limit=min(limit, 50))
            bundle["receipts"] = {
                "entries": receipts,
                "total": receipt_store.count(),
                "available": True,
            }
            bundle["summary"]["total_receipts"] = receipt_store.count()

    except Exception:
        bundle["error"] = True

    return bundle


# C-25: Audit replay / incident reconstruction
@router.get("/api/audit-replay", include_in_schema=False)
async def audit_replay(limit: int = 10):
    """
    Compact incident reconstruction from recent flow executions + receipts.
    Merges flow log entries with matching receipts into a causal sequence.
    Read-only. No DB dependency. Fail-closed.
    Not a raw log viewer — structured reconstruction only.
    """
    now = datetime.now(timezone.utc)

    replay = {
        "replay_version": "C-25",
        "generated_at": now.isoformat(),
        "sequence": [],
        "incident_summary": {
            "total_events": 0,
            "sent": 0,
            "suppressed": 0,
            "escalated": 0,
            "resolved": 0,
            "errors": 0,
        },
    }

    try:
        import app.main as main_module

        app_instance = main_module.app

        flow_log = getattr(app_instance.state, "flow_log", None)
        receipt_store = getattr(app_instance.state, "receipt_store", None)

        if flow_log is None:
            replay["available"] = False
            return replay

        # Get flow entries (newest first from list_entries)
        flow_entries = flow_log.list_entries(limit=min(limit, 50))

        # Build receipt lookup by receipt_id
        receipt_lookup = {}
        if receipt_store is not None:
            for r in receipt_store.list_receipts(limit=100):
                rid = r.get("receipt_id", "")
                if rid:
                    receipt_lookup[rid] = r

        # Build reconstruction sequence (causal order = oldest first)
        sequence = []
        for entry in reversed(flow_entries):
            step = {
                "log_id": entry.get("log_id", ""),
                "executed_at": entry.get("executed_at", ""),
                "stages": {},
            }

            # Stage 1: Routing
            step["stages"]["routing"] = {
                "ok": entry.get("routing_ok", False),
            }

            # Stage 2: Policy
            step["stages"]["policy"] = {
                "action": entry.get("policy_action", ""),
                "suppressed": entry.get("policy_suppressed", False),
                "urgent": entry.get("policy_urgent", False),
            }

            # Stage 3: Sender
            step["stages"]["sender"] = {
                "ok": entry.get("send_ok", False),
                "channels_attempted": entry.get("channels_attempted", 0),
                "channels_delivered": entry.get("channels_delivered", 0),
            }

            # Stage 4: Receipt (match by receipt_id)
            rid = entry.get("receipt_id", "")
            matched_receipt = receipt_lookup.get(rid)
            if matched_receipt:
                step["stages"]["receipt"] = {
                    "id": rid,
                    "severity": matched_receipt.get("severity_tier", ""),
                    "incident": matched_receipt.get("highest_incident", ""),
                    "stored_at": matched_receipt.get("stored_at", ""),
                }
            else:
                step["stages"]["receipt"] = {
                    "id": rid or "(none)",
                    "matched": False,
                }

            # Errors
            err_count = entry.get("error_count", 0)
            if err_count > 0:
                step["error_count"] = err_count
                step["top_error"] = entry.get("top_error", "")

            sequence.append(step)

            # Update summary
            action = entry.get("policy_action", "")
            if action == "send":
                replay["incident_summary"]["sent"] += 1
            elif action == "suppress":
                replay["incident_summary"]["suppressed"] += 1
            elif action == "escalate":
                replay["incident_summary"]["escalated"] += 1
            elif action == "resolve":
                replay["incident_summary"]["resolved"] += 1
            if err_count > 0:
                replay["incident_summary"]["errors"] += 1

        replay["sequence"] = sequence
        replay["incident_summary"]["total_events"] = len(sequence)
        replay["available"] = True

    except Exception:
        replay["available"] = False
        replay["error"] = True

    return replay


@router.get("/api/data", include_in_schema=False)
async def dashboard_data(db: AsyncSession = Depends(get_db)):
    """
    Read-only data endpoint for dashboard panels.
    Returns aggregated data from existing DB models only.
    No exchange API calls here — uses synced DB data.
    """
    binance_data = await _get_exchange_panel_data(db, "binance")
    upbit_data = await _get_exchange_panel_data(db, "upbit")
    bitget_data = await _get_exchange_panel_data(db, "bitget")
    kis_data = await _get_exchange_panel_data(db, "kis")
    kiwoom_data = await _get_exchange_panel_data(db, "kiwoom")

    # Aggregate stats from all connected exchanges
    all_exchange_data = [binance_data, upbit_data, bitget_data, kis_data, kiwoom_data]
    all_positions = []
    any_connected = False
    for exd in all_exchange_data:
        all_positions.extend(exd.get("positions", []))
        if exd["status"] == "connected":
            any_connected = True

    total_pnl = None
    total_value = None
    if any_connected:
        total_pnl = sum(p.get("unrealized_pnl", 0) or 0 for p in all_positions)
        total_value = sum(
            (p.get("entry_price", 0) or 0) * (p.get("quantity", 0) or 0) for p in all_positions
        )

    # Trade count across all exchanges
    trade_count_result = await db.execute(select(func.count(Trade.id)))
    total_trade_count = trade_count_result.scalar() or 0

    # Governance state (safe read-only access)
    governance_info = _get_governance_info()

    # Time-window asset snapshots
    time_windows = await _get_time_window_stats(db)

    return {
        "binance": binance_data,
        "upbit": upbit_data,
        "bitget": bitget_data,
        "kis": kis_data,
        "kiwoom": kiwoom_data,
        "stats": {
            "total_value": total_value,
            "trade_count": total_trade_count,
            "unrealized_pnl": total_pnl,
            "windows": time_windows,
        },
        "governance": governance_info,
    }


async def _get_exchange_panel_data(db: AsyncSession, exchange: str) -> dict:
    """Retrieve position and trade data for a specific exchange from DB."""
    try:
        # Positions from DB (synced by Celery worker)
        pos_result = await db.execute(
            select(Position)
            .where(Position.exchange == exchange)
            .order_by(Position.opened_at.desc())
        )
        positions = list(pos_result.scalars().all())

        # Trade count for this exchange
        trade_count_result = await db.execute(
            select(func.count(Trade.id)).where(Trade.exchange == exchange)
        )
        trade_count = trade_count_result.scalar() or 0

        # Aggregate PnL
        unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)
        total_value = sum((p.entry_price or 0) * (p.quantity or 0) for p in positions)

        position_list = [
            {
                "symbol": p.symbol,
                "symbol_name": p.symbol_name,
                "side": p.side.value if p.side else "-",
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "liquidation_price": p.liquidation_price,
                "leverage": p.leverage,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions
        ]

        return {
            "status": "connected" if True else "disconnected",
            "total_value": total_value if positions else None,
            "position_count": len(positions),
            "trade_count": trade_count,
            "unrealized_pnl": unrealized_pnl if positions else None,
            "positions": position_list,
        }
    except Exception as e:
        logger.error("dashboard_exchange_query_failed", exchange=exchange, error=str(e))
        return {
            "status": "disconnected",
            "total_value": None,
            "position_count": None,
            "trade_count": None,
            "unrealized_pnl": None,
            "positions": [],
        }


# ---------------------------------------------------------------------------
# Time-window asset snapshot statistics
# ---------------------------------------------------------------------------

# Time-window definitions: (label, timedelta, min_samples)
_TIME_WINDOWS = [
    ("실시간", None, 0),  # live — no snapshot needed
    ("12시간", timedelta(hours=12), 2),
    ("24시간", timedelta(hours=24), 4),
    ("60시간", timedelta(hours=60), 10),
    ("1주", timedelta(weeks=1), 20),
    ("1달", timedelta(days=30), 80),
    ("3개월", timedelta(days=90), 200),
    ("6개월", timedelta(days=180), 400),
]


async def _get_time_window_stats(db: AsyncSession) -> list[dict]:
    """
    Read-only query: retrieve asset snapshot statistics per time window.
    Returns list of dicts with label, total_value, trade_count, balance, pnl.
    Missing/insufficient data shown as None (rendered as "-" or "미집계").
    """
    # BL-TZ02: naive UTC for DB binding boundary (CR-034)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    results = []

    for label, delta, min_samples in _TIME_WINDOWS:
        if delta is None:
            # "실시간" row is filled from live aggregation, not snapshots
            results.append(
                {
                    "label": label,
                    "total_value": None,  # filled by JS from stats.total_value
                    "trade_count": None,
                    "balance": None,
                    "pnl": None,
                    "status": "live",
                }
            )
            continue

        cutoff = now_naive - delta
        try:
            # Count snapshots in window
            count_result = await db.execute(
                select(func.count(AssetSnapshot.id)).where(AssetSnapshot.snapshot_at >= cutoff)
            )
            sample_count = count_result.scalar() or 0

            if sample_count < min_samples:
                results.append(
                    {
                        "label": label,
                        "total_value": None,
                        "trade_count": None,
                        "balance": None,
                        "pnl": None,
                        "status": "insufficient",
                        "samples": sample_count,
                        "min_samples": min_samples,
                    }
                )
                continue

            # Get latest snapshot in window (most recent)
            latest_result = await db.execute(
                select(AssetSnapshot)
                .where(AssetSnapshot.snapshot_at >= cutoff)
                .order_by(desc(AssetSnapshot.snapshot_at))
                .limit(1)
            )
            latest = latest_result.scalar_one_or_none()

            # Get earliest snapshot in window (for comparison)
            earliest_result = await db.execute(
                select(AssetSnapshot)
                .where(AssetSnapshot.snapshot_at >= cutoff)
                .order_by(AssetSnapshot.snapshot_at)
                .limit(1)
            )
            earliest = earliest_result.scalar_one_or_none()

            if latest and earliest:
                # PnL semantics: unrealized PnL delta (미실현 손익 변동).
                # NOT realized PnL. Measures open position value change over the window.
                pnl_change = (latest.unrealized_pnl or 0) - (earliest.unrealized_pnl or 0)
                results.append(
                    {
                        "label": label,
                        "total_value": latest.total_value,
                        "trade_count": latest.trade_count,
                        "balance": latest.total_balance,
                        "pnl": pnl_change,
                        "status": "ready",
                        "samples": sample_count,
                    }
                )
            else:
                results.append(
                    {
                        "label": label,
                        "total_value": None,
                        "trade_count": None,
                        "balance": None,
                        "pnl": None,
                        "status": "insufficient",
                        "samples": sample_count,
                        "min_samples": min_samples,
                    }
                )

        except Exception as e:
            logger.warning("time_window_query_failed", label=label, error=str(e))
            results.append(
                {
                    "label": label,
                    "total_value": None,
                    "trade_count": None,
                    "balance": None,
                    "pnl": None,
                    "status": "error",
                }
            )

    return results


def _get_governance_info() -> dict:
    """
    Read-only governance state snapshot.
    No raw prompt/reasoning/error_class exposure.
    """
    try:
        from fastapi import FastAPI
        from starlette.requests import Request as StarletteRequest
        import app.main as main_module

        app_instance = main_module.app
        gate = getattr(app_instance.state, "governance_gate", None)

        if gate is None:
            return {
                "security_state": "UNKNOWN",
                "orphan_count": None,
                "evidence_total": None,
                "enabled": False,
            }

        # Security state
        security_state = "NORMAL"
        if hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            if hasattr(ctx, "current"):
                security_state = (
                    str(ctx.current.value) if hasattr(ctx.current, "value") else str(ctx.current)
                )
            elif hasattr(ctx, "state"):
                security_state = (
                    str(ctx.state.value) if hasattr(ctx.state, "value") else str(ctx.state)
                )

        # Evidence summary (counts only, no raw data)
        orphan_count = None
        evidence_total = None
        if hasattr(gate, "evidence_store"):
            store = gate.evidence_store
            # CR-027: Use count() (indexed O(1)) instead of full scan.
            evidence_total = store.count()
            # CR-027: Orphan calculation on 500K+ records caused timeout.
            # Use bounded recent window instead of full scan.
            try:
                if hasattr(store, "list_by_actor_recent"):
                    recent = store.list_by_actor_recent("i04_preflight", 50)
                else:
                    recent = store.list_by_actor("i04_preflight")[-50:]
                pre_ids = set()
                linked_pre_ids = set()
                for b in recent:
                    artifacts = b.artifacts if hasattr(b, "artifacts") else []
                    for art in artifacts:
                        phase = (
                            art.get("phase", "")
                            if isinstance(art, dict)
                            else getattr(art, "phase", "")
                        )
                        if phase == "PRE":
                            pre_ids.add(b.bundle_id)
                        elif phase in ("POST", "ERROR"):
                            linked = (
                                art.get("pre_evidence_id", "")
                                if isinstance(art, dict)
                                else getattr(art, "pre_evidence_id", "")
                            )
                            if linked:
                                linked_pre_ids.add(linked)
                orphan_count = len(pre_ids - linked_pre_ids)
            except Exception:
                orphan_count = None

        return {
            "security_state": security_state,
            "orphan_count": orphan_count,
            "evidence_total": evidence_total,
            "enabled": True,
        }
    except Exception as e:
        logger.warning("governance_info_read_failed", error=str(e))
        return {
            "security_state": "UNKNOWN",
            "orphan_count": None,
            "evidence_total": None,
            "enabled": None,
        }


# ---------------------------------------------------------------------------
# v2 helpers — recent events, open orders, signal summary, venue freshness
# ---------------------------------------------------------------------------
# Sensitive field blocklist (N-01 ~ N-12):
# See docs for full list. None of these 12 blocked fields appear in
# any v1 or v2 API response. Dashboard is READ-ONLY with no hidden
# analysis exposure.
# ---------------------------------------------------------------------------


async def _get_recent_events(db: AsyncSession, limit: int = 5) -> list[dict]:
    """
    Merge recent Trade, Signal, Order events into a single timeline.
    No agent_analysis / blocked-fields / reasoning exposure.
    """
    events: list[dict] = []
    # BL-TZ02: naive UTC for DB binding boundary (CR-034)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        # Recent trades
        trade_result = await db.execute(
            select(Trade).order_by(desc(Trade.executed_at)).limit(limit)
        )
        for t in trade_result.scalars().all():
            events.append(
                {
                    "ts": t.executed_at.isoformat() if t.executed_at else None,
                    "exchange": t.exchange,
                    "event_type": "trade",
                    "summary": f"{t.symbol} {t.side} {t.quantity} @ {t.price}",
                    "severity": "info",
                }
            )
    except Exception:
        pass

    try:
        # Recent signals — NO agent_analysis
        cutoff_24h = now_naive - timedelta(hours=24)
        sig_result = await db.execute(
            select(Signal)
            .where(Signal.created_at >= cutoff_24h)
            .order_by(desc(Signal.created_at))
            .limit(limit)
        )
        for s in sig_result.scalars().all():
            status_val = s.status.value if hasattr(s.status, "value") else str(s.status)
            severity = "warning" if status_val == "rejected" else "info"
            events.append(
                {
                    "ts": s.created_at.isoformat() if s.created_at else None,
                    "exchange": s.exchange,
                    "event_type": "signal",
                    "summary": f"{s.symbol} {s.signal_type.value if hasattr(s.signal_type, 'value') else s.signal_type} [{status_val}]",
                    "severity": severity,
                }
            )
    except Exception:
        pass

    try:
        # Recent order status changes (filled/cancelled/rejected)
        ord_result = await db.execute(
            select(Order)
            .where(
                Order.status.in_(
                    [
                        OrderStatus.FILLED,
                        OrderStatus.CANCELLED,
                        OrderStatus.REJECTED,
                    ]
                )
            )
            .order_by(desc(Order.updated_at))
            .limit(limit)
        )
        for o in ord_result.scalars().all():
            status_val = o.status.value if hasattr(o.status, "value") else str(o.status)
            severity = "warning" if status_val in ("cancelled", "rejected") else "info"
            events.append(
                {
                    "ts": o.updated_at.isoformat() if o.updated_at else None,
                    "exchange": o.exchange,
                    "event_type": "order_status",
                    "summary": f"{o.symbol} {o.side.value if hasattr(o.side, 'value') else o.side} [{status_val}]",
                    "severity": severity,
                }
            )
    except Exception:
        pass

    # Sort by timestamp desc, return top N
    events.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return events[:limit]


async def _get_open_orders_by_exchange(db: AsyncSession) -> dict:
    """
    Open orders grouped by exchange.
    No signal_id (N-12) exposure.
    """
    result = {ex: [] for ex in _EXCHANGES}
    try:
        ord_result = await db.execute(
            select(Order).where(
                Order.status.in_(
                    [
                        OrderStatus.PENDING,
                        OrderStatus.SUBMITTED,
                        OrderStatus.PARTIALLY_FILLED,
                    ]
                )
            )
        )
        for o in ord_result.scalars().all():
            entry = {
                "symbol": o.symbol,
                "side": o.side.value if hasattr(o.side, "value") else str(o.side),
                "order_type": o.order_type.value
                if hasattr(o.order_type, "value")
                else str(o.order_type),
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "quantity": o.quantity,
                "price": o.price,
                "filled_quantity": o.filled_quantity,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            ex = o.exchange
            if ex in result:
                result[ex].append(entry)
    except Exception as e:
        logger.warning("open_orders_query_failed", error=str(e))
    return result


async def _get_signal_summary(db: AsyncSession) -> dict:
    """
    Signal counts for last 24h + recent 5.
    No agent_analysis (N-08) exposure.
    """
    # BL-TZ02: DB columns are TIMESTAMP WITHOUT TIME ZONE (naive).
    # Strip tzinfo at binding boundary to prevent asyncpg DataError. (CR-034)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    summary: dict = {
        "total_24h": 0,
        "validated": 0,
        "rejected": 0,
        "executed": 0,
        "pending": 0,
        "recent": [],
    }
    try:
        count_result = await db.execute(
            select(Signal.status, func.count(Signal.id))
            .where(Signal.created_at >= cutoff)
            .group_by(Signal.status)
        )
        for status, cnt in count_result.all():
            status_val = status.value if hasattr(status, "value") else str(status)
            summary["total_24h"] += cnt
            if status_val in summary:
                summary[status_val] = cnt

        # Recent 5 signals — NO agent_analysis
        recent_result = await db.execute(select(Signal).order_by(desc(Signal.created_at)).limit(5))
        for s in recent_result.scalars().all():
            summary["recent"].append(
                {
                    "exchange": s.exchange,
                    "symbol": s.symbol,
                    "signal_type": s.signal_type.value
                    if hasattr(s.signal_type, "value")
                    else str(s.signal_type),
                    "confidence": s.confidence,
                    "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
            )
    except Exception as e:
        logger.warning("signal_summary_query_failed", error=str(e))
    return summary


async def _get_venue_freshness(db: AsyncSession) -> dict:
    """
    Raw freshness data per exchange — backend provides data only,
    no status judgment.  Frontend deriveConnectionState() is the
    sole state derivation point.

    Returns: {exchange: {freshness_source, last_updated_at, age_seconds, error?}}
    """
    # BL-TZ02: naive UTC for DB result comparison (CR-034)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    result = {}
    for ex in _EXCHANGES:
        try:
            max_result = await db.execute(
                select(func.max(Position.updated_at)).where(Position.exchange == ex)
            )
            last_updated = max_result.scalar()
            if last_updated is not None:
                age = (now_naive - last_updated).total_seconds()
                result[ex] = {
                    "freshness_source": "position_proxy",
                    "last_updated_at": last_updated.isoformat(),
                    "age_seconds": round(age, 1),
                }
            else:
                result[ex] = {
                    "freshness_source": "position_proxy",
                    "last_updated_at": None,
                    "age_seconds": None,
                }
        except Exception as e:
            logger.warning("venue_freshness_query_failed", exchange=ex, error=str(e))
            result[ex] = {
                "freshness_source": "position_proxy",
                "last_updated_at": None,
                "age_seconds": None,
                "error": True,
            }
    return result


# ---------------------------------------------------------------------------
# B-09: Quote Truth Layer — bid/ask/spread from exchange ticker
# ---------------------------------------------------------------------------
# READ_ONLY: fetch_ticker is a read-only exchange API call.
# No DB schema change. No write action.
# Backend judges trust_state. Frontend displays only.
#
# Quote Trust States (6-state, single authority):
#   LIVE: valid value, age <= _QUOTE_STALE_THRESHOLD_S
#   STALE: valid value, age > _QUOTE_STALE_THRESHOLD_S
#   DISCONNECTED: adapter connection-layer failure (network/auth/DNS)
#   UNAVAILABLE: fetch succeeded but response parse/processing failed
#   NOT_AVAILABLE: field structurally unsupported (e.g. KIS/Kiwoom bid/ask)
#   NOT_QUERIED: no tracked symbol for this venue (position count = 0)
#
# Exception classification for DISCONNECTED vs UNAVAILABLE:
#   DISCONNECTED: ConnectionError, TimeoutError, OSError, AuthenticationError
#   UNAVAILABLE:  all other exceptions (parse error, unexpected response, etc.)
# ---------------------------------------------------------------------------

_QUOTE_STALE_THRESHOLD_S = 120  # same as FRESHNESS_THRESHOLD_DEGRADED_S

# Exchanges where bid/ask is structurally unsupported
_BID_ASK_NOT_SUPPORTED = {"kis", "kiwoom"}

# Connection-layer exception types → DISCONNECTED
_CONNECTION_ERRORS = (ConnectionError, TimeoutError, OSError)


async def _get_quote_data(exchange_data: dict) -> dict:
    """
    Fetch bid/ask/spread for symbols with open positions.
    Returns Quote Truth 6-tuple per symbol per venue.
    Backend judges trust_state — frontend displays only.
    """
    from exchanges.factory import ExchangeFactory

    now = datetime.now(timezone.utc)
    result = {}

    for ex in _EXCHANGES:
        ex_info = exchange_data.get(ex, {})
        positions = ex_info.get("positions", [])

        # No tracked symbol → NOT_QUERIED
        if not positions:
            result[ex] = {
                "_venue_summary": {
                    "trust_state": "NOT_QUERIED",
                    "reason": "no tracked symbol",
                    "live_count": 0,
                    "stale_count": 0,
                },
                "symbols": {},
            }
            continue

        symbols_data = {}
        live_count = 0
        stale_count = 0
        worst_state = "LIVE"

        for pos in positions:
            symbol = pos.get("symbol")
            if not symbol:
                continue

            quote_entry = await _fetch_single_quote(ex, symbol, now)
            symbols_data[symbol] = quote_entry

            st = quote_entry.get("trust_state", "UNAVAILABLE")
            if st == "LIVE":
                live_count += 1
            elif st == "STALE":
                stale_count += 1
                if worst_state == "LIVE":
                    worst_state = "STALE"
            elif st in ("DISCONNECTED", "UNAVAILABLE", "NOT_AVAILABLE"):
                if worst_state in ("LIVE", "STALE"):
                    worst_state = st

        result[ex] = {
            "_venue_summary": {
                "trust_state": worst_state,
                "live_count": live_count,
                "stale_count": stale_count,
            },
            "symbols": symbols_data,
        }

    return result


async def _fetch_single_quote(exchange: str, symbol: str, now: datetime) -> dict:
    """Fetch ticker for one symbol and return Quote Truth 6-tuple."""
    from exchanges.factory import ExchangeFactory

    base_entry = {
        "bid": None,
        "ask": None,
        "spread": None,
        "last": None,
        "as_of": None,
        "age_seconds": None,
        "trust_state": "UNAVAILABLE",
        "source_venue": exchange,
        "timestamp_origin": "not_supported",
    }

    try:
        adapter = ExchangeFactory.create(exchange)
        ticker = await adapter.fetch_ticker(symbol)

        # Determine timestamp
        venue_ts = ticker.get("timestamp")
        if venue_ts and isinstance(venue_ts, (int, float)):
            as_of = datetime.fromtimestamp(venue_ts / 1000, tz=timezone.utc)
            ts_origin = "venue_timestamp"
        else:
            as_of = now
            ts_origin = "server_fetch_time"

        age = (now - as_of).total_seconds()

        bid = ticker.get("bid")
        ask = ticker.get("ask")
        last_price = ticker.get("last")

        # KIS/Kiwoom: bid/ask structurally unsupported
        bid_ask_supported = exchange not in _BID_ASK_NOT_SUPPORTED

        if not bid_ask_supported:
            spread = None
            trust_for_bidask = "NOT_AVAILABLE"
        elif bid is not None and ask is not None:
            spread = ask - bid
            trust_for_bidask = "LIVE" if age <= _QUOTE_STALE_THRESHOLD_S else "STALE"
        else:
            spread = None
            trust_for_bidask = "UNAVAILABLE"

        # Overall trust_state: worst of bid/ask trust and last price trust
        if last_price is not None:
            last_trust = "LIVE" if age <= _QUOTE_STALE_THRESHOLD_S else "STALE"
        else:
            last_trust = "UNAVAILABLE"

        # Pick worst state
        state_priority = {
            "LIVE": 0,
            "STALE": 1,
            "NOT_AVAILABLE": 2,
            "UNAVAILABLE": 3,
            "DISCONNECTED": 4,
        }
        overall = max([trust_for_bidask, last_trust], key=lambda s: state_priority.get(s, 5))

        return {
            "bid": float(bid) if bid is not None else None,
            "ask": float(ask) if ask is not None else None,
            "spread": round(float(spread), 6) if spread is not None else None,
            "last": float(last_price) if last_price is not None else None,
            "as_of": as_of.isoformat(),
            "age_seconds": round(age, 1),
            "trust_state": overall,
            "source_venue": exchange,
            "timestamp_origin": ts_origin,
        }

    except _CONNECTION_ERRORS as e:
        logger.warning("quote_fetch_disconnected", exchange=exchange, symbol=symbol, error=str(e))
        base_entry["trust_state"] = "DISCONNECTED"
        return base_entry
    except Exception as e:
        logger.warning("quote_fetch_unavailable", exchange=exchange, symbol=symbol, error=str(e))
        base_entry["trust_state"] = "UNAVAILABLE"
        return base_entry


# ---------------------------------------------------------------------------
# C-01: Runtime data source helpers (read-only / fail-closed)
# ---------------------------------------------------------------------------


def _get_loop_monitor_info() -> dict:
    """
    Read-only Loop Monitor (L28) state snapshot.
    Reads .last_result only — NEVER calls .check().
    """
    try:
        import app.main as main_module

        app_instance = main_module.app
        monitor = getattr(app_instance.state, "loop_monitor", None)

        if monitor is None:
            return {"available": False, "loops": {}}

        result = getattr(monitor, "last_result", None)
        if result is None:
            return {"available": True, "overall_health": None, "any_exceeded": False, "loops": {}}

        loops = {}
        for name, status in result.loop_statuses.items():
            loop_entry = {
                "health": status.health.value
                if hasattr(status.health, "value")
                else str(status.health),
                "max_usage_ratio": float(status.max_usage_ratio),
                "incident_count": int(status.incident_count),
                "incident_ceiling": int(status.incident_ceiling),
            }
            # C-02: expose daily/weekly counts and ceilings if present
            if hasattr(status, "daily_count"):
                loop_entry["daily_count"] = int(status.daily_count)
            if hasattr(status, "daily_ceiling"):
                loop_entry["daily_ceiling"] = int(status.daily_ceiling)
            if hasattr(status, "weekly_count"):
                loop_entry["weekly_count"] = int(status.weekly_count)
            if hasattr(status, "weekly_ceiling"):
                loop_entry["weekly_ceiling"] = int(status.weekly_ceiling)
            loops[name] = loop_entry

        return {
            "available": True,
            "overall_health": result.overall_health.value
            if hasattr(result.overall_health, "value")
            else str(result.overall_health),
            "any_exceeded": bool(result.any_exceeded),
            "checked_at": result.checked_at.isoformat() if hasattr(result, "checked_at") else None,
            "loops": loops,
        }
    except Exception as e:
        logger.warning("loop_monitor_info_read_failed", error=str(e))
        return {"available": False, "loops": {}, "error": True}


def _get_work_state_info() -> dict:
    """
    Read-only Work State snapshot.
    Safe fields only — no guard internals.
    """
    try:
        import app.main as main_module

        app_instance = main_module.app
        ctx = getattr(app_instance.state, "work_state_ctx", None)

        if ctx is None:
            return {"available": False, "current": None}

        validation_results = []
        for r in getattr(ctx, "validation_results", []):
            validation_results.append(
                {
                    "check": r.check.name if hasattr(r.check, "name") else str(r.check),
                    "passed": bool(r.passed),
                }
            )

        return {
            "available": True,
            "current": ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current),
            "previous": ctx.previous.value
            if ctx.previous and hasattr(ctx.previous, "value")
            else None,
            "failed_check": ctx.failed_check.name
            if ctx.failed_check and hasattr(ctx.failed_check, "name")
            else None,
            "validation_results": validation_results,
            "last_transition": ctx.last_transition.isoformat()
            if hasattr(ctx, "last_transition")
            else None,
        }
    except Exception as e:
        logger.warning("work_state_info_read_failed", error=str(e))
        return {"available": False, "current": None, "error": True}


def _get_trust_state_info() -> dict:
    """
    Read-only Trust State snapshot.
    Score: numeric only (no repr). No internal method exposure.
    """
    try:
        import app.main as main_module

        app_instance = main_module.app
        registry = getattr(app_instance.state, "trust_registry", None)

        if registry is None or not isinstance(registry, dict) or len(registry) == 0:
            return {"available": False, "components": {}}

        components = {}
        for cid, ctx in registry.items():
            score = getattr(ctx, "score", None)
            if score is not None and not isinstance(score, (int, float)):
                score = None

            current = getattr(ctx, "current", None)
            components[str(cid)] = {
                "state": current.value
                if current and hasattr(current, "value")
                else str(current)
                if current
                else None,
                "score": float(score) if score is not None else None,
                "allows_execution": bool(current.allows_execution())
                if current and hasattr(current, "allows_execution")
                else None,
                "requires_monitoring": bool(current.requires_monitoring())
                if current and hasattr(current, "requires_monitoring")
                else None,
                "last_refreshed": ctx.last_refreshed.isoformat()
                if hasattr(ctx, "last_refreshed")
                else None,
            }

        return {
            "available": True,
            "components": components,
        }
    except Exception as e:
        logger.warning("trust_state_info_read_failed", error=str(e))
        return {"available": False, "components": {}, "error": True}


def _get_doctrine_info() -> dict:
    """
    Read-only Doctrine snapshot.
    Fallback: fresh DoctrineRegistry for static data, available=False.
    recent_violations capped at 5. No constraint/debug fields.
    """
    try:
        import app.main as main_module

        app_instance = main_module.app
        registry = getattr(app_instance.state, "doctrine_registry", None)

        if registry is None:
            # Fallback: load static doctrine definitions only
            from kdexter.governance.doctrine import DoctrineRegistry

            registry = DoctrineRegistry()
            is_live = False
        else:
            is_live = True

        doctrines = []
        for d in registry.list_all():
            doctrines.append(
                {
                    "id": d.doctrine_id,
                    "name": d.name,
                    "severity": d.severity.value
                    if hasattr(d.severity, "value")
                    else str(d.severity),
                    "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                }
            )

        recent_violations = []
        for v in registry.list_violations()[-5:]:
            recent_violations.append(
                {
                    "violation_id": v.violation_id,
                    "doctrine_id": v.doctrine_id,
                    "severity": v.severity.value
                    if hasattr(v.severity, "value")
                    else str(v.severity),
                    "detected_at": v.detected_at.isoformat() if hasattr(v, "detected_at") else None,
                }
            )

        return {
            "available": is_live,
            "total": registry.count(),
            "violation_count": registry.violation_count(),
            "doctrines": doctrines,
            "recent_violations": recent_violations,
        }
    except Exception as e:
        logger.warning("doctrine_info_read_failed", error=str(e))
        return {
            "available": False,
            "total": None,
            "violation_count": None,
            "doctrines": [],
            "recent_violations": [],
        }


# ---------------------------------------------------------------------------
# C-08: Source freshness summary (read-only aggregation of existing data)
# ---------------------------------------------------------------------------


def _get_source_freshness_summary(v2_result: dict) -> dict:
    """
    Aggregate freshness timestamps from all data sources in the v2 result.
    Read-only: no new queries, no state mutation. Derives from existing payload.

    Returns per-source: {name, status (fresh|stale|unknown|disconnected),
                         last_updated, age_seconds}
    """
    now = datetime.now(timezone.utc)
    sources = []

    # 1. Venue freshness (position proxy) — per exchange
    venue_freshness = v2_result.get("venue_freshness", {})
    for ex in _EXCHANGES:
        vf = venue_freshness.get(ex, {})
        last_updated = vf.get("last_updated_at")
        age = vf.get("age_seconds")
        error = vf.get("error", False)

        if error:
            status = "disconnected"
        elif last_updated is None:
            status = "unknown"
        elif age is not None and age > 300:
            status = "stale"
        else:
            status = "fresh"

        sources.append(
            {
                "name": f"venue:{ex}",
                "source_type": "position_proxy",
                "status": status,
                "last_updated": last_updated,
                "age_seconds": age,
            }
        )

    # 2. Quote feed freshness — per exchange (from quote_data venue_summary)
    quote_data = v2_result.get("quote_data", {})
    for ex in _EXCHANGES:
        qd = quote_data.get(ex, {})
        summary = qd.get("_venue_summary", {})
        trust = summary.get("trust_state", "UNAVAILABLE")

        if trust == "LIVE":
            status = "fresh"
        elif trust == "STALE":
            status = "stale"
        elif trust == "NOT_QUERIED":
            status = "unknown"
        elif trust == "DISCONNECTED":
            status = "disconnected"
        else:
            status = "unknown"

        sources.append(
            {
                "name": f"quote:{ex}",
                "source_type": "quote_feed",
                "status": status,
                "last_updated": None,
                "age_seconds": None,
            }
        )

    # 3. Loop monitor freshness
    lm = v2_result.get("loop_monitor", {})
    if lm.get("available"):
        checked_at = lm.get("checked_at")
        sources.append(
            {
                "name": "loop_monitor",
                "source_type": "runtime",
                "status": "fresh" if checked_at else "unknown",
                "last_updated": checked_at,
                "age_seconds": None,
            }
        )
    else:
        sources.append(
            {
                "name": "loop_monitor",
                "source_type": "runtime",
                "status": "unknown",
                "last_updated": None,
                "age_seconds": None,
            }
        )

    # 4. Work state freshness
    ws = v2_result.get("work_state", {})
    if ws.get("available"):
        last_transition = ws.get("last_transition")
        sources.append(
            {
                "name": "work_state",
                "source_type": "runtime",
                "status": "fresh" if last_transition else "unknown",
                "last_updated": last_transition,
                "age_seconds": None,
            }
        )
    else:
        sources.append(
            {
                "name": "work_state",
                "source_type": "runtime",
                "status": "unknown",
                "last_updated": None,
                "age_seconds": None,
            }
        )

    # 5. Trust state freshness (earliest refresh across components)
    ts = v2_result.get("trust_state", {})
    if ts.get("available") and ts.get("components"):
        refreshes = [
            c.get("last_refreshed") for c in ts["components"].values() if c.get("last_refreshed")
        ]
        sources.append(
            {
                "name": "trust_state",
                "source_type": "runtime",
                "status": "fresh" if refreshes else "unknown",
                "last_updated": min(refreshes) if refreshes else None,
                "age_seconds": None,
            }
        )
    else:
        sources.append(
            {
                "name": "trust_state",
                "source_type": "runtime",
                "status": "unknown",
                "last_updated": None,
                "age_seconds": None,
            }
        )

    # 6. Doctrine freshness
    doc = v2_result.get("doctrine", {})
    sources.append(
        {
            "name": "doctrine",
            "source_type": "runtime",
            "status": "fresh" if doc.get("available") else "unknown",
            "last_updated": None,
            "age_seconds": None,
        }
    )

    # Summary counts
    fresh_count = sum(1 for s in sources if s["status"] == "fresh")
    stale_count = sum(1 for s in sources if s["status"] == "stale")
    unknown_count = sum(1 for s in sources if s["status"] == "unknown")
    disconnected_count = sum(1 for s in sources if s["status"] == "disconnected")

    return {
        "sources": sources,
        "summary": {
            "total": len(sources),
            "fresh": fresh_count,
            "stale": stale_count,
            "unknown": unknown_count,
            "disconnected": disconnected_count,
        },
        "polled_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# C-09: Source provenance metadata (read-only, no new queries)
# ---------------------------------------------------------------------------


def _get_provenance_metadata(v2_result: dict) -> dict:
    """
    Annotate each major dashboard state with its source provenance.
    Read-only: derives from existing v2 payload fields only.
    No hidden reasoning, no debug traces, no chain_of_thought.

    Returns per-state: {state_name, source, basis, confidence_note}
    """
    entries = []

    # 1. Governance state provenance
    gov = v2_result.get("governance", {})
    entries.append(
        {
            "state": "governance",
            "display_value": gov.get("security_state", "UNKNOWN"),
            "source": "GovernanceGate._security_ctx",
            "basis": "SecurityStateContext.current",
            "data_origin": "app.state.governance_gate" if gov.get("enabled") else "not_initialized",
        }
    )

    # 2. Loop monitor provenance
    lm = v2_result.get("loop_monitor", {})
    entries.append(
        {
            "state": "loop_health",
            "display_value": lm.get("overall_health", "N/A"),
            "source": "LoopMonitor.last_result",
            "basis": "LoopCounter incident/daily/weekly vs ceilings",
            "data_origin": "app.state.loop_monitor" if lm.get("available") else "not_connected",
        }
    )

    # 3. Work state provenance
    ws = v2_result.get("work_state", {})
    entries.append(
        {
            "state": "work_state",
            "display_value": ws.get("current", "N/A"),
            "source": "WorkStateContext.current",
            "basis": "WorkStateMachine transition + guard checks",
            "data_origin": "app.state.work_state_ctx" if ws.get("available") else "not_connected",
        }
    )

    # 4. Trust state provenance
    ts = v2_result.get("trust_state", {})
    comp_count = len(ts.get("components", {})) if ts.get("available") else 0
    entries.append(
        {
            "state": "trust_state",
            "display_value": str(comp_count) + " component(s)" if ts.get("available") else "N/A",
            "source": "TrustStateContext per component",
            "basis": "score decay + event-based step-down/up",
            "data_origin": "app.state.trust_registry" if ts.get("available") else "not_connected",
        }
    )

    # 5. Doctrine provenance
    doc = v2_result.get("doctrine", {})
    entries.append(
        {
            "state": "doctrine",
            "display_value": str(doc.get("total", 0))
            + " articles, "
            + str(doc.get("violation_count", 0))
            + " violation(s)",
            "source": "DoctrineRegistry",
            "basis": "D-001~D-010 core doctrines + runtime violations",
            "data_origin": "app.state.doctrine_registry"
            if doc.get("available")
            else "fallback_static",
        }
    )

    # 6. Venue freshness provenance (aggregate)
    vf = v2_result.get("venue_freshness", {})
    venue_count = len(vf)
    with_data = sum(1 for v in vf.values() if v.get("last_updated_at") is not None)
    entries.append(
        {
            "state": "venue_freshness",
            "display_value": str(with_data) + "/" + str(venue_count) + " venues with data",
            "source": "Position.updated_at (DB proxy)",
            "basis": "max(Position.updated_at) per exchange",
            "data_origin": "database_query",
        }
    )

    # 7. Quote feed provenance (aggregate)
    qd = v2_result.get("quote_data", {})
    live_venues = 0
    for vq in qd.values():
        if vq.get("_venue_summary", {}).get("trust_state") == "LIVE":
            live_venues += 1
    entries.append(
        {
            "state": "quote_feed",
            "display_value": str(live_venues) + "/" + str(len(qd)) + " venues LIVE",
            "source": "ExchangeFactory.fetch_ticker()",
            "basis": "bid/ask/last + venue timestamp vs stale threshold",
            "data_origin": "exchange_api_call",
        }
    )

    return {"entries": entries}


# ---------------------------------------------------------------------------
# C-13: Incident snapshot builder (read-only, no new queries)
# ---------------------------------------------------------------------------


def _build_incident_snapshot(v2: dict) -> dict:
    """
    Build a compact incident snapshot from existing v2 payload.
    Suitable for alerts, logs, external handoff, or post-restart comparison.
    Read-only: no state mutation, no new DB queries, no hidden reasoning.
    """
    now = datetime.now(timezone.utc)

    # 1. Overall status
    gov = v2.get("governance", {})
    overall_status = gov.get("security_state", "UNKNOWN")

    # 2. Highest incident
    incidents = []
    if overall_status in ("LOCKDOWN", "QUARANTINED"):
        incidents.append(overall_status)

    lm = v2.get("loop_monitor", {})
    if lm.get("available") and lm.get("any_exceeded"):
        incidents.append("LOOP_EXCEEDED")
    elif lm.get("available") and lm.get("overall_health") == "CRITICAL":
        incidents.append("LOOP_CRITICAL")

    doc = v2.get("doctrine", {})
    if doc.get("available") and doc.get("violation_count", 0) > 0:
        incidents.append("DOCTRINE_VIOLATION_x" + str(doc["violation_count"]))

    ws = v2.get("work_state", {})
    if ws.get("available") and ws.get("current") in ("FAILED", "BLOCKED"):
        incidents.append("WORK_" + ws["current"])

    highest_incident = incidents[0] if incidents else "NONE"

    # 3. Degraded reasons (from source_freshness)
    sf = v2.get("source_freshness", {})
    degraded_reasons = []
    for src in sf.get("sources", []):
        if src.get("status") in ("stale", "disconnected"):
            degraded_reasons.append(src["name"] + ":" + src["status"])

    # 4. Freshness summary
    sm = sf.get("summary", {})
    freshness_summary = {
        "total": sm.get("total", 0),
        "fresh": sm.get("fresh", 0),
        "stale": sm.get("stale", 0),
        "unknown": sm.get("unknown", 0),
        "disconnected": sm.get("disconnected", 0),
    }

    # 5. Venue summary
    venue_summary = {}
    vf = v2.get("venue_freshness", {})
    for ex in _EXCHANGES:
        f = vf.get(ex, {})
        venue_summary[ex] = {
            "age_seconds": f.get("age_seconds"),
            "has_data": f.get("last_updated_at") is not None,
        }

    # 6. Quote summary
    qd = v2.get("quote_data", {})
    quote_summary = {}
    for ex in _EXCHANGES:
        vq = qd.get(ex, {})
        trust = vq.get("_venue_summary", {}).get("trust_state", "UNAVAILABLE")
        quote_summary[ex] = trust

    # 7. Loop summary
    loop_summary = {}
    if lm.get("available"):
        loop_summary["overall_health"] = lm.get("overall_health")
        loop_summary["any_exceeded"] = lm.get("any_exceeded", False)

    # 8. Last successful poll
    last_poll = sf.get("polled_at")

    # 9. Triage top item (simplified)
    triage_top = None
    if highest_incident != "NONE":
        triage_top = "Resolve " + highest_incident
    elif len(degraded_reasons) > 0:
        triage_top = "Investigate " + degraded_reasons[0]

    return {
        "snapshot_version": "C-13",
        "generated_at": now.isoformat(),
        "overall_status": overall_status,
        "highest_incident": highest_incident,
        "active_incidents": incidents,
        "degraded_reasons": degraded_reasons[:5],
        "freshness_summary": freshness_summary,
        "venue_summary": venue_summary,
        "quote_summary": quote_summary,
        "loop_summary": loop_summary,
        "last_successful_poll": last_poll,
        "triage_top": triage_top,
    }


# ===========================================================================
# I-01: Constitution-Compliant Ops Status Endpoint
# 역참조: Operating Constitution v1.0 제5조~제13조, 제41조~제42조
# 기준 문서: docs/operations/dashboard_spec.md
#
# 제약:
#   - Read-Only (GET only, no POST/PUT/DELETE)
#   - 허용 상태 문구: HEALTHY / DEGRADED / UNVERIFIED / BRAKE / LOCKDOWN
#   - System Healthy / Trading Authorized 분리 표기 (제42조)
#   - Ops Score는 보조 지표이며 단독 권한을 생성하지 않는다 (제41조)
#   - 절대시간(ISO 8601) 우선 (제13조)
#   - 자동 승인 / 자동 해제 / 거래 권한 생성 금지
#   - I-02~I-05 범위 침범 금지
# ===========================================================================


@router.get("/api/ops-status", include_in_schema=False)
async def ops_status(db: AsyncSession = Depends(get_db)):
    """
    I-01: Constitution-compliant operations status.
    Returns 4-zone structured data per Operating Constitution 제5~13조.
    Read-only. No auto-approval. No trading authority generation.
    """
    now = datetime.now(timezone.utc)

    # --- Zone 1: Global Status Bar (제7조) ---
    global_bar = _compute_global_status_bar(now)

    # --- Zone 2: Integrity Panel (제8조) ---
    integrity = await _compute_integrity_panel(db, now)

    # --- Zone 3: Trading Safety Panel (제9조) ---
    trading_safety = await _compute_trading_safety_panel(db)

    # --- Zone 4: Incident & Evidence Panel (제10조) ---
    incident = _compute_incident_panel()

    # --- System Status (제12조) ---
    system_status = _compute_system_status(global_bar, integrity, trading_safety)

    # --- Dual Lock (제42조) ---
    dual_lock = _compute_dual_lock(system_status, trading_safety)

    # --- Ops Score (제41조, 보조 지표) ---
    ops_score = _compute_ops_score(integrity, trading_safety, incident)

    return OpsStatusResponse(
        global_status_bar=global_bar,
        integrity_panel=integrity,
        trading_safety_panel=trading_safety,
        incident_evidence_panel=incident,
        system_status=system_status,
        dual_lock=dual_lock,
        ops_score=ops_score,
    )


# ===========================================================================
# I-02: Constitution-Compliant Alert Summary Endpoint
# 역참조: Operating Constitution v1.0 제14조~제22조
# 기준 문서: docs/operations/alert_policy.md
#
# 제약:
#   - Read-Only (GET only)
#   - 허용 등급: INFO / WARNING / CRITICAL / PROMOTION (제15조)
#   - 표준 필드 8항목 필수 (제20조)
#   - WARNING 이상 operator_action_required 강제
#   - 알림은 자동 실행 권한을 가지지 않는다 (제14조)
#   - 기존 C-14~C-32 인프라 파괴 수정 금지
# ===========================================================================


@router.get("/api/ops-alerts", include_in_schema=False)
async def ops_alerts(limit: int = 10):
    """
    I-02: Constitution-compliant alert summary.
    Converts existing receipt/flow data to constitution alert levels.
    Read-only. No auto-execution authority.
    """
    try:
        import app.main as main_module

        app_instance = main_module.app

        alerts = []
        suppressed_count = 0
        recovery_count = 0

        # Source 1: Receipt store (primary — most recent alerts)
        receipt_store = getattr(app_instance.state, "receipt_store", None)
        if receipt_store is not None:
            receipts = receipt_store.list_receipts(limit=min(limit, 20))
            for r in receipts:
                alert = convert_receipt_to_alert(r)
                alerts.append(alert)

        # Source 2: Flow log (suppression/recovery statistics)
        flow_log = getattr(app_instance.state, "flow_log", None)
        if flow_log is not None:
            entries = flow_log.list_entries(limit=50)
            for e in entries:
                action = e.get("policy_action", "")
                if action == "suppress":
                    suppressed_count += 1
                elif action == "resolve":
                    recovery_count += 1

            # If receipt store was empty, fall back to flow entries
            if not alerts:
                for e in entries[: min(limit, 10)]:
                    if e.get("policy_action") != "suppress":
                        alert = convert_flow_entry_to_alert(e)
                        alerts.append(alert)

        return AlertSummaryResponse(
            alerts=alerts[: min(limit, 10)],
            total_count=len(alerts),
            suppressed_count=suppressed_count,
            recovery_count=recovery_count,
        )
    except Exception as e:
        logger.warning("ops_alerts_failed", error=str(e))
        return AlertSummaryResponse()


# ===========================================================================
# I-03: Constitution-Compliant Auto-Check Results Endpoint
# 역참조: Operating Constitution v1.0 제23조~제31조
# 기준 문서: docs/operations/daily_hourly_event_checks.md
#
# 원칙: Check, Don't Repair (제24조)
# 제약:
#   - Read-Only (GET only)
#   - 결과 등급: OK / WARN / FAIL / BLOCK (제29조)
#   - evidence 누락 PASS 금지 (제31조)
#   - 자동 실행 권한 없음
# ===========================================================================


@router.get("/api/ops-checks", include_in_schema=False)
async def ops_checks(limit: int = 20):
    """
    I-03: Constitution-compliant auto-check results.
    Returns recent check results from evidence store.
    Read-only. Check, Don't Repair. No auto-execution.
    """
    try:
        from app.core.constitution_check_runner import (
            run_daily_check,
            run_hourly_check,
            enrich_hourly_from_ops_status,
        )

        # Run a lightweight daily check to get current status
        # This is read-only observation, not auto-repair
        latest_daily = run_daily_check()
        latest_hourly = run_hourly_check()

        # S-01C: Enrich hourly unknown items from ops-status (async context)
        try:
            ops_data = await ops_status(db)
            if hasattr(ops_data, "integrity_panel"):
                ops_dict = {
                    "integrity_panel": {
                        "stale_data": ops_data.integrity_panel.stale_data,
                        "snapshot_age_seconds": ops_data.integrity_panel.snapshot_age_seconds,
                    }
                }
                latest_hourly = enrich_hourly_from_ops_status(latest_hourly, ops_dict)
        except Exception:
            pass  # fail-closed: enrichment is optional

        recent_checks = []
        if latest_daily:
            recent_checks.append(latest_daily)
        if latest_hourly:
            recent_checks.append(latest_hourly)

        # Also pull historical results from evidence store
        try:
            import app.main as main_module

            gate = getattr(main_module.app.state, "governance_gate", None)
            if gate is not None and hasattr(gate, "evidence_store"):
                store = gate.evidence_store
                # CR-027: Bounded query — only recent N bundles per actor.
                # list_by_actor on 84K+ rows caused 196s timeout.
                _recent_limit = limit  # use the endpoint's limit param
                if hasattr(store, "list_by_actor_recent"):
                    check_bundles = store.list_by_actor_recent("i03_daily_check", _recent_limit)
                    check_bundles += store.list_by_actor_recent("i03_hourly_check", _recent_limit)
                    check_bundles += store.list_by_actor_recent("i03_event_check", _recent_limit)
                else:
                    check_bundles = store.list_by_actor("i03_daily_check")[-_recent_limit:]
                    check_bundles += store.list_by_actor("i03_hourly_check")[-_recent_limit:]
                    check_bundles += store.list_by_actor("i03_event_check")[-_recent_limit:]

                # Convert evidence bundles to check results (lightweight)
                for b in sorted(
                    check_bundles,
                    key=lambda x: x.created_at if hasattr(x, "created_at") else "",
                    reverse=True,
                )[:limit]:
                    after = b.after_state if hasattr(b, "after_state") else {}
                    if isinstance(after, dict) and "result" in after:
                        from app.schemas.check_schema import (
                            ConstitutionCheckResult,
                            CheckResultGrade,
                            CheckType,
                        )

                        check_type_str = (
                            b.actor.replace("i03_", "").replace("_check", "").upper()
                            if hasattr(b, "actor")
                            else "DAILY"
                        )
                        try:
                            ct = CheckType(check_type_str)
                        except ValueError:
                            ct = CheckType.DAILY

                        recent_checks.append(
                            ConstitutionCheckResult(
                                check_type=ct,
                                timestamp=b.created_at.isoformat()
                                if hasattr(b.created_at, "isoformat")
                                else str(b.created_at),
                                result=CheckResultGrade(after.get("result", "WARN")),
                                summary=after.get("summary", "Historical check"),
                                items=[],
                                failures=sorted(after.get("failures", [])),
                                evidence_id=b.bundle_id if hasattr(b, "bundle_id") else "unknown",
                                rule_refs=after.get("rule_refs", ["Art23-Art31"]),
                                operator_action_required=after.get("result") in ("FAIL", "BLOCK"),
                            )
                        )
        except Exception:
            pass  # fail-closed: historical data optional

        # Deduplicate by evidence_id, limit
        seen_ids = set()
        deduped = []
        for c in recent_checks:
            eid = c.evidence_id
            if eid not in seen_ids:
                seen_ids.add(eid)
                deduped.append(c)

        deduped = deduped[: min(limit, 20)]

        # Compute by-type grouping
        by_type = {}
        block_count = 0
        fail_count = 0
        for c in deduped:
            ct = c.check_type.value if hasattr(c.check_type, "value") else str(c.check_type)
            by_type[ct] = by_type.get(ct, 0) + 1
            if hasattr(c.result, "value"):
                if c.result.value == "BLOCK":
                    block_count += 1
                elif c.result.value == "FAIL":
                    fail_count += 1

        return CheckSummaryResponse(
            recent_checks=deduped,
            total_count=len(deduped),
            by_type=by_type,
            block_count=block_count,
            fail_count=fail_count,
        )
    except Exception as e:
        logger.warning("ops_checks_failed", error=str(e))
        return CheckSummaryResponse()


# ===========================================================================
# I-04: Recovery Preflight + Incident Playback Endpoints
# 역참조: Operating Constitution v1.0 제43조~제44조
# I-04는 recovery engine이 아니라 recovery preflight / incident review 계층이다.
# READY means preflight-ready, not execution-authorized.
# 금지: 실제 recovery/failover/promotion/trading resume 실행, state mutation
# ===========================================================================


@router.get("/api/ops-preflight", include_in_schema=False)
async def ops_preflight():
    """
    I-04: Recovery Preflight assessment (제43조).
    Read-only. READY means preflight-ready, not execution-authorized.
    """
    try:
        from app.core.recovery_preflight import run_recovery_preflight

        return run_recovery_preflight()
    except Exception as e:
        logger.warning("ops_preflight_failed", error=str(e))
        return RecoveryPreflightResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision="NOT_READY",
            summary=f"Preflight failed: {e}",
            evidence_id=f"fallback-pf-err",
            rule_refs=["Art43"],
        )


@router.get("/api/ops-playback", include_in_schema=False)
async def ops_playback():
    """
    I-04: Incident Playback reconstruction (제44조).
    Review only. No re-execution. No failover.
    """
    try:
        from app.core.incident_playback import build_incident_playback

        return build_incident_playback()
    except Exception as e:
        logger.warning("ops_playback_failed", error=str(e))
        now = datetime.now(timezone.utc)
        return IncidentPlaybackResult(
            incident_id=f"INC-ERR-{now.strftime('%H%M%S')}",
            time_range={"start": now.isoformat(), "end": now.isoformat()},
            summary=f"Playback failed: {e}",
            rule_refs=["Art44"],
        )


# ===========================================================================
# I-05: Execution Gate — 4조건 통합 판정
# 역참조: Operating Constitution v1.0 제7조, 제41조, 제42조, 제43조
# OPEN means gate-open, not execution-authorized.
# 자동 거래 실행/재개/승격/자본 확대 금지.
# ===========================================================================


@router.get("/api/ops-gate", include_in_schema=False)
async def ops_gate():
    """
    I-05: Execution Gate 4-condition evaluation.
    Read-only. OPEN means gate-open, not execution-authorized.
    """
    try:
        from app.core.execution_gate import evaluate_execution_gate

        return evaluate_execution_gate()
    except Exception as e:
        logger.warning("ops_gate_failed", error=str(e))
        return ExecutionGateResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision="CLOSED",
            summary=f"Gate evaluation failed: {e}",
            evidence_id=f"fallback-gate-err",
            rule_refs=["Art7", "Art41", "Art42", "Art43"],
        )


# ===========================================================================
# I-06: Operator Approval Receipt Endpoint
# 역참조: Operating Constitution v1.0 제43조, 제45조
# 승인 영수증 계층. 실행 계층 아님.
# APPROVED means operator-approved receipt only, not execution-authorized.
# ===========================================================================


@router.get("/api/ops-approval", include_in_schema=False)
async def ops_approval():
    """
    I-06: Issue operator approval receipt (read-only validation + append-only receipt).
    APPROVED means operator-approved receipt only, not execution-authorized.
    """
    try:
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import ApprovalScope

        return issue_approval(
            approved_by="operator",
            approval_scope=ApprovalScope.NO_EXECUTION,
        )
    except Exception as e:
        logger.warning("ops_approval_failed", error=str(e))
        return OperatorApprovalReceipt(
            approval_id=f"APR-ERR",
            decision="REJECTED",
            gate_snapshot_id="error",
            preflight_id="error",
            check_id="error",
            ops_score=0.0,
            security_state="ERROR",
            timestamp=datetime.now(timezone.utc).isoformat(),
            approval_expiry_at=datetime.now(timezone.utc).isoformat(),
            approval_scope="NO_EXECUTION",
            rejection_reasons=["MISSING_REQUIRED_FIELD"],
            rule_refs=["Art43", "Art45"],
        )


# ===========================================================================
# B-14A: Operator Safety Summary — 3계층 집계 read-only
# Preflight (I-04) + Gate (I-05) + Approval (I-06) 집계.
# Read-only. Not execution-authorized.
# 역참조: Operating Constitution v1.0 제43조, 제45조
# ===========================================================================


# 표준 코드별 고정 step 매핑 (자유 생성 금지)
_B14_STEP_MAP = {
    "PREFLIGHT_BLOCKED": "Review preflight blockers before any operator action.",
    "PREFLIGHT_NOT_READY": "Resolve preflight conditions to reach READY state.",
    "GATE_UNMET": "Verify gate conditions and required thresholds.",
    "APPROVAL_REJECTED": "Review approval fields and rejection reasons.",
    "EVIDENCE_MISSING": "Collect required evidence before proceeding.",
    "LOCKDOWN_ACTIVE": "Confirm lockdown state and release policy.",
    "UNKNOWN_STATE": "Recheck operator safety state and investigate missing data.",
}
_B14_STEP_FALLBACK = "Recheck operator safety state"


@router.get("/api/ops-safety-summary", include_in_schema=False)
async def ops_safety_summary():
    """
    B-14A: Aggregate Preflight + Gate + Approval into single operator safety view.
    Read-only. No state changes. Not execution-authorized.
    """
    from app.schemas.ops_safety_schema import OpsSafetySummary

    now = datetime.now(timezone.utc).isoformat()

    # --- Layer 1: Preflight ---
    pf_decision = "NOT_READY"
    pf_eid = None
    pf_reasons: list[str] = []
    try:
        from app.core.recovery_preflight import run_recovery_preflight

        pf = run_recovery_preflight()
        pf_decision = pf.decision.value
        pf_eid = pf.evidence_id
        if pf_decision == "BLOCKED":
            pf_reasons.append("PREFLIGHT_BLOCKED")
        elif pf_decision == "NOT_READY":
            pf_reasons.append("PREFLIGHT_NOT_READY")
        # Propagate specific reason codes
        for rc in pf.reason_codes:
            if rc.value == "LOCKDOWN_ACTIVE":
                pf_reasons.append("LOCKDOWN_ACTIVE")
            elif rc.value == "MISSING_EVIDENCE":
                pf_reasons.append("EVIDENCE_MISSING")
    except Exception as e:
        logger.warning("safety_summary_preflight_failed", error=str(e))
        pf_reasons.append("UNKNOWN_STATE")

    # --- Layer 2: Gate ---
    gate_decision = "CLOSED"
    gate_eid = None
    gate_reasons: list[str] = []
    ext_ops_score = None
    ext_conditions_met = None
    ext_trading_auth = None
    ext_lockdown = "UNKNOWN"
    try:
        from app.core.execution_gate import evaluate_execution_gate

        gate = evaluate_execution_gate()
        gate_decision = gate.decision.value
        gate_eid = gate.evidence_id
        ext_ops_score = gate.ops_score_average
        ext_conditions_met = gate.conditions_met
        # Read trading_authorized and lockdown from gate conditions (기존 값)
        for c in gate.conditions:
            if c.name == "trading_authorized":
                ext_trading_auth = c.met
            if c.name == "lockdown_inactive":
                ext_lockdown = c.observed
        if gate_decision == "CLOSED":
            gate_reasons.append("GATE_UNMET")
    except Exception as e:
        logger.warning("safety_summary_gate_failed", error=str(e))
        gate_reasons.append("UNKNOWN_STATE")

    # --- Layer 3: Approval ---
    apr_decision = "REJECTED"
    apr_id = None
    apr_reasons: list[str] = []
    try:
        from app.core.operator_approval import issue_approval
        from app.schemas.operator_approval_schema import ApprovalScope

        apr = issue_approval(
            approved_by="operator",
            approval_scope=ApprovalScope.NO_EXECUTION,
        )
        apr_decision = apr.decision.value
        apr_id = apr.approval_id
        if apr_decision == "REJECTED":
            apr_reasons.append("APPROVAL_REJECTED")
    except Exception as e:
        logger.warning("safety_summary_approval_failed", error=str(e))
        apr_reasons.append("UNKNOWN_STATE")

    # --- Extended: Policy + Check (기존 값 읽기만) ---
    ext_policy = "UNKNOWN"
    ext_check = "UNKNOWN"
    try:
        from app.core.execution_policy import evaluate_execution_policy

        pol = evaluate_execution_policy()
        ext_policy = (
            pol.decision
            if isinstance(pol.decision, str)
            else getattr(pol.decision, "value", "UNKNOWN")
        )
    except Exception:
        pass
    try:
        from app.core.constitution_check_runner import run_daily_check

        chk = run_daily_check()
        ext_check = chk.result.value if hasattr(chk.result, "value") else str(chk.result)
    except Exception:
        pass

    # --- Pipeline state (첫 번째 비통과 단계) ---
    _pipe_stages = [
        ("I-03 Check", ext_check == "OK"),
        ("I-04 Preflight", pf_decision == "READY"),
        ("I-05 Gate", gate_decision == "OPEN"),
        ("I-06 Approval", apr_decision == "APPROVED"),
        ("I-07 Policy", ext_policy == "MATCH"),
    ]
    ext_pipeline = "ALL_CLEAR"
    for name, passed in _pipe_stages:
        if not passed:
            ext_pipeline = name
            break

    # --- Aggregate (순서 고정: Preflight → Gate → Approval → System, 중복 제거) ---
    all_reasons = list(dict.fromkeys(pf_reasons + gate_reasons + apr_reasons))

    # all_clear 정의: preflight=READY + gate=OPEN + approval=APPROVED + blocked_reasons=[]
    all_clear = (
        pf_decision == "READY"
        and gate_decision == "OPEN"
        and apr_decision == "APPROVED"
        and len(all_reasons) == 0
    )

    # next_safe_steps: 고정 매핑만 (자유 생성 금지)
    steps = []
    for code in all_reasons:
        step = _B14_STEP_MAP.get(code, _B14_STEP_FALLBACK)
        if step not in steps:
            steps.append(step)

    return OpsSafetySummary(
        timestamp=now,
        preflight_decision=pf_decision,
        gate_decision=gate_decision,
        approval_decision=apr_decision,
        all_clear=all_clear,
        blocked_reasons=all_reasons,
        next_safe_steps=steps,
        pipeline_state=ext_pipeline,
        ops_score=ext_ops_score,
        policy_decision=ext_policy,
        lockdown_state=ext_lockdown,
        trading_authorized=ext_trading_auth,
        check_grade=ext_check,
        conditions_met=ext_conditions_met,
        preflight_evidence_id=pf_eid,
        gate_evidence_id=gate_eid,
        approval_id=apr_id,
    )


# ===========================================================================
# I-07: Execution Policy — 승인-실행 상태 일치 검증
# MATCH means policy-match only, not execution-performed.
# ===========================================================================


@router.get("/api/ops-policy", include_in_schema=False)
async def ops_policy():
    """
    I-07: Execution policy revalidation.
    MATCH means policy-match only, not execution-performed.
    """
    try:
        from app.core.execution_policy import evaluate_execution_policy

        return evaluate_execution_policy()
    except Exception as e:
        logger.warning("ops_policy_failed", error=str(e))
        return ExecutionPolicyResult(
            policy_id="POL-ERR",
            approval_id="none",
            decision="DRIFT",
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=f"Policy evaluation failed: {e}",
            drift_reasons=["MISSING_REQUIRED_FIELD"],
            rule_refs=["Art33", "Art39", "Art43"],
        )


# ===========================================================================
# E-01: Executor Design — 전제 조건 검증 (설계만, 실행 금지)
# 거래소 호출, 주문 전송, 자동 실행, unlock/resume 금지.
# ===========================================================================


@router.get("/api/ops-executor", include_in_schema=False)
async def ops_executor():
    """
    E-01: Executor precondition check (design only).
    No execution. No trading. No order submission.
    """
    try:
        from app.core.executor_design import validate_execution_preconditions
        from app.schemas.executor_schema import ExecutionScope

        return validate_execution_preconditions(
            execution_scope=ExecutionScope.NO_EXECUTION,
        )
    except Exception as e:
        logger.warning("ops_executor_failed", error=str(e))
        return ExecutionReceipt(
            execution_id="EXE-ERR",
            state="PRECONDITION_FAILED",
            execution_scope="NO_EXECUTION",
            evidence_chain={
                "check_id": "err",
                "preflight_id": "err",
                "gate_snapshot_id": "err",
                "approval_id": "err",
                "approval_receipt_hash": "err",
                "policy_snapshot_id": "err",
                "policy_decision": "err",
            },
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=f"Executor check failed: {e}",
            rule_refs=["Art36", "Art37", "Art38"],
        )


# ===========================================================================
# E-02: Executor Activation Rule — 활성화 조건 판정 (실행 금지)
# ACTIVATION_ALLOWED means activation-eligible only, not execution-performed.
# ===========================================================================


@router.get("/api/ops-activation", include_in_schema=False)
async def ops_activation():
    """
    E-02: Activation rule check (12 conditions).
    No execution. No order send. No exchange API.
    """
    try:
        from app.core.executor_activation import evaluate_activation

        return evaluate_activation()
    except Exception as e:
        logger.warning("ops_activation_failed", error=str(e))
        return ActivationReceipt(
            activation_id="ACT-ERR",
            decision="ACTIVATION_DENIED",
            timestamp=datetime.now(timezone.utc).isoformat(),
            reasons=["MISSING_REQUIRED_FIELD"],
            rule_refs=["Art43"],
        )


# ===========================================================================
# E-03: Micro Executor Dispatch Guard (실행 금지, dispatch 판정만)
# DISPATCH_ALLOWED means dispatch-eligible only, not order-sent.
# ===========================================================================


@router.get("/api/ops-dispatch", include_in_schema=False)
async def ops_dispatch():
    """E-03: Dispatch guard check. No execution. No order send."""
    try:
        from app.core.micro_executor import evaluate_dispatch

        return evaluate_dispatch()
    except Exception as e:
        logger.warning("ops_dispatch_failed", error=str(e))
        return DispatchReceipt(
            execution_id="DIS-ERR",
            decision="DISPATCH_DENIED",
            timestamp=datetime.now(timezone.utc).isoformat(),
            reasons=["MISSING_REQUIRED_FIELD"],
            rule_refs=["Art43"],
        )


# ===========================================================================
# B-08: AI Assist Data Sources — read-only 정규화 소스
# ===========================================================================


@router.get("/api/ai-sources", include_in_schema=False)
async def ai_sources():
    """B-08: AI Assist data sources (read-only, no execution/recommendation)."""
    try:
        from app.core.ai_assist_source import collect_ai_assist_sources

        return collect_ai_assist_sources()
    except Exception as e:
        logger.warning("ai_sources_failed", error=str(e))
        return AIAssistSources()


# ===========================================================================
# B-09: Market Feed — read-only best bid/ask/spread service
# ===========================================================================


@router.get("/api/market-feed", include_in_schema=False)
async def market_feed(db: AsyncSession = Depends(get_db)):
    """B-09: Market feed (read-only, best bid/ask/spread/trust/stale)."""
    try:
        from app.core.market_feed_service import (
            build_market_feed_from_quote_data,
            build_empty_market_feed,
        )

        # Reuse existing quote fetch
        exchange_data = {}
        for ex in _EXCHANGES:
            exchange_data[ex] = await _get_exchange_panel_data(db, ex)
        quote_data = await _get_quote_data(exchange_data)
        return build_market_feed_from_quote_data(quote_data)
    except Exception as e:
        logger.warning("market_feed_failed", error=str(e))
        from app.core.market_feed_service import build_empty_market_feed

        return build_empty_market_feed()


# ===========================================================================
# B-10: Ops Aggregate — 종합 운영 health 집계
# ===========================================================================


@router.get("/api/ops-aggregate", include_in_schema=False)
async def ops_aggregate():
    """B-10: Ops aggregate (read-only, health/availability/stale summary)."""
    try:
        from app.core.ops_aggregate_service import build_ops_aggregate

        return build_ops_aggregate()
    except Exception as e:
        logger.warning("ops_aggregate_failed", error=str(e))
        return OpsAggregateResponse()


# ===========================================================================
# B-11: Governance Summary — read-only 통제 상태 요약
# ===========================================================================


@router.get("/api/governance-summary", include_in_schema=False)
async def governance_summary():
    """B-11: Governance summary (read-only, no enforcement change)."""
    try:
        from app.core.governance_summary_service import build_governance_summary

        return build_governance_summary()
    except Exception as e:
        logger.warning("governance_summary_failed", error=str(e))
        return GovernanceSummaryResponse()


# ===========================================================================
# B-13: Alert Priority / Escalation Summary
# ===========================================================================


@router.get("/api/alert-summary", include_in_schema=False)
async def alert_summary_detail():
    """B-13: Alert priority summary (read-only, no ack/write/mute)."""
    try:
        from app.core.alert_summary_service import build_alert_summary

        return build_alert_summary()
    except Exception as e:
        logger.warning("alert_summary_failed", error=str(e))
        return AlertSummaryDetailResponse()


# ---------------------------------------------------------------------------
# 4-Tier Seal Chain Board — read-only unified view
# ---------------------------------------------------------------------------


@router.get("/api/four-tier-board", include_in_schema=False)
async def four_tier_board():
    """
    Read-only 4-tier seal chain board.
    Aggregates Agent → Execution → Submit → Orders into a single view.
    Data source: in-memory ledgers + OrderExecutor (via app.state).
    No mutations, no side-effects.
    """
    try:
        import app.main as main_module
        from app.services.four_tier_board_service import build_four_tier_board

        app_instance = main_module.app

        action_ledger = getattr(app_instance.state, "action_ledger", None)
        execution_ledger = getattr(app_instance.state, "execution_ledger", None)
        submit_ledger = getattr(app_instance.state, "submit_ledger", None)
        order_executor = getattr(app_instance.state, "order_executor", None)

        board = build_four_tier_board(
            action_ledger=action_ledger,
            execution_ledger=execution_ledger,
            submit_ledger=submit_ledger,
            order_executor=order_executor,
        )
        return board.model_dump()
    except Exception as e:
        logger.warning("four_tier_board_failed", error=str(e))
        return {
            "agent_tier": {"tier_name": "Agent", "tier_number": 1, "connected": False},
            "execution_tier": {"tier_name": "Execution", "tier_number": 2, "connected": False},
            "submit_tier": {"tier_name": "Submit", "tier_number": 3, "connected": False},
            "order_tier": {"tier_name": "Orders", "tier_number": 4, "connected": False},
            "error": str(e)[:200],
        }


# ---------------------------------------------------------------------------
# AutoFix / Evaluation Status — read-only (Skill Loop integration)
# ---------------------------------------------------------------------------


@router.get("/api/evaluation-status", include_in_schema=False)
async def evaluation_status():
    """Read-only: latest evaluation report + autofix loop status + self-healing card."""
    from pathlib import Path
    import json as _json
    from datetime import datetime, timezone
    from collections import Counter

    # ------------------------------------------------------------------
    # Raw data loading
    # ------------------------------------------------------------------
    evaluation = None
    autofix_loop = None
    patterns_list: list = []

    eval_path = Path("data/evaluation_report.json")
    if eval_path.exists():
        try:
            evaluation = _json.loads(eval_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    loop_path = Path("data/autofix_loop_report.json")
    if loop_path.exists():
        try:
            autofix_loop = _json.loads(loop_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    patterns_path = Path("data/failure_patterns.json")
    if patterns_path.exists():
        try:
            raw = _json.loads(patterns_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                patterns_list = raw
        except Exception:
            pass

    # Load grade history
    grade_history = []
    history_path = Path("data/grade_history.json")
    if history_path.exists():
        try:
            grade_history = _json.loads(history_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Load evolution history
    evolution_history = []
    evo_path = Path("data/evolution_history.json")
    if evo_path.exists():
        try:
            evolution_history = _json.loads(evo_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Self-Healing Status Card — derived, read-only
    # ------------------------------------------------------------------

    def _compute_grade_trend(recent: list) -> str:
        if len(recent) < 2:
            return "STABLE"
        grade_rank = {"GREEN": 0, "YELLOW": 1, "RED": 2}
        grades = [grade_rank.get(e.get("grade", "RED"), 2) for e in recent[-3:]]
        if (
            all(grades[i] >= grades[i + 1] for i in range(len(grades) - 1))
            and grades[0] > grades[-1]
        ):
            return "IMPROVING"
        if (
            all(grades[i] <= grades[i + 1] for i in range(len(grades) - 1))
            and grades[0] < grades[-1]
        ):
            return "DECLINING"
        return "STABLE"

    # Grade / risk from evaluation
    grade = "UNKNOWN"
    risk_score = None
    eval_ts = None
    if isinstance(evaluation, dict):
        grade = evaluation.get("grade") or evaluation.get("final_grade") or "UNKNOWN"
        risk_score = evaluation.get("risk_score") or evaluation.get("score")
        eval_ts = (
            evaluation.get("timestamp")
            or evaluation.get("evaluated_at")
            or evaluation.get("created_at")
        )

    # Loop metadata
    last_loop_status = None
    last_loop_iterations = None
    last_loop_duration_seconds = None
    last_blocked_reason = None
    if isinstance(autofix_loop, dict):
        loop_final_grade = autofix_loop.get("final_grade")
        loop_exit_reason = autofix_loop.get("exit_reason")
        if loop_final_grade or loop_exit_reason:
            last_loop_status = {
                "final_grade": loop_final_grade,
                "exit_reason": loop_exit_reason,
            }
        last_loop_iterations = autofix_loop.get("iterations_run") or autofix_loop.get("iterations")
        last_loop_duration_seconds = (
            autofix_loop.get("duration_seconds")
            or autofix_loop.get("elapsed_seconds")
            or autofix_loop.get("duration")
        )
        if loop_exit_reason == "governance_block":
            last_blocked_reason = (
                autofix_loop.get("blocked_reason")
                or autofix_loop.get("block_reason")
                or autofix_loop.get("governance_block_reason")
                or "governance_block"
            )

    # Pattern statistics
    recurrence_distribution: dict = {}
    top_failure_types: list = []
    if patterns_list:
        recurrence_counter: Counter = Counter()
        failure_type_counter: Counter = Counter()
        for p in patterns_list:
            if not isinstance(p, dict):
                continue
            recurrence = p.get("recurrence") or p.get("recurrence_type") or p.get("type")
            if recurrence:
                recurrence_counter[str(recurrence)] += 1
            failure_type = p.get("failure_type") or p.get("error_type") or p.get("category")
            if failure_type:
                failure_type_counter[str(failure_type)] += 1
        recurrence_distribution = dict(recurrence_counter)
        top_failure_types = [
            {"failure_type": ft, "count": cnt} for ft, cnt in failure_type_counter.most_common(5)
        ]

    # Green / Red timestamps — prefer history, fall back to current evaluation
    last_green_at = None
    last_red_at = None
    for entry in reversed(grade_history):
        if not isinstance(entry, dict):
            continue
        if last_green_at is None and entry.get("grade", "").upper() == "GREEN":
            last_green_at = entry.get("timestamp")
        if last_red_at is None and entry.get("grade", "").upper() != "GREEN":
            last_red_at = entry.get("timestamp")
        if last_green_at and last_red_at:
            break
    # Fall back to current evaluation when history is empty
    if eval_ts and last_green_at is None and last_red_at is None:
        if isinstance(grade, str) and grade.upper() == "GREEN":
            last_green_at = eval_ts
        else:
            last_red_at = eval_ts

    # Governance blocked state
    governance_blocked = False
    blocked_at = None
    gov_summary = evaluation.get("governance_summary", {}) if isinstance(evaluation, dict) else {}
    if gov_summary.get("status") == "BLOCK" or (
        isinstance(evaluation, dict) and evaluation.get("blocked")
    ):
        governance_blocked = True
        # blocked_at: find most recent history entry where governance_status == "BLOCK"
        for entry in reversed(grade_history):
            if not isinstance(entry, dict):
                continue
            if entry.get("governance_status") == "BLOCK":
                blocked_at = entry.get("timestamp")
                break
        # Fall back to current evaluation timestamp when no history entry has BLOCK
        if blocked_at is None and eval_ts:
            blocked_at = eval_ts

    # Status priority: most critical of current grade vs governance block
    _priority_rank = {"BLOCK": 0, "RED": 1, "YELLOW": 2, "GREEN": 3, "UNKNOWN": 4}
    current_grade_upper = grade.upper() if isinstance(grade, str) else "UNKNOWN"
    candidate_statuses = [current_grade_upper]
    if governance_blocked:
        candidate_statuses.append("BLOCK")
    status_priority = min(candidate_statuses, key=lambda s: _priority_rank.get(s, 4))

    # Recent grades (last 7) and trend
    recent_grades = [
        {
            "timestamp": e.get("timestamp"),
            "grade": e.get("grade"),
            "risk_score": e.get("risk_score"),
        }
        for e in grade_history[-7:]
        if isinstance(e, dict)
    ]
    grade_trend = _compute_grade_trend(grade_history)

    self_healing_card = {
        "current_grade": grade,
        "risk_score": risk_score,
        "last_loop_status": last_loop_status,
        "last_loop_iterations": last_loop_iterations,
        "last_loop_duration_seconds": last_loop_duration_seconds,
        "last_blocked_reason": last_blocked_reason,
        "pattern_count": len(patterns_list),
        "recurrence_distribution": recurrence_distribution,
        "top_failure_types": top_failure_types,
        "last_green_at": last_green_at,
        "last_red_at": last_red_at,
        "recent_grades": recent_grades,
        "grade_trend": grade_trend,
        "governance_blocked": governance_blocked,
        "blocked_at": blocked_at,
        "status_priority": status_priority,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # ------------------------------------------------------------------
    # Evolution Card
    # ------------------------------------------------------------------
    evo_proposals = [e.get("proposal") for e in evolution_history if e.get("proposal")]
    pending = [p for p in evo_proposals if p.get("status") == "PROPOSED"]
    approved = [p for p in evo_proposals if p.get("status") == "APPROVED"]
    rejected = [p for p in evo_proposals if p.get("status") == "REJECTED"]
    applied = [p for p in evo_proposals if p.get("status") == "APPLIED"]

    latest_proposal = evo_proposals[-1] if evo_proposals else None
    latest_analysis = evolution_history[-1].get("analysis_summary", {}) if evolution_history else {}

    evolution_card = {
        "latest_proposal_id": latest_proposal.get("proposal_id") if latest_proposal else None,
        "latest_diagnosis": latest_proposal.get("category") if latest_proposal else None,
        "latest_severity": latest_proposal.get("severity") if latest_proposal else None,
        "latest_score": latest_proposal.get("score") if latest_proposal else None,
        "latest_status": latest_proposal.get("status") if latest_proposal else None,
        "pending_count": len(pending),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "applied_count": len(applied),
        "total_proposals": len(evo_proposals),
        "health_trend": latest_analysis.get("health_trend"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # ------------------------------------------------------------------
    # Compose final result
    # ------------------------------------------------------------------
    result = {
        "self_healing_card": self_healing_card,
        "evaluation": evaluation,
        "autofix_loop": autofix_loop,
        "failure_patterns": {
            "total": len(patterns_list),
            "patterns": patterns_list[-10:],  # last 10
        },
        "grade_history": grade_history[-20:],  # last 20 entries
    }
    result["evolution_card"] = evolution_card
    result["evolution_board"] = {
        "pending": [_proposal_summary(p) for p in pending],
        "approved": [_proposal_summary(p) for p in approved],
        "rejected": [_proposal_summary(p) for p in rejected],
        "applied": [_proposal_summary(p) for p in applied],
    }
    result["evolution_history"] = evolution_history[-10:]  # last 10
    return result


def _proposal_summary(p: dict) -> dict:
    """Compact proposal summary for board display."""
    return {
        "proposal_id": p.get("proposal_id"),
        "category": p.get("category"),
        "severity": p.get("severity"),
        "score": p.get("score"),
        "action": p.get("action", "")[:80],
        "status": p.get("status"),
        "created_at": p.get("created_at"),
        "approved_at": p.get("approved_at"),
        "rejected_at": p.get("rejected_at"),
    }


# ---------------------------------------------------------------------------
# C-04 Manual Action — Phase 5 Bounded Execution
# 9-stage chain gated. Fail-closed. Synchronous only.
# No background / queue / worker / command bus.
# Receipt + audit on every attempt.
# ---------------------------------------------------------------------------
def _get_operator_id(request: Request) -> str:
    """Extract operator identity for receipt/audit quality. Display only, not auth gate."""
    try:
        # Try X-Operator-Id header (set by operator tools)
        op = request.headers.get("x-operator-id", "").strip()
        if op:
            return op[:64]
        # Try client IP as identifier
        client = getattr(request, "client", None)
        if client and client.host:
            return f"op@{client.host}"
    except Exception:
        pass
    return "operator"  # fail-closed default


@router.post("/api/manual-action/execute", include_in_schema=False)
async def manual_action_execute(request: Request):
    """C-04: Execute manual action after 9-stage chain validation.

    - Server-side chain revalidation (never trust client alone)
    - Fail-closed: any missing/error → REJECTED
    - Receipt on every attempt (success, rejection, failure)
    - Synchronous only. No background. No queue.
    """
    try:
        from app.core.manual_action_handler import validate_and_execute

        # Rebuild safety data server-side — never trust client
        safety_data = await _build_ops_safety_summary()
        receipt = validate_and_execute(
            safety_data=safety_data,
            operator_id=_get_operator_id(request),
        )
        return receipt.model_dump()
    except Exception as e:
        logger.error("manual_action_execute_failed", error=str(e))
        from app.schemas.manual_action_schema import ManualActionReceipt, ManualActionDecision
        import uuid
        from datetime import timezone as tz

        return ManualActionReceipt(
            receipt_id=f"RCP-{uuid.uuid4().hex[:12]}",
            action_id=f"MA-ERR-{uuid.uuid4().hex[:8]}",
            operator_id=_get_operator_id(request),
            timestamp=datetime.now(tz.utc).isoformat(),
            decision=ManualActionDecision.FAILED,
            block_code="EXECUTION_FAILED",
            reason="Server error during execution attempt",
            error_summary=str(e)[:200],
            audit_id=f"AUD-ERR-{uuid.uuid4().hex[:8]}",
        ).model_dump()


async def _build_ops_safety_summary() -> dict:
    """Rebuild ops-safety-summary data server-side for chain validation."""
    try:
        from app.core.recovery_preflight import run_recovery_preflight
        from app.core.execution_gate import evaluate_execution_gate
        from app.core.operator_approval import issue_approval
        from app.core.execution_policy import evaluate_execution_policy

        pf = run_recovery_preflight()
        gate = evaluate_execution_gate()
        apr = issue_approval()
        pol = evaluate_execution_policy()

        # Extract trading_authorized from gate conditions
        trading_auth = None
        if gate:
            for c in gate.conditions:
                if c.name == "trading_authorized":
                    trading_auth = c.observed == "true"

        return {
            "pipeline_state": "ALL_CLEAR" if (gate and gate.conditions_met == 4) else "BLOCKED",
            "preflight_decision": pf.decision.value if pf else "NOT_READY",
            "gate_decision": gate.decision.value if gate else "CLOSED",
            "approval_decision": apr.decision.value if apr else "REJECTED",
            "policy_decision": pol.decision.value if pol else "UNKNOWN",
            "ops_score": gate.ops_score_average if gate else None,
            "trading_authorized": trading_auth,
            "lockdown_state": "NORMAL",
            "preflight_evidence_id": pf.evidence_id if pf else "",
            "gate_evidence_id": gate.evidence_id if (gate and hasattr(gate, "evidence_id")) else "",
            "approval_id": apr.approval_id if (apr and hasattr(apr, "approval_id")) else "",
        }
    except Exception as e:
        logger.error("_build_ops_safety_summary_failed", error=str(e))
        return {}  # Fail-closed: empty data → all stages MISSING


# ---------------------------------------------------------------------------
# C-04 Phase 7 — Manual Recovery / Simulation / Preview
# Manual only. Sync only. Chain-gated. Receipt + audit.
# ---------------------------------------------------------------------------
@router.post("/api/manual-action/rollback", include_in_schema=False)
async def manual_action_rollback(request: Request):
    """C-04 Phase 7: Manual rollback — 9-stage chain revalidation required."""
    try:
        from app.core.manual_recovery_handler import manual_rollback

        body = (
            await request.json()
            if request.headers.get("content-type") == "application/json"
            else {}
        )
        safety_data = await _build_ops_safety_summary()
        op = _get_operator_id(request)
        receipt = manual_rollback(
            safety_data, original_receipt_id=body.get("original_receipt_id", ""), operator_id=op
        )
        return receipt.model_dump()
    except Exception as e:
        logger.error("manual_rollback_failed", error=str(e))
        return {"decision": "FAILED", "reason": str(e)[:200]}


@router.post("/api/manual-action/retry", include_in_schema=False)
async def manual_action_retry(request: Request):
    """C-04 Phase 7: Manual retry — 9-stage chain revalidation required."""
    try:
        from app.core.manual_recovery_handler import manual_retry

        body = (
            await request.json()
            if request.headers.get("content-type") == "application/json"
            else {}
        )
        safety_data = await _build_ops_safety_summary()
        op = _get_operator_id(request)
        receipt = manual_retry(
            safety_data, original_receipt_id=body.get("original_receipt_id", ""), operator_id=op
        )
        return receipt.model_dump()
    except Exception as e:
        logger.error("manual_retry_failed", error=str(e))
        return {"decision": "FAILED", "reason": str(e)[:200]}


@router.post("/api/manual-action/simulate", include_in_schema=False)
async def manual_action_simulate(request: Request):
    """C-04 Phase 7: Simulation — read-only chain check. No mutation."""
    try:
        from app.core.manual_recovery_handler import simulate_action

        safety_data = await _build_ops_safety_summary()
        op = _get_operator_id(request)
        receipt = simulate_action(safety_data, operator_id=op)
        return receipt.model_dump()
    except Exception as e:
        logger.error("manual_simulate_failed", error=str(e))
        return {"decision": "FAILED", "reason": str(e)[:200]}


@router.post("/api/manual-action/preview", include_in_schema=False)
async def manual_action_preview(request: Request):
    """C-04 Phase 7: Preview — text-based action description. No computation."""
    try:
        from app.core.manual_recovery_handler import preview_action

        safety_data = await _build_ops_safety_summary()
        op = _get_operator_id(request)
        result = preview_action(safety_data, operator_id=op)
        return result.model_dump()
    except Exception as e:
        logger.error("manual_preview_failed", error=str(e))
        return {"action_summary": "Preview unavailable", "preview_note": "Error occurred"}


def _compute_global_status_bar(now: datetime) -> GlobalStatusBar:
    """제7조: 전역 상태 바 계산. 표시 전용."""
    try:
        import app.main as main_module

        app_instance = main_module.app
        gate = getattr(app_instance.state, "governance_gate", None)

        # Enforcement state from security context
        enforcement_state = "UNKNOWN"
        if gate is not None and hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            if hasattr(ctx, "current"):
                enforcement_state = (
                    ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)
                )

        # Trading permission: conservative — only True when governance active
        # and security state is NORMAL. Display value only, not authority.
        trading_permission = gate is not None and enforcement_state == "NORMAL"

        return GlobalStatusBar(
            app_env=settings.app_env,
            phase="prod" if settings.is_production else settings.app_env,
            enforcement_state=enforcement_state,
            trading_permission=trading_permission,
            current_server_time=now.isoformat(),
            last_successful_api_poll=None,  # populated by exchange sync layer
            link_lost_since=None,
            prod_lock=settings.is_production,
        )
    except Exception as e:
        logger.warning("ops_global_status_bar_failed", error=str(e))
        return GlobalStatusBar(
            app_env=settings.app_env,
            phase=settings.app_env,
            enforcement_state="UNKNOWN",
            trading_permission=False,
            current_server_time=now.isoformat(),
            last_successful_api_poll=None,
            link_lost_since=None,
            prod_lock=settings.is_production,
        )


async def _compute_integrity_panel(db: AsyncSession, now: datetime) -> IntegrityPanel:
    """제8조: 무결성 패널 계산. 표시용 계산만, 자동 점검 엔진 아님."""
    # CR-026: Mode 1 awareness — distinguish "no trades yet" from "data stale".
    from app.core.config import settings as _cfg

    is_testnet = getattr(_cfg, "binance_testnet", True)

    try:
        # Snapshot age: newest position update (primary)
        latest_pos = await db.execute(
            select(Position.updated_at).order_by(Position.updated_at.desc()).limit(1)
        )
        latest_ts = latest_pos.scalar()

        # Fallback: newest AssetSnapshot.snapshot_at (when no positions exist)
        if latest_ts is None:
            from app.models.asset_snapshot import AssetSnapshot

            latest_snap = await db.execute(
                select(AssetSnapshot.snapshot_at)
                .order_by(AssetSnapshot.snapshot_at.desc())
                .limit(1)
            )
            latest_ts = latest_snap.scalar()

        snapshot_age = (
            int((now - latest_ts.replace(tzinfo=timezone.utc)).total_seconds())
            if latest_ts
            else None
        )

        # CR-026: Stale data判定 — Mode 1 cold-start (no positions, no snapshots)
        # is NOT the same as "stale". Stale = data EXISTS but is old.
        if snapshot_age is None:
            # No data at all — cold-start, not stale
            stale_data = False
        elif snapshot_age > 300:
            stale_data = True
        else:
            stale_data = False

        return IntegrityPanel(
            exchange_db_consistency="unknown",  # full check requires exchange API
            snapshot_age_seconds=snapshot_age,
            position_mismatch=False,  # requires exchange comparison (future)
            open_orders_mismatch=False,
            balance_mismatch=False,
            stale_data=stale_data,
        )
    except Exception as e:
        logger.warning("ops_integrity_panel_failed", error=str(e))
        return IntegrityPanel(
            exchange_db_consistency="unknown",
            snapshot_age_seconds=None,
            position_mismatch=False,
            open_orders_mismatch=False,
            balance_mismatch=False,
            stale_data=False,  # CR-026: fail-closed changed to fail-neutral for cold-start
        )


async def _compute_trading_safety_panel(db: AsyncSession) -> TradingSafetyPanel:
    """제9조: 거래 안전 패널 계산. 표시 전용, 거래 승인/해제 로직 없음."""
    # CR-026: Fail-soft per field. One query failure must not collapse entire panel.
    # CR-026: Mode 1 steady-state awareness — testnet observation is the default mode.
    from app.core.config import settings as _cfg

    is_testnet = getattr(_cfg, "binance_testnet", True)

    # --- Order metrics (fail-soft: isolated try/except) ---
    total_orders = 0
    reject_count = 0
    success_rate = None
    cancel_count = 0
    order_query_ok = True
    try:
        # BL-TZ01: Order.created_at is DateTime (naive, TIMESTAMP WITHOUT TIME ZONE).
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        total_orders_result = await db.execute(
            select(func.count(Order.id)).where(Order.created_at >= recent_cutoff)
        )
        total_orders = total_orders_result.scalar() or 0

        rejected_result = await db.execute(
            select(func.count(Order.id)).where(
                Order.created_at >= recent_cutoff,
                Order.status == OrderStatus.REJECTED,
            )
        )
        reject_count = rejected_result.scalar() or 0

        success_rate = (
            round((total_orders - reject_count) / total_orders, 4) if total_orders > 0 else None
        )

        cancelled_result = await db.execute(
            select(func.count(Order.id)).where(
                Order.created_at >= recent_cutoff,
                Order.status == OrderStatus.CANCELLED,
            )
        )
        cancel_count = cancelled_result.scalar() or 0
    except Exception as e:
        logger.warning("ops_trading_safety_order_query_failed", error=str(e))
        order_query_ok = False

    # --- Security context (fail-soft: isolated try/except) ---
    kill_switch = False
    enforcement = "NORMAL"
    try:
        import app.main as main_module

        gate = getattr(main_module.app.state, "governance_gate", None)
        if gate is not None and hasattr(gate, "security_ctx"):
            ctx = gate.security_ctx
            state_val = ctx.current.value if hasattr(ctx.current, "value") else str(ctx.current)
            enforcement = state_val
            kill_switch = state_val in ("LOCKDOWN", "QUARANTINED")
    except Exception:
        pass

    # --- Trading block reason ---
    block_reason = None
    if kill_switch:
        block_reason = f"Security state: {enforcement}"
    elif reject_count > 0 and total_orders > 0 and reject_count / total_orders > 0.5:
        block_reason = f"High reject rate: {reject_count}/{total_orders}"
    elif not order_query_ok:
        block_reason = "Order metrics unavailable (DB query failed)"

    # CR-026: trading_mode reflects operational reality.
    # Mode 1 (testnet=true) → "observation" always.
    # Mode 2 would be "active" (when kill_switch is not engaged).
    if kill_switch:
        trading_mode = "observation"
    elif is_testnet:
        trading_mode = "observation"
    else:
        trading_mode = "active"

    # CR-026: latency_status — "not_measured" is not a warning.
    # Measurement requires active order flow (Mode 2+).
    latency = "not_measured"

    return TradingSafetyPanel(
        allowed_capital_ratio=None,  # requires risk manager (future)
        order_success_rate=success_rate,
        reject_count=reject_count,
        cancel_residual=cancel_count > 0,
        latency_status=latency,
        kill_switch_active=kill_switch,
        current_trading_mode=trading_mode,
        trading_block_reason=block_reason,
    )


def _compute_incident_panel() -> IncidentEvidencePanel:
    """제10조: 사고·증거 패널. 현재/최근 요약만 표시. Playback/Recovery 금지."""
    try:
        import app.main as main_module

        app_instance = main_module.app

        # Check receipt store for most recent incident
        receipt_store = getattr(app_instance.state, "receipt_store", None)
        if receipt_store is not None and receipt_store.count() > 0:
            receipts = receipt_store.list_receipts(limit=1)
            if receipts:
                latest = receipts[0]
                return IncidentEvidencePanel(
                    incident_title=latest.get("highest_incident"),
                    severity=latest.get("severity_tier"),
                    first_occurred_at=latest.get("stored_at"),
                    last_confirmed_at=latest.get("stored_at"),
                    impact_scope=None,
                    auto_action_result=latest.get("policy_action"),
                    operator_action_required=latest.get("severity_tier") in ("critical", "high"),
                    evidence_receipt_id=latest.get("receipt_id"),
                )

        return IncidentEvidencePanel()
    except Exception as e:
        logger.warning("ops_incident_panel_failed", error=str(e))
        return IncidentEvidencePanel()


def _compute_system_status(
    global_bar: GlobalStatusBar,
    integrity: IntegrityPanel,
    trading_safety: TradingSafetyPanel,
) -> SystemStatus:
    """
    제12조: 시스템 상태 문구 결정.
    상태 매핑 원칙:
      LOCKDOWN → LOCKDOWN
      명시적 제약/격리 → BRAKE
      제한 + 일부 기능 유지 → DEGRADED
      startup incomplete / unknown / evidence 부족 → UNVERIFIED
      모든 핵심 체크 통과 → HEALTHY
      모호하면 UNVERIFIED (Unknown ≠ Normal)
    """
    enforcement = global_bar.enforcement_state

    # LOCKDOWN
    if enforcement == "LOCKDOWN":
        return SystemStatus(
            status_word=SystemStatusWord.LOCKDOWN,
            status_reason="Security state: LOCKDOWN",
        )

    # BRAKE
    if enforcement in ("QUARANTINED",):
        return SystemStatus(
            status_word=SystemStatusWord.BRAKE,
            status_reason=f"Security state: {enforcement}",
        )

    # Kill switch active → BRAKE
    if trading_safety.kill_switch_active:
        return SystemStatus(
            status_word=SystemStatusWord.BRAKE,
            status_reason="Kill switch active",
        )

    # UNVERIFIED: unknown enforcement state
    if enforcement in ("UNKNOWN", ""):
        return SystemStatus(
            status_word=SystemStatusWord.UNVERIFIED,
            status_reason=f"Enforcement state unknown: {enforcement}",
        )

    # DEGRADED: stale data or integrity issues
    degraded_reasons = []
    if integrity.stale_data:
        degraded_reasons.append("stale data")
    if integrity.exchange_db_consistency == "mismatch":
        degraded_reasons.append("integrity mismatch")
    if integrity.position_mismatch or integrity.open_orders_mismatch:
        degraded_reasons.append("data mismatch")
    if trading_safety.trading_block_reason:
        degraded_reasons.append(trading_safety.trading_block_reason)

    if enforcement == "RESTRICTED":
        return SystemStatus(
            status_word=SystemStatusWord.DEGRADED,
            status_reason=f"Restricted: {', '.join(degraded_reasons) or enforcement}",
        )

    if degraded_reasons:
        return SystemStatus(
            status_word=SystemStatusWord.DEGRADED,
            status_reason=f"Degraded: {', '.join(degraded_reasons)}",
        )

    # HEALTHY: all checks pass
    if enforcement == "NORMAL" and not integrity.stale_data:
        return SystemStatus(
            status_word=SystemStatusWord.HEALTHY,
            status_reason="All checks passed",
        )

    # Default: UNVERIFIED (Unknown ≠ Normal)
    return SystemStatus(
        status_word=SystemStatusWord.UNVERIFIED,
        status_reason="Insufficient evidence for HEALTHY determination",
    )


def _compute_dual_lock(system_status: SystemStatus, trading_safety: TradingSafetyPanel) -> DualLock:
    """
    제42조: System Healthy / Trading Authorized 분리 표기.
    두 상태는 독립적. 시스템 정상이어도 거래 금지 가능.
    표시값 전용. 실제 거래 승인/해제 로직 아님.
    """
    system_healthy = system_status.status_word == SystemStatusWord.HEALTHY

    # Trading authorized: system must be healthy AND no kill switch AND no block reason
    trading_authorized = (
        system_healthy
        and not trading_safety.kill_switch_active
        and trading_safety.trading_block_reason is None
    )

    return DualLock(
        system_healthy=system_healthy,
        trading_authorized=trading_authorized,
    )


def _compute_ops_score(
    integrity: IntegrityPanel,
    trading_safety: TradingSafetyPanel,
    incident: IncidentEvidencePanel,
) -> OpsScore:
    """
    제41조: Ops Score 4축 계산. 보조 지표. 단독 권한 없음.
    Ops Score 하락은 BRAKE 권고 근거로 사용할 수 있으나, 자동 차단을 실행하지 않는다.
    """
    # Integrity axis
    integrity_score = 1.0
    if integrity.stale_data:
        integrity_score -= 0.3
    if integrity.exchange_db_consistency == "mismatch":
        integrity_score -= 0.3
    if integrity.position_mismatch or integrity.open_orders_mismatch:
        integrity_score -= 0.2
    if integrity.exchange_db_consistency == "unknown":
        integrity_score -= 0.1

    # Connectivity axis
    # CR-026: snapshot_age=None means cold-start (no data yet), not disconnected.
    # Check worker health as secondary signal before collapsing to 0.
    connectivity_score = 1.0
    if integrity.snapshot_age_seconds is None:
        # CR-026: Cold-start — no snapshot data. Check if workers are alive.
        try:
            import app.main as main_module

            gate = getattr(main_module.app.state, "governance_gate", None)
            if gate is not None:
                connectivity_score = 0.6  # workers up, no snapshot yet
            else:
                connectivity_score = 0.3  # no gate, uncertain
        except Exception:
            connectivity_score = 0.3  # uncertain, not zero
    elif integrity.snapshot_age_seconds > 600:
        connectivity_score = 0.2
    elif integrity.snapshot_age_seconds > 300:
        connectivity_score = 0.5
    elif integrity.snapshot_age_seconds > 60:
        connectivity_score = 0.8

    # Execution Safety axis
    execution_score = 1.0
    if trading_safety.kill_switch_active:
        execution_score = 0.0
    elif trading_safety.order_success_rate is not None:
        execution_score = min(trading_safety.order_success_rate, 1.0)
    if trading_safety.cancel_residual:
        execution_score = max(execution_score - 0.2, 0.0)

    # Evidence Completeness axis
    evidence_score = 1.0
    if incident.evidence_receipt_id is None and incident.incident_title is not None:
        evidence_score = 0.3  # incident without evidence
    elif incident.incident_title is None:
        evidence_score = 0.8  # no incident, partial evidence check

    return OpsScore(
        integrity=round(max(integrity_score, 0.0), 2),
        connectivity=round(max(connectivity_score, 0.0), 2),
        execution_safety=round(max(execution_score, 0.0), 2),
        evidence_completeness=round(max(evidence_score, 0.0), 2),
        note="보조 지표. 단독 권한 없음.",
    )
