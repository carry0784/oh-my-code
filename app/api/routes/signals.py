from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.signal import SignalCreate, SignalResponse, SignalList
from app.services.signal_service import SignalService

router = APIRouter()


@router.post("/", response_model=SignalResponse)
async def create_signal(
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
