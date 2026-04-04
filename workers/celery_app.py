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
}
