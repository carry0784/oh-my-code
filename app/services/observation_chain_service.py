"""Observation Chain Service — long-term time-series state recording.

Periodic snapshot of system state for trend analysis:
  - Market regime (V1 + V2 parallel)
  - Price/volatility metrics
  - Strategy activity
  - Infrastructure health

Append-only: entries are never updated or deleted.
Query interface for trend analysis and drift detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.observation_chain import ObservationChainEntry

logger = get_logger(__name__)


@dataclass
class ObservationSnapshot:
    """Input for recording a single observation."""

    symbol: str = ""
    exchange: str = "binance"
    observation_type: str = "hourly"
    close_price: float | None = None
    regime_v1: str | None = None
    regime_v2: str | None = None
    realized_volatility: float | None = None
    choppiness_index: float | None = None
    active_strategy: str | None = None
    signal_count_24h: int | None = None
    consensus_ratio_24h: float | None = None
    ohlcv_coverage_pct: float | None = None
    shadow_task_healthy: bool | None = None
    ppf_baseline_active: bool | None = None
    novelty_detected: bool = False
    anomaly_flag: str | None = None
    notes: str | None = None


@dataclass
class TrendSummary:
    """Summary of observation chain trends over a time window."""

    symbol: str = ""
    window_hours: int = 0
    observation_count: int = 0
    regime_v1_distribution: dict[str, int] = field(default_factory=dict)
    regime_v2_distribution: dict[str, int] = field(default_factory=dict)
    price_change_pct: float | None = None
    avg_realized_vol: float | None = None
    avg_choppiness: float | None = None
    novelty_count: int = 0
    anomaly_flags: list[str] = field(default_factory=list)
    regime_transitions_v1: int = 0
    regime_transitions_v2: int = 0


class ObservationChainService:
    """Manages the long-term observation chain."""

    async def record(
        self,
        session: AsyncSession,
        snapshot: ObservationSnapshot,
    ) -> int:
        """Append a new observation entry.

        Returns:
            ID of the newly created entry.
        """
        entry = ObservationChainEntry(
            symbol=snapshot.symbol,
            exchange=snapshot.exchange,
            observation_type=snapshot.observation_type,
            close_price=snapshot.close_price,
            regime_v1=snapshot.regime_v1,
            regime_v2=snapshot.regime_v2,
            realized_volatility=snapshot.realized_volatility,
            choppiness_index=snapshot.choppiness_index,
            active_strategy=snapshot.active_strategy,
            signal_count_24h=snapshot.signal_count_24h,
            consensus_ratio_24h=snapshot.consensus_ratio_24h,
            ohlcv_coverage_pct=snapshot.ohlcv_coverage_pct,
            shadow_task_healthy=snapshot.shadow_task_healthy,
            ppf_baseline_active=snapshot.ppf_baseline_active,
            novelty_detected=snapshot.novelty_detected,
            anomaly_flag=snapshot.anomaly_flag,
            notes=snapshot.notes,
        )
        session.add(entry)
        await session.flush()

        logger.info(
            "observation_recorded",
            symbol=snapshot.symbol,
            type=snapshot.observation_type,
            regime_v1=snapshot.regime_v1,
            regime_v2=snapshot.regime_v2,
            novelty=snapshot.novelty_detected,
        )
        return entry.id

    async def get_trend_summary(
        self,
        session: AsyncSession,
        symbol: str,
        hours: int = 168,  # 7 days default
    ) -> TrendSummary:
        """Compute trend summary over a time window.

        Args:
            symbol: Target symbol.
            hours: Lookback window in hours.

        Returns:
            TrendSummary with distributions, transitions, and averages.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(ObservationChainEntry)
            .where(
                ObservationChainEntry.symbol == symbol,
                ObservationChainEntry.observed_at >= cutoff,
            )
            .order_by(ObservationChainEntry.observed_at.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()

        summary = TrendSummary(symbol=symbol, window_hours=hours)
        summary.observation_count = len(rows)

        if not rows:
            return summary

        # Regime distributions
        v1_dist: dict[str, int] = {}
        v2_dist: dict[str, int] = {}
        rv_vals = []
        ci_vals = []
        prices = []
        anomalies = []
        prev_v1 = None
        prev_v2 = None

        for r in rows:
            if r.regime_v1:
                v1_dist[r.regime_v1] = v1_dist.get(r.regime_v1, 0) + 1
                if prev_v1 is not None and r.regime_v1 != prev_v1:
                    summary.regime_transitions_v1 += 1
                prev_v1 = r.regime_v1

            if r.regime_v2:
                v2_dist[r.regime_v2] = v2_dist.get(r.regime_v2, 0) + 1
                if prev_v2 is not None and r.regime_v2 != prev_v2:
                    summary.regime_transitions_v2 += 1
                prev_v2 = r.regime_v2

            if r.realized_volatility is not None:
                rv_vals.append(r.realized_volatility)
            if r.choppiness_index is not None:
                ci_vals.append(r.choppiness_index)
            if r.close_price is not None:
                prices.append(r.close_price)
            if r.novelty_detected:
                summary.novelty_count += 1
            if r.anomaly_flag:
                anomalies.append(r.anomaly_flag)

        summary.regime_v1_distribution = v1_dist
        summary.regime_v2_distribution = v2_dist

        if prices and len(prices) >= 2:
            summary.price_change_pct = round((prices[-1] - prices[0]) / prices[0] * 100, 4)
        if rv_vals:
            summary.avg_realized_vol = round(float(np.mean(rv_vals)), 4)
        if ci_vals:
            summary.avg_choppiness = round(float(np.mean(ci_vals)), 4)
        summary.anomaly_flags = list(set(anomalies))

        return summary

    async def get_recent_entries(
        self,
        session: AsyncSession,
        symbol: str,
        limit: int = 24,
    ) -> list[ObservationChainEntry]:
        """Get most recent observation entries.

        Returns entries ordered by observed_at DESC.
        """
        stmt = (
            select(ObservationChainEntry)
            .where(ObservationChainEntry.symbol == symbol)
            .order_by(ObservationChainEntry.observed_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return list(rows)

    async def detect_regime_drift(
        self,
        session: AsyncSession,
        symbol: str,
        window_hours: int = 48,
        transition_threshold: int = 3,
    ) -> dict:
        """Detect regime drift by counting transitions in a window.

        Returns:
            Dict with drift_detected (bool), v1_transitions, v2_transitions.
        """
        summary = await self.get_trend_summary(session, symbol, window_hours)
        v1_drift = summary.regime_transitions_v1 >= transition_threshold
        v2_drift = summary.regime_transitions_v2 >= transition_threshold

        return {
            "drift_detected": v1_drift or v2_drift,
            "v1_transitions": summary.regime_transitions_v1,
            "v2_transitions": summary.regime_transitions_v2,
            "threshold": transition_threshold,
            "window_hours": window_hours,
        }
