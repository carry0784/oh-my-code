"""Registry Service — CRUD operations for Control Plane registries.

CR-048 Stage 1 L3: Phase 1 서비스 완결.
Gateway 검증을 거친 후 Indicator/FeaturePack/Strategy/PromotionEvent에 대한
생성(Create), 조회(Read), 비활성화(Retire/Disable) 작업을 수행합니다.

규칙:
- Strategy 생성은 반드시 InjectionGateway.validate_strategy() 통과 후에만.
- PromotionEvent는 append-only (수정/삭제 금지).
- hard delete 금지. 비활성화는 status 변경만 허용.
- Promotion 상태 전이 **실행**은 Stage 1 범위 아님 (기록만 허용).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator_registry import Indicator, IndicatorStatus
from app.models.feature_pack import FeaturePack, FeaturePackStatus
from app.models.strategy_registry import Strategy, PromotionStatus
from app.models.promotion_state import PromotionEvent
from app.services.injection_gateway import (
    InjectionGateway,
    GatewayVerdict,
    GatewayResult,
)

logger = logging.getLogger(__name__)


class RegistryServiceError(Exception):
    """Base exception for registry service errors."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class GatewayRejectionError(RegistryServiceError):
    """Raised when a registration request is rejected by the Gateway."""

    def __init__(self, result: GatewayResult):
        super().__init__(
            f"Gateway rejected: {result.violations}",
            code=result.blocked_code,
        )
        self.result = result


class NotFoundError(RegistryServiceError):
    """Raised when a requested entity is not found."""

    def __init__(self, entity: str, entity_id: str):
        super().__init__(f"{entity} not found: {entity_id}", code="NOT_FOUND")


class InvalidOperationError(RegistryServiceError):
    """Raised when an invalid operation is attempted."""

    pass


# ── Registry Service ─────────────────────────────────────────────────


