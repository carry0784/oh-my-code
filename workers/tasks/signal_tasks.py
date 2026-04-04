import asyncio
from datetime import datetime, timedelta, timezone

from workers.celery_app import celery_app
from workers.tasks.order_tasks import get_sync_session
from app.models.signal import Signal, SignalStatus
from app.agents.signal_validator import SignalValidatorAgent
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)
def validate_signal(self, signal_id: str):
    """Validate signal using LLM agent."""
    session = get_sync_session()
    try:
        signal = session.query(Signal).filter(Signal.id == signal_id).first()
        if not signal:
            return {"success": False, "error": "Signal not found"}

        validator = SignalValidatorAgent()

        async def _validate():
            return await validator.validate(signal)

        result = asyncio.run(_validate())

        signal.agent_analysis = result.get("reasoning")
        if result.get("approved"):
            signal.status = SignalStatus.VALIDATED
            signal.confidence = result.get("confidence", signal.confidence)
        else:
            signal.status = SignalStatus.REJECTED

        session.commit()
        logger.info("Signal validated via worker", signal_id=signal_id, status=signal.status.value)
        return {"success": True, "status": signal.status.value}

    except Exception as e:
        logger.error("Signal validation failed", signal_id=signal_id, error=str(e))
        self.retry(exc=e, countdown=10)
    finally:
        session.close()


@celery_app.task
def expire_signals():
    """Mark expired signals."""
    session = get_sync_session()
    try:
        now = datetime.now(timezone.utc)
        expired = session.query(Signal).filter(
            Signal.status == SignalStatus.PENDING,
            Signal.expires_at < now,
        ).all()

        for signal in expired:
            signal.status = SignalStatus.EXPIRED

        session.commit()
        logger.info("Expired signals processed", count=len(expired))
        return {"expired_count": len(expired)}

    finally:
        session.close()


@celery_app.task
def process_signal_pipeline(signal_id: str):
    """Full signal processing pipeline: validate -> risk check -> execute."""
    from workers.tasks.order_tasks import submit_order

    session = get_sync_session()
    try:
        signal = session.query(Signal).filter(Signal.id == signal_id).first()
        if not signal:
            return {"success": False, "error": "Signal not found"}

        # Validate
        validator = SignalValidatorAgent()

        async def _validate():
            return await validator.validate(signal)

        validation = asyncio.run(_validate())

        if not validation.get("approved"):
            signal.status = SignalStatus.REJECTED
            signal.agent_analysis = validation.get("reasoning")
            session.commit()
            return {"success": False, "reason": "Signal rejected", "analysis": validation}

        signal.status = SignalStatus.VALIDATED
        signal.confidence = validation.get("confidence", 0.5)
        signal.agent_analysis = validation.get("reasoning")
        session.commit()

        logger.info("Signal pipeline complete", signal_id=signal_id)
        return {"success": True, "signal_id": signal_id}

    except Exception as e:
        logger.error("Signal pipeline failed", signal_id=signal_id, error=str(e))
        raise
    finally:
        session.close()
