"""Control Plane Registry API — indicators, feature packs, strategies.

CR-048 Stage 1 L3: Gateway-validated CRUD + PromotionEvent audit trail.

API Capability Matrix:
  Create: allowed (control-plane metadata only)
  Read:   allowed
  Update: version publishing only (metadata)
  Delete: hard delete PROHIBITED, retire/disable only
  Execute: PROHIBITED
  Promote: PROHIBITED (event recording only)
  Activate runtime: PROHIBITED
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.indicator_registry import Indicator
from app.models.feature_pack import FeaturePack
from app.models.strategy_registry import Strategy, PromotionStatus
from app.models.promotion_state import PromotionEvent
from app.schemas.registry_schema import (
    IndicatorCreate,
    IndicatorResponse,
    FeaturePackCreate,
    FeaturePackResponse,
    StrategyCreate,
    StrategyResponse,
    PromotionEventResponse,
    RetireRequest,
    RegistryStatsResponse,
    GatewayResultResponse,
)
from app.services.injection_gateway import InjectionGateway, GatewayVerdict
from app.services.registry_service import (
    RegistryService,
    GatewayRejectionError,
    NotFoundError,
    InvalidOperationError,
)

router = APIRouter()


# ── Helper ────────────────────────────────────────────────────────────


def _service(db: AsyncSession) -> RegistryService:
    return RegistryService(db)


# ── Indicators ────────────────────────────────────────────────────────


@router.post("/indicators", response_model=IndicatorResponse)
async def register_indicator(
    data: IndicatorCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        indicator = await svc.create_indicator(data.model_dump())
    except GatewayRejectionError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "verdict": "rejected",
                "violations": e.result.violations,
                "blocked_code": e.code,
            },
        )
    return indicator


@router.get("/indicators", response_model=list[IndicatorResponse])
async def list_indicators(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    return await svc.list_indicators(status=status, category=category, skip=skip, limit=limit)


@router.get("/indicators/{indicator_id}", response_model=IndicatorResponse)
async def get_indicator(
    indicator_id: str,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        return await svc.get_indicator(indicator_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Indicator not found")


@router.post("/indicators/{indicator_id}/retire", response_model=IndicatorResponse)
async def retire_indicator(
    indicator_id: str,
    body: RetireRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    reason = body.reason if body else ""
    try:
        return await svc.retire_indicator(indicator_id, reason=reason)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Indicator not found")
    except InvalidOperationError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Feature Packs ─────────────────────────────────────────────────────


@router.post("/feature-packs", response_model=FeaturePackResponse)
async def register_feature_pack(
    data: FeaturePackCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        fp = await svc.create_feature_pack(data.model_dump())
    except GatewayRejectionError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "verdict": "rejected",
                "violations": e.result.violations,
                "blocked_code": e.code,
            },
        )
    return fp


@router.get("/feature-packs", response_model=list[FeaturePackResponse])
async def list_feature_packs(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    return await svc.list_feature_packs(status=status, skip=skip, limit=limit)


@router.get("/feature-packs/{fp_id}", response_model=FeaturePackResponse)
async def get_feature_pack(
    fp_id: str,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        return await svc.get_feature_pack(fp_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Feature pack not found")


@router.post("/feature-packs/{fp_id}/retire", response_model=FeaturePackResponse)
async def retire_feature_pack(
    fp_id: str,
    body: RetireRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    reason = body.reason if body else ""
    try:
        return await svc.retire_feature_pack(fp_id, reason=reason)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Feature pack not found")
    except InvalidOperationError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Strategies ────────────────────────────────────────────────────────


@router.post("/strategies", response_model=StrategyResponse)
async def register_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        strategy, _event = await svc.create_strategy(data.model_dump())
    except GatewayRejectionError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "verdict": "rejected",
                "violations": e.result.violations,
                "blocked_code": e.code,
            },
        )
    return strategy


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    return await svc.list_strategies(status=status, skip=skip, limit=limit)


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        return await svc.get_strategy(strategy_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.post("/strategies/{strategy_id}/retire", response_model=StrategyResponse)
async def retire_strategy(
    strategy_id: str,
    body: RetireRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    reason = body.reason if body else ""
    retired_by = body.retired_by if body else "operator"
    try:
        strategy, _event = await svc.retire_strategy(
            strategy_id, reason=reason, retired_by=retired_by
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Strategy not found")
    except InvalidOperationError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return strategy


# ── Promotion Events (read-only + record) ─────────────────────────────


@router.get("/promotion-events", response_model=list[PromotionEventResponse])
async def list_promotion_events(
    strategy_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    return await svc.list_promotion_events(strategy_id=strategy_id, skip=skip, limit=limit)


@router.get("/promotion-events/{event_id}", response_model=PromotionEventResponse)
async def get_promotion_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    try:
        return await svc.get_promotion_event(event_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Promotion event not found")


# ── Registry Stats ───────────────────────────────────────────────────


@router.get("/stats", response_model=RegistryStatsResponse)
async def get_registry_stats(
    db: AsyncSession = Depends(get_db),
):
    svc = _service(db)
    stats = await svc.get_registry_stats()
    return RegistryStatsResponse(**stats)


# ── Gateway validation (standalone) ───────────────────────────────────


@router.post("/validate/strategy", response_model=GatewayResultResponse)
async def validate_strategy(
    data: StrategyCreate,
    db: AsyncSession = Depends(get_db),
):
    gateway = InjectionGateway(db)
    result = await gateway.validate_strategy(data.model_dump())
    return GatewayResultResponse(
        verdict=result.verdict.value,
        violations=result.violations,
        blocked_code=result.blocked_code,
    )
