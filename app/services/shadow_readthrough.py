"""RI-2A-1: Shadow Read-through Comparison — DB SELECT + in-memory compare.

Fetches existing screening/qualification results from DB (read-only),
then compares against shadow pipeline output using pure comparison logic.

DB write: ZERO (any table).
DB access: SELECT only on screening_results, qualification_results.
State change: ZERO.
FROZEN modification: ZERO.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import ScreeningResult
from app.models.qualification import QualificationResult
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ReadthroughFailureCode,
    ReasonComparisonDetail,
    ShadowComparisonInput,
    ShadowRunResult,
    compare_shadow_to_existing,
)

logger = logging.getLogger(__name__)


# ── ExistingResultSource ─────────────────────────────────────────


@dataclass(frozen=True)
class ExistingResultSource:
    """Metadata about where existing results came from."""

    screening_result_id: str | None = None
    screening_screened_at: datetime | None = None
    qualification_result_id: str | None = None
    qualification_evaluated_at: datetime | None = None
    failure_code: ReadthroughFailureCode | None = None


# ── ReadthroughComparisonResult ──────────────────────────────────


@dataclass(frozen=True)
class ReadthroughComparisonResult:
    """RI-2A-1 comparison result. In-memory only, no persistence."""

    symbol: str
    shadow_result: ShadowRunResult
    comparison_verdict: ComparisonVerdict
    reason_comparison: ReasonComparisonDetail | None
    existing_source: ExistingResultSource


# ── Read-through fetch ───────────────────────────────────────────


def _extract_screening_fail_stages(row: ScreeningResult) -> frozenset[str] | None:
    """Extract failed stage names from a ScreeningResult DB row."""
    stages = []
    if not row.stage1_exclusion:
        stages.append("stage1")
    if not row.stage2_liquidity:
        stages.append("stage2")
    if not row.stage3_technical:
        stages.append("stage3")
    if not row.stage4_fundamental:
        stages.append("stage4")
    if not row.stage5_backtest:
        stages.append("stage5")
    return frozenset(stages) if stages else None


def _extract_qualification_fail_checks(row: QualificationResult) -> frozenset[str] | None:
    """Extract failed check names from a QualificationResult DB row.

    Prefers the explicit failed_checks JSON column.
    Falls back to individual check_* booleans.
    """
    # Try JSON column first
    if row.failed_checks:
        try:
            checks = json.loads(row.failed_checks)
            if isinstance(checks, list) and checks:
                return frozenset(checks)
        except (json.JSONDecodeError, TypeError):
            pass  # Fall through to boolean extraction

    # Fallback: individual check booleans
    checks = []
    if not row.check_data_compat:
        checks.append("data_compat")
    if not row.check_warmup:
        checks.append("warmup")
    if not row.check_leakage:
        checks.append("leakage")
    if not row.check_data_quality:
        checks.append("data_quality")
    if not row.check_min_bars:
        checks.append("min_bars")
    if not row.check_performance:
        checks.append("performance")
    if not row.check_cost_sanity:
        checks.append("cost_sanity")
    return frozenset(checks) if checks else None


async def fetch_existing_for_comparison(
    db: AsyncSession,
    symbol: str,
) -> tuple[ShadowComparisonInput, ExistingResultSource]:
    """Fetch existing screening/qualification results from DB for comparison.

    Contract:
      - SELECT only (INSERT/UPDATE/DELETE: ZERO)
      - Bounded query (WHERE symbol = ?, ORDER BY ... DESC, LIMIT 1)
      - Fail-closed: DB error → (None fields, failure_code)
      - No MATCH inference: missing data = INSUFFICIENT, never guessed
    """
    screening_passed: bool | None = None
    qual_passed: bool | None = None
    screen_fail_stages: frozenset[str] | None = None
    qual_fail_checks: frozenset[str] | None = None
    screen_id: str | None = None
    screen_at: datetime | None = None
    qual_id: str | None = None
    qual_at: datetime | None = None
    failure_code: ReadthroughFailureCode | None = None

    try:
        # Screening: latest result for symbol
        stmt = (
            select(ScreeningResult)
            .where(ScreeningResult.symbol == symbol)
            .order_by(ScreeningResult.screened_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        screen_row = result.scalar_one_or_none()

        if screen_row is not None:
            screening_passed = screen_row.all_passed
            screen_id = screen_row.id
            screen_at = screen_row.screened_at
            if not screen_row.all_passed:
                screen_fail_stages = _extract_screening_fail_stages(screen_row)

        # Qualification: latest result for symbol
        stmt = (
            select(QualificationResult)
            .where(QualificationResult.symbol == symbol)
            .order_by(QualificationResult.evaluated_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        qual_row = result.scalar_one_or_none()

        if qual_row is not None:
            qual_passed = qual_row.all_passed
            qual_id = qual_row.id
            qual_at = qual_row.evaluated_at
            if not qual_row.all_passed:
                qual_fail_checks = _extract_qualification_fail_checks(qual_row)

    except Exception:
        logger.exception("read-through DB query failed for symbol=%s", symbol)
        failure_code = ReadthroughFailureCode.READTHROUGH_DB_UNAVAILABLE
        return (
            ShadowComparisonInput(),  # All None → INSUFFICIENT_OPERATIONAL
            ExistingResultSource(failure_code=failure_code),
        )

    if screening_passed is None:
        failure_code = ReadthroughFailureCode.READTHROUGH_RESULT_NOT_FOUND

    comparison_input = ShadowComparisonInput(
        existing_screening_passed=screening_passed,
        existing_qualification_passed=qual_passed,
        existing_screening_fail_stages=screen_fail_stages,
        existing_qualification_fail_checks=qual_fail_checks,
    )

    source = ExistingResultSource(
        screening_result_id=screen_id,
        screening_screened_at=screen_at,
        qualification_result_id=qual_id,
        qualification_evaluated_at=qual_at,
        failure_code=failure_code,
    )

    return comparison_input, source


# ── Read-through Comparison ──────────────────────────────────────


async def run_readthrough_comparison(
    db: AsyncSession,
    shadow_result: ShadowRunResult,
) -> ReadthroughComparisonResult:
    """Run full read-through comparison: DB fetch + pure compare.

    1. Fetch existing results from DB (SELECT only)
    2. Compare shadow vs existing (pure, in-memory)
    3. Return comparison result (no persistence)

    DB write: ZERO.
    State change: ZERO.
    """
    existing_input, source = await fetch_existing_for_comparison(
        db,
        shadow_result.symbol,
    )

    compared = compare_shadow_to_existing(shadow_result, existing_input)

    return ReadthroughComparisonResult(
        symbol=shadow_result.symbol,
        shadow_result=compared,
        comparison_verdict=compared.comparison_verdict,
        reason_comparison=compared.reason_comparison,
        existing_source=source,
    )
