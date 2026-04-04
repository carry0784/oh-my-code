"""Tests for Phase 5A+5B: Runtime Strategy Loader, Strategy Router,
Feature Cache, Bundle Fingerprint, Integrity Hardening.

All tests use mocked DB sessions (no infrastructure dependency).
"""

from __future__ import annotations

import json
import importlib.util
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.asset import (
    AssetClass,
    AssetSector,
    AssetTheme,
    SymbolStatus,
    Symbol,
)
from app.models.strategy_registry import Strategy, PromotionStatus
from app.models.feature_pack import FeaturePack
from app.models.load_decision_receipt import LoadDecisionReceipt
from app.services.runtime_strategy_loader import (
    LoadEligibilityChecker,
    LoadEligibilityOutput,
    LoadDecision,
    LoadRejectReason,
    LoadCheck,
    LOADABLE_STRATEGY_STATUSES,
    LOADABLE_PROMOTION_STATUSES,
)
from app.services.runtime_loader_service import RuntimeLoaderService
from app.services.strategy_router import StrategyRouter, RoutingResult
from app.services.feature_cache import (
    FeatureCache,
    FeatureCacheKey,
    FeatureCacheEntry,
    FeatureCacheStats,
)
from app.services.bundle_fingerprint import (
    canonical_json,
    sha256_hex,
    compute_strategy_fingerprint,
    compute_feature_pack_fingerprint,
    compute_load_fingerprint,
    fingerprint_from_strategy,
    fingerprint_from_feature_pack,
)
from app.schemas.runtime_loader_schema import (
    LoadDecisionReceiptRead,
    RoutingResultRead,
    FeatureCacheStatsRead,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_symbol(**overrides):
    defaults = dict(
        id="sym-001",
        symbol="SOL/USDT",
        name="Solana",
        asset_class=AssetClass.CRYPTO,
        sector=AssetSector.LAYER1,
        theme=AssetTheme.L1_SCALING,
        exchanges='["BINANCE"]',
        market_cap_usd=50_000_000_000,
        avg_daily_volume=1_000_000_000,
        status=SymbolStatus.CORE,
        screening_score=0.9,
        qualification_status="pass",
        promotion_eligibility_status="paper_pass",
        paper_evaluation_status="pass",
        regime_allow=None,
        candidate_expire_at=None,
        paper_allowed=True,
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
    defaults.update(overrides)
    sym = MagicMock(spec=Symbol)
    for k, v in defaults.items():
        setattr(sym, k, v)
    return sym


def _make_strategy(**overrides):
    defaults = dict(
        id="strat-001",
        name="smc_wavetrend",
        version="1.0.0",
        description=None,
        feature_pack_id="fp-001",
        compute_module="strategies.smc_wavetrend",
        checksum="abc123",
        asset_classes='["crypto"]',
        exchanges='["BINANCE"]',
        sectors='["layer1", "defi"]',
        timeframes='["1h", "4h"]',
        regimes=None,
        max_symbols=20,
        status=PromotionStatus.PAPER_PASS,
        promoted_at=None,
        promoted_by=None,
        is_champion=False,
        champion_since=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    strat = MagicMock(spec=Strategy)
    for k, v in defaults.items():
        setattr(strat, k, v)
    return strat


def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


# ═══════════════════════════════════════════════════════════════════════
# PART 1: Load Eligibility Checker (stateless engine)
# ═══════════════════════════════════════════════════════════════════════


class TestLoadCheck1ScreeningStatus:
    def test_core_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert out.decision == LoadDecision.APPROVED
        c1 = [c for c in out.checks if c.check_name == "screening_status_core"][0]
        assert c1.passed

    def test_watch_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="watch",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert out.decision == LoadDecision.REJECTED
        assert "screening_status_core" in out.failed_checks

    def test_excluded_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="excluded",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert out.decision == LoadDecision.REJECTED
        assert out.primary_reason == LoadRejectReason.SCREENING_NOT_CORE


class TestLoadCheck2QualificationStatus:
    def test_pass_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c2 = [c for c in out.checks if c.check_name == "qualification_status_pass"][0]
        assert c2.passed

    def test_unchecked_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="unchecked",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "qualification_status_pass" in out.failed_checks

    def test_fail_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="fail",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "qualification_status_pass" in out.failed_checks


class TestLoadCheck3PromotionEligibility:
    def test_paper_pass_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c3 = [c for c in out.checks if c.check_name == "promotion_eligible"][0]
        assert c3.passed

    def test_eligible_for_paper_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="eligible_for_paper",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c3 = [c for c in out.checks if c.check_name == "promotion_eligible"][0]
        assert c3.passed

    def test_unchecked_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="unchecked",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "promotion_eligible" in out.failed_checks

    def test_paper_hold_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_hold",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "promotion_eligible" in out.failed_checks


class TestLoadCheck4PaperEvaluation:
    def test_pass_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c4 = [c for c in out.checks if c.check_name == "paper_evaluation_pass"][0]
        assert c4.passed

    def test_pending_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pending",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "paper_evaluation_pass" in out.failed_checks

    def test_fail_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="fail",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "paper_evaluation_pass" in out.failed_checks


class TestLoadCheck5StrategyStatus:
    def test_paper_pass_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c5 = [c for c in out.checks if c.check_name == "strategy_status_loadable"][0]
        assert c5.passed

    def test_guarded_live_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="GUARDED_LIVE",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c5 = [c for c in out.checks if c.check_name == "strategy_status_loadable"][0]
        assert c5.passed

    def test_live_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="LIVE",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c5 = [c for c in out.checks if c.check_name == "strategy_status_loadable"][0]
        assert c5.passed

    def test_draft_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="DRAFT",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "strategy_status_loadable" in out.failed_checks

    def test_registered_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="REGISTERED",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "strategy_status_loadable" in out.failed_checks


class TestLoadCheck6Checksum:
    def test_matching_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc123",
            checksum_actual="abc123",
            safe_mode_active=False,
            drift_active=False,
        )
        c6 = [c for c in out.checks if c.check_name == "checksum_match"][0]
        assert c6.passed

    def test_mismatch_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc123",
            checksum_actual="xyz789",
            safe_mode_active=False,
            drift_active=False,
        )
        assert "checksum_match" in out.failed_checks
        assert out.primary_reason == LoadRejectReason.CHECKSUM_MISMATCH

    def test_none_passes(self):
        """No checksum to verify = pass."""
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c6 = [c for c in out.checks if c.check_name == "checksum_match"][0]
        assert c6.passed


class TestLoadCheck7SafeMode:
    def test_normal_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c7 = [c for c in out.checks if c.check_name == "safe_mode_normal"][0]
        assert c7.passed

    def test_active_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=True,
            drift_active=False,
        )
        assert "safe_mode_normal" in out.failed_checks


