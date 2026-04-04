"""RI-1: Pipeline Shadow Runner — pure read-only shadow execution.

Executes the full screening-qualification pipeline in shadow mode.
No DB, no async, no I/O, no state mutation, no side-effect.
Returns ShadowRunResult for observation/comparison only.

Pure Zone file #10.

Layer 1 (Pure Shadow) of the RI architecture:
  L1: pipeline_shadow_runner.py  (this file)
  L2: tests/  (fixtures + tests)
  L3: runtime/service path  (BLOCKED in RI-1)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.models.asset import AssetClass, AssetSector
from app.services.data_provider import (
    BacktestReadiness,
    FundamentalSnapshot,
    MarketDataSnapshot,
    SymbolMetadata,
)
from app.services.backtest_qualification import QualificationThresholds
from app.services.screening_qualification_pipeline import (
    PipelineOutput,
    run_screening_qualification_pipeline,
)
from app.services.screening_transform import transform_provider_to_screening
from app.services.symbol_screener import ScreeningThresholds


# ── ComparisonVerdict ──────────────────────────────────────────────


class ComparisonVerdict(str, Enum):
    """Outcome of comparing shadow result to existing results."""

    MATCH = "match"
    VERDICT_MISMATCH = "verdict_mismatch"
    REASON_MISMATCH = "reason_mismatch"
    INSUFFICIENT_STRUCTURAL = "insufficient_structural"
    INSUFFICIENT_OPERATIONAL = "insufficient_operational"


# ── ShadowComparisonInput ─────────────────────────────────────────


@dataclass(frozen=True)
class ShadowComparisonInput:
    """Existing screening/qualification results for comparison.

    Provided by caller. Shadow runner does NOT fetch these.
    """

    existing_screening_passed: bool | None = None
    existing_qualification_passed: bool | None = None
    existing_symbol_status: str | None = None
    existing_screening_fail_stages: frozenset[str] | None = None
    existing_qualification_fail_checks: frozenset[str] | None = None


# ── ShadowRunResult ───────────────────────────────────────────────


@dataclass(frozen=True)
class ShadowRunResult:
    """Shadow pipeline execution result. Pure data, no side-effect."""

    symbol: str
    pipeline_output: PipelineOutput
    shadow_timestamp: datetime
    input_fingerprint: str
    comparison_verdict: ComparisonVerdict | None = None
    reason_comparison: ReasonComparisonDetail | None = None


# ── ReadthroughFailureCode ────────────────────────────────────────


class ReadthroughFailureCode(str, Enum):
    """Reason why read-through could not produce a comparison."""

    READTHROUGH_DB_UNAVAILABLE = "readthrough_db_unavailable"
    READTHROUGH_RESULT_NOT_FOUND = "readthrough_result_not_found"
    READTHROUGH_QUERY_ERROR = "readthrough_query_error"


# ── ReasonComparisonDetail ───────────────────────────────────────


@dataclass(frozen=True)
class ReasonComparisonDetail:
    """Reason-level comparison breakdown. Audit-only, does not influence verdict."""

    screening_reasons_match: bool | None = None
    shadow_screening_fail_stages: frozenset[str] | None = None
    existing_screening_fail_stages: frozenset[str] | None = None
    qualification_reasons_match: bool | None = None
    shadow_qualification_fail_checks: frozenset[str] | None = None
    existing_qualification_fail_checks: frozenset[str] | None = None


# ── Input Fingerprint ─────────────────────────────────────────────


def _compute_input_fingerprint(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    asset_class: AssetClass,
    sector: AssetSector,
) -> str:
    """Deterministic hash of shadow inputs for dedup/comparison."""
    parts = [
        market.symbol,
        str(market.timestamp),
        str(market.avg_daily_volume_usd),
        str(market.atr_pct),
        str(market.adx),
        backtest.symbol,
        str(backtest.available_bars),
        str(backtest.sharpe_ratio),
        str(backtest.missing_data_pct),
        asset_class.value,
        sector.value,
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Shadow Pipeline ───────────────────────────────────────────────


def run_shadow_pipeline(
    market: MarketDataSnapshot,
    backtest: BacktestReadiness,
    asset_class: AssetClass,
    sector: AssetSector,
    fundamental: FundamentalSnapshot | None = None,
    metadata: SymbolMetadata | None = None,
    strategy_id: str = "",
    timeframe: str = "1h",
    screening_thresholds: ScreeningThresholds | None = None,
    qualification_thresholds: QualificationThresholds | None = None,
    now_utc: datetime | None = None,
) -> ShadowRunResult:
    """Execute full pipeline in shadow mode. Pure function.

    1. transform_provider_to_screening(market, backtest, ...)
    2. run_screening_qualification_pipeline(transform_result, backtest, ...)
    3. Package result as ShadowRunResult

    No DB, no async, no side-effect.
    """
    ts = now_utc or datetime.now(timezone.utc)

    # Step 1: Transform
    transform_result = transform_provider_to_screening(
        market,
        backtest,
        fundamental,
        metadata,
        asset_class,
        sector,
        ts,
    )

    # Step 2: Pipeline
    pipeline_output = run_screening_qualification_pipeline(
        transform_result,
        backtest,
        strategy_id=strategy_id,
        timeframe=timeframe,
        screening_thresholds=screening_thresholds,
        qualification_thresholds=qualification_thresholds,
        now_utc=ts,
    )

    # Step 3: Package
    fingerprint = _compute_input_fingerprint(market, backtest, asset_class, sector)

    return ShadowRunResult(
        symbol=market.symbol,
        pipeline_output=pipeline_output,
        shadow_timestamp=ts,
        input_fingerprint=fingerprint,
    )


# ── Shadow Comparison ─────────────────────────────────────────────


def _extract_shadow_fail_stages(shadow_result: ShadowRunResult) -> frozenset[str] | None:
    """Extract failed screening stage names from shadow result."""
    screening = shadow_result.pipeline_output.result.screening_output
    if screening is None:
        return None
    failed = frozenset(f"stage{sr.stage}" for sr in screening.stages if not sr.passed)
    return failed if failed else None


def _extract_shadow_fail_checks(shadow_result: ShadowRunResult) -> frozenset[str] | None:
    """Extract failed qualification check names from shadow result."""
    qual = shadow_result.pipeline_output.result.qualification_output
    if qual is None:
        return None
    failed = frozenset(cr.check_name for cr in qual.checks if not cr.passed)
    return failed if failed else None


def compare_shadow_to_existing(
    shadow_result: ShadowRunResult,
    existing: ShadowComparisonInput,
) -> ShadowRunResult:
    """Compare shadow pipeline verdict against existing results.

    Returns new ShadowRunResult with comparison_verdict filled.
    Pure function. No mutation. No fetch. No DB.

    INSUFFICIENT split (RI-2A-1):
      - INSUFFICIENT_OPERATIONAL: existing has no screening data (DB에 기존 결과 없음)
      - INSUFFICIENT_STRUCTURAL: shadow verdict is DATA_REJECTED (데이터 품질 불량)
    """
    from app.services.screening_qualification_pipeline import PipelineVerdict

    verdict = shadow_result.pipeline_output.result.verdict

    # INSUFFICIENT_OPERATIONAL: existing has no screening info
    if existing.existing_screening_passed is None:
        return ShadowRunResult(
            symbol=shadow_result.symbol,
            pipeline_output=shadow_result.pipeline_output,
            shadow_timestamp=shadow_result.shadow_timestamp,
            input_fingerprint=shadow_result.input_fingerprint,
            comparison_verdict=ComparisonVerdict.INSUFFICIENT_OPERATIONAL,
        )

    # INSUFFICIENT_STRUCTURAL: DATA_REJECTED has no equivalent in existing
    if verdict == PipelineVerdict.DATA_REJECTED:
        return ShadowRunResult(
            symbol=shadow_result.symbol,
            pipeline_output=shadow_result.pipeline_output,
            shadow_timestamp=shadow_result.shadow_timestamp,
            input_fingerprint=shadow_result.input_fingerprint,
            comparison_verdict=ComparisonVerdict.INSUFFICIENT_STRUCTURAL,
        )

    # Compare verdict against existing
    shadow_screen_passed = verdict in (
        PipelineVerdict.QUALIFIED,
        PipelineVerdict.QUALIFY_FAILED,
    )
    shadow_qual_passed = verdict == PipelineVerdict.QUALIFIED

    # Screening verdict check
    if shadow_screen_passed != existing.existing_screening_passed:
        return ShadowRunResult(
            symbol=shadow_result.symbol,
            pipeline_output=shadow_result.pipeline_output,
            shadow_timestamp=shadow_result.shadow_timestamp,
            input_fingerprint=shadow_result.input_fingerprint,
            comparison_verdict=ComparisonVerdict.VERDICT_MISMATCH,
        )

    # Qualification verdict check (only if existing has qual data)
    if existing.existing_qualification_passed is not None:
        if shadow_qual_passed != existing.existing_qualification_passed:
            return ShadowRunResult(
                symbol=shadow_result.symbol,
                pipeline_output=shadow_result.pipeline_output,
                shadow_timestamp=shadow_result.shadow_timestamp,
                input_fingerprint=shadow_result.input_fingerprint,
                comparison_verdict=ComparisonVerdict.VERDICT_MISMATCH,
            )

    # Reason-level comparison (verdict matches, both fail → compare reasons)
    reason_detail = _compare_reasons(
        shadow_result, existing, shadow_screen_passed, shadow_qual_passed
    )

    if reason_detail is not None:
        has_screen_mismatch = reason_detail.screening_reasons_match is False
        has_qual_mismatch = reason_detail.qualification_reasons_match is False
        if has_screen_mismatch or has_qual_mismatch:
            return ShadowRunResult(
                symbol=shadow_result.symbol,
                pipeline_output=shadow_result.pipeline_output,
                shadow_timestamp=shadow_result.shadow_timestamp,
                input_fingerprint=shadow_result.input_fingerprint,
                comparison_verdict=ComparisonVerdict.REASON_MISMATCH,
                reason_comparison=reason_detail,
            )

    return ShadowRunResult(
        symbol=shadow_result.symbol,
        pipeline_output=shadow_result.pipeline_output,
        shadow_timestamp=shadow_result.shadow_timestamp,
        input_fingerprint=shadow_result.input_fingerprint,
        comparison_verdict=ComparisonVerdict.MATCH,
        reason_comparison=reason_detail,
    )


def _compare_reasons(
    shadow_result: ShadowRunResult,
    existing: ShadowComparisonInput,
    shadow_screen_passed: bool,
    shadow_qual_passed: bool,
) -> ReasonComparisonDetail | None:
    """Compare fail reasons when verdict matches.

    Only compares reasons when both shadow and existing fail at the same level.
    Returns None if no reason comparison is applicable.
    """
    screening_match: bool | None = None
    shadow_screen_fails: frozenset[str] | None = None
    existing_screen_fails: frozenset[str] | None = None
    qual_match: bool | None = None
    shadow_qual_fails: frozenset[str] | None = None
    existing_qual_fails: frozenset[str] | None = None

    # Screen fail reason comparison (both failed screening)
    if not shadow_screen_passed and existing.existing_screening_passed is False:
        shadow_screen_fails = _extract_shadow_fail_stages(shadow_result)
        existing_screen_fails = existing.existing_screening_fail_stages
        if shadow_screen_fails is not None and existing_screen_fails is not None:
            screening_match = shadow_screen_fails == existing_screen_fails
        # else: one side has no reason data → skip (None)

    # Qual fail reason comparison (both failed qualification)
    if not shadow_qual_passed and existing.existing_qualification_passed is False:
        shadow_qual_fails = _extract_shadow_fail_checks(shadow_result)
        existing_qual_fails = existing.existing_qualification_fail_checks
        if shadow_qual_fails is not None and existing_qual_fails is not None:
            qual_match = shadow_qual_fails == existing_qual_fails
        # else: one side has no reason data → skip (None)

    # If no reason comparison was applicable, return None
    if screening_match is None and qual_match is None:
        return None

    return ReasonComparisonDetail(
        screening_reasons_match=screening_match,
        shadow_screening_fail_stages=shadow_screen_fails,
        existing_screening_fail_stages=existing_screen_fails,
        qualification_reasons_match=qual_match,
        shadow_qualification_fail_checks=shadow_qual_fails,
        existing_qualification_fail_checks=existing_qual_fails,
    )
