from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal, SignalStatus
from app.schemas.signal import SignalCreate
from app.agents.signal_validator import SignalValidatorAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


class SignalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_signal(self, signal_data: SignalCreate) -> Signal:
        signal = Signal(
            source=signal_data.source,
            exchange=signal_data.exchange,
            symbol=signal_data.symbol,
            signal_type=signal_data.signal_type,
            entry_price=signal_data.entry_price,
            stop_loss=signal_data.stop_loss,
            take_profit=signal_data.take_profit,
            confidence=signal_data.confidence,
            signal_metadata=signal_data.signal_metadata,
        )
        self.db.add(signal)
        await self.db.flush()
        logger.info("Signal created", signal_id=signal.id, symbol=signal.symbol)
        return signal

    async def get_signals(self, skip: int = 0, limit: int = 100) -> list[Signal]:
        result = await self.db.execute(
            select(Signal).offset(skip).limit(limit).order_by(Signal.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_signal(self, signal_id: str) -> Signal | None:
        result = await self.db.execute(select(Signal).where(Signal.id == signal_id))
        return result.scalar_one_or_none()

    async def validate_with_agent(self, signal_id: str) -> dict:
        signal = await self.get_signal(signal_id)
        if not signal:
            return {"success": False, "error": "Signal not found"}

        validator = SignalValidatorAgent()
        result = await validator.validate(signal)

        signal.agent_analysis = result.get("reasoning")
        if result.get("approved"):
            signal.status = SignalStatus.VALIDATED
            signal.confidence = result.get("confidence", signal.confidence)
        else:
            signal.status = SignalStatus.REJECTED

        logger.info(
            "Signal validated",
            signal_id=signal_id,
            status=signal.status.value,
            confidence=signal.confidence,
        )
        return result
