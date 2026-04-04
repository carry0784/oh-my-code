"""Tests for Phase 3A: Symbol Screener — 5-stage screening engine,
AssetService integration, canonicalization, and constitution alignment.

All tests use mocked DB sessions (no infrastructure dependency).
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.asset import (
    AssetClass,
    AssetSector,
    AssetTheme,
    SymbolStatus,
    SymbolStatusReason,
    ScreeningStageReason,
    Symbol,
    ScreeningResult,
    EXCLUDED_SECTORS,
    canonicalize_symbol,
)
from app.services.symbol_screener import (
    ScreeningInput,
    ScreeningOutput,
    ScreeningThresholds,
    StageResult,
    SymbolScreener,
)
from app.services.asset_service import AssetService


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
        status=SymbolStatus.WATCH,
        status_reason_code=None,
        exclusion_reason=None,
        screening_score=0.0,
        regime_allow=json.dumps(["trending_up"]),
        candidate_expire_at=None,
        paper_allowed=False,
        live_allowed=False,
        manual_override=False,
        override_by=None,
        override_reason=None,
        override_at=None,
        qualification_status="unchecked",
        promotion_eligibility_status="unchecked",
        paper_evaluation_status="pending",
        broker_policy=None,
        paper_pass_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return Symbol(**base)


def _full_pass_input(**overrides) -> ScreeningInput:
    """Create a ScreeningInput that passes all 5 stages."""
    base = dict(
        symbol="SOL/USDT",
        asset_class=AssetClass.CRYPTO,
        sector=AssetSector.LAYER1,
        market_cap_usd=80_000_000_000,
        listing_age_days=365,
        avg_daily_volume_usd=500_000_000,
        spread_pct=0.05,
        atr_pct=5.0,
        adx=25.0,
        price_vs_200ma=1.2,
        available_bars=1000,
        sharpe_ratio=0.8,
        missing_data_pct=1.0,
    )
    base.update(overrides)
    return ScreeningInput(**base)


# ── Stage 1: Exclusion Filter ────────────────────────────────────────


class TestStage1Exclusion:
    def test_excluded_sector_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(sector=AssetSector.MEME)
        out = sc.screen(inp)
        assert out.resulting_status == SymbolStatus.EXCLUDED
        assert out.stage_reason_code == ScreeningStageReason.EXCLUDED_SECTOR
        assert len(out.stages) == 1  # short-circuits

    def test_all_excluded_sectors_fail(self):
        sc = SymbolScreener()
        for sector in EXCLUDED_SECTORS:
            inp = _full_pass_input(sector=sector)
            out = sc.screen(inp)
            assert out.resulting_status == SymbolStatus.EXCLUDED, (
                f"Sector {sector.value} should produce EXCLUDED"
            )

    def test_low_market_cap_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(market_cap_usd=10_000_000)  # $10M < $50M
        out = sc.screen(inp)
        assert out.resulting_status == SymbolStatus.EXCLUDED
        assert out.stage_reason_code == ScreeningStageReason.LOW_MARKET_CAP

    def test_recent_listing_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(listing_age_days=30)  # 30 < 180 days
        out = sc.screen(inp)
        assert out.resulting_status == SymbolStatus.EXCLUDED
        assert out.stage_reason_code == ScreeningStageReason.RECENT_LISTING

    def test_allowed_sector_passes(self):
        sc = SymbolScreener()
        inp = _full_pass_input(sector=AssetSector.LAYER1)
        out = sc.screen(inp)
        assert out.stages[0].passed is True

    def test_no_market_cap_passes(self):
        """None market_cap = no data, stage 1 passes (not excluded by cap)."""
        sc = SymbolScreener()
        inp = _full_pass_input(market_cap_usd=None)
        out = sc.screen(inp)
        assert out.stages[0].passed is True


# ── Stage 2: Liquidity ───────────────────────────────────────────────


class TestStage2Liquidity:
    def test_low_volume_crypto_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(avg_daily_volume_usd=1_000_000)  # $1M < $10M
        out = sc.screen(inp)
        assert not out.stages[1].passed
        assert out.stage_reason_code == ScreeningStageReason.LOW_VOLUME

    def test_low_volume_us_stock_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(
            asset_class=AssetClass.US_STOCK,
            sector=AssetSector.TECH,
            avg_daily_volume_usd=1_000_000,  # $1M < $5M
        )
        out = sc.screen(inp)
        assert not out.stages[1].passed

    def test_low_volume_kr_stock_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(
            asset_class=AssetClass.KR_STOCK,
            sector=AssetSector.SEMICONDUCTOR,
            avg_daily_volume_usd=100_000_000,  # ₩1억 < ₩5억
        )
        out = sc.screen(inp)
        assert not out.stages[1].passed

    def test_missing_volume_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(avg_daily_volume_usd=None)
        out = sc.screen(inp)
        assert not out.stages[1].passed

    def test_wide_spread_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(spread_pct=1.5)  # 1.5% > 0.5%
        out = sc.screen(inp)
        assert not out.stages[1].passed
        assert out.stage_reason_code == ScreeningStageReason.WIDE_SPREAD

    def test_good_volume_passes(self):
        sc = SymbolScreener()
        inp = _full_pass_input(avg_daily_volume_usd=50_000_000)
        out = sc.screen(inp)
        assert out.stages[1].passed


# ── Stage 3: Technical Structure ─────────────────────────────────────


class TestStage3Technical:
    def test_low_atr_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(atr_pct=0.3)  # 0.3% < 1%
        out = sc.screen(inp)
        assert not out.stages[2].passed
        assert out.stage_reason_code == ScreeningStageReason.LOW_ATR

    def test_high_atr_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(atr_pct=25.0)  # 25% > 20%
        out = sc.screen(inp)
        assert not out.stages[2].passed
        assert out.stage_reason_code == ScreeningStageReason.HIGH_ATR

    def test_low_adx_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(adx=10.0)  # 10 < 15
        out = sc.screen(inp)
        assert not out.stages[2].passed
        assert out.stage_reason_code == ScreeningStageReason.LOW_ADX

    def test_missing_atr_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(atr_pct=None)
        out = sc.screen(inp)
        assert not out.stages[2].passed

    def test_missing_adx_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(adx=None)
        out = sc.screen(inp)
        assert not out.stages[2].passed

    def test_good_technical_passes(self):
        sc = SymbolScreener()
        inp = _full_pass_input(atr_pct=5.0, adx=25.0)
        out = sc.screen(inp)
        assert out.stages[2].passed


# ── Stage 4: Fundamental / On-chain ──────────────────────────────────


class TestStage4Fundamental:
    def test_high_per_stock_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(
            asset_class=AssetClass.US_STOCK,
            sector=AssetSector.TECH,
            per=150.0,  # > 100
        )
        out = sc.screen(inp)
        assert not out.stages[3].passed
        assert out.stage_reason_code == ScreeningStageReason.HIGH_PER

    def test_low_roe_stock_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(
            asset_class=AssetClass.US_STOCK,
            sector=AssetSector.TECH,
            per=20.0,
            roe=2.0,  # < 5%
        )
        out = sc.screen(inp)
        assert not out.stages[3].passed
        assert out.stage_reason_code == ScreeningStageReason.LOW_ROE

    def test_low_tvl_defi_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(
            sector=AssetSector.DEFI,
            tvl_usd=1_000_000,  # $1M < $10M
        )
        out = sc.screen(inp)
        assert not out.stages[3].passed
        assert out.stage_reason_code == ScreeningStageReason.LOW_TVL

    def test_crypto_non_defi_passes(self):
        """Non-DeFi crypto gets placeholder pass on stage 4."""
        sc = SymbolScreener()
        inp = _full_pass_input(sector=AssetSector.LAYER1)
        out = sc.screen(inp)
        assert out.stages[3].passed

    def test_stock_no_data_passes(self):
        """Stocks with no fundamental data still pass (placeholder)."""
        sc = SymbolScreener()
        inp = _full_pass_input(
            asset_class=AssetClass.US_STOCK,
            sector=AssetSector.TECH,
            per=None,
            roe=None,
        )
        out = sc.screen(inp)
        assert out.stages[3].passed


# ── Stage 5: Backtest Qualification ──────────────────────────────────


class TestStage5Backtest:
    def test_insufficient_bars_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(available_bars=200)  # < 500
        out = sc.screen(inp)
        assert not out.stages[4].passed
        assert out.stage_reason_code == ScreeningStageReason.INSUFFICIENT_BARS

    def test_negative_sharpe_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(sharpe_ratio=-0.5)
        out = sc.screen(inp)
        assert not out.stages[4].passed
        assert out.stage_reason_code == ScreeningStageReason.NEGATIVE_SHARPE

    def test_high_missing_data_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(missing_data_pct=10.0)  # > 5%
        out = sc.screen(inp)
        assert not out.stages[4].passed
        assert out.stage_reason_code == ScreeningStageReason.HIGH_MISSING_DATA

    def test_missing_bars_fails(self):
        sc = SymbolScreener()
        inp = _full_pass_input(available_bars=None)
        out = sc.screen(inp)
        assert not out.stages[4].passed

    def test_good_backtest_passes(self):
        sc = SymbolScreener()
        inp = _full_pass_input(available_bars=1000, sharpe_ratio=0.5, missing_data_pct=2.0)
        out = sc.screen(inp)
        assert out.stages[4].passed


# ── Aggregate / Full Pass ────────────────────────────────────────────


class TestAggregateResults:
    def test_all_pass_produces_core(self):
        sc = SymbolScreener()
        inp = _full_pass_input()
        out = sc.screen(inp)
        assert out.all_passed is True
        assert out.resulting_status == SymbolStatus.CORE
        assert out.status_reason_code == SymbolStatusReason.SCREENING_FULL_PASS
        assert out.stage_reason_code == ScreeningStageReason.ALL_STAGES_PASSED
        assert out.score == 1.0
        assert out.candidate_ttl_hours == 48

    def test_partial_fail_produces_watch(self):
        sc = SymbolScreener()
        inp = _full_pass_input(adx=5.0)  # stage 3 fail
        out = sc.screen(inp)
        assert out.all_passed is False
        assert out.resulting_status == SymbolStatus.WATCH
        assert out.status_reason_code == SymbolStatusReason.SCREENING_PARTIAL_PASS

    def test_exclusion_fail_produces_excluded(self):
        sc = SymbolScreener()
        inp = _full_pass_input(sector=AssetSector.MEME)
        out = sc.screen(inp)
        assert out.resulting_status == SymbolStatus.EXCLUDED
        assert out.status_reason_code == SymbolStatusReason.EXCLUSION_BASELINE

    def test_score_calculation(self):
        """Score = passed_stages / total_stages."""
        sc = SymbolScreener()
        # Make stage 3 and 5 fail
        inp = _full_pass_input(atr_pct=0.1, available_bars=10)
        out = sc.screen(inp)
        # stages 1,2,4 pass; 3,5 fail → 3/5 = 0.6
        assert out.score == pytest.approx(0.6)

    def test_exclusion_short_circuits(self):
        """Stage 1 fail should short-circuit — only 1 stage in output."""
        sc = SymbolScreener()
        inp = _full_pass_input(sector=AssetSector.GAMEFI)
        out = sc.screen(inp)
        assert len(out.stages) == 1

    def test_five_stages_on_non_exclusion(self):
        sc = SymbolScreener()
        inp = _full_pass_input()
        out = sc.screen(inp)
        assert len(out.stages) == 5


# ── Custom Thresholds ────────────────────────────────────────────────


class TestCustomThresholds:
    def test_relaxed_volume_passes(self):
        t = ScreeningThresholds(min_avg_daily_volume_crypto=1_000_000)
        sc = SymbolScreener(thresholds=t)
        inp = _full_pass_input(avg_daily_volume_usd=2_000_000)
        out = sc.screen(inp)
        assert out.stages[1].passed

    def test_strict_adx_fails(self):
        t = ScreeningThresholds(min_adx=30.0)
        sc = SymbolScreener(thresholds=t)
        inp = _full_pass_input(adx=25.0)
        out = sc.screen(inp)
        assert not out.stages[2].passed

    def test_custom_ttl(self):
        t = ScreeningThresholds(candidate_ttl_hours=24)
        sc = SymbolScreener(thresholds=t)
        inp = _full_pass_input()
        out = sc.screen(inp)
        assert out.candidate_ttl_hours == 24


# ── Symbol Canonicalization ──────────────────────────────────────────


class TestCanonicalization:
    def test_crypto_uppercase(self):
        assert canonicalize_symbol("sol/usdt", AssetClass.CRYPTO) == "SOL/USDT"

    def test_crypto_strip_whitespace(self):
        assert canonicalize_symbol("  BTC/USDT  ", AssetClass.CRYPTO) == "BTC/USDT"

    def test_us_stock_uppercase(self):
        assert canonicalize_symbol("aapl", AssetClass.US_STOCK) == "AAPL"

    def test_us_stock_strip_exchange_prefix(self):
        assert canonicalize_symbol("NASDAQ:NVDA", AssetClass.US_STOCK) == "NVDA"

    def test_kr_stock_zero_pad(self):
        assert canonicalize_symbol("5930", AssetClass.KR_STOCK) == "005930"

    def test_kr_stock_already_6_digits(self):
        assert canonicalize_symbol("005930", AssetClass.KR_STOCK) == "005930"

    def test_kr_stock_strip_non_digit(self):
        assert canonicalize_symbol("KRX:035420", AssetClass.KR_STOCK) == "035420"


# ── AssetService Integration ────────────────────────────────────────


class TestScreenAndUpdate:
    @pytest.mark.asyncio
    async def test_full_pass_sets_core(self):
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.WATCH)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input()
        out = await svc.screen_and_update("sym-001", inp)

        assert out.all_passed is True
        assert sym.status == SymbolStatus.CORE
        assert sym.screening_score == 1.0
        assert sym.candidate_expire_at is not None

    @pytest.mark.asyncio
    async def test_partial_fail_sets_watch(self):
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input(adx=5.0)  # stage 3 fail
        out = await svc.screen_and_update("sym-001", inp)

        assert out.all_passed is False
        assert sym.status == SymbolStatus.WATCH
        assert sym.candidate_expire_at is None

    @pytest.mark.asyncio
    async def test_excluded_sector_stays_excluded(self):
        """Even if screening somehow passes, excluded-sector symbol stays EXCLUDED."""
        db = _mock_db()
        sym = _make_symbol(
            sector=AssetSector.MEME,
            status=SymbolStatus.EXCLUDED,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input(sector=AssetSector.MEME)
        out = await svc.screen_and_update("sym-001", inp)

        # Screener says EXCLUDED, service enforces EXCLUDED
        assert sym.status == SymbolStatus.EXCLUDED

    @pytest.mark.asyncio
    async def test_screening_result_recorded(self):
        """screen_and_update must call record_screening (append-only)."""
        db = _mock_db()
        sym = _make_symbol()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input()
        await svc.screen_and_update("sym-001", inp)

        # db.add should have been called for the ScreeningResult
        assert db.add.called

    @pytest.mark.asyncio
    async def test_candidate_ttl_set_on_core(self):
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.WATCH)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        inp = _full_pass_input()
        await svc.screen_and_update("sym-001", inp)

        assert sym.candidate_expire_at is not None
        # TTL should be ~48h from now
        delta = sym.candidate_expire_at - datetime.now(timezone.utc)
        assert timedelta(hours=47) < delta < timedelta(hours=49)

    @pytest.mark.asyncio
    async def test_nonexistent_symbol_raises(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        svc = AssetService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.screen_and_update("bad-id", _full_pass_input())


# ── Screening History (append-only) ─────────────────────────────────


class TestScreeningHistory:
    @pytest.mark.asyncio
    async def test_screening_is_append_only(self):
        """Multiple screenings should create separate records."""
        db = _mock_db()
        svc = AssetService(db)

        await svc.record_screening(
            {
                "symbol_id": "sym-001",
                "symbol": "SOL/USDT",
                "all_passed": False,
                "resulting_status": SymbolStatus.WATCH,
            }
        )
        await svc.record_screening(
            {
                "symbol_id": "sym-001",
                "symbol": "SOL/USDT",
                "all_passed": True,
                "resulting_status": SymbolStatus.CORE,
            }
        )

        # db.add called twice (once per screening)
        assert db.add.call_count == 2


# ── Reason Code Consistency ──────────────────────────────────────────


class TestReasonCodeConsistency:
    def test_all_stage_reasons_are_enum_members(self):
        """Every reason code used by the screener is a valid enum member."""
        sc = SymbolScreener()

        # Test each stage failure path
        failures = [
            _full_pass_input(sector=AssetSector.MEME),
            _full_pass_input(market_cap_usd=1_000),
            _full_pass_input(listing_age_days=1),
            _full_pass_input(avg_daily_volume_usd=1),
            _full_pass_input(spread_pct=5.0),
            _full_pass_input(atr_pct=0.01),
            _full_pass_input(atr_pct=99.0),
            _full_pass_input(adx=1.0),
            _full_pass_input(
                asset_class=AssetClass.US_STOCK,
                sector=AssetSector.TECH,
                per=999.0,
            ),
            _full_pass_input(available_bars=1),
            _full_pass_input(sharpe_ratio=-1.0),
            _full_pass_input(missing_data_pct=99.0),
        ]
        for inp in failures:
            out = sc.screen(inp)
            if out.stage_reason_code is not None:
                assert isinstance(out.stage_reason_code, ScreeningStageReason), (
                    f"Unexpected reason type: {out.stage_reason_code}"
                )

    def test_full_pass_reason_code(self):
        sc = SymbolScreener()
        out = sc.screen(_full_pass_input())
        assert out.stage_reason_code == ScreeningStageReason.ALL_STAGES_PASSED


# ── Constitution Alignment ───────────────────────────────────────────


class TestConstitutionAlignment:
    def test_excluded_can_never_become_core(self):
        """Constitution rule: EXCLUDED symbols cannot enter CORE."""
        sc = SymbolScreener()
        for sector in EXCLUDED_SECTORS:
            inp = _full_pass_input(sector=sector)
            out = sc.screen(inp)
            assert out.resulting_status != SymbolStatus.CORE

    def test_five_stages_structure(self):
        """Screener must have exactly 5 stages per constitution."""
        sc = SymbolScreener()
        out = sc.screen(_full_pass_input())
        assert len(out.stages) == 5
        for i, s in enumerate(out.stages, 1):
            assert s.stage == i

    def test_candidate_ttl_default_48h(self):
        """Constitution A-4: TTL = 24-48h. Default = 48h."""
        t = ScreeningThresholds()
        assert t.candidate_ttl_hours == 48

    def test_min_bars_500(self):
        """Constitution: 500bars+ for backtest qualification."""
        t = ScreeningThresholds()
        assert t.min_bars == 500

    def test_max_missing_data_5pct(self):
        """Constitution: missing data < 5%."""
        t = ScreeningThresholds()
        assert t.max_missing_data_pct == 5.0

    def test_adx_threshold_15(self):
        """Constitution: ADX > 15."""
        t = ScreeningThresholds()
        assert t.min_adx == 15.0

    def test_atr_range_1_to_20(self):
        """Constitution: ATR 1-20%."""
        t = ScreeningThresholds()
        assert t.min_atr_pct == 1.0
        assert t.max_atr_pct == 20.0


# ── Override Audit Fields ────────────────────────────────────────────


class TestOverrideAudit:
    def test_symbol_has_override_audit_fields(self):
        sym = _make_symbol()
        assert hasattr(sym, "override_by")
        assert hasattr(sym, "override_reason")
        assert hasattr(sym, "override_at")

    def test_override_fields_default_none(self):
        sym = _make_symbol()
        assert sym.override_by is None
        assert sym.override_reason is None
        assert sym.override_at is None

    def test_override_fields_set(self):
        now = datetime.now(timezone.utc)
        sym = _make_symbol(
            manual_override=True,
            override_by="admin@example.com",
            override_reason="Emergency re-evaluation needed",
            override_at=now,
        )
        assert sym.manual_override is True
        assert sym.override_by == "admin@example.com"
        assert sym.override_reason == "Emergency re-evaluation needed"
        assert sym.override_at == now


# ── ScreeningResult stage_reason_code ────────────────────────────────


class TestScreeningStageReasonCode:
    def test_screening_result_has_stage_reason_code(self):
        sr = ScreeningResult(
            symbol_id="sym-001",
            symbol="SOL/USDT",
            stage_reason_code="low_volume",
            resulting_status=SymbolStatus.WATCH,
        )
        assert sr.stage_reason_code == "low_volume"

    def test_screening_result_stage_reason_none(self):
        sr = ScreeningResult(
            symbol_id="sym-001",
            symbol="SOL/USDT",
            resulting_status=SymbolStatus.CORE,
        )
        assert sr.stage_reason_code is None
