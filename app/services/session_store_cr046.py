"""
CR-046 SessionStore & ReceiptStore

Postgres-backed persistence for paper trading sessions and receipts.
SessionStore uses optimistic locking (version column).
ReceiptStore is append-only.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.paper_session import (
    PaperTradingSessionModel,
    PaperTradingReceiptModel,
    PromotionReceiptModel,
)
from app.services.paper_trading_session_cr046 import (
    CR046PaperSession,
    PaperTradingReceipt,
    PromotionReceipt,
)

logger = get_logger(__name__)

STALE_THRESHOLD = timedelta(hours=2)


class OptimisticLockError(Exception):
    """Raised when version mismatch on session save."""

    pass


class DuplicateBarError(Exception):
    """Raised when (session_id, bar_ts) already exists."""

    pass


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------


class SessionStore:
    """CR046PaperSession persistence. Postgres-backed, optimistic lock."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, session_id: str) -> CR046PaperSession | None:
        stmt = select(PaperTradingSessionModel).where(
            PaperTradingSessionModel.session_id == session_id,
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        session = CR046PaperSession(
            session_id=row.session_id,
            symbol=row.symbol,
            daily_pnl=row.daily_pnl,
            weekly_trades=row.weekly_trades,
            consecutive_losing_days=row.consecutive_losing_days,
            is_halted=row.is_halted,
            halt_reason=row.halt_reason,
            open_position=row.open_position,
            consecutive_high_latency=getattr(row, "consecutive_high_latency", 0),
            last_daily_reset_utc=row.last_daily_reset_utc,
            last_weekly_reset_utc=row.last_weekly_reset_utc,
            version=row.version,
            last_updated_at=row.last_updated_at,
        )

        # Stale check
        age = datetime.now(timezone.utc) - row.last_updated_at.replace(tzinfo=timezone.utc)
        if age > STALE_THRESHOLD:
            logger.warning(
                "stale_session_detected",
                session_id=session_id,
                age_seconds=age.total_seconds(),
            )

        return session

    async def save(self, session: CR046PaperSession) -> None:
        """Atomic save with optimistic lock. Raises OptimisticLockError on conflict."""
        now = datetime.now(timezone.utc)
        new_version = session.version + 1

        stmt = (
            update(PaperTradingSessionModel)
            .where(
                PaperTradingSessionModel.session_id == session.session_id,
                PaperTradingSessionModel.version == session.version,
            )
            .values(
                daily_pnl=session.daily_pnl,
                weekly_trades=session.weekly_trades,
                consecutive_losing_days=session.consecutive_losing_days,
                is_halted=session.is_halted,
                halt_reason=session.halt_reason,
                open_position=session.open_position,
                consecutive_high_latency=session.consecutive_high_latency,
                last_daily_reset_utc=session.last_daily_reset_utc,
                last_weekly_reset_utc=session.last_weekly_reset_utc,
                version=new_version,
                last_updated_at=now,
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            raise OptimisticLockError(
                f"Version mismatch for session {session.session_id} "
                f"(expected version={session.version})"
            )
        session.version = new_version
        session.last_updated_at = now

    async def create(self, session: CR046PaperSession) -> None:
        """Create new session. Raises IntegrityError on duplicate session_id."""
        now = datetime.now(timezone.utc)
        model = PaperTradingSessionModel(
            session_id=session.session_id,
            symbol=session.symbol,
            daily_pnl=session.daily_pnl,
            weekly_trades=session.weekly_trades,
            consecutive_losing_days=session.consecutive_losing_days,
            is_halted=session.is_halted,
            halt_reason=session.halt_reason,
            open_position=session.open_position,
            consecutive_high_latency=session.consecutive_high_latency,
            last_daily_reset_utc=session.last_daily_reset_utc or now,
            last_weekly_reset_utc=session.last_weekly_reset_utc or now,
            version=1,
            last_updated_at=now,
            created_at=now,
        )
        self.db.add(model)
        await self.db.flush()
        session.version = 1
        session.last_updated_at = now


# ---------------------------------------------------------------------------
# ReceiptStore
# ---------------------------------------------------------------------------


class ReceiptStore:
    """PaperTradingReceipt persistence. Append-only."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, receipt: PaperTradingReceipt) -> None:
        """Insert receipt. Raises DuplicateBarError on (session_id, bar_ts) conflict."""
        import dataclasses

        data = dataclasses.asdict(receipt)

        model = PaperTradingReceiptModel(
            receipt_id=receipt.receipt_id,
            session_id=receipt.session_id,
            bar_ts=receipt.bar_ts,
            symbol=receipt.symbol,
            action=receipt.action,
            decision_source=receipt.decision_source,
            dry_run=receipt.dry_run,
            data=data,
        )
        try:
            self.db.add(model)
            await self.db.flush()
        except IntegrityError as e:
            if "uq_session_bar" in str(e).lower() or "session_id" in str(e).lower():
                raise DuplicateBarError(
                    f"Duplicate bar: session={receipt.session_id}, bar_ts={receipt.bar_ts}"
                ) from e
            raise

    async def get_by_session(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[PaperTradingReceipt]:
        stmt = (
            select(PaperTradingReceiptModel)
            .where(PaperTradingReceiptModel.session_id == session_id)
            .order_by(PaperTradingReceiptModel.bar_ts)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [self._to_receipt(r) for r in rows]

    async def get_by_ids(self, receipt_ids: list[str]) -> list[PaperTradingReceipt]:
        if not receipt_ids:
            return []
        stmt = select(PaperTradingReceiptModel).where(
            PaperTradingReceiptModel.receipt_id.in_(receipt_ids),
        )
        result = await self.db.execute(stmt)
        return [self._to_receipt(r) for r in result.scalars().all()]

    def _to_receipt(self, model: PaperTradingReceiptModel) -> PaperTradingReceipt:
        data = model.data or {}
        return PaperTradingReceipt(
            receipt_id=model.receipt_id,
            session_id=model.session_id,
            bar_ts=model.bar_ts,
            symbol=model.symbol,
            action=model.action,
            decision_source=model.decision_source,
            dry_run=model.dry_run,
            signal=data.get("signal"),
            consensus_pass=data.get("consensus_pass", False),
            session_can_enter=data.get("session_can_enter", False),
            guard_pass=data.get("guard_pass"),
            guard_details=data.get("guard_details"),
            strategy_version=data.get("strategy_version", ""),
            entry_price=data.get("entry_price"),
            expected_sl=data.get("expected_sl"),
            expected_tp=data.get("expected_tp"),
            halt_state=data.get("halt_state", False),
            block_reason=data.get("block_reason"),
            execution_latency_ms=data.get("execution_latency_ms"),
            api_latency_ms=data.get("api_latency_ms"),
            spread_pct=data.get("spread_pct"),
        )


# ---------------------------------------------------------------------------
# PromotionReceiptStore
# ---------------------------------------------------------------------------


class PromotionReceiptStore:
    """PromotionReceipt persistence. Append-only INSERT, no UPDATE/DELETE."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, receipt: PromotionReceipt) -> None:
        if not receipt.approved_by:
            raise ValueError("approved_by must not be empty")
        if not receipt.linked_receipt_ids:
            raise ValueError("linked_receipt_ids must have at least 1 entry")

        model = PromotionReceiptModel(
            receipt_id=receipt.receipt_id,
            session_id=receipt.session_id,
            promotion_target=receipt.promotion_target,
            promotion_basis=receipt.promotion_basis,
            approved_by=receipt.approved_by,
            approved_at=datetime.fromisoformat(receipt.approved_at),
            linked_receipt_ids=receipt.linked_receipt_ids,
            risk_notes=receipt.risk_notes,
        )
        self.db.add(model)
        await self.db.flush()
