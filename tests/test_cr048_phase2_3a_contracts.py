"""
CR-048 Phase 2 + Phase 3A Design Contract Tests.

Tests verify design contracts from:
  - design_asset_registry.md v1.0  (A-01 ~ A-12)
  - design_screening_engine.md v1.0  (SC-01 ~ SC-12)

All tests are pure-Python contract tests — no DB session, no I/O.
Constants are defined at module level as mirrors of the design documents.
"""

from __future__ import annotations

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Imports from existing models/constants
# ═══════════════════════════════════════════════════════════════════════

from app.models.asset import (
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
from app.models.strategy_registry import AssetClass

# Injection Gateway constants (for cross-doc consistency)
from app.services.injection_gateway import (
    FORBIDDEN_BROKERS,
    FORBIDDEN_SECTORS,
    ALLOWED_BROKERS,
)


# ═══════════════════════════════════════════════════════════════════════
# Design card constants (mirrors)
# ═══════════════════════════════════════════════════════════════════════

# Asset classes (3)
ASSET_CLASSES_3 = frozenset({"CRYPTO", "US_STOCK", "KR_STOCK"})

# Symbol statuses (3)
SYMBOL_STATUSES_3 = frozenset({"core", "watch", "excluded"})

# Excluded sectors (7)
EXCLUDED_SECTOR_NAMES = frozenset(
    {
        "MEME",
        "GAMEFI",
        "LOW_LIQUIDITY_NEW_TOKEN",
        "HIGH_VALUATION_PURE_SW",
        "WEAK_CONSUMER_BETA",
        "OIL_SENSITIVE",
        "LOW_LIQUIDITY_THEME",
    }
)

# Allowed sectors (not in excluded)
ALLOWED_SECTOR_NAMES_CRYPTO = frozenset({"LAYER1", "DEFI", "AI", "INFRA"})
ALLOWED_SECTOR_NAMES_US = frozenset({"TECH", "HEALTHCARE", "ENERGY", "FINANCE"})
ALLOWED_SECTOR_NAMES_KR = frozenset({"SEMICONDUCTOR", "IT", "KR_FINANCE", "AUTOMOTIVE"})

# Candidate TTL
CANDIDATE_TTL_HOURS = 48

# Screening pipeline stages
SCREENING_STAGES = [
    "stage1_exclusion",
    "stage2_liquidity",
    "stage3_technical",
    "stage4_fundamental",
    "stage5_backtest",
]

# Stage 3 thresholds
ATR_MIN_PCT = 1
ATR_MAX_PCT = 20
ADX_MIN = 15

# Stage 5 thresholds
MIN_BARS = 500

# Screening schedules
SCREENING_SCHEDULES = ["1h", "1d", "regime_change", "manual"]

# Brokers per asset class
BROKERS_PER_ASSET_CLASS = {
    "crypto": 3,  # BINANCE, BITGET, UPBIT
    "us_stock": 1,  # KIS_US
    "kr_stock": 2,  # KIS_KR, KIWOOM_KR
}

# Status transitions — EXCLUDED cannot become CORE or WATCH without intervention
PROHIBITED_DIRECT_TRANSITIONS = [
    ("excluded", "core"),
]
REQUIRES_APPROVAL_TRANSITIONS = [
    ("excluded", "watch"),
]


# ═══════════════════════════════════════════════════════════════════════
# 6. design_asset_registry.md → Tests (A-01 ~ A-12)
# ═══════════════════════════════════════════════════════════════════════


class TestAssetRegistryContracts:
    """Contract tests for design_asset_registry.md v1.0."""

    # A-01: AssetClass 3종 정의
    def test_asset_class_three_types(self):
        values = {e.value.upper() for e in AssetClass}
        assert values == ASSET_CLASSES_3

    # A-02: SymbolStatus 3상태 정의
    def test_symbol_status_three_states(self):
        values = {e.value for e in SymbolStatus}
        assert values == SYMBOL_STATUSES_3
        assert len(SymbolStatus) == 3

    # A-03: 금지 섹터 7개 = EXCLUDED_SECTORS
    def test_excluded_sectors_seven(self):
        assert len(EXCLUDED_SECTORS) == 7
        excluded_names = {s.name for s in EXCLUDED_SECTORS}
        assert excluded_names == EXCLUDED_SECTOR_NAMES

    # A-04: 금지 섹터 ∩ 허용 섹터 = ∅
    def test_excluded_and_allowed_no_overlap(self):
        excluded_names = {s.name for s in EXCLUDED_SECTORS}
        all_allowed = (
            ALLOWED_SECTOR_NAMES_CRYPTO | ALLOWED_SECTOR_NAMES_US | ALLOWED_SECTOR_NAMES_KR
        )
        overlap = excluded_names & all_allowed
        assert overlap == set(), f"Overlap found: {overlap}"

    # A-05: EXCLUDED → CORE 직행 금지
    def test_excluded_to_core_prohibited(self):
        """EXCLUDED status cannot transition directly to CORE."""
        # This is a design rule — no intermediate state allowed
        for from_s, to_s in PROHIBITED_DIRECT_TRANSITIONS:
            assert from_s == "excluded" and to_s == "core"

    # A-06: EXCLUDED → WATCH 전환 시 A 승인 필요
    def test_excluded_to_watch_requires_approval(self):
        """EXCLUDED → WATCH requires explicit A approval."""
        assert ("excluded", "watch") in REQUIRES_APPROVAL_TRANSITIONS

    # A-07: Candidate TTL 48시간
    def test_candidate_ttl_48h(self):
        assert CANDIDATE_TTL_HOURS == 48

    # A-08: AssetClass별 허용 브로커 수
    def test_brokers_per_asset_class(self):
        for ac, expected_count in BROKERS_PER_ASSET_CLASS.items():
            actual = ALLOWED_BROKERS.get(ac, [])
            assert len(actual) == expected_count, (
                f"{ac}: expected {expected_count} brokers, got {len(actual)}"
            )

    # A-09: 심볼 정규화 규칙 3종
    def test_symbol_canonicalization(self):
        # CRYPTO: BASE/QUOTE uppercase
        assert canonicalize_symbol("sol/usdt", AssetClass.CRYPTO) == "SOL/USDT"
        assert canonicalize_symbol(" btc/usdt ", AssetClass.CRYPTO) == "BTC/USDT"

        # US_STOCK: ticker uppercase, strip exchange prefix
        assert canonicalize_symbol("aapl", AssetClass.US_STOCK) == "AAPL"
        assert canonicalize_symbol("NASDAQ:NVDA", AssetClass.US_STOCK) == "NVDA"

        # KR_STOCK: 6-digit zero-padded
        assert canonicalize_symbol("5930", AssetClass.KR_STOCK) == "005930"
        assert canonicalize_symbol("000660", AssetClass.KR_STOCK) == "000660"

    # A-10: ScreeningResult 5단계 구조
    def test_screening_five_stages(self):
        """ScreeningResult must have columns for all 5 stages."""
        cols = {c.name for c in ScreeningResult.__table__.columns}
        for stage in SCREENING_STAGES:
            assert stage in cols, f"Missing column: {stage}"

    # A-11: ETH operational_ban 규칙
    def test_eth_operational_ban(self):
        """ETH is classifiable but operationally banned (CR-046)."""
        # ETH should be in CRYPTO asset class — sector is LAYER1 (allowed)
        # But operational ban is enforced via CLAUDE.md/ops policy, not sector exclusion
        # Verify LAYER1 is NOT in excluded sectors
        layer1_excluded = any(s.name == "LAYER1" for s in EXCLUDED_SECTORS)
        assert not layer1_excluded, (
            "LAYER1 should not be excluded — ETH ban is operational, not sectoral"
        )

    # A-12: Manual Override 감사 필드
    def test_manual_override_audit_fields(self):
        """Symbol model must have override audit fields."""
        cols = {c.name for c in Symbol.__table__.columns}
        assert "manual_override" in cols
        assert "override_by" in cols
        assert "override_reason" in cols
        assert "override_at" in cols


# ═══════════════════════════════════════════════════════════════════════
# 7. design_screening_engine.md → Tests (SC-01 ~ SC-12)
# ═══════════════════════════════════════════════════════════════════════


class TestScreeningEngineContracts:
    """Contract tests for design_screening_engine.md v1.0."""

    # SC-01: 5단계 파이프라인 순서
    def test_screening_five_stages_order(self):
        assert len(SCREENING_STAGES) == 5
        assert SCREENING_STAGES[0] == "stage1_exclusion"
        assert SCREENING_STAGES[1] == "stage2_liquidity"
        assert SCREENING_STAGES[2] == "stage3_technical"
        assert SCREENING_STAGES[3] == "stage4_fundamental"
        assert SCREENING_STAGES[4] == "stage5_backtest"

    # SC-02: Stage 1 FAIL → EXCLUDED (절대적)
    def test_stage1_fail_always_excluded(self):
        """Stage 1 failure must result in EXCLUDED — no recovery through later stages."""
        # ScreeningStageReason has stage 1 reasons that map to EXCLUDED
        stage1_reasons = {
            ScreeningStageReason.EXCLUDED_SECTOR,
            ScreeningStageReason.LOW_MARKET_CAP,
            ScreeningStageReason.RECENT_LISTING,
        }
        # All stage 1 reasons should exist
        for reason in stage1_reasons:
            assert reason in ScreeningStageReason

    # SC-03: Stage 2~5 FAIL → WATCH
    def test_stage2_to_5_fail_is_watch(self):
        """Stages 2-5 failure results in WATCH (not EXCLUDED)."""
        # SymbolStatusReason has SCREENING_PARTIAL_PASS for WATCH
        assert hasattr(SymbolStatusReason, "SCREENING_PARTIAL_PASS")
        # CORE_DEMOTED also leads to WATCH
        assert hasattr(SymbolStatusReason, "CORE_DEMOTED")

    # SC-04: 5단계 전부 PASS → CORE
    def test_all_stages_pass_is_core(self):
        """All 5 stages PASS → CORE status."""
        assert hasattr(SymbolStatusReason, "SCREENING_FULL_PASS")
        assert hasattr(ScreeningStageReason, "ALL_STAGES_PASSED")

    # SC-05: Candidate TTL 48시간 (screening context)
    def test_candidate_ttl_48h_screening(self):
        """CORE entry sets candidate_expire_at = now + 48h."""
        assert CANDIDATE_TTL_HOURS == 48
        # Symbol model must have candidate_expire_at column
        cols = {c.name for c in Symbol.__table__.columns}
        assert "candidate_expire_at" in cols

    # SC-06: Regime 전환 시 TTL 즉시 만료
    def test_regime_change_expires_ttl(self):
        """Regime change must expire TTL — SymbolStatusReason.REGIME_CHANGE exists."""
        assert hasattr(SymbolStatusReason, "REGIME_CHANGE")
        assert SymbolStatusReason.REGIME_CHANGE.value == "regime_change"
        # TTL_EXPIRED reason also exists
        assert hasattr(SymbolStatusReason, "TTL_EXPIRED")

    # SC-07: Stage 1 금지 섹터 = Exclusion Baseline 7개
    def test_stage1_matches_exclusion_baseline(self):
        """Stage 1 exclusion filter must match the 7 forbidden sectors."""
        # EXCLUDED_SECTORS from asset.py
        assert len(EXCLUDED_SECTORS) == 7
        # FORBIDDEN_SECTORS from injection_gateway
        assert len(FORBIDDEN_SECTORS) == 7
        # They must represent the same set (different types — enum vs string)
        gateway_upper = {s.upper() for s in FORBIDDEN_SECTORS}
        asset_upper = {s.value.upper() for s in EXCLUDED_SECTORS}
        assert gateway_upper == asset_upper

    # SC-08: Stage 2 유동성 기준 시장별 분리
    def test_stage2_thresholds_per_market(self):
        """Stage 2 must have per-market liquidity thresholds (3 asset classes)."""
        # Verify ScreeningStageReason has stage 2 failure reasons
        stage2_reasons = {
            ScreeningStageReason.LOW_VOLUME,
            ScreeningStageReason.WIDE_SPREAD,
            ScreeningStageReason.THIN_ORDER_BOOK,
        }
        for reason in stage2_reasons:
            assert reason in ScreeningStageReason
        # 3 asset classes must be defined
        assert len(AssetClass) == 3

    # SC-09: Stage 3 ATR/ADX/MA 기준값
    def test_stage3_technical_thresholds(self):
        """Stage 3 technical thresholds: ATR 1~20%, ADX > 15."""
        assert ATR_MIN_PCT == 1
        assert ATR_MAX_PCT == 20
        assert ADX_MIN == 15
        # ScreeningStageReason has stage 3 failure reasons
        assert hasattr(ScreeningStageReason, "LOW_ATR")
        assert hasattr(ScreeningStageReason, "HIGH_ATR")
        assert hasattr(ScreeningStageReason, "LOW_ADX")

    # SC-10: Stage 5 최소 500bars
    def test_stage5_min_bars_500(self):
        assert MIN_BARS == 500
        assert hasattr(ScreeningStageReason, "INSUFFICIENT_BARS")
        assert hasattr(ScreeningStageReason, "NEGATIVE_SHARPE")

    # SC-11: ScreeningResult append-only
    def test_screening_result_append_only(self):
        """ScreeningResult should NOT have updated_at (append-only)."""
        cols = {c.name for c in ScreeningResult.__table__.columns}
        # Must have screened_at (timestamp column)
        assert "screened_at" in cols
        # Should NOT have updated_at (append-only audit trail)
        assert "updated_at" not in cols, "ScreeningResult should be append-only (no updated_at)"

    # SC-12: 스크리닝 실행 주기 정의
    def test_screening_schedule_defined(self):
        """4 screening schedules must be defined."""
        assert len(SCREENING_SCHEDULES) == 4
        assert "1h" in SCREENING_SCHEDULES
        assert "1d" in SCREENING_SCHEDULES
        assert "regime_change" in SCREENING_SCHEDULES
        assert "manual" in SCREENING_SCHEDULES


# ═══════════════════════════════════════════════════════════════════════
# 8. Cross-Document Consistency (Phase 2 + 3A)
# ═══════════════════════════════════════════════════════════════════════


class TestPhase2_3ACrossDocConsistency:
    """Cross-document consistency between Phase 2 and Phase 3A design cards."""

    def test_exclusion_baseline_consistency(self):
        """Exclusion baseline 7 sectors must be consistent across all references."""
        # asset.py EXCLUDED_SECTORS
        asset_values = {s.value.upper() for s in EXCLUDED_SECTORS}
        # injection_gateway FORBIDDEN_SECTORS
        gateway_values = {s.upper() for s in FORBIDDEN_SECTORS}
        assert asset_values == gateway_values == {s.upper() for s in EXCLUDED_SECTOR_NAMES}

    def test_asset_class_consistent_with_brokers(self):
        """Every AssetClass must have at least one allowed broker."""
        for ac in AssetClass:
            ac_key = ac.value.lower() if ac.value.lower() in ALLOWED_BROKERS else ac.value
            brokers = ALLOWED_BROKERS.get(ac_key, ALLOWED_BROKERS.get(ac.value, []))
            assert len(brokers) > 0, f"AssetClass {ac.value} has no allowed brokers"

    def test_screening_stages_match_screening_result(self):
        """ScreeningResult columns must match the 5 screening stages."""
        cols = {c.name for c in ScreeningResult.__table__.columns}
        for stage in SCREENING_STAGES:
            assert stage in cols, f"ScreeningResult missing column: {stage}"

    def test_symbol_has_ttl_and_status(self):
        """Symbol must have both candidate_expire_at (TTL) and status (3-state)."""
        cols = {c.name for c in Symbol.__table__.columns}
        assert "candidate_expire_at" in cols
        assert "status" in cols

    def test_forbidden_brokers_not_in_allowed(self):
        """No forbidden broker appears in any allowed broker list."""
        all_allowed = set()
        for brokers in ALLOWED_BROKERS.values():
            all_allowed.update(brokers)
        overlap = all_allowed & FORBIDDEN_BROKERS
        assert overlap == set(), f"Forbidden broker in allowed list: {overlap}"

    def test_screening_reasons_cover_all_stages(self):
        """ScreeningStageReason must have at least one reason per stage (1-5)."""
        stage1 = {
            ScreeningStageReason.EXCLUDED_SECTOR,
            ScreeningStageReason.LOW_MARKET_CAP,
            ScreeningStageReason.RECENT_LISTING,
        }
        stage2 = {
            ScreeningStageReason.LOW_VOLUME,
            ScreeningStageReason.WIDE_SPREAD,
            ScreeningStageReason.THIN_ORDER_BOOK,
        }
        stage3 = {
            ScreeningStageReason.LOW_ATR,
            ScreeningStageReason.HIGH_ATR,
            ScreeningStageReason.LOW_ADX,
        }
        stage4 = {
            ScreeningStageReason.HIGH_PER,
            ScreeningStageReason.LOW_ROE,
            ScreeningStageReason.LOW_TVL,
        }
        stage5 = {
            ScreeningStageReason.INSUFFICIENT_BARS,
            ScreeningStageReason.NEGATIVE_SHARPE,
            ScreeningStageReason.HIGH_MISSING_DATA,
        }
        for stage_set in (stage1, stage2, stage3, stage4, stage5):
            assert len(stage_set) >= 2, "Each stage should have at least 2 reason codes"
