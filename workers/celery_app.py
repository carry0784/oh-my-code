from celery import Celery

from app.core.config import settings

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
    "sync-positions-every-minute": {
        "task": "workers.tasks.market_tasks.sync_all_positions",
        "schedule": 60.0,
    },
    "check-order-status-every-30s": {
        "task": "workers.tasks.order_tasks.check_pending_orders",
        "schedule": 30.0,
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
    # CR-046 Phase 5a-B: SOL paper trading observation (dry_run=True hardcoded)
    # Beat registered for receipt accumulation. BTC beat registration is separate.
    "sol-paper-trading-hourly": {
        "task": "workers.tasks.sol_paper_tasks.run_sol_paper_bar",
        "schedule": 3600.0,  # 1H — matches strategy timeframe
        "kwargs": {"symbol": "SOL/USDT", "exchange_name": "binance"},
    },
}
