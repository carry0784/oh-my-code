from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.signal import SignalCreate, SignalResponse, SignalList
from app.services.signal_service import SignalService

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=SignalResponse)
@limiter.limit("30/minute")
async def create_signal(
    request: Request,
    signal: SignalCreate,
    db: AsyncSession = Depends(get_db),
):
    service = SignalService(db)
    return await service.create_signal(signal)


@router.get("/", response_model=SignalList)
async def list_signals(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    service = SignalService(db)
    signals = await service.get_signals(skip=skip, limit=limit)
    return SignalList(signals=signals, total=len(signals))


@router.post("/{signal_id}/validate")
async def validate_signal(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = SignalService(db)
    result = await service.validate_with_agent(signal_id)
    return result
