from fastapi import APIRouter

from app.api.routes import orders, signals, positions, agents

router = APIRouter()

router.include_router(orders.router, prefix="/orders", tags=["orders"])
router.include_router(signals.router, prefix="/signals", tags=["signals"])
router.include_router(positions.router, prefix="/positions", tags=["positions"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
