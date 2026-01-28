from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.order import OrderCreate, OrderResponse, OrderList
from app.services.order_service import OrderService

router = APIRouter()


@router.post("/", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    return await service.create_order(order)


@router.get("/", response_model=OrderList)
async def list_orders(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    orders = await service.get_orders(skip=skip, limit=limit)
    return OrderList(orders=orders, total=len(orders))


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = OrderService(db)
    success = await service.cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=400, detail="Could not cancel order")
    return {"status": "cancelled"}
