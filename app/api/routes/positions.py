from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.position import PositionResponse, PositionList
from app.services.position_service import PositionService

router = APIRouter()


@router.get("/", response_model=PositionList)
async def list_positions(
    exchange: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = PositionService(db)
    positions = await service.get_positions(exchange=exchange)
    return PositionList(positions=positions, total=len(positions))


@router.get("/sync")
async def sync_positions(
    exchange: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = PositionService(db)
    await service.sync_from_exchange(exchange=exchange)
    return {"status": "synced"}


@router.post("/{position_id}/close")
async def close_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = PositionService(db)
    result = await service.close_position(position_id)
    return result
