"""MarketStateAdapter — CR-048 Follow-Up 2A P1.

Read-only adapter: market_states table -> MarketDataSnapshot.

Implements the data provider contract for shadow pipeline.
Zero writes.  SELECT only.

Freshness policy (SP-03 aligned):
  snapshot_at within 1 h   -> DataQuality.HIGH
  1 h < snapshot_at <= 4 h -> DataQuality.STALE
  4 h exceeded or absent   -> DataQuality.UNAVAILABLE

Fail-closed on every error path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_state import MarketState
from app.services.data_provider import DataQuality, MarketDataSnapshot

logger = logging.getLogger(__name__)


class MarketStateAdapter:
    """Read-only adapter: market_states table -> MarketDataSnapshot.

    Implements the data provider contract for shadow pipeline.
    Zero writes. SELECT only.
    """

    FRESHNESS_HIGH_SECONDS: int = 3600  # 1 hour
    FRESHNESS_STALE_SECONDS: int = 14400  # 4 hours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_market_data(
        self,
        db: AsyncSession,
        symbol: str,
        now_utc: datetime | None = None,
    ) -> MarketDataSnapshot:
        """Return the latest MarketDataSnapshot for *symbol*.

        Always returns a snapshot (never raises).  Failed or missing data
        yields quality=UNAVAILABLE.
        """
        now = now_utc or datetime.now(timezone.utc)
        try:
            row = await self._fetch_latest(db, symbol)
        except Exception:
            logger.exception("MarketStateAdapter: DB error for symbol=%s", symbol)
            return MarketDataSnapshot(symbol=symbol, quality=DataQuality.UNAVAILABLE)

        if row is None:
            return MarketDataSnapshot(symbol=symbol, quality=DataQuality.UNAVAILABLE)

        return self._to_snapshot(row, now)

    async def get_market_data_batch(
        self,
        db: AsyncSession,
        symbols: list[str],
        now_utc: datetime | None = None,
    ) -> list[MarketDataSnapshot]:
        """Return MarketDataSnapshot for each symbol in *symbols*.

        Processes symbols sequentially; individual failures yield
        UNAVAILABLE without aborting the batch.
        """
        now = now_utc or datetime.now(timezone.utc)
        results: list[MarketDataSnapshot] = []
        for symbol in symbols:
            try:
                row = await self._fetch_latest(db, symbol)
                if row is None:
                    results.append(
                        MarketDataSnapshot(symbol=symbol, quality=DataQuality.UNAVAILABLE)
                    )
                else:
                    results.append(self._to_snapshot(row, now))
            except Exception:
                logger.exception("MarketStateAdapter: DB error in batch for symbol=%s", symbol)
                results.append(MarketDataSnapshot(symbol=symbol, quality=DataQuality.UNAVAILABLE))
        return results

    async def health_check(self, db: AsyncSession) -> bool:
        """Return True if market_states table is reachable and non-empty."""
        try:
            stmt = select(MarketState.id).limit(1)
            result = await db.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception:
            logger.exception("MarketStateAdapter: health_check failed")
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_latest(self, db: AsyncSession, symbol: str) -> MarketState | None:
        """SELECT the most recent MarketState row for *symbol*."""
        stmt = (
            select(MarketState)
            .where(MarketState.symbol == symbol)
            .order_by(desc(MarketState.snapshot_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def _determine_quality(self, snapshot_at: datetime | None, now: datetime) -> DataQuality:
        """Apply freshness policy and return DataQuality."""
        if snapshot_at is None:
            return DataQuality.UNAVAILABLE

        # Normalise timezone: treat naive timestamps as UTC
        ts = snapshot_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age_seconds = (now - ts).total_seconds()

        if age_seconds <= self.FRESHNESS_HIGH_SECONDS:
            return DataQuality.HIGH
        if age_seconds <= self.FRESHNESS_STALE_SECONDS:
            return DataQuality.STALE
        return DataQuality.UNAVAILABLE

    def _to_snapshot(self, row: MarketState, now: datetime) -> MarketDataSnapshot:
        """Convert a MarketState ORM row to MarketDataSnapshot.

        Fail-closed: price missing or zero -> UNAVAILABLE.
        adx_14 accessed via getattr (column added post-baseline; may be absent).
        """
        price: float | None = row.price

        quality = self._determine_quality(row.snapshot_at, now)

        if not price:
            # price is None or 0 — cannot derive ratio fields
            return MarketDataSnapshot(
                symbol=row.symbol,
                timestamp=row.snapshot_at,
                quality=DataQuality.UNAVAILABLE,
            )

        # atr_pct: only when both atr_14 and price are available
        atr_pct: float | None = None
        if row.atr_14 is not None and price:
            atr_pct = row.atr_14 / price

        # price_vs_200ma: only when both sma_200 and price are available
        price_vs_200ma: float | None = None
        if row.sma_200 is not None and price:
            price_vs_200ma = price / row.sma_200

        # adx_14 is a new column; guard with getattr for schema migration safety
        adx: float | None = getattr(row, "adx_14", None)

        return MarketDataSnapshot(
            symbol=row.symbol,
            timestamp=row.snapshot_at,
            price_usd=price,
            market_cap_usd=row.total_market_cap_usd,
            avg_daily_volume_usd=row.volume_24h,
            spread_pct=row.spread_pct,
            atr_pct=atr_pct,
            adx=adx,
            price_vs_200ma=price_vs_200ma,
            quality=quality,
        )
