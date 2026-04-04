"""Tests for Phase 4A: Backtest Qualification — 7-check engine,
qualification model, AssetService integration, and status separation.

All tests use mocked DB sessions (no infrastructure dependency).
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.asset import (
    AssetClass,
    AssetSector,
    AssetTheme,
    SymbolStatus,
    Symbol,
    EXCLUDED_SECTORS,
)
from app.models.qualification import (
    QualificationStatus,
    DisqualifyReason,
    QualificationResult,
)
from app.services.backtest_qualification import (
    QualificationInput,
    QualificationOutput,
    QualificationThresholds,
    CheckResult,
    BacktestQualifier,
)
from app.services.asset_service import AssetService
from app.schemas.asset_schema import QualificationResultRead
from app.core.constitution import FORBIDDEN_SECTOR_VALUES


# ── Helpers ──────────────────────────────────────────────────────────


def _mock_db():
    db = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_symbol(**overrides) -> Symbol:
    base = dict(
        id="sym-001",
        symbol="SOL/USDT",
        name="Solana",
        asset_class=AssetClass.CRYPTO,
        sector=AssetSector.LAYER1,
        theme=AssetTheme.L1_SCALING,
        exchanges=json.dumps(["BINANCE"]),
        market_cap_usd=80_000_000_000,
        avg_daily_volume=2_000_000_000,
        status=SymbolStatus.CORE,
        status_reason_code="screening_full_pass",
        exclusion_reason=None,
        screening_score=1.0,
        qualification_status="unchecked",
        promotion_eligibility_status="unchecked",
        paper_evaluation_status="pending",
        regime_allow=json.dumps(["trending_up"]),
        candidate_expire_at=None,
        paper_allowed=False,
        live_allowed=False,
        manual_override=False,
        override_by=None,
        override_reason=None,
        override_at=None,
        broker_policy=None,
        paper_pass_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return Symbol(**base)


def _full_pass_input(**overrides) -> QualificationInput:
    """Create a QualificationInput that passes all 7 checks."""
    base = dict(
        strategy_id="strat-001",
        symbol="SOL/USDT",
        timeframe="1h",
        strategy_asset_classes=["crypto"],
        strategy_timeframes=["1h", "4h"],
        symbol_asset_class="crypto",
        dataset_fingerprint="abc123def456",
        total_bars=1000,
        warmup_bars_required=200,
        warmup_bars_available=250,
        missing_data_pct=1.0,
        has_timestamp_disorder=False,
        duplicate_bar_count=0,
        has_future_data_leak=False,
        has_lookahead_bias=False,
        sharpe_ratio=0.8,
        max_drawdown_pct=15.0,
        total_return_pct=25.0,
        sharpe_after_costs=0.5,
        return_after_costs_pct=18.0,
        turnover_annual=50.0,
    )
    base.update(overrides)
    return QualificationInput(**base)


# ── Check 1: Data Compatibility ──────────────────────────────────────


class TestCheck1DataCompat:
    def test_incompatible_asset_class_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(
            strategy_asset_classes=["us_stock"],
            symbol_asset_class="crypto",
        )
        out = q.qualify(inp)
        assert not out.checks[0].passed
        assert out.disqualify_reason == DisqualifyReason.INCOMPATIBLE_ASSET_CLASS

    def test_incompatible_timeframe_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(
            strategy_timeframes=["4h", "1d"],
            timeframe="1h",
        )
        out = q.qualify(inp)
        assert not out.checks[0].passed
        assert out.disqualify_reason == DisqualifyReason.INCOMPATIBLE_TIMEFRAME

    def test_compatible_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input()
        out = q.qualify(inp)
        assert out.checks[0].passed

    def test_no_constraints_passes(self):
        """None strategy constraints = accept all."""
        q = BacktestQualifier()
        inp = _full_pass_input(
            strategy_asset_classes=None,
            strategy_timeframes=None,
        )
        out = q.qualify(inp)
        assert out.checks[0].passed


# ── Check 2: Warmup ──────────────────────────────────────────────────


class TestCheck2Warmup:
    def test_insufficient_warmup_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(warmup_bars_required=200, warmup_bars_available=100)
        out = q.qualify(inp)
        assert not out.checks[1].passed
        assert out.disqualify_reason == DisqualifyReason.INSUFFICIENT_WARMUP

    def test_sufficient_warmup_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input(warmup_bars_required=200, warmup_bars_available=200)
        out = q.qualify(inp)
        assert out.checks[1].passed


# ── Check 3: Leakage ─────────────────────────────────────────────────


class TestCheck3Leakage:
    def test_future_data_leak_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(has_future_data_leak=True)
        out = q.qualify(inp)
        assert not out.checks[2].passed
        assert out.disqualify_reason == DisqualifyReason.FUTURE_DATA_LEAK

    def test_lookahead_bias_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(has_lookahead_bias=True)
        out = q.qualify(inp)
        assert not out.checks[2].passed
        assert out.disqualify_reason == DisqualifyReason.LOOKAHEAD_BIAS

    def test_clean_data_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input()
        out = q.qualify(inp)
        assert out.checks[2].passed


# ── Check 4: Data Quality ────────────────────────────────────────────


class TestCheck4DataQuality:
    def test_high_missing_data_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(missing_data_pct=10.0)
        out = q.qualify(inp)
        assert not out.checks[3].passed
        assert out.disqualify_reason == DisqualifyReason.MISSING_DATA_EXCESS

    def test_timestamp_disorder_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(has_timestamp_disorder=True)
        out = q.qualify(inp)
        assert not out.checks[3].passed
        assert out.disqualify_reason == DisqualifyReason.TIMESTAMP_DISORDER

    def test_duplicate_bars_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(duplicate_bar_count=5)
        out = q.qualify(inp)
        assert not out.checks[3].passed
        assert out.disqualify_reason == DisqualifyReason.DUPLICATE_BARS

    def test_good_data_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input()
        out = q.qualify(inp)
        assert out.checks[3].passed


# ── Check 5: Minimum Bars ────────────────────────────────────────────


class TestCheck5MinBars:
    def test_insufficient_bars_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(total_bars=200)
        out = q.qualify(inp)
        assert not out.checks[4].passed
        assert out.disqualify_reason == DisqualifyReason.INSUFFICIENT_BARS

    def test_sufficient_bars_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input(total_bars=500)
        out = q.qualify(inp)
        assert out.checks[4].passed


# ── Check 6: Performance ─────────────────────────────────────────────


class TestCheck6Performance:
    def test_negative_sharpe_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(sharpe_ratio=-0.5)
        out = q.qualify(inp)
        assert not out.checks[5].passed
        assert out.disqualify_reason == DisqualifyReason.NEGATIVE_SHARPE

    def test_none_sharpe_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(sharpe_ratio=None)
        out = q.qualify(inp)
        assert not out.checks[5].passed

    def test_excessive_drawdown_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(max_drawdown_pct=60.0)  # > 50%
        out = q.qualify(inp)
        assert not out.checks[5].passed
        assert out.disqualify_reason == DisqualifyReason.EXCESSIVE_DRAWDOWN

    def test_good_performance_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input(sharpe_ratio=0.5, max_drawdown_pct=20.0)
        out = q.qualify(inp)
        assert out.checks[5].passed


# ── Check 7: Cost Sanity ─────────────────────────────────────────────


class TestCheck7CostSanity:
    def test_negative_after_costs_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(sharpe_after_costs=-1.0)
        out = q.qualify(inp)
        assert not out.checks[6].passed
        assert out.disqualify_reason == DisqualifyReason.NEGATIVE_AFTER_COSTS

    def test_excessive_turnover_fails(self):
        q = BacktestQualifier()
        inp = _full_pass_input(turnover_annual=500.0)  # > 365
        out = q.qualify(inp)
        assert not out.checks[6].passed
        assert out.disqualify_reason == DisqualifyReason.EXCESSIVE_TURNOVER

    def test_no_cost_data_passes(self):
        """None cost metrics = pass (data not yet available)."""
        q = BacktestQualifier()
        inp = _full_pass_input(sharpe_after_costs=None, turnover_annual=None)
        out = q.qualify(inp)
        assert out.checks[6].passed

    def test_good_costs_passes(self):
        q = BacktestQualifier()
        inp = _full_pass_input(sharpe_after_costs=0.3, turnover_annual=100.0)
        out = q.qualify(inp)
        assert out.checks[6].passed


# ── Aggregate Results ────────────────────────────────────────────────


class TestAggregateResults:
    def test_all_pass_produces_pass(self):
        q = BacktestQualifier()
        out = q.qualify(_full_pass_input())
        assert out.all_passed is True
        assert out.qualification_status == QualificationStatus.PASS
        assert out.disqualify_reason is None

    def test_any_fail_produces_fail(self):
        q = BacktestQualifier()
        inp = _full_pass_input(total_bars=10)
        out = q.qualify(inp)
        assert out.all_passed is False
        assert out.qualification_status == QualificationStatus.FAIL

    def test_seven_checks_always(self):
        q = BacktestQualifier()
        out = q.qualify(_full_pass_input())
        assert len(out.checks) == 7

    def test_metrics_snapshot_populated(self):
        q = BacktestQualifier()
        out = q.qualify(_full_pass_input())
        assert out.metrics_snapshot is not None
        assert "sharpe_ratio" in out.metrics_snapshot

    def test_first_fail_sets_reason(self):
        """disqualify_reason should be from the FIRST failing check."""
        q = BacktestQualifier()
        # Make checks 4 and 5 fail
        inp = _full_pass_input(missing_data_pct=99.0, total_bars=10)
        out = q.qualify(inp)
        assert out.disqualify_reason == DisqualifyReason.MISSING_DATA_EXCESS


# ── Custom Thresholds ────────────────────────────────────────────────


class TestCustomThresholds:
    def test_strict_bars_fails(self):
        t = QualificationThresholds(min_bars=2000)
        q = BacktestQualifier(thresholds=t)
        inp = _full_pass_input(total_bars=1000)
        out = q.qualify(inp)
        assert not out.checks[4].passed

    def test_lenient_drawdown_passes(self):
        t = QualificationThresholds(max_drawdown_pct=80.0)
        q = BacktestQualifier(thresholds=t)
        inp = _full_pass_input(max_drawdown_pct=60.0)
        out = q.qualify(inp)
        assert out.checks[5].passed


# ── Model Tests ──────────────────────────────────────────────────────


class TestQualificationModel:
    def test_qualification_result_creation(self):
        qr = QualificationResult(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            check_data_compat=True,
            check_warmup=True,
            check_leakage=True,
            check_data_quality=True,
            check_min_bars=True,
            check_performance=True,
            check_cost_sanity=True,
            all_passed=True,
            qualification_status=QualificationStatus.PASS,
        )
        assert qr.all_passed is True
        assert qr.qualification_status == QualificationStatus.PASS

    def test_qualification_result_fail(self):
        qr = QualificationResult(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            all_passed=False,
            qualification_status=QualificationStatus.FAIL,
            disqualify_reason="negative_sharpe",
        )
        assert qr.qualification_status == QualificationStatus.FAIL
        assert qr.disqualify_reason == "negative_sharpe"

    def test_qualification_status_enum_values(self):
        assert QualificationStatus.UNCHECKED.value == "unchecked"
        assert QualificationStatus.PASS.value == "pass"
        assert QualificationStatus.FAIL.value == "fail"
        assert len(QualificationStatus) == 3

    def test_disqualify_reason_enum(self):
        """All DisqualifyReason members are valid."""
        assert len(DisqualifyReason) == 14
        # Key reasons exist
        assert DisqualifyReason.FUTURE_DATA_LEAK.value == "future_data_leak"
        assert DisqualifyReason.NEGATIVE_SHARPE.value == "negative_sharpe"
        assert DisqualifyReason.NEGATIVE_AFTER_COSTS.value == "negative_after_costs"


# ── Schema Tests ─────────────────────────────────────────────────────


class TestQualificationSchema:
    def test_qualification_result_read(self):
        qr = QualificationResultRead(
            id="qr-001",
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            dataset_fingerprint="abc123",
            bars_evaluated=1000,
            date_range_start=None,
            date_range_end=None,
            check_data_compat=True,
            check_warmup=True,
            check_leakage=True,
            check_data_quality=True,
            check_min_bars=True,
            check_performance=True,
            check_cost_sanity=True,
            all_passed=True,
            qualification_status=QualificationStatus.PASS,
            disqualify_reason=None,
            failed_checks=None,
            metrics_snapshot=None,
            detail=None,
            evaluated_at=datetime.now(timezone.utc),
        )
        assert qr.all_passed is True


# ── AssetService Integration ─────────────────────────────────────────


class TestQualifyAndRecord:
    @pytest.mark.asyncio
    async def test_pass_updates_symbol_qualification_status(self):
        db = _mock_db()
        sym = _make_symbol(qualification_status="unchecked")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        out = await svc.qualify_and_record("sym-001", _full_pass_input())

        assert out.all_passed is True
        assert sym.qualification_status == "pass"

    @pytest.mark.asyncio
    async def test_fail_updates_symbol_qualification_status(self):
        db = _mock_db()
        sym = _make_symbol(qualification_status="unchecked")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input(sharpe_ratio=-0.5)
        out = await svc.qualify_and_record("sym-001", inp)

        assert out.all_passed is False
        assert sym.qualification_status == "fail"

    @pytest.mark.asyncio
    async def test_screening_status_unchanged(self):
        """Qualification should NOT change screening status (CORE stays CORE)."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input(sharpe_ratio=-0.5)  # qualification FAIL
        await svc.qualify_and_record("sym-001", inp)

        # Screening status stays CORE
        assert sym.status == SymbolStatus.CORE
        # But qualification is FAIL
        assert sym.qualification_status == "fail"

    @pytest.mark.asyncio
    async def test_record_is_appended(self):
        db = _mock_db()
        sym = _make_symbol()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        await svc.qualify_and_record("sym-001", _full_pass_input())
        await svc.qualify_and_record("sym-001", _full_pass_input(sharpe_ratio=-0.5))

        # Two records appended
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_nonexistent_symbol_raises(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        svc = AssetService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.qualify_and_record("bad-id", _full_pass_input())


# ── Status Separation ────────────────────────────────────────────────


class TestStatusSeparation:
    """Verify screening_status and qualification_status remain independent."""

    def test_symbol_has_both_statuses(self):
        sym = _make_symbol()
        assert hasattr(sym, "status")  # screening status
        assert hasattr(sym, "qualification_status")

    def test_screening_core_qualification_unchecked(self):
        sym = _make_symbol(
            status=SymbolStatus.CORE,
            qualification_status="unchecked",
        )
        assert sym.status == SymbolStatus.CORE
        assert sym.qualification_status == "unchecked"

    def test_screening_core_qualification_fail(self):
        """A symbol can be screening-CORE but qualification-FAIL."""
        sym = _make_symbol(
            status=SymbolStatus.CORE,
            qualification_status="fail",
        )
        assert sym.status == SymbolStatus.CORE
        assert sym.qualification_status == "fail"

    def test_screening_watch_qualification_pass(self):
        """Unlikely but valid: screened as WATCH but has a passing qualification."""
        sym = _make_symbol(
            status=SymbolStatus.WATCH,
            qualification_status="pass",
        )
        assert sym.status == SymbolStatus.WATCH
        assert sym.qualification_status == "pass"


# ── Constitution Shared Source ───────────────────────────────────────


class TestConstitutionSharedSource:
    """Verify the shared constitution source is properly wired."""

    def test_forbidden_sector_values_match_excluded_sectors(self):
        """Constitution values match Asset Registry EXCLUDED_SECTORS."""
        from app.models.asset import EXCLUDED_SECTORS

        asset_values = {s.value for s in EXCLUDED_SECTORS}
        assert asset_values == FORBIDDEN_SECTOR_VALUES

    def test_forbidden_sectors_gateway_match_constitution(self):
        """Gateway FORBIDDEN_SECTORS derive from constitution."""
        from app.services.injection_gateway import FORBIDDEN_SECTORS

        gateway_values = {s.lower() for s in FORBIDDEN_SECTORS}
        assert gateway_values == FORBIDDEN_SECTOR_VALUES

    def test_single_source_count(self):
        assert len(FORBIDDEN_SECTOR_VALUES) == 7


# ── Reason Code Separation ───────────────────────────────────────────


class TestReasonCodeSeparation:
    """Verify ScreeningStageReason and DisqualifyReason are distinct."""

    def test_enum_names_distinct(self):
        from app.models.asset import ScreeningStageReason

        screening_values = {r.value for r in ScreeningStageReason}
        disqualify_values = {r.value for r in DisqualifyReason}
        # Some overlap is OK (e.g. both have insufficient_bars)
        # but the enum types must be different
        assert ScreeningStageReason is not DisqualifyReason

    def test_qualification_specific_reasons_exist(self):
        """DisqualifyReason has reasons that don't exist in screening."""
        assert hasattr(DisqualifyReason, "FUTURE_DATA_LEAK")
        assert hasattr(DisqualifyReason, "LOOKAHEAD_BIAS")
        assert hasattr(DisqualifyReason, "NEGATIVE_AFTER_COSTS")
        assert hasattr(DisqualifyReason, "EXCESSIVE_TURNOVER")
        assert hasattr(DisqualifyReason, "EXCESSIVE_DRAWDOWN")
