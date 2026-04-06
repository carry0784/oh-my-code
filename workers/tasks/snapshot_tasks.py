"""
Asset Snapshot Task — I-05 총 자산 시계열
Celery beat task: records periodic asset snapshots from DB positions/trades.
Read-only aggregation from existing data — no exchange API calls.
"""

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from workers.celery_app import celery_app
from app.core.config import settings
from app.models.position import Position
from app.models.trade import Trade
from app.models.asset_snapshot import AssetSnapshot
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level bounded engine: pool_size=1, max_overflow=0
# Prevents per-invocation engine leak (CR-048 DB saturation fix)
_sync_engine = create_engine(
    settings.database_url_sync,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=0,
    pool_recycle=1800,
)
_SyncSessionFactory = sessionmaker(bind=_sync_engine)


@celery_app.task
def record_asset_snapshot():
    """
    Record a periodic snapshot of total portfolio value.
    Reads from DB positions and trades — no exchange API calls.
    """
    session = _SyncSessionFactory()
    try:
        # Aggregate total value from all positions
        positions = session.query(Position).all()
        total_value = sum((p.entry_price or 0) * (p.quantity or 0) for p in positions)
        unrealized_pnl = sum(p.unrealized_pnl or 0 for p in positions)
        total_balance = sum((p.current_price or 0) * (p.quantity or 0) for p in positions)

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
