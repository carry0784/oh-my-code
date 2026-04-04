"""RI-2A-2a: Shadow Observation Service — append-only INSERT.

Records shadow observation results to shadow_observation_log.
This service has exactly ONE write method: record_shadow_observation().
No update. No delete. No merge. No upsert.

INSERT failure does NOT propagate — logged and swallowed.
Pipeline and read-through are never blocked by observation failure.

business_impact = false.
Retention/purge: deferred to RI-2A-2b.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetClass, AssetSector
from app.models.shadow_observation import ShadowObservationLog
from app.services.pipeline_shadow_runner import ShadowRunResult
from app.services.shadow_readthrough import (
    ExistingResultSource,
    ReadthroughComparisonResult,
)

from app.services.screening_qualification_pipeline import PipelineVerdict

logger = logging.getLogger(__name__)


def _serialize_reason_comparison(reason_detail) -> str | None:
    """Serialize ReasonComparisonDetail to JSON string.

    Handles frozenset -> sorted list conversion for JSON compatibility.
    Returns None if input is None.
    """
    if reason_detail is None:
        return None
    d = asdict(reason_detail)
    for key, val in d.items():
        if isinstance(val, frozenset):
            d[key] = sorted(val)
    return json.dumps(d, ensure_ascii=False)


def _is_screening_passed(shadow_result: ShadowRunResult) -> bool | None:
    """Derive screening pass/fail from pipeline verdict."""
    v = shadow_result.pipeline_output.result.verdict
    if v == PipelineVerdict.DATA_REJECTED:
        return None
    return v in (PipelineVerdict.QUALIFIED, PipelineVerdict.QUALIFY_FAILED)


def _is_qualification_passed(shadow_result: ShadowRunResult) -> bool | None:
    """Derive qualification pass/fail from pipeline verdict."""
    v = shadow_result.pipeline_output.result.verdict
    if v in (PipelineVerdict.DATA_REJECTED, PipelineVerdict.SCREEN_FAILED):
        return None
    return v == PipelineVerdict.QUALIFIED


async def record_shadow_observation(
    db: AsyncSession,
    shadow_result: ShadowRunResult,
    readthrough_result: ReadthroughComparisonResult,
    asset_class: AssetClass,
    asset_sector: AssetSector,
    existing_screening_passed: bool | None = None,
    existing_qualification_passed: bool | None = None,
) -> ShadowObservationLog | None:
    """Record one shadow observation. Append-only INSERT.

    Contract:
      - INSERT only (UPDATE/DELETE: ZERO)
      - Failure does NOT raise — logged and swallowed
      - Pipeline/readthrough execution is never blocked
      - Returns ShadowObservationLog on success, None on failure

    Args:
        db: AsyncSession for INSERT
        shadow_result: From run_shadow_pipeline() (RI-1 SEALED)
        readthrough_result: From run_readthrough_comparison() (RI-2A-1 SEALED)
        asset_class: Asset class enum
        asset_sector: Asset sector enum
        existing_screening_passed: From fetch_existing_for_comparison (optional)
        existing_qualification_passed: From fetch_existing_for_comparison (optional)

    Returns:
        ShadowObservationLog on success, None on failure.
    """
    if shadow_result is None:
        logger.warning("record_shadow_observation: shadow_result is None")
        return None
    if readthrough_result is None:
        logger.warning("record_shadow_observation: readthrough_result is None")
        return None

    try:
        source: ExistingResultSource = readthrough_result.existing_source
        failure_code = source.failure_code.value if source.failure_code else None

        row = ShadowObservationLog(
            # 관찰 대상
            symbol=shadow_result.symbol,
            asset_class=asset_class.value if hasattr(asset_class, "value") else str(asset_class),
            asset_sector=asset_sector.value
            if hasattr(asset_sector, "value")
            else str(asset_sector),
            # Shadow 결과
            shadow_verdict=shadow_result.pipeline_output.result.verdict.value,
            shadow_screening_passed=_is_screening_passed(shadow_result),
            shadow_qualification_passed=_is_qualification_passed(shadow_result),
            # 비교 결과
            comparison_verdict=readthrough_result.comparison_verdict.value,
            existing_screening_passed=existing_screening_passed,
            existing_qualification_passed=existing_qualification_passed,
            # Reason-level
            reason_comparison_json=_serialize_reason_comparison(
                readthrough_result.reason_comparison,
            ),
            # Read-through metadata
            readthrough_failure_code=failure_code,
            existing_screening_result_id=source.screening_result_id,
            existing_qualification_result_id=source.qualification_result_id,
            # 재현성
            input_fingerprint=shadow_result.input_fingerprint,
            # 시각
            shadow_timestamp=shadow_result.shadow_timestamp,
        )

        db.add(row)
        await db.flush()
        return row

    except Exception:
        logger.exception(
            "shadow observation INSERT failed for %s",
            getattr(shadow_result, "symbol", "unknown"),
        )
        return None
