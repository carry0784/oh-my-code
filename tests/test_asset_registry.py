"""Tests for Phase 2: Asset Registry — enums, models, 3-state rules,
excluded-sector enforcement, service logic, schemas, and screening.

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
    Symbol,
    ScreeningResult,
    EXCLUDED_SECTORS,
)
from app.models.strategy_registry import AssetClass as StrategyAssetClass
from app.schemas.asset_schema import SymbolCreate, SymbolRead, SymbolUpdate, ScreeningResultRead
from app.services.asset_service import AssetService


# ── Helpers ──────────────────────────────────────────────────────────


def _mock_db():
    """Create a mock AsyncSession where flush is async but add is sync."""
    db = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_symbol(**overrides) -> Symbol:
    """Create a Symbol instance with sensible defaults."""
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


# ── Enum Tests ───────────────────────────────────────────────────────


class TestAssetEnums:
    def test_asset_class_values(self):
        assert AssetClass.CRYPTO.value == "CRYPTO"
        assert AssetClass.US_STOCK.value == "US_STOCK"
        assert AssetClass.KR_STOCK.value == "KR_STOCK"
        assert len(AssetClass) == 3

    def test_asset_class_reexport_matches_strategy(self):
        """AssetClass from asset.py is the same as strategy_registry.py."""
        assert AssetClass is StrategyAssetClass

    def test_asset_sector_crypto_allowed(self):
        allowed = {AssetSector.LAYER1, AssetSector.DEFI, AssetSector.AI, AssetSector.INFRA}
        for s in allowed:
            assert s not in EXCLUDED_SECTORS

    def test_asset_sector_crypto_excluded(self):
        excluded = {AssetSector.MEME, AssetSector.GAMEFI, AssetSector.LOW_LIQUIDITY_NEW_TOKEN}
        for s in excluded:
            assert s in EXCLUDED_SECTORS

    def test_asset_sector_us_stock_allowed(self):
        allowed = {
            AssetSector.TECH,
            AssetSector.HEALTHCARE,
            AssetSector.ENERGY,
            AssetSector.FINANCE,
        }
        for s in allowed:
            assert s not in EXCLUDED_SECTORS

    def test_asset_sector_us_stock_excluded(self):
        excluded = {AssetSector.HIGH_VALUATION_PURE_SW, AssetSector.WEAK_CONSUMER_BETA}
        for s in excluded:
            assert s in EXCLUDED_SECTORS

    def test_asset_sector_kr_stock_allowed(self):
        allowed = {
            AssetSector.SEMICONDUCTOR,
            AssetSector.IT,
            AssetSector.KR_FINANCE,
            AssetSector.AUTOMOTIVE,
        }
        for s in allowed:
            assert s not in EXCLUDED_SECTORS

    def test_asset_sector_kr_stock_excluded(self):
        excluded = {AssetSector.OIL_SENSITIVE, AssetSector.LOW_LIQUIDITY_THEME}
        for s in excluded:
            assert s in EXCLUDED_SECTORS

    def test_excluded_sectors_complete(self):
        """Verify completeness: 7 excluded sectors total."""
        expected = {
            AssetSector.MEME,
            AssetSector.GAMEFI,
            AssetSector.LOW_LIQUIDITY_NEW_TOKEN,
            AssetSector.HIGH_VALUATION_PURE_SW,
            AssetSector.WEAK_CONSUMER_BETA,
            AssetSector.OIL_SENSITIVE,
            AssetSector.LOW_LIQUIDITY_THEME,
        }
        assert EXCLUDED_SECTORS == expected

    def test_excluded_sectors_matches_gateway(self):
        """EXCLUDED_SECTORS values must match Injection Gateway FORBIDDEN_SECTORS."""
        from app.services.injection_gateway import FORBIDDEN_SECTORS

        # Gateway uses uppercase string keys; asset model uses enum values
        gateway_values = {s.upper() for s in FORBIDDEN_SECTORS}
        asset_values = {s.value.upper() for s in EXCLUDED_SECTORS}
        assert gateway_values == asset_values

    def test_symbol_status_values(self):
        assert SymbolStatus.CORE.value == "core"
        assert SymbolStatus.WATCH.value == "watch"
        assert SymbolStatus.EXCLUDED.value == "excluded"
        assert len(SymbolStatus) == 3

    def test_asset_theme_values(self):
        assert AssetTheme.NONE.value == "none"
        assert len(AssetTheme) == 8

    def test_status_reason_codes(self):
        assert len(SymbolStatusReason) == 10


# ── Model Tests ──────────────────────────────────────────────────────


class TestSymbolModel:
    def test_symbol_creation(self):
        sym = _make_symbol()
        assert sym.symbol == "SOL/USDT"
        assert sym.asset_class == AssetClass.CRYPTO
        assert sym.sector == AssetSector.LAYER1
        assert sym.status == SymbolStatus.WATCH

    def test_symbol_exchanges_json(self):
        sym = _make_symbol(exchanges=json.dumps(["BINANCE", "BITGET"]))
        exchanges = json.loads(sym.exchanges)
        assert exchanges == ["BINANCE", "BITGET"]

    def test_symbol_regime_allow_json(self):
        sym = _make_symbol(regime_allow=json.dumps(["trending_up", "ranging"]))
        regimes = json.loads(sym.regime_allow)
        assert "trending_up" in regimes
        assert "ranging" in regimes

    def test_excluded_symbol_creation(self):
        sym = _make_symbol(
            symbol="DOGE/USDT",
            sector=AssetSector.MEME,
            status=SymbolStatus.EXCLUDED,
            exclusion_reason="Meme coin",
        )
        assert sym.status == SymbolStatus.EXCLUDED
        assert sym.sector == AssetSector.MEME

    def test_symbol_default_flags(self):
        sym = _make_symbol()
        assert sym.paper_allowed is False
        assert sym.live_allowed is False
        assert sym.manual_override is False

    def test_symbol_candidate_expire(self):
        expire = datetime.now(timezone.utc) + timedelta(hours=48)
        sym = _make_symbol(candidate_expire_at=expire)
        assert sym.candidate_expire_at == expire


class TestScreeningResultModel:
    def test_screening_result_all_pass(self):
        sr = ScreeningResult(
            symbol_id="sym-001",
            symbol="SOL/USDT",
            stage1_exclusion=True,
            stage2_liquidity=True,
            stage3_technical=True,
            stage4_fundamental=True,
            stage5_backtest=True,
            all_passed=True,
            score=0.92,
            resulting_status=SymbolStatus.CORE,
        )
        assert sr.all_passed is True
        assert sr.resulting_status == SymbolStatus.CORE

    def test_screening_result_partial_fail(self):
        sr = ScreeningResult(
            symbol_id="sym-002",
            symbol="ETH/USDT",
            stage1_exclusion=True,
            stage2_liquidity=True,
            stage3_technical=False,
            stage4_fundamental=True,
            stage5_backtest=False,
            all_passed=False,
            score=0.55,
            resulting_status=SymbolStatus.WATCH,
        )
        assert sr.all_passed is False
        assert sr.resulting_status == SymbolStatus.WATCH

    def test_screening_result_excluded(self):
        sr = ScreeningResult(
            symbol_id="sym-003",
            symbol="DOGE/USDT",
            stage1_exclusion=False,  # failed exclusion check
            stage2_liquidity=False,
            stage3_technical=False,
            stage4_fundamental=False,
            stage5_backtest=False,
            all_passed=False,
            score=0.0,
            resulting_status=SymbolStatus.EXCLUDED,
        )
        assert sr.stage1_exclusion is False
        assert sr.resulting_status == SymbolStatus.EXCLUDED


# ── Schema Tests ─────────────────────────────────────────────────────


class TestAssetSchemas:
    def test_symbol_create_valid(self):
        sc = SymbolCreate(
            symbol="SOL/USDT",
            name="Solana",
            asset_class=AssetClass.CRYPTO,
            sector=AssetSector.LAYER1,
            exchanges=["BINANCE"],
        )
        assert sc.symbol == "SOL/USDT"
        assert sc.status == SymbolStatus.WATCH

    def test_symbol_create_defaults(self):
        sc = SymbolCreate(
            symbol="AAPL",
            name="Apple Inc",
            asset_class=AssetClass.US_STOCK,
            sector=AssetSector.TECH,
            exchanges=["KIS_US"],
        )
        assert sc.theme == AssetTheme.NONE
        assert sc.paper_allowed is False
        assert sc.screening_score == 0.0

    def test_symbol_read_from_model(self):
        sym = _make_symbol()
        data = {
            "id": sym.id,
            "symbol": sym.symbol,
            "name": sym.name,
            "asset_class": sym.asset_class,
            "sector": sym.sector,
            "theme": sym.theme,
            "exchanges": json.loads(sym.exchanges),
            "market_cap_usd": sym.market_cap_usd,
            "avg_daily_volume": sym.avg_daily_volume,
            "status": sym.status,
            "status_reason_code": sym.status_reason_code,
            "exclusion_reason": sym.exclusion_reason,
            "screening_score": sym.screening_score,
            "regime_allow": json.loads(sym.regime_allow) if sym.regime_allow else None,
            "candidate_expire_at": sym.candidate_expire_at,
            "paper_allowed": sym.paper_allowed,
            "live_allowed": sym.live_allowed,
            "manual_override": sym.manual_override,
            "override_by": sym.override_by,
            "override_reason": sym.override_reason,
            "override_at": sym.override_at,
            "qualification_status": sym.qualification_status,
            "promotion_eligibility_status": sym.promotion_eligibility_status,
            "paper_evaluation_status": sym.paper_evaluation_status,
            "paper_pass_at": sym.paper_pass_at,
            "broker_policy": sym.broker_policy,
            "created_at": sym.created_at,
            "updated_at": sym.updated_at,
        }
        sr = SymbolRead(**data)
        assert sr.symbol == "SOL/USDT"
        assert sr.asset_class == AssetClass.CRYPTO

    def test_symbol_update_partial(self):
        su = SymbolUpdate(status=SymbolStatus.CORE, screening_score=0.95)
        assert su.status == SymbolStatus.CORE
        assert su.name is None  # not provided

    def test_screening_result_read_schema(self):
        sr = ScreeningResultRead(
            id="sr-001",
            symbol_id="sym-001",
            symbol="SOL/USDT",
            stage1_exclusion=True,
            stage2_liquidity=True,
            stage3_technical=True,
            stage_reason_code=None,
            stage4_fundamental=True,
            stage5_backtest=True,
            all_passed=True,
            score=0.92,
            detail=None,
            resulting_status=SymbolStatus.CORE,
            screened_at=datetime.now(timezone.utc),
        )
        assert sr.all_passed is True


# ── Service Tests ────────────────────────────────────────────────────


class TestAssetServiceRegister:
    @pytest.mark.asyncio
    async def test_register_allowed_sector_watch(self):
        db = _mock_db()
        svc = AssetService(db)
        sym = await svc.register_symbol(
            {
                "symbol": "SOL/USDT",
                "name": "Solana",
                "asset_class": AssetClass.CRYPTO,
                "sector": AssetSector.LAYER1,
                "exchanges": ["BINANCE"],
            }
        )
        assert sym.status == SymbolStatus.WATCH
        assert sym.sector == AssetSector.LAYER1

    @pytest.mark.asyncio
    async def test_register_excluded_sector_forced_excluded(self):
        """Registering a meme-sector symbol must force EXCLUDED status."""
        db = _mock_db()
        svc = AssetService(db)
        sym = await svc.register_symbol(
            {
                "symbol": "DOGE/USDT",
                "name": "Dogecoin",
                "asset_class": AssetClass.CRYPTO,
                "sector": AssetSector.MEME,
                "exchanges": ["BINANCE"],
                "status": SymbolStatus.WATCH.value,  # attempted override
            }
        )
        assert sym.status == SymbolStatus.EXCLUDED
        assert sym.status_reason_code == SymbolStatusReason.EXCLUSION_BASELINE.value
        assert "meme" in sym.exclusion_reason.lower()

    @pytest.mark.asyncio
    async def test_register_gamefi_forced_excluded(self):
        db = _mock_db()
        svc = AssetService(db)
        sym = await svc.register_symbol(
            {
                "symbol": "AXS/USDT",
                "name": "Axie Infinity",
                "asset_class": AssetClass.CRYPTO,
                "sector": AssetSector.GAMEFI,
                "exchanges": ["BINANCE"],
            }
        )
        assert sym.status == SymbolStatus.EXCLUDED

    @pytest.mark.asyncio
    async def test_register_oil_sensitive_forced_excluded(self):
        db = _mock_db()
        svc = AssetService(db)
        sym = await svc.register_symbol(
            {
                "symbol": "010950",
                "name": "S-Oil",
                "asset_class": AssetClass.KR_STOCK,
                "sector": AssetSector.OIL_SENSITIVE,
                "exchanges": ["KIS_KR"],
            }
        )
        assert sym.status == SymbolStatus.EXCLUDED
        assert sym.status_reason_code == SymbolStatusReason.EXCLUSION_BASELINE.value

    @pytest.mark.asyncio
    async def test_register_serializes_exchanges(self):
        db = _mock_db()
        svc = AssetService(db)
        sym = await svc.register_symbol(
            {
                "symbol": "BTC/USDT",
                "name": "Bitcoin",
                "asset_class": AssetClass.CRYPTO,
                "sector": AssetSector.LAYER1,
                "exchanges": ["BINANCE", "BITGET"],
            }
        )
        assert json.loads(sym.exchanges) == ["BINANCE", "BITGET"]

    @pytest.mark.asyncio
    async def test_register_all_excluded_sectors(self):
        """Every excluded sector must force EXCLUDED on registration."""
        db = _mock_db()
        svc = AssetService(db)
        for sector in EXCLUDED_SECTORS:
            sym = await svc.register_symbol(
                {
                    "symbol": f"TEST_{sector.value}",
                    "name": f"Test {sector.value}",
                    "asset_class": AssetClass.CRYPTO,
                    "sector": sector,
                    "exchanges": ["BINANCE"],
                }
            )
            assert sym.status == SymbolStatus.EXCLUDED, (
                f"Sector {sector.value} should force EXCLUDED"
            )


class TestAssetServiceTransition:
    @pytest.mark.asyncio
    async def test_excluded_sector_cannot_leave_excluded(self):
        """Symbol in excluded sector can never transition out of EXCLUDED."""
        db = _mock_db()
        sym = _make_symbol(
            sector=AssetSector.MEME,
            status=SymbolStatus.EXCLUDED,
            manual_override=True,  # even with override
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        with pytest.raises(ValueError, match="exclusion baseline"):
            await svc.transition_status("sym-001", SymbolStatus.CORE, "screening_full_pass")

    @pytest.mark.asyncio
    async def test_excluded_to_core_requires_manual_override(self):
        """EXCLUDED symbol (non-excluded sector) needs manual_override to leave."""
        db = _mock_db()
        sym = _make_symbol(
            sector=AssetSector.LAYER1,
            status=SymbolStatus.EXCLUDED,
            manual_override=False,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        with pytest.raises(ValueError, match="forbidden"):
            await svc.transition_status("sym-001", SymbolStatus.CORE, "screening_full_pass")

    @pytest.mark.asyncio
    async def test_excluded_to_core_with_manual_override_still_forbidden(self):
        """EXCLUDED→CORE is always forbidden, even with manual_override.

        Stage 2B rule: EXCLUDED→CORE direct transition is forbidden.
        The valid path is EXCLUDED→WATCH (with override) → CORE.
        """
        db = _mock_db()
        sym = _make_symbol(
            sector=AssetSector.LAYER1,
            status=SymbolStatus.EXCLUDED,
            manual_override=True,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        with pytest.raises(ValueError, match="forbidden"):
            await svc.transition_status("sym-001", SymbolStatus.CORE, "manual_promotion")

    @pytest.mark.asyncio
    async def test_watch_to_core_normal(self):
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.WATCH)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        result = await svc.transition_status("sym-001", SymbolStatus.CORE, "screening_full_pass")
        assert result.status == SymbolStatus.CORE
        assert result.status_reason_code == "screening_full_pass"

    @pytest.mark.asyncio
    async def test_core_to_watch_demotion(self):
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sym
        db.execute.return_value = mock_result

        svc = AssetService(db)
        result = await svc.transition_status("sym-001", SymbolStatus.WATCH, "core_demoted")
        assert result.status == SymbolStatus.WATCH

    @pytest.mark.asyncio
    async def test_transition_nonexistent_raises(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        svc = AssetService(db)
        with pytest.raises(ValueError, match="not found"):
            await svc.transition_status("bad-id", SymbolStatus.CORE, "test")


class TestAssetServiceScreening:
    @pytest.mark.asyncio
    async def test_record_screening(self):
        db = _mock_db()
        svc = AssetService(db)
        sr = await svc.record_screening(
            {
                "symbol_id": "sym-001",
                "symbol": "SOL/USDT",
                "stage1_exclusion": True,
                "stage2_liquidity": True,
                "stage3_technical": True,
                "stage4_fundamental": True,
                "stage5_backtest": True,
                "all_passed": True,
                "score": 0.92,
                "resulting_status": SymbolStatus.CORE,
            }
        )
        assert sr.all_passed is True
        assert sr.score == 0.92

    @pytest.mark.asyncio
    async def test_record_screening_defaults(self):
        db = _mock_db()
        svc = AssetService(db)
        sr = await svc.record_screening(
            {
                "symbol_id": "sym-002",
                "symbol": "ETH/USDT",
            }
        )
        assert sr.stage1_exclusion is False
        assert sr.all_passed is False
        assert sr.resulting_status == SymbolStatus.WATCH


# ── Constitution Alignment Tests ─────────────────────────────────────


class TestConstitutionAlignment:
    """Verify Phase 2 models align with Phase 0 Constitution."""

    def test_three_states_only(self):
        """Only 3 symbol states: CORE, WATCH, EXCLUDED."""
        assert len(SymbolStatus) == 3
        assert {s.value for s in SymbolStatus} == {"core", "watch", "excluded"}

    def test_excluded_sectors_count(self):
        """7 excluded sectors as defined in exclusion baseline."""
        assert len(EXCLUDED_SECTORS) == 7

    def test_crypto_allowed_sectors_not_excluded(self):
        crypto_allowed = [AssetSector.LAYER1, AssetSector.DEFI, AssetSector.AI, AssetSector.INFRA]
        for s in crypto_allowed:
            assert s not in EXCLUDED_SECTORS

    def test_us_stock_allowed_sectors_not_excluded(self):
        us_allowed = [
            AssetSector.TECH,
            AssetSector.HEALTHCARE,
            AssetSector.ENERGY,
            AssetSector.FINANCE,
        ]
        for s in us_allowed:
            assert s not in EXCLUDED_SECTORS

    def test_kr_stock_allowed_sectors_not_excluded(self):
        kr_allowed = [
            AssetSector.SEMICONDUCTOR,
            AssetSector.IT,
            AssetSector.KR_FINANCE,
            AssetSector.AUTOMOTIVE,
        ]
        for s in kr_allowed:
            assert s not in EXCLUDED_SECTORS

    def test_symbol_has_ttl_field(self):
        """candidate_expire_at required per constitution A-4."""
        sym = _make_symbol()
        assert hasattr(sym, "candidate_expire_at")

    def test_symbol_has_paper_live_flags(self):
        sym = _make_symbol()
        assert hasattr(sym, "paper_allowed")
        assert hasattr(sym, "live_allowed")

    def test_symbol_has_broker_policy(self):
        sym = _make_symbol()
        assert hasattr(sym, "broker_policy")
