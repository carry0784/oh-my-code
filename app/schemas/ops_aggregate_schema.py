"""
B-10: Ops Aggregate Schema — 종합 운영 health/availability/stale 집계

overall_status 판정:
  HEALTHY: 모든 source OK
  DEGRADED: stale 또는 unavailable 1개 이상
  UNHEALTHY: unavailable 2개 이상

Read-only. No execution. No raw text exposure.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OverallStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class SourceStatus(str, Enum):
    OK = "OK"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class SourceCoverage(BaseModel):
    sources_total: int = 0
    ok: int = 0
    stale: int = 0
    unavailable: int = 0


class SourceEntry(BaseModel):
    """개별 source 상태. raw 원문 미포함."""

    name: str
    status: SourceStatus = SourceStatus.UNAVAILABLE
    summary: str = ""
    last_checked: Optional[str] = Field(default=None, description="ISO 8601")


class OpsHealth(BaseModel):
    """v2 경량 요약. 4필드만."""

    overall_status: OverallStatus = OverallStatus.UNHEALTHY
    source_coverage: SourceCoverage = Field(default_factory=SourceCoverage)
    dominant_reason: str = ""
    updated_at: str = ""


class OpsAggregateResponse(BaseModel):
    """
    B-10: 종합 운영 aggregate.
    상세 source 상태 포함. /api/ops-aggregate 전용.
    """

    overall_status: OverallStatus = OverallStatus.UNHEALTHY
    source_coverage: SourceCoverage = Field(default_factory=SourceCoverage)
    dominant_reason: str = ""
    updated_at: str = ""
    sources: list[SourceEntry] = Field(default_factory=list)
    aggregate_note: str = Field(
        default="Read-only aggregate. No execution. No raw text.",
    )