class RegistryService:
    """CRUD service for Control Plane registries.

    All write operations go through InjectionGateway for validation.
    PromotionEvent is append-only.
    Hard delete is prohibited; use retire/disable instead.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.gateway = InjectionGateway(db)

    # ── Indicator CRUD ───────────────────────────────────────────────

    async def create_indicator(self, data: dict[str, Any]) -> Indicator:
        """Create an indicator after Gateway validation."""
        result = await self.gateway.validate_indicator(data)
        if result.verdict == GatewayVerdict.REJECTED:
            raise GatewayRejectionError(result)

        indicator = Indicator(
            name=data["name"],
            version=data["version"],
            description=data.get("description"),
            input_params=data.get("input_params"),
            output_fields=data.get("output_fields"),
            warmup_bars=data.get("warmup_bars", 0),
            compute_module=data["compute_module"],
            checksum=data.get("checksum"),
            category=data.get("category"),
            asset_classes=data.get("asset_classes"),
            timeframes=data.get("timeframes"),
        )
        self.db.add(indicator)
        await self.db.flush()
        logger.info(
            "Indicator created: %s v%s (id=%s)", indicator.name, indicator.version, indicator.id
        )
        return indicator

    async def get_indicator(self, indicator_id: str) -> Indicator:
        """Get a single indicator by ID."""
        result = await self.db.execute(select(Indicator).where(Indicator.id == indicator_id))
        indicator = result.scalar_one_or_none()
        if not indicator:
            raise NotFoundError("Indicator", indicator_id)
        return indicator

    async def list_indicators(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Indicator]:
        """List indicators with optional filtering."""
        query = select(Indicator)
        if status:
            query = query.where(Indicator.status == status)
        if category:
            query = query.where(Indicator.category == category)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def retire_indicator(self, indicator_id: str, reason: str = "") -> Indicator:
        """Retire (soft-disable) an indicator. No hard delete."""
        indicator = await self.get_indicator(indicator_id)
        if indicator.status == IndicatorStatus.BLOCKED.value:
            raise InvalidOperationError(
                f"Cannot retire BLOCKED indicator: {indicator_id}",
                code="ALREADY_BLOCKED",
            )
        indicator.status = IndicatorStatus.DEPRECATED.value
        await self.db.flush()
        logger.info("Indicator retired: %s (reason: %s)", indicator_id, reason)
        return indicator

    # ── Feature Pack CRUD ────────────────────────────────────────────

    async def create_feature_pack(self, data: dict[str, Any]) -> FeaturePack:
        """Create a feature pack after Gateway validation."""
        result = await self.gateway.validate_feature_pack(data)
        if result.verdict == GatewayVerdict.REJECTED:
            raise GatewayRejectionError(result)

        fp = FeaturePack(
            name=data["name"],
            version=data["version"],
            description=data.get("description"),
            indicator_ids=data["indicator_ids"]
            if isinstance(data["indicator_ids"], str)
            else json.dumps(data["indicator_ids"]),
            weights=data.get("weights"),
            checksum=data.get("checksum"),
            asset_classes=data.get("asset_classes"),
            timeframes=data.get("timeframes"),
            warmup_bars=data.get("warmup_bars", 0),
        )
        self.db.add(fp)
        await self.db.flush()
        logger.info("FeaturePack created: %s v%s (id=%s)", fp.name, fp.version, fp.id)
        return fp

    async def get_feature_pack(self, fp_id: str) -> FeaturePack:
        """Get a single feature pack by ID."""
        result = await self.db.execute(select(FeaturePack).where(FeaturePack.id == fp_id))
        fp = result.scalar_one_or_none()
        if not fp:
            raise NotFoundError("FeaturePack", fp_id)
        return fp

    async def list_feature_packs(
        self,
        *,
        status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[FeaturePack]:
        """List feature packs with optional filtering."""
        query = select(FeaturePack)
        if status:
            query = query.where(FeaturePack.status == status)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def retire_feature_pack(self, fp_id: str, reason: str = "") -> FeaturePack:
        """Retire (soft-disable) a feature pack. No hard delete."""
        fp = await self.get_feature_pack(fp_id)
        if fp.status == FeaturePackStatus.BLOCKED.value:
            raise InvalidOperationError(
                f"Cannot retire BLOCKED feature pack: {fp_id}",
                code="ALREADY_BLOCKED",
            )
        fp.status = FeaturePackStatus.DEPRECATED.value
        await self.db.flush()
        logger.info("FeaturePack retired: %s (reason: %s)", fp_id, reason)
        return fp

    # ── Strategy CRUD ────────────────────────────────────────────────

    async def create_strategy(self, data: dict[str, Any]) -> tuple[Strategy, PromotionEvent]:
        """Create a strategy after Gateway validation.

        Returns (strategy, initial_promotion_event).
        Strategy is created in REGISTERED status (gateway-approved = past DRAFT).
        """
        result = await self.gateway.validate_strategy(data)
        if result.verdict == GatewayVerdict.REJECTED:
            raise GatewayRejectionError(result)

        strategy = Strategy(
            name=data["name"],
            version=data["version"],
            description=data.get("description"),
            feature_pack_id=data["feature_pack_id"],
            compute_module=data["compute_module"],
            checksum=data.get("checksum"),
            asset_classes=data["asset_classes"]
            if isinstance(data["asset_classes"], str)
            else json.dumps(data["asset_classes"]),
            exchanges=data["exchanges"]
            if isinstance(data["exchanges"], str)
            else json.dumps(data["exchanges"]),
            sectors=data.get("sectors"),
            timeframes=data["timeframes"]
            if isinstance(data["timeframes"], str)
            else json.dumps(data["timeframes"]),
            regimes=data.get("regimes"),
            max_symbols=data.get("max_symbols", 20),
            status=PromotionStatus.REGISTERED.value,
        )
        self.db.add(strategy)
        await self.db.flush()

        # Record initial promotion event (DRAFT→REGISTERED)
        event = await self.record_promotion_event(
            strategy_id=strategy.id,
            from_status=PromotionStatus.DRAFT.value,
            to_status=PromotionStatus.REGISTERED.value,
            reason="Initial registration via Injection Gateway",
            triggered_by="system",
            approval_level="low",
        )

        logger.info(
            "Strategy created: %s v%s (id=%s, status=REGISTERED)",
            strategy.name,
            strategy.version,
            strategy.id,
        )
        return strategy, event

    async def get_strategy(self, strategy_id: str) -> Strategy:
        """Get a single strategy by ID."""
        result = await self.db.execute(select(Strategy).where(Strategy.id == strategy_id))
        strategy = result.scalar_one_or_none()
        if not strategy:
            raise NotFoundError("Strategy", strategy_id)
        return strategy

    async def list_strategies(
        self,
        *,
        status: str | None = None,
        asset_class: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Strategy]:
        """List strategies with optional filtering."""
        query = select(Strategy)
        if status:
            query = query.where(Strategy.status == status)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def retire_strategy(
        self, strategy_id: str, reason: str = "", retired_by: str = "system"
    ) -> tuple[Strategy, PromotionEvent]:
        """Retire (soft-disable) a strategy. No hard delete.

        Records a PromotionEvent for the transition.
        Returns (strategy, retirement_event).
        """
        strategy = await self.get_strategy(strategy_id)
        old_status = strategy.status

        if old_status == PromotionStatus.BLOCKED.value:
            raise InvalidOperationError(
                f"Cannot retire BLOCKED strategy: {strategy_id}",
                code="ALREADY_BLOCKED",
            )
        if old_status == PromotionStatus.RETIRED.value:
            raise InvalidOperationError(
                f"Strategy already retired: {strategy_id}",
                code="ALREADY_RETIRED",
            )

        strategy.status = PromotionStatus.RETIRED.value
        await self.db.flush()

        event = await self.record_promotion_event(
            strategy_id=strategy_id,
            from_status=old_status,
            to_status=PromotionStatus.RETIRED.value,
            reason=reason or "Retired via registry service",
            triggered_by=retired_by,
            approval_level="medium",
        )

        logger.info("Strategy retired: %s (reason: %s)", strategy_id, reason)
        return strategy, event

    # ── Promotion Event (append-only) ────────────────────────────────

    async def record_promotion_event(
        self,
        *,
        strategy_id: str,
        from_status: str,
        to_status: str,
        reason: str = "",
        triggered_by: str = "system",
        approval_level: str | None = None,
        evidence: str | None = None,
        approved_by: str | None = None,
    ) -> PromotionEvent:
        """Record a promotion event. Append-only — no update/delete.

        NOTE: This method records the event but does NOT execute the actual
        status transition on Strategy.status. Promotion execution is
        outside Stage 1 scope.
        """
        event = PromotionEvent(
            strategy_id=strategy_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            triggered_by=triggered_by,
            approval_level=approval_level,
            evidence=evidence,
            approved_by=approved_by,
        )
        self.db.add(event)
        await self.db.flush()
        logger.info(
            "PromotionEvent recorded: strategy=%s %s→%s",
            strategy_id,
            from_status,
            to_status,
        )
        return event

    async def list_promotion_events(
        self,
        *,
        strategy_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PromotionEvent]:
        """List promotion events, optionally filtered by strategy_id."""
        query = select(PromotionEvent)
        if strategy_id:
            query = query.where(PromotionEvent.strategy_id == strategy_id)
        query = query.order_by(PromotionEvent.created_at.desc())
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_promotion_event(self, event_id: str) -> PromotionEvent:
        """Get a single promotion event by ID."""
        result = await self.db.execute(select(PromotionEvent).where(PromotionEvent.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise NotFoundError("PromotionEvent", event_id)
        return event

    # ── Statistics ────────────────────────────────────────────────────

    async def get_registry_stats(self) -> dict[str, Any]:
        """Get counts for each registry entity."""
        ind_count = await self.db.execute(select(func.count(Indicator.id)))
        fp_count = await self.db.execute(select(func.count(FeaturePack.id)))
        strat_count = await self.db.execute(select(func.count(Strategy.id)))
        event_count = await self.db.execute(select(func.count(PromotionEvent.id)))

        return {
            "indicators": ind_count.scalar() or 0,
            "feature_packs": fp_count.scalar() or 0,
            "strategies": strat_count.scalar() or 0,
            "promotion_events": event_count.scalar() or 0,
        }
