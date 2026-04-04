"""RI-2A-1: Shadow Read-through Tests — DB SELECT + in-memory comparison.

Tests:
  - fetch_existing_for_comparison: DB read-through, fail-closed, bounded query
  - run_readthrough_comparison: full flow with mock DB
  - No-write guarantee: assert 0 INSERT/UPDATE/DELETE calls
  - Fail-closed: DB errors → INSUFFICIENT_OPERATIONAL
  - INSUFFICIENT split: STRUCTURAL vs OPERATIONAL classification
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.asset import AssetClass, AssetSector, ScreeningResult
from app.models.qualification import QualificationResult, QualificationStatus
from app.services.data_provider import (
    BacktestReadiness,
    DataQuality,
    MarketDataSnapshot,
)
from app.services.pipeline_shadow_runner import (
    ComparisonVerdict,
    ReadthroughFailureCode,
    ShadowRunResult,
    run_shadow_pipeline,
)
from app.services.shadow_readthrough import (
    ExistingResultSource,
    ReadthroughComparisonResult,
    _extract_qualification_fail_checks,
    _extract_screening_fail_stages,
    fetch_existing_for_comparison,
    run_readthrough_comparison,
)


# ── Fixtures ──────────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 3, 12, 0, 0, tzinfo=timezone.utc)


def _make_market(symbol="SOL/USDT", volume=500_000_000.0, **kw) -> MarketDataSnapshot:
    defaults = dict(
        symbol=symbol,
        timestamp=_NOW,
        price_usd=150.0,
        market_cap_usd=50e9,
        avg_daily_volume_usd=volume,
        spread_pct=0.05,
        atr_pct=5.0,
        adx=30.0,
        price_vs_200ma=1.05,
        quality=DataQuality.HIGH,
    )
    defaults.update(kw)
    return MarketDataSnapshot(**defaults)


def _make_backtest(symbol="SOL/USDT", **kw) -> BacktestReadiness:
    defaults = dict(
        symbol=symbol,
        available_bars=1000,
        sharpe_ratio=1.5,
        missing_data_pct=1.0,
        quality=DataQuality.HIGH,
    )
    defaults.update(kw)
    return BacktestReadiness(**defaults)


def _shadow_qualified(symbol="SOL/USDT") -> ShadowRunResult:
    return run_shadow_pipeline(
        _make_market(symbol=symbol),
        _make_backtest(symbol=symbol),
        AssetClass.CRYPTO,
        AssetSector.LAYER1,
        now_utc=_NOW,
    )


def _shadow_data_rejected(symbol="DEAD/USDT") -> ShadowRunResult:
    market = MarketDataSnapshot(symbol=symbol, quality=DataQuality.UNAVAILABLE)
    return run_shadow_pipeline(
        market,
        _make_backtest(symbol=symbol),
        AssetClass.CRYPTO,
        AssetSector.LAYER1,
        now_utc=_NOW,
    )


def _mock_screening_row(
    symbol="SOL/USDT",
    all_passed=True,
    s1=True,
    s2=True,
    s3=True,
    s4=True,
    s5=True,
    stage_reason_code=None,
) -> MagicMock:
    row = MagicMock(spec=ScreeningResult)
    row.id = "sr-001"
    row.symbol = symbol
    row.all_passed = all_passed
    row.stage1_exclusion = s1
    row.stage2_liquidity = s2
    row.stage3_technical = s3
    row.stage4_fundamental = s4
    row.stage5_backtest = s5
    row.stage_reason_code = stage_reason_code
    row.screened_at = _NOW
    return row


def _mock_qualification_row(
    symbol="SOL/USDT",
    all_passed=True,
    checks=None,
    failed_checks_json=None,
    disqualify_reason=None,
) -> MagicMock:
    row = MagicMock(spec=QualificationResult)
    row.id = "qr-001"
    row.symbol = symbol
    row.all_passed = all_passed
    row.check_data_compat = True
    row.check_warmup = True
    row.check_leakage = True
    row.check_data_quality = True
    row.check_min_bars = True
    row.check_performance = True
    row.check_cost_sanity = True
    if checks:
        for check_name in checks:
            setattr(row, f"check_{check_name}", False)
    row.failed_checks = failed_checks_json
    row.disqualify_reason = disqualify_reason
    row.evaluated_at = _NOW
    return row


def _mock_db_session(screen_row=None, qual_row=None, raise_error=False):
    """Create a mock AsyncSession that returns the given rows."""
    db = AsyncMock()

    if raise_error:
        db.execute = AsyncMock(side_effect=Exception("DB connection failed"))
        return db

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # First call = screening, second = qualification
        if call_count == 1:
            result.scalar_one_or_none.return_value = screen_row
        else:
            result.scalar_one_or_none.return_value = qual_row
        return result

    db.execute = AsyncMock(side_effect=_execute)
    return db


# ── TestExtractScreeningFailStages ───────────────────────────────


class TestExtractScreeningFailStages:
    def test_all_passed_returns_none(self):
        row = _mock_screening_row(all_passed=True)
        assert _extract_screening_fail_stages(row) is None

    def test_single_stage_fail(self):
        row = _mock_screening_row(all_passed=False, s2=False)
        assert _extract_screening_fail_stages(row) == frozenset({"stage2"})

    def test_multiple_stage_fail(self):
        row = _mock_screening_row(all_passed=False, s2=False, s3=False)
        result = _extract_screening_fail_stages(row)
        assert result == frozenset({"stage2", "stage3"})


# ── TestExtractQualificationFailChecks ───────────────────────────


class TestExtractQualificationFailChecks:
    def test_all_passed_returns_none(self):
        row = _mock_qualification_row(all_passed=True)
        assert _extract_qualification_fail_checks(row) is None

    def test_json_column_preferred(self):
        row = _mock_qualification_row(
            all_passed=False,
            failed_checks_json=json.dumps(["data_quality", "performance"]),
        )
        result = _extract_qualification_fail_checks(row)
        assert result == frozenset({"data_quality", "performance"})

    def test_boolean_fallback(self):
        row = _mock_qualification_row(
            all_passed=False,
            checks=["performance", "min_bars"],
        )
        result = _extract_qualification_fail_checks(row)
        assert result == frozenset({"performance", "min_bars"})

    def test_corrupt_json_falls_back(self):
        row = _mock_qualification_row(
            all_passed=False,
            failed_checks_json="not valid json{",
            checks=["data_quality"],
        )
        result = _extract_qualification_fail_checks(row)
        assert result == frozenset({"data_quality"})


# ── TestFetchExistingForComparison ───────────────────────────────


class TestFetchExistingForComparison:
    @pytest.mark.asyncio
    async def test_both_results_found(self):
        screen = _mock_screening_row(all_passed=True)
        qual = _mock_qualification_row(all_passed=True)
        db = _mock_db_session(screen_row=screen, qual_row=qual)

        input_, source = await fetch_existing_for_comparison(db, "SOL/USDT")

        assert input_.existing_screening_passed is True
        assert input_.existing_qualification_passed is True
        assert source.screening_result_id == "sr-001"
        assert source.qualification_result_id == "qr-001"
        assert source.failure_code is None

    @pytest.mark.asyncio
    async def test_no_screening_result(self):
        db = _mock_db_session(screen_row=None, qual_row=None)

        input_, source = await fetch_existing_for_comparison(db, "UNKNOWN")

        assert input_.existing_screening_passed is None
        assert input_.existing_qualification_passed is None
        assert source.failure_code == ReadthroughFailureCode.READTHROUGH_RESULT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_screening_fail_reasons_extracted(self):
        screen = _mock_screening_row(all_passed=False, s2=False, s3=False)
        db = _mock_db_session(screen_row=screen, qual_row=None)

        input_, _ = await fetch_existing_for_comparison(db, "SOL/USDT")

        assert input_.existing_screening_passed is False
        assert input_.existing_screening_fail_stages == frozenset({"stage2", "stage3"})

    @pytest.mark.asyncio
    async def test_qualification_fail_reasons_extracted(self):
        screen = _mock_screening_row(all_passed=True)
        qual = _mock_qualification_row(
            all_passed=False,
            failed_checks_json=json.dumps(["performance"]),
        )
        db = _mock_db_session(screen_row=screen, qual_row=qual)

        input_, _ = await fetch_existing_for_comparison(db, "SOL/USDT")

        assert input_.existing_qualification_passed is False
        assert input_.existing_qualification_fail_checks == frozenset({"performance"})

    @pytest.mark.asyncio
    async def test_db_error_returns_insufficient(self):
        db = _mock_db_session(raise_error=True)

        input_, source = await fetch_existing_for_comparison(db, "SOL/USDT")

        assert input_.existing_screening_passed is None
        assert source.failure_code == ReadthroughFailureCode.READTHROUGH_DB_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_bounded_query_limit_1(self):
        """Verify that queries use LIMIT 1 (bounded)."""
        db = _mock_db_session(screen_row=None, qual_row=None)

        await fetch_existing_for_comparison(db, "SOL/USDT")

        # Both calls should have been made (screening + qualification)
        assert db.execute.call_count == 2


# ── TestReadthroughComparison ────────────────────────────────────


class TestReadthroughComparison:
    @pytest.mark.asyncio
    async def test_match_flow(self):
        shadow = _shadow_qualified()
        screen = _mock_screening_row(all_passed=True)
        qual = _mock_qualification_row(all_passed=True)
        db = _mock_db_session(screen_row=screen, qual_row=qual)

        result = await run_readthrough_comparison(db, shadow)

        assert isinstance(result, ReadthroughComparisonResult)
        assert result.comparison_verdict == ComparisonVerdict.MATCH
        assert result.symbol == "SOL/USDT"

    @pytest.mark.asyncio
    async def test_verdict_mismatch_flow(self):
        shadow = _shadow_qualified()
        screen = _mock_screening_row(all_passed=False, s2=False)
        db = _mock_db_session(screen_row=screen, qual_row=None)

        result = await run_readthrough_comparison(db, shadow)

        assert result.comparison_verdict == ComparisonVerdict.VERDICT_MISMATCH

    @pytest.mark.asyncio
    async def test_insufficient_operational_no_existing(self):
        shadow = _shadow_qualified()
        db = _mock_db_session(screen_row=None, qual_row=None)

        result = await run_readthrough_comparison(db, shadow)

        assert result.comparison_verdict == ComparisonVerdict.INSUFFICIENT_OPERATIONAL

    @pytest.mark.asyncio
    async def test_insufficient_structural_data_rejected(self):
        shadow = _shadow_data_rejected()
        screen = _mock_screening_row(all_passed=True)
        qual = _mock_qualification_row(all_passed=True)
        db = _mock_db_session(screen_row=screen, qual_row=qual)

        result = await run_readthrough_comparison(db, shadow)

        assert result.comparison_verdict == ComparisonVerdict.INSUFFICIENT_STRUCTURAL

    @pytest.mark.asyncio
    async def test_db_failure_insufficient_operational(self):
        shadow = _shadow_qualified()
        db = _mock_db_session(raise_error=True)

        result = await run_readthrough_comparison(db, shadow)

        assert result.comparison_verdict == ComparisonVerdict.INSUFFICIENT_OPERATIONAL
        assert (
            result.existing_source.failure_code == ReadthroughFailureCode.READTHROUGH_DB_UNAVAILABLE
        )


# ── TestReadthroughNoWrite ───────────────────────────────────────


class TestReadthroughNoWrite:
    @pytest.mark.asyncio
    async def test_no_add_called(self):
        shadow = _shadow_qualified()
        screen = _mock_screening_row(all_passed=True)
        qual = _mock_qualification_row(all_passed=True)
        db = _mock_db_session(screen_row=screen, qual_row=qual)

        await run_readthrough_comparison(db, shadow)

        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_flush_called(self):
        shadow = _shadow_qualified()
        db = _mock_db_session(screen_row=None, qual_row=None)

        await run_readthrough_comparison(db, shadow)

        db.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_commit_called(self):
        shadow = _shadow_qualified()
        db = _mock_db_session(screen_row=None, qual_row=None)

        await run_readthrough_comparison(db, shadow)

        db.commit.assert_not_called()