class TestLoadCheck8Drift:
    def test_no_drift_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c8 = [c for c in out.checks if c.check_name == "no_drift"][0]
        assert c8.passed

    def test_drift_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=True,
        )
        assert "no_drift" in out.failed_checks


class TestLoadCheck9Freshness:
    def test_fresh_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
            paper_pass_fresh=True,
        )
        c9 = [c for c in out.checks if c.check_name == "paper_pass_fresh"][0]
        assert c9.passed

    def test_stale_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
            paper_pass_fresh=False,
        )
        assert "paper_pass_fresh" in out.failed_checks
        assert LoadRejectReason.PAPER_PASS_STALE in [c.reason for c in out.checks if not c.passed]


class TestAggregateLoadEligibility:
    def test_all_pass_produces_approved(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert out.decision == LoadDecision.APPROVED
        assert len(out.failed_checks) == 0
        assert out.primary_reason is None

    def test_any_fail_produces_rejected(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="watch",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert out.decision == LoadDecision.REJECTED
        assert len(out.failed_checks) > 0

    def test_ten_checks_always(self):
        """All 10 checks run regardless of failures."""
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="excluded",
            qualification_status="fail",
            promotion_eligibility_status="unchecked",
            paper_evaluation_status="pending",
            strategy_status="DRAFT",
            checksum_expected="a",
            checksum_actual="b",
            fp_fingerprint_expected="x",
            fp_fingerprint_actual="y",
            safe_mode_active=True,
            drift_active=True,
            paper_pass_fresh=False,
        )
        assert len(out.checks) == 10
        assert len(out.failed_checks) == 10

    def test_status_snapshot_populated(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert out.status_snapshot is not None
        assert out.status_snapshot["screening_status"] == "core"
        assert out.status_snapshot["paper_evaluation_status"] == "pass"

    def test_multiple_failures_all_recorded(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="watch",
            qualification_status="fail",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected=None,
            checksum_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        assert "screening_status_core" in out.failed_checks
        assert "qualification_status_pass" in out.failed_checks
        assert len(out.failed_checks) == 2


class TestLoadableStatusSets:
    def test_loadable_strategy_statuses(self):
        assert "PAPER_PASS" in LOADABLE_STRATEGY_STATUSES
        assert "GUARDED_LIVE" in LOADABLE_STRATEGY_STATUSES
        assert "LIVE" in LOADABLE_STRATEGY_STATUSES
        assert "DRAFT" not in LOADABLE_STRATEGY_STATUSES
        assert "REGISTERED" not in LOADABLE_STRATEGY_STATUSES

    def test_loadable_promotion_statuses(self):
        assert "eligible_for_paper" in LOADABLE_PROMOTION_STATUSES
        assert "paper_pass" in LOADABLE_PROMOTION_STATUSES
        assert "unchecked" not in LOADABLE_PROMOTION_STATUSES


class TestLoadDecisionEnums:
    def test_load_decision_values(self):
        assert LoadDecision.APPROVED.value == "approved"
        assert LoadDecision.REJECTED.value == "rejected"

    def test_load_reject_reason_count(self):
        assert len(LoadRejectReason) == 13


# ═══════════════════════════════════════════════════════════════════════
# PART 2: Runtime Loader Service (DB integration)
# ═══════════════════════════════════════════════════════════════════════


class TestLoaderServiceInternalState:
    @pytest.mark.asyncio
    async def test_safe_mode_normal_returns_false(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        svc = RuntimeLoaderService(db)
        assert await svc.is_safe_mode_active() is False

    @pytest.mark.asyncio
    async def test_safe_mode_active_returns_true(self):
        db = _mock_db()
        mock_status = MagicMock()
        from app.models.safe_mode import SafeModeState

        mock_status.current_state = SafeModeState.SM3_RECOVERY_ONLY
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_status
        db.execute = AsyncMock(return_value=mock_result)

        svc = RuntimeLoaderService(db)
        assert await svc.is_safe_mode_active() is True

    @pytest.mark.asyncio
    async def test_drift_none_returns_false(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)

        svc = RuntimeLoaderService(db)
        assert await svc.has_unprocessed_drift() is False

    @pytest.mark.asyncio
    async def test_drift_some_returns_true(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        db.execute = AsyncMock(return_value=mock_result)

        svc = RuntimeLoaderService(db)
        assert await svc.has_unprocessed_drift() is True


def _make_feature_pack(**overrides):
    defaults = dict(
        id="fp-001",
        name="trend_pack_v1",
        version="1.0.0",
        indicator_ids='["ind-001", "ind-002"]',
        weights='{"ind-001": 1.0, "ind-002": 0.5}',
        checksum=None,  # will be set to actual fingerprint in tests
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    fp = MagicMock(spec=FeaturePack)
    for k, v in defaults.items():
        setattr(fp, k, v)
    return fp


class TestLoaderServiceEvaluateAndRecord:
    """Service tests — now with 5 DB calls: symbol, strategy, FP, safe_mode, drift."""

    @pytest.mark.asyncio
    async def test_approved_records_receipt(self):
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        fp = _make_feature_pack()
        # Set strategy checksum to match computed fingerprint
        strat.checksum = fingerprint_from_strategy(strat)
        fp.checksum = fingerprint_from_feature_pack(fp)

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp  # feature pack
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None  # safe mode
            elif call_count == 5:
                mock.scalar_one.return_value = 0  # no drift
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "approved"
        assert receipt.primary_reason is None
        assert receipt.strategy_id == "strat-001"
        assert receipt.strategy_fingerprint is not None
        assert receipt.fp_fingerprint is not None

    @pytest.mark.asyncio
    async def test_rejected_records_reason(self):
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.WATCH)
        strat = _make_strategy()
        fp = _make_feature_pack()
        strat.checksum = fingerprint_from_strategy(strat)
        fp.checksum = fingerprint_from_feature_pack(fp)

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None
            elif call_count == 5:
                mock.scalar_one.return_value = 0
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "rejected"
        assert receipt.primary_reason == "screening_not_core"

    @pytest.mark.asyncio
    async def test_symbol_not_found(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "missing", "1h")
        assert receipt.decision == "rejected"
        assert receipt.primary_reason == "symbol_not_found"

    @pytest.mark.asyncio
    async def test_strategy_not_found(self):
        db = _mock_db()
        sym = _make_symbol()

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            else:
                mock.scalar_one_or_none.return_value = None
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("missing", "sym-001", "1h")
        assert receipt.decision == "rejected"
        assert receipt.primary_reason == "strategy_not_found"

    @pytest.mark.asyncio
    async def test_safe_mode_rejects(self):
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        fp = _make_feature_pack()
        strat.checksum = fingerprint_from_strategy(strat)
        fp.checksum = fingerprint_from_feature_pack(fp)

        from app.models.safe_mode import SafeModeState

        mock_sm = MagicMock()
        mock_sm.current_state = SafeModeState.SM2_EXIT_ONLY

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = mock_sm
            elif call_count == 5:
                mock.scalar_one.return_value = 0
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "rejected"
        assert "safe_mode_active" in (receipt.primary_reason or "")

    @pytest.mark.asyncio
    async def test_drift_rejects(self):
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        fp = _make_feature_pack()
        strat.checksum = fingerprint_from_strategy(strat)
        fp.checksum = fingerprint_from_feature_pack(fp)

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None  # safe mode normal
            elif call_count == 5:
                mock.scalar_one.return_value = 2  # drift!
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "rejected"
        failed = json.loads(receipt.failed_checks) if receipt.failed_checks else []
        assert "no_drift" in failed


# ═══════════════════════════════════════════════════════════════════════
# PART 3: Strategy Router (stateless engine)
# ═══════════════════════════════════════════════════════════════════════


class TestRoutingAssetClass:
    def test_matching_asset_class_passes(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert result.routable is True

    def test_mismatched_asset_class_fails(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["us_stock"],
            strategy_exchanges=["KIS_US"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert result.routable is False
        assert "asset_class_match" in result.failed_checks


class TestRoutingExchange:
    def test_matching_exchange_passes(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE", "UPBIT"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert result.routable is True

    def test_no_exchange_overlap_fails(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["UPBIT"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert "exchange_match" in result.failed_checks


class TestRoutingSector:
    def test_matching_sector_passes(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=["layer1", "defi"],
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert result.routable is True

    def test_no_sector_constraint_passes_any(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert result.routable is True

    def test_mismatched_sector_fails(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=["defi"],
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert "sector_match" in result.failed_checks


class TestRoutingTimeframe:
    def test_matching_timeframe_passes(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h", "4h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="4h",
        )
        assert result.routable is True

    def test_mismatched_timeframe_fails(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="4h",
        )
        assert "timeframe_match" in result.failed_checks


class TestRoutingMaxSymbols:
    def test_within_cap_passes(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=5,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
            current_symbol_count=4,
        )
        assert result.routable is True

    def test_at_cap_fails(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=5,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
            current_symbol_count=5,
        )
        assert "max_symbols_cap" in result.failed_checks


class TestFindEligibleStrategies:
    def test_finds_matching_strategies(self):
        router = StrategyRouter()
        strategies = [
            {
                "id": "s1",
                "asset_classes": ["crypto"],
                "exchanges": ["BINANCE"],
                "sectors": ["layer1"],
                "timeframes": ["1h"],
                "max_symbols": 20,
            },
            {
                "id": "s2",
                "asset_classes": ["us_stock"],
                "exchanges": ["KIS_US"],
                "sectors": None,
                "timeframes": ["1h"],
                "max_symbols": 20,
            },
        ]
        results = router.find_eligible_strategies(
            strategies=strategies,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert len(results) == 2
        assert results[0].routable is True
        assert results[1].routable is False

    def test_five_checks_always(self):
        router = StrategyRouter()
        result = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert len(result.checks) == 5


# ═══════════════════════════════════════════════════════════════════════
# PART 4: Feature Cache
# ═══════════════════════════════════════════════════════════════════════


class TestFeatureCachePutGet:
    def test_put_and_get(self):
        cache = FeatureCache()
        key = FeatureCacheKey("SOL/USDT", "1h", "2026-04-01T00:00:00Z")
        cache.put(key, {"rsi": 65.0, "adx": 28.0})
        result = cache.get(key)
        assert result is not None
        assert result["rsi"] == 65.0
        assert result["adx"] == 28.0

    def test_miss_returns_none(self):
        cache = FeatureCache()
        key = FeatureCacheKey("SOL/USDT", "1h", "2026-04-01T00:00:00Z")
        assert cache.get(key) is None

    def test_different_keys_independent(self):
        cache = FeatureCache()
        k1 = FeatureCacheKey("SOL/USDT", "1h", "2026-04-01T00:00:00Z")
        k2 = FeatureCacheKey("BTC/USDT", "1h", "2026-04-01T00:00:00Z")
        cache.put(k1, {"rsi": 65.0})
        cache.put(k2, {"rsi": 42.0})
        assert cache.get(k1)["rsi"] == 65.0
        assert cache.get(k2)["rsi"] == 42.0


class TestFeatureCacheTTL:
    def test_expired_entry_returns_none(self):
        cache = FeatureCache(default_ttl_seconds=1)
        key = FeatureCacheKey("SOL/USDT", "1h", "2026-04-01T00:00:00Z")
        cache.put(key, {"rsi": 65.0})
        # Force expiry
        entry = cache._store[key]
        entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        assert cache.get(key) is None

    def test_zero_ttl_never_expires(self):
        cache = FeatureCache(default_ttl_seconds=0)
        key = FeatureCacheKey("SOL/USDT", "1h", "2026-04-01T00:00:00Z")
        cache.put(key, {"rsi": 65.0})
        assert cache.get(key) is not None


class TestFeatureCacheInvalidation:
    def test_invalidate_symbol_timeframe(self):
        cache = FeatureCache()
        k1 = FeatureCacheKey("SOL/USDT", "1h", "bar1")
        k2 = FeatureCacheKey("SOL/USDT", "1h", "bar2")
        k3 = FeatureCacheKey("SOL/USDT", "4h", "bar1")
        cache.put(k1, {"a": 1})
        cache.put(k2, {"a": 2})
        cache.put(k3, {"a": 3})
        removed = cache.invalidate("SOL/USDT", "1h")
        assert removed == 2
        assert cache.get(k1) is None
        assert cache.get(k2) is None
        assert cache.get(k3) is not None

    def test_invalidate_symbol_all_timeframes(self):
        cache = FeatureCache()
        k1 = FeatureCacheKey("SOL/USDT", "1h", "bar1")
        k2 = FeatureCacheKey("SOL/USDT", "4h", "bar1")
        k3 = FeatureCacheKey("BTC/USDT", "1h", "bar1")
        cache.put(k1, {"a": 1})
        cache.put(k2, {"a": 2})
        cache.put(k3, {"a": 3})
        removed = cache.invalidate_symbol("SOL/USDT")
        assert removed == 2
        assert cache.get(k3) is not None

    def test_clear(self):
        cache = FeatureCache()
        for i in range(5):
            cache.put(FeatureCacheKey(f"SYM{i}", "1h", "bar1"), {"x": i})
        removed = cache.clear()
        assert removed == 5
        assert cache.size() == 0


class TestFeatureCacheStats:
    def test_hit_miss_tracking(self):
        cache = FeatureCache()
        key = FeatureCacheKey("SOL/USDT", "1h", "bar1")
        cache.get(key)  # miss
        cache.put(key, {"rsi": 65})
        cache.get(key)  # hit
        cache.get(key)  # hit
        stats = cache.stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2 / 3

    def test_eviction_tracking(self):
        cache = FeatureCache(default_ttl_seconds=1)
        key = FeatureCacheKey("SOL/USDT", "1h", "bar1")
        cache.put(key, {"rsi": 65})
        cache._store[key].expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        cache.get(key)  # triggers eviction
        stats = cache.stats()
        assert stats.evictions == 1

    def test_invalidation_tracking(self):
        cache = FeatureCache()
        cache.put(FeatureCacheKey("SOL/USDT", "1h", "b1"), {"x": 1})
        cache.put(FeatureCacheKey("SOL/USDT", "1h", "b2"), {"x": 2})
        cache.invalidate("SOL/USDT", "1h")
        stats = cache.stats()
        assert stats.invalidations == 2

    def test_empty_cache_hit_rate(self):
        cache = FeatureCache()
        stats = cache.stats()
        assert stats.hit_rate == 0.0


# ═══════════════════════════════════════════════════════════════════════
# PART 5: Models and Schemas
# ═══════════════════════════════════════════════════════════════════════


class TestLoadDecisionReceiptModel:
    def test_creation(self):
        receipt = LoadDecisionReceipt(
            strategy_id="strat-001",
            symbol_id="sym-001",
            timeframe="1h",
            decision="approved",
            primary_reason=None,
            failed_checks=None,
            status_snapshot='{"screening_status": "core"}',
            decided_at=datetime.now(timezone.utc),
        )
        assert receipt.strategy_id == "strat-001"
        assert receipt.decision == "approved"

    def test_rejected_with_reason(self):
        receipt = LoadDecisionReceipt(
            strategy_id="strat-001",
            symbol_id="sym-001",
            timeframe="1h",
            decision="rejected",
            primary_reason="screening_not_core",
            failed_checks='["screening_status_core"]',
            status_snapshot=None,
            decided_at=datetime.now(timezone.utc),
        )
        assert receipt.decision == "rejected"
        assert receipt.primary_reason == "screening_not_core"


class TestPhase5ASchemas:
    def test_load_decision_receipt_read(self):
        data = {
            "id": "r-001",
            "strategy_id": "strat-001",
            "symbol_id": "sym-001",
            "timeframe": "1h",
            "decision": "approved",
            "primary_reason": None,
            "failed_checks": None,
            "status_snapshot": None,
            "decided_at": datetime.now(timezone.utc),
        }
        schema = LoadDecisionReceiptRead(**data)
        assert schema.decision == "approved"

    def test_routing_result_read(self):
        data = {
            "strategy_id": "s1",
            "symbol": "SOL/USDT",
            "timeframe": "1h",
            "routable": True,
            "checks": [{"check_name": "asset_class_match", "passed": True}],
            "failed_checks": [],
        }
        schema = RoutingResultRead(**data)
        assert schema.routable is True
        assert len(schema.checks) == 1

    def test_feature_cache_stats_read(self):
        data = {
            "hits": 10,
            "misses": 5,
            "evictions": 1,
            "invalidations": 2,
            "current_size": 100,
            "hit_rate": 0.667,
        }
        schema = FeatureCacheStatsRead(**data)
        assert schema.hit_rate == 0.667


# ═══════════════════════════════════════════════════════════════════════
# PART 6: Migration Structure
# ═══════════════════════════════════════════════════════════════════════


class TestMigrationStructure:
    def test_migration_012_revision_chain(self):
        spec = importlib.util.spec_from_file_location(
            "m012",
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "alembic",
                "versions",
                "012_runtime_loader_tables.py",
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "012_runtime_loader"
        assert mod.down_revision == "011_paper_evaluation"

    def test_migration_012_has_upgrade_downgrade(self):
        spec = importlib.util.spec_from_file_location(
            "m012",
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "alembic",
                "versions",
                "012_runtime_loader_tables.py",
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


# ═══════════════════════════════════════════════════════════════════════
# PART 7: Integration — Load + Route combined
# ═══════════════════════════════════════════════════════════════════════


class TestLoadAndRouteCombined:
    def test_approved_load_then_route_check(self):
        """If load eligibility passes, routing can run separately."""
        chk = LoadEligibilityChecker()
        load_out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert load_out.decision == LoadDecision.APPROVED

        router = StrategyRouter()
        route_out = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=["layer1"],
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert route_out.routable is True

    def test_rejected_load_blocks_routing(self):
        """If load eligibility fails, routing is moot."""
        chk = LoadEligibilityChecker()
        load_out = chk.check(
            screening_status="watch",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            safe_mode_active=False,
            drift_active=False,
        )
        assert load_out.decision == LoadDecision.REJECTED
        # Routing check would pass but load gate prevents execution
        router = StrategyRouter()
        route_out = router.route(
            strategy_id="s1",
            strategy_asset_classes=["crypto"],
            strategy_exchanges=["BINANCE"],
            strategy_sectors=None,
            strategy_timeframes=["1h"],
            strategy_max_symbols=20,
            symbol="SOL/USDT",
            symbol_asset_class="crypto",
            symbol_exchanges=["BINANCE"],
            symbol_sector="layer1",
            timeframe="1h",
        )
        assert route_out.routable is True  # routing ok, but load was rejected


# ═══════════════════════════════════════════════════════════════════════
# PART 8: Phase 5B — Bundle Fingerprint Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCanonicalJson:
    def test_deterministic_key_order(self):
        d1 = {"b": 2, "a": 1, "c": 3}
        d2 = {"c": 3, "a": 1, "b": 2}
        assert canonical_json(d1) == canonical_json(d2)

    def test_no_whitespace(self):
        result = canonical_json({"a": 1, "b": 2})
        assert " " not in result
        assert result == '{"a":1,"b":2}'

    def test_sorted_nested(self):
        d = {"z": {"b": 2, "a": 1}, "a": 0}
        result = canonical_json(d)
        assert result == '{"a":0,"z":{"a":1,"b":2}}'

    def test_unicode_stability(self):
        d = {"name": "한국주식"}
        result = canonical_json(d)
        assert "한국주식" in result  # ensure_ascii=False


class TestSha256Hex:
    def test_known_hash(self):
        import hashlib

        expected = hashlib.sha256(b"hello").hexdigest()
        assert sha256_hex("hello") == expected

    def test_empty_string(self):
        result = sha256_hex("")
        assert len(result) == 64  # SHA-256 hex digest length

    def test_different_inputs_different_hashes(self):
        assert sha256_hex("a") != sha256_hex("b")


class TestStrategyFingerprint:
    def test_deterministic(self):
        fp1 = compute_strategy_fingerprint(
            compute_module="strategies.smc",
            version="1.0.0",
            asset_classes='["crypto"]',
            exchanges='["BINANCE"]',
            sectors='["layer1"]',
            timeframes='["1h"]',
            max_symbols=20,
        )
        fp2 = compute_strategy_fingerprint(
            compute_module="strategies.smc",
            version="1.0.0",
            asset_classes='["crypto"]',
            exchanges='["BINANCE"]',
            sectors='["layer1"]',
            timeframes='["1h"]',
            max_symbols=20,
        )
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_list_order_invariant(self):
        """Sorted lists should produce same fingerprint regardless of input order."""
        fp1 = compute_strategy_fingerprint(
            compute_module="mod",
            version="1.0",
            asset_classes=["crypto", "us_stock"],
            exchanges=["BINANCE", "KIS_US"],
            sectors=["layer1", "defi"],
            timeframes=["1h", "4h"],
            max_symbols=10,
        )
        fp2 = compute_strategy_fingerprint(
            compute_module="mod",
            version="1.0",
            asset_classes=["us_stock", "crypto"],
            exchanges=["KIS_US", "BINANCE"],
            sectors=["defi", "layer1"],
            timeframes=["4h", "1h"],
            max_symbols=10,
        )
        assert fp1 == fp2

    def test_json_string_and_list_equivalent(self):
        """JSON-encoded string and native list produce same fingerprint."""
        fp1 = compute_strategy_fingerprint(
            compute_module="mod",
            version="1.0",
            asset_classes='["crypto"]',
            exchanges='["BINANCE"]',
            sectors='["layer1"]',
            timeframes='["1h"]',
            max_symbols=5,
        )
        fp2 = compute_strategy_fingerprint(
            compute_module="mod",
            version="1.0",
            asset_classes=["crypto"],
            exchanges=["BINANCE"],
            sectors=["layer1"],
            timeframes=["1h"],
            max_symbols=5,
        )
        assert fp1 == fp2

    def test_version_change_changes_fingerprint(self):
        fp1 = compute_strategy_fingerprint(
            compute_module="mod",
            version="1.0.0",
            asset_classes=["crypto"],
            exchanges=["BINANCE"],
            sectors=None,
            timeframes=["1h"],
            max_symbols=20,
        )
        fp2 = compute_strategy_fingerprint(
            compute_module="mod",
            version="1.0.1",
            asset_classes=["crypto"],
            exchanges=["BINANCE"],
            sectors=None,
            timeframes=["1h"],
            max_symbols=20,
        )
        assert fp1 != fp2

    def test_from_model_convenience(self):
        strat = _make_strategy()
        fp = fingerprint_from_strategy(strat)
        assert len(fp) == 64
        # Must be deterministic
        assert fp == fingerprint_from_strategy(strat)


class TestFeaturePackFingerprint:
    def test_deterministic(self):
        fp1 = compute_feature_pack_fingerprint(
            name="trend_pack",
            version="1.0",
            indicator_ids='["ind-001", "ind-002"]',
            weights='{"ind-001": 1.0, "ind-002": 0.5}',
        )
        fp2 = compute_feature_pack_fingerprint(
            name="trend_pack",
            version="1.0",
            indicator_ids='["ind-001", "ind-002"]',
            weights='{"ind-001": 1.0, "ind-002": 0.5}',
        )
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_indicator_order_invariant(self):
        fp1 = compute_feature_pack_fingerprint(
            name="pack",
            version="1.0",
            indicator_ids=["ind-002", "ind-001"],
            weights=None,
        )
        fp2 = compute_feature_pack_fingerprint(
            name="pack",
            version="1.0",
            indicator_ids=["ind-001", "ind-002"],
            weights=None,
        )
        assert fp1 == fp2

    def test_weight_change_changes_fingerprint(self):
        fp1 = compute_feature_pack_fingerprint(
            name="pack",
            version="1.0",
            indicator_ids=["ind-001"],
            weights={"ind-001": 1.0},
        )
        fp2 = compute_feature_pack_fingerprint(
            name="pack",
            version="1.0",
            indicator_ids=["ind-001"],
            weights={"ind-001": 0.5},
        )
        assert fp1 != fp2

    def test_from_model_convenience(self):
        fp_model = _make_feature_pack()
        fp = fingerprint_from_feature_pack(fp_model)
        assert len(fp) == 64
        assert fp == fingerprint_from_feature_pack(fp_model)


class TestCombinedLoadFingerprint:
    def test_combined_deterministic(self):
        lf1 = compute_load_fingerprint("strat_fp_aaa", "fp_fp_bbb")
        lf2 = compute_load_fingerprint("strat_fp_aaa", "fp_fp_bbb")
        assert lf1 == lf2

    def test_either_change_changes_combined(self):
        base = compute_load_fingerprint("aaa", "bbb")
        changed_strat = compute_load_fingerprint("xxx", "bbb")
        changed_fp = compute_load_fingerprint("aaa", "xxx")
        assert base != changed_strat
        assert base != changed_fp


# ═══════════════════════════════════════════════════════════════════════
# PART 9: Phase 5B — Feature Pack Mismatch in Load Eligibility
# ═══════════════════════════════════════════════════════════════════════


class TestLoadCheck6bFeaturePackMatch:
    def test_matching_fp_passes(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            fp_fingerprint_expected="fp123",
            fp_fingerprint_actual="fp123",
            safe_mode_active=False,
            drift_active=False,
        )
        c6b = [c for c in out.checks if c.check_name == "feature_pack_match"][0]
        assert c6b.passed

    def test_mismatched_fp_fails(self):
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            fp_fingerprint_expected="fp123",
            fp_fingerprint_actual="fp999",
            safe_mode_active=False,
            drift_active=False,
        )
        assert "feature_pack_match" in out.failed_checks
        c6b = [c for c in out.checks if c.check_name == "feature_pack_match"][0]
        assert c6b.reason == LoadRejectReason.FEATURE_PACK_MISMATCH

    def test_none_fp_passes(self):
        """No FP fingerprint to verify = pass (backwards compat)."""
        chk = LoadEligibilityChecker()
        out = chk.check(
            screening_status="core",
            qualification_status="pass",
            promotion_eligibility_status="paper_pass",
            paper_evaluation_status="pass",
            strategy_status="PAPER_PASS",
            checksum_expected="abc",
            checksum_actual="abc",
            fp_fingerprint_expected=None,
            fp_fingerprint_actual=None,
            safe_mode_active=False,
            drift_active=False,
        )
        c6b = [c for c in out.checks if c.check_name == "feature_pack_match"][0]
        assert c6b.passed


class TestServiceFpMismatchRejects:
    """Feature pack fingerprint mismatch at service level → rejected."""

    @pytest.mark.asyncio
    async def test_fp_checksum_mismatch_rejects(self):
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        fp = _make_feature_pack()
        strat.checksum = fingerprint_from_strategy(strat)
        fp.checksum = "wrong_stored_checksum"  # mismatch!

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None
            elif call_count == 5:
                mock.scalar_one.return_value = 0
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "rejected"
        failed = json.loads(receipt.failed_checks) if receipt.failed_checks else []
        assert "feature_pack_match" in failed

    @pytest.mark.asyncio
    async def test_fp_not_found_still_approves(self):
        """If feature pack is not found, FP fingerprint check passes (None/None)."""
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        strat.checksum = fingerprint_from_strategy(strat)

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = None  # FP not found
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None  # safe mode
            elif call_count == 5:
                mock.scalar_one.return_value = 0
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "approved"


# ═══════════════════════════════════════════════════════════════════════
# PART 10: Phase 5B — Strategy Checksum with Real Fingerprints
# ═══════════════════════════════════════════════════════════════════════


class TestServiceRealChecksumMismatch:
    """Strategy stored checksum != computed fingerprint → rejected."""

    @pytest.mark.asyncio
    async def test_strategy_checksum_mismatch_rejects(self):
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        fp = _make_feature_pack()
        strat.checksum = "stale_old_checksum"  # doesn't match computed
        fp.checksum = fingerprint_from_feature_pack(fp)

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None
            elif call_count == 5:
                mock.scalar_one.return_value = 0
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.decision == "rejected"
        failed = json.loads(receipt.failed_checks) if receipt.failed_checks else []
        assert "checksum_match" in failed

    @pytest.mark.asyncio
    async def test_real_fingerprint_recorded_on_receipt(self):
        """Receipt must record the actual computed fingerprints."""
        db = _mock_db()
        sym = _make_symbol()
        strat = _make_strategy()
        fp = _make_feature_pack()
        strat.checksum = fingerprint_from_strategy(strat)
        fp.checksum = fingerprint_from_feature_pack(fp)

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 2:
                mock.scalar_one_or_none.return_value = strat
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = fp
            elif call_count == 4:
                mock.scalar_one_or_none.return_value = None
            elif call_count == 5:
                mock.scalar_one.return_value = 0
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = RuntimeLoaderService(db)
        receipt = await svc.evaluate_and_record("strat-001", "sym-001", "1h")
        assert receipt.strategy_fingerprint == fingerprint_from_strategy(strat)
        assert receipt.fp_fingerprint == fingerprint_from_feature_pack(fp)


# ═══════════════════════════════════════════════════════════════════════
# PART 11: Phase 5B — Freshness with paper_pass_at
# ═══════════════════════════════════════════════════════════════════════


class TestFreshnessWithPaperPassAt:
    def test_recent_paper_pass_at_is_fresh(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(
            paper_evaluation_status="pass",
            paper_pass_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert svc._check_paper_pass_freshness(sym, 14) is True

    def test_stale_paper_pass_at_is_stale(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(
            paper_evaluation_status="pass",
            paper_pass_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        assert svc._check_paper_pass_freshness(sym, 14) is False

    def test_no_paper_pass_at_falls_back_to_updated_at(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(
            paper_evaluation_status="pass",
            paper_pass_at=None,
            updated_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert svc._check_paper_pass_freshness(sym, 14) is True

    def test_no_paper_pass_at_and_stale_updated_at(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(
            paper_evaluation_status="pass",
            paper_pass_at=None,
            updated_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        assert svc._check_paper_pass_freshness(sym, 14) is False

    def test_non_pass_status_always_fresh(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(paper_evaluation_status="pending", paper_pass_at=None)
        assert svc._check_paper_pass_freshness(sym, 14) is True

    def test_zero_ttl_disables_check(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(
            paper_evaluation_status="pass",
            paper_pass_at=datetime.now(timezone.utc) - timedelta(days=999),
        )
        assert svc._check_paper_pass_freshness(sym, 0) is True

    def test_no_timestamp_at_all_is_stale(self):
        svc = RuntimeLoaderService.__new__(RuntimeLoaderService)
        sym = _make_symbol(
            paper_evaluation_status="pass",
            paper_pass_at=None,
            updated_at=None,
        )
        assert svc._check_paper_pass_freshness(sym, 14) is False


# ═══════════════════════════════════════════════════════════════════════
# PART 12: Phase 5B — Cache Revision Token
# ═══════════════════════════════════════════════════════════════════════


class TestCacheRevisionToken:
    def test_revision_token_in_key(self):
        k1 = FeatureCacheKey("SOL/USDT", "1h", "bar1", revision_token="v1")
        k2 = FeatureCacheKey("SOL/USDT", "1h", "bar1", revision_token="v2")
        assert k1 != k2  # different revision tokens = different keys

    def test_invalidate_revision_removes_matching(self):
        cache = FeatureCache()
        k1 = FeatureCacheKey("SOL/USDT", "1h", "bar1", revision_token="old_fp")
        k2 = FeatureCacheKey("BTC/USDT", "1h", "bar1", revision_token="old_fp")
        k3 = FeatureCacheKey("SOL/USDT", "1h", "bar1", revision_token="new_fp")
        cache.put(k1, {"rsi": 65})
        cache.put(k2, {"rsi": 42})
        cache.put(k3, {"rsi": 70})
        removed = cache.invalidate_revision("old_fp")
        assert removed == 2
        assert cache.get(k1) is None
        assert cache.get(k2) is None
        assert cache.get(k3) is not None

    def test_invalidate_revision_no_match(self):
        cache = FeatureCache()
        k1 = FeatureCacheKey("SOL/USDT", "1h", "bar1", revision_token="v1")
        cache.put(k1, {"rsi": 65})
        removed = cache.invalidate_revision("nonexistent")
        assert removed == 0
        assert cache.get(k1) is not None

    def test_invalidation_stats_tracked(self):
        cache = FeatureCache()
        cache.put(FeatureCacheKey("A", "1h", "b1", revision_token="old"), {"x": 1})
        cache.put(FeatureCacheKey("B", "1h", "b1", revision_token="old"), {"x": 2})
        cache.invalidate_revision("old")
        stats = cache.stats()
        assert stats.invalidations == 2
        assert stats.current_size == 0


# ═══════════════════════════════════════════════════════════════════════
# PART 13: Phase 5B — Migration 013 + Receipt Fingerprints + Schema
# ═══════════════════════════════════════════════════════════════════════


class TestMigration013IntegrityHardening:
    def test_revision_chain(self):
        spec = importlib.util.spec_from_file_location(
            "m013",
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "alembic",
                "versions",
                "013_integrity_hardening.py",
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "013_integrity_hardening"
        assert mod.down_revision == "012_runtime_loader"

    def test_has_upgrade_downgrade(self):
        spec = importlib.util.spec_from_file_location(
            "m013",
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "alembic",
                "versions",
                "013_integrity_hardening.py",
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


class TestReceiptFingerprintFields:
    def test_receipt_stores_strategy_fingerprint(self):
        receipt = LoadDecisionReceipt(
            strategy_id="strat-001",
            symbol_id="sym-001",
            timeframe="1h",
            decision="approved",
            strategy_fingerprint="abc123def456",
            fp_fingerprint="xyz789",
            decided_at=datetime.now(timezone.utc),
        )
        assert receipt.strategy_fingerprint == "abc123def456"
        assert receipt.fp_fingerprint == "xyz789"

    def test_receipt_fingerprints_nullable(self):
        receipt = LoadDecisionReceipt(
            strategy_id="strat-001",
            symbol_id="sym-001",
            timeframe="1h",
            decision="rejected",
            decided_at=datetime.now(timezone.utc),
        )
        assert receipt.strategy_fingerprint is None
        assert receipt.fp_fingerprint is None


class TestPhase5BSchemas:
    def test_receipt_read_with_fingerprints(self):
        data = {
            "id": "r-002",
            "strategy_id": "strat-001",
            "symbol_id": "sym-001",
            "timeframe": "1h",
            "decision": "approved",
            "primary_reason": None,
            "failed_checks": None,
            "status_snapshot": None,
            "strategy_fingerprint": "abc123",
            "fp_fingerprint": "xyz789",
            "decided_at": datetime.now(timezone.utc),
        }
        schema = LoadDecisionReceiptRead(**data)
        assert schema.strategy_fingerprint == "abc123"
        assert schema.fp_fingerprint == "xyz789"

    def test_receipt_read_fingerprints_optional(self):
        data = {
            "id": "r-003",
            "strategy_id": "strat-001",
            "symbol_id": "sym-001",
            "timeframe": "1h",
            "decision": "rejected",
            "primary_reason": "screening_not_core",
            "failed_checks": None,
            "status_snapshot": None,
            "decided_at": datetime.now(timezone.utc),
        }
        schema = LoadDecisionReceiptRead(**data)
        assert schema.strategy_fingerprint is None
        assert schema.fp_fingerprint is None
