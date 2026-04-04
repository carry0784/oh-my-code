"""
Asset Snapshot Task — I-05 총 자산 시계열
Celery beat task: records periodic asset snapshots from DB positions/trades.
Read-only aggregation from existing data — no exchange API calls.
"""

from sqlalchemy import func

from workers.celery_app import celery_app
from workers.tasks.order_tasks import get_sync_session
from app.models.position import Position
from app.models.trade import Trade
from app.models.asset_snapshot import AssetSnapshot
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task
def record_asset_snapshot():
    """
    Record a periodic snapshot of total portfolio value.
    Reads from DB positions and trades — no exchange API calls.
    """
    session = get_sync_session()
    try:
        # Aggregate total value from all positions
        positions = session.query(Position).all()
        total_value = sum(
            (p.entry_price or 0) * (p.quantity or 0) for p in positions
        )
        unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)
        total_balance = sum(
            (p.current_price or 0) * (p.quantity or 0) for p in positions
        )

        # Total trade count
        trade_count = session.query(func.count(Trade.id)).scalar() or 0

        snapshot = AssetSnapshot(
            total_value=total_value,
            trade_count=trade_count,
            total_balance=total_balance,
            unrealized_pnl=unrealized_pnl,
        )
        session.add(snapshot)
        session.commit()
        logger.info(
            "Asset snapshot recorded",
            total_value=total_value,
            trade_count=trade_count,
            unrealized_pnl=unrealized_pnl,
            position_count=len(positions),
        )
    except Exception as e:
        session.rollback()
        logger.error("Asset snapshot failed", error=str(e))
        raise
    finally:
        session.close()
