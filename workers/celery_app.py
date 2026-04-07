import json
import logging
import os

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "trading_workers",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.order_tasks",
        "workers.tasks.signal_tasks",
        "workers.tasks.market_tasks",
        "workers.tasks.snapshot_tasks",
        "workers.tasks.check_tasks",  # S-02: operational check tasks
        "workers.tasks.governance_monitor_tasks",  # G-MON: governance monitor
        "workers.tasks.data_collection_tasks",  # CR-038: market data + sentiment
        "workers.tasks.shadow_observation_tasks",  # CR-048 2A P3-B: shadow observation (dry-run)
        "workers.tasks.sol_paper_tasks",  # CR-046 Phase 5a-B: SOL paper trading (dry_run=True)
        "workers.tasks.cycle_runner_tasks",  # CR-048: strategy cycle runner (dry_run=True)
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    # ── DISABLED (CR-049 BL-EXMODE01): private API tasks removed from schedule ──
    # "sync-positions-every-minute" — REQUIRES_PRIVATE_API, re-enable at PAPER mode
    # "check-order-status-every-30s" — REQUIRES_PRIVATE_API, re-enable at PAPER mode
    #
    # ── Active schedule (14 entries) ──
    # CR-046 Stage B: SOL paper trading (dry_run=True, hourly, SOL only)
    "sol-paper-trading-hourly": {
        "task": "workers.tasks.sol_paper_tasks.run_sol_paper_bar",
        "schedule": 3600.0,  # 1h
        "kwargs": {"symbol": "SOL/USDT", "exchange_name": "binance"},
    },
    "expire-old-signals": {
        "task": "workers.tasks.signal_tasks.expire_signals",
        "schedule": 300.0,
    },
    "record-asset-snapshot-every-5m": {
        "task": "workers.tasks.snapshot_tasks.record_asset_snapshot",
        "schedule": 300.0,
    },
    # S-02: read-only operational checks (Check, Don't Repair)
    "ops-daily-check": {
        "task": "workers.tasks.check_tasks.run_daily_ops_check",
        "schedule": 86400.0,  # 24h
    },
    "ops-hourly-check": {
        "task": "workers.tasks.check_tasks.run_hourly_ops_check",
        "schedule": 3600.0,  # 1h
    },
    # G-MON: governance monitor (6 indicators, notification on WARN/FAIL)
    "governance-monitor-daily": {
        "task": "workers.tasks.governance_monitor_tasks.run_daily_governance_report",
        "schedule": 86400.0,  # 24h
    },
    "governance-monitor-weekly": {
        "task": "workers.tasks.governance_monitor_tasks.run_weekly_governance_summary",
        "schedule": 604800.0,  # 7d
    },
    # CR-038: market state collection (price + indicators + sentiment)
    "collect-market-state-every-5m": {
        "task": "workers.tasks.data_collection_tasks.collect_market_state",
        "schedule": 300.0,  # 5min
        "kwargs": {"symbol": "BTC/USDT", "exchange_name": "binance"},
    },
    # CR-046: SOL market state collection (mirrors BTC entry for SOL symbol)
    "collect-sol-market-state-every-5m": {
        "task": "workers.tasks.data_collection_tasks.collect_market_state",
        "schedule": 300.0,  # 5min
        "kwargs": {"symbol": "SOL/USDT", "exchange_name": "binance"},
    },
    "collect-sentiment-hourly": {
        "task": "workers.tasks.data_collection_tasks.collect_sentiment_only",
        "schedule": 3600.0,  # 1h
    },
    # CR-048 2A P3-B: shadow observation dry-run (DRY_SCHEDULE=True)
    # Activated from dormant state. DRY_SCHEDULE=False requires P4 approval.
    "shadow-observation-5m": {
        "task": "workers.tasks.shadow_observation_tasks.run_shadow_observation",
        "schedule": 300.0,  # 5min — must remain 300s
    },
    # CR-048: Strategy cycle runners (dry_run=True, DATA_ONLY mode)
    "strategy-cycle-crypto-5m": {
        "task": "workers.tasks.cycle_runner_tasks.run_strategy_cycle",
        "schedule": 300.0,  # 5min
        "kwargs": {"market": "CRYPTO", "dry_run": True},
    },
    "strategy-cycle-kr-stock-5m": {
        "task": "workers.tasks.cycle_runner_tasks.run_strategy_cycle",
        "schedule": 300.0,  # 5min
        "kwargs": {"market": "KR_STOCK", "dry_run": True},
    },
    "strategy-cycle-us-stock-5m": {
        "task": "workers.tasks.cycle_runner_tasks.run_strategy_cycle",
        "schedule": 300.0,  # 5min
        "kwargs": {"market": "US_STOCK", "dry_run": True},
    },
}

# ---------------------------------------------------------------------------
# BL-OPS-RESTART01: Startup fingerprint & beat init guard
# ---------------------------------------------------------------------------

_OPS_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "ops_state.json")


def _load_ops_state() -> dict:
    """Load ops_state.json (read-only). Returns empty dict on failure."""
    try:
        with open(_OPS_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _startup_fingerprint(caller: str) -> None:
    """
    Log operational_mode, exchange_mode, and schedule counts at startup.
    Called by worker/beat init and tests. Never raises.
    """
    try:
        state = _load_ops_state()
        operational_mode = state.get("operational_mode", "UNKNOWN")
        exchange_mode = state.get("baseline_values", {}).get("exchange_mode", "UNKNOWN")
        schedule = celery_app.conf.beat_schedule or {}
        active_count = len(schedule)

        logger.info(
            "startup_fingerprint",
            extra={
                "caller": caller,
                "operational_mode": operational_mode,
                "exchange_mode": exchange_mode,
                "active_schedule_count": active_count,
            },
        )
    except Exception as exc:
        logger.warning("startup_fingerprint_failed", extra={"error": str(exc)})


def _on_beat_init(**kwargs) -> None:
    """
    Beat init guard: detect stale beat entries not defined in code.
    Compares effective schedule keys against code-defined keys.
    Never raises.
    """
    try:
        effective_keys = set((celery_app.conf.beat_schedule or {}).keys())
        # Code-defined keys are the ones in this module's beat_schedule dict
        code_defined_keys = set(celery_app.conf.beat_schedule.keys())

        stale = effective_keys - code_defined_keys
        if stale:
            logger.warning(
                "stale_beat_entry_detected",
                extra={"stale_keys": sorted(stale)},
            )
        else:
            logger.info(
                "beat_init_clean",
                extra={"schedule_count": len(effective_keys)},
            )
    except Exception as exc:
        logger.warning("beat_init_guard_failed", extra={"error": str(exc)})
