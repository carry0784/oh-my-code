"""Stage 4A: Screening-Qualification Pipeline Composition — pure functions only.

Composes sealed engines into a single static pipe:
  TransformResult → screen() → qualify() → PipelineOutput

No async, no I/O, no DB, no network, no retry, no orchestration.
Pure Zone file #8.

Layer 1 (Pure Composition) of the 3-layer architecture:
  L1: screening_qualification_pipeline.py  (this file)
  L2: tests/  (fixtures + tests)
  L3: runtime/service path  (BLOCKED in Stage 4A)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.services.backtest_qualification import (
    BacktestQualifier,
    QualificationInput,
    QualificationOutput,
    QualificationThresholds,
)
from app.services.data_provider import BacktestReadiness, DataQualityDecision
from app.services.screening_transform import (
    TransformResult,
    _REJECT_DECISIONS,
)


# Decisions that allow pipeline to proceed past FC-1/FC-2.
# Any DataQualityDecision NOT in either set is unknown → fail-fast.
_PROCEED_DECISIONS: frozenset[DataQualityDecision] = frozenset(
    {
        DataQualityDecision.OK,
        DataQualityDecision.PARTIAL_USABLE,
        DataQualityDecision.STALE_USABLE,
        DataQualityDecision.INSUFFICIENT_BARS,
        DataQualityDecision.MISSING_LISTING_AGE,
    }
)
from app.services.symbol_screener import (
    ScreeningInput,
    ScreeningOutput,
    ScreeningThresholds,
    SymbolScreener,
)


# ── PipelineVerdict ─────────────────────────────────────────────────


class PipelineVerdict(str, Enum):
    """Outcome of the full screening-qualification pipeline."""

    DATA_REJECTED = "data_rejected"
    SCREEN_FAILED = "screen_failed"
    QUALIFY_FAILED = "qualify_failed"
    QUALIFIED = "qualified"


# ── PipelineResult ──────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineResult:
    """Computation result of the pipeline.

    Invariants:
      - DATA_REJECTED → screening_output=None, qualification_output=None
      - SCREEN_FAILED → screening_output is not None, qualification_output=None
      - QUALIFY_FAILED → both not None
      - QUALIFIED → both not None, both all_passed=True
    """

    symbol: str
    verdict: PipelineVerdict
    screening_output: ScreeningOutput | None = None
    qualification_output: QualificationOutput | None = None


# ── PipelineEvidence ────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineEvidence:
    """Audit-only provenance record.  Does NOT influence verdict."""

    symbol: str
    transform_decision: DataQualityDecision
    transform_source: object | None = None
    screening_score: float | None = None
    screening_stage_count: int = 0
    qualification_status: str | None = None
    qualification_check_count: int = 0
    pipeline_timestamp: datetime | None = None


# ── PipelineOutput ──────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineOutput:
    """Top-level return: result + evidence."""

    result: PipelineResult
    evidence: PipelineEvidence


# ── Mapping Helper ──────────────────────────────────────────────────


def _map_to_qualification_input(
    screening_input: ScreeningInput,
    backtest: BacktestReadiness,
    strategy_id: str,
    timeframe: str,
) -> QualificationInput:
    """Map ScreeningInput + BacktestReadiness → QualificationInput.

    Deterministic field copy.  No interpretation, no branching.
    """
    return QualificationInput(
        strategy_id=strategy_id,
        symbol=screening_input.symbol,
        timeframe=timeframe,
        symbol_asset_class=screening_input.asset_class.value,
        total_bars=backtest.available_bars or 0,
        warmup_bars_available=backtest.available_bars or 0,
        missing_data_pct=backtest.missing_data_pct or 0.0,
        sharpe_ratio=backtest.sharpe_ratio,
    )


# ── Main Pipeline ───────────────────────────────────────────────────


def run_screening_qualification_pipeline(
    transform_result: TransformResult,
    backtest: BacktestReadiness,
    strategy_id: str = "",
    timeframe: str = "1h",
    screening_thresholds: ScreeningThresholds | None = None,
    qualification_thresholds: QualificationThresholds | None = None,
    now_utc: datetime | None = None,
) -> PipelineOutput:
    """Compose screening transform → screen → qualify in a single pure call.

    Pure function.  No async, no I/O, no DB.
    Caller supplies TransformResult (from screening_transform) and
    BacktestReadiness (from data provider).

    Fail-closed: each stage failure halts subsequent stages.
    """
    symbol = (
        transform_result.screening_input.symbol
        if transform_result.screening_input
        else backtest.symbol
    )

    # ── FC-0: Unknown decision fail-fast ──────────────────────────
    if (
        transform_result.decision not in _REJECT_DECISIONS
        and transform_result.decision not in _PROCEED_DECISIONS
    ):
        raise ValueError(f"Unknown DataQualityDecision: {transform_result.decision!r}")

    # ── FC-1 / FC-2: TransformResult reject check ───────────────────
    if transform_result.decision in _REJECT_DECISIONS:
        return _make_rejected_output(symbol, transform_result, now_utc)

    if transform_result.screening_input is None:
        return _make_rejected_output(symbol, transform_result, now_utc)

    screening_input = transform_result.screening_input

    # ── Screen ──────────────────────────────────────────────────────
    screener = SymbolScreener(thresholds=screening_thresholds)
    screening_output = screener.screen(screening_input)

    # ── FC-3: Screen fail check ─────────────────────────────────────
    if not screening_output.all_passed:
        return PipelineOutput(
            result=PipelineResult(
                symbol=symbol,
                verdict=PipelineVerdict.SCREEN_FAILED,
                screening_output=screening_output,
            ),
            evidence=_build_evidence(
                symbol,
                transform_result,
                screening_output,
                None,
                now_utc,
            ),
        )

    # ── Qualify ─────────────────────────────────────────────────────
    qual_input = _map_to_qualification_input(
        screening_input,
        backtest,
        strategy_id,
        timeframe,
    )
    qualifier = BacktestQualifier(thresholds=qualification_thresholds)
    qual_output = qualifier.qualify(qual_input)

    # ── FC-4: Qualify fail check ────────────────────────────────────
    if not qual_output.all_passed:
        return PipelineOutput(
            result=PipelineResult(
                symbol=symbol,
                verdict=PipelineVerdict.QUALIFY_FAILED,
                screening_output=screening_output,
                qualification_output=qual_output,
            ),
            evidence=_build_evidence(
                symbol,
                transform_result,
                screening_output,
                qual_output,
                now_utc,
            ),
        )

    # ── FC-5: All pass ──────────────────────────────────────────────
    return PipelineOutput(
        result=PipelineResult(
            symbol=symbol,
            verdict=PipelineVerdict.QUALIFIED,
            screening_output=screening_output,
            qualification_output=qual_output,
        ),
        evidence=_build_evidence(
            symbol,
            transform_result,
            screening_output,
            qual_output,
            now_utc,
        ),
    )


# ── Internal Helpers ────────────────────────────────────────────────


def _make_rejected_output(
    symbol: str,
    transform_result: TransformResult,
    now_utc: datetime | None,
) -> PipelineOutput:
    return PipelineOutput(
        result=PipelineResult(
            symbol=symbol,
            verdict=PipelineVerdict.DATA_REJECTED,
        ),
        evidence=PipelineEvidence(
            symbol=symbol,
            transform_decision=transform_result.decision,
            transform_source=transform_result.source,
            pipeline_timestamp=now_utc,
        ),
    )


def _build_evidence(
    symbol: str,
    transform_result: TransformResult,
    screening_output: ScreeningOutput | None,
    qual_output: QualificationOutput | None,
    now_utc: datetime | None,
) -> PipelineEvidence:
    return PipelineEvidence(
        symbol=symbol,
        transform_decision=transform_result.decision,
        transform_source=transform_result.source,
        screening_score=(screening_output.score if screening_output is not None else None),
        screening_stage_count=(len(screening_output.stages) if screening_output is not None else 0),
        qualification_status=(
            qual_output.qualification_status.value if qual_output is not None else None
        ),
        qualification_check_count=(len(qual_output.checks) if qual_output is not None else 0),
        pipeline_timestamp=now_utc,
    )
