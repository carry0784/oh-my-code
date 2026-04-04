"""Tests for Phase 4B: Paper Shadow + Promotion Gate — eligibility engine,
observation model, decision model, service integration, duplicate suppression,
EXCLUDED qualification blocking, and status separation.

All tests use mocked DB sessions (no infrastructure dependency).
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock

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
    QualificationResult,
)
from app.models.paper_shadow import (
    ObservationStatus,
    PromotionEligibility,
    EligibilityBlockReason,
    PaperObservation,
    PromotionDecision,
)
from app.services.promotion_gate import (
    EligibilityInput,
    EligibilityOutput,
    EligibilityCheck,
    PromotionGate,
)
from app.services.paper_shadow_service import PaperShadowService
from app.services.asset_service import AssetService
from app.services.backtest_qualification import (
    QualificationInput,
    BacktestQualifier,
)
from app.schemas.paper_shadow_schema import (
    PaperObservationRead,
    PromotionDecisionRead,
    EligibilityCheckRead,
    EligibilityResultRead,
)
from app.schemas.asset_schema import SymbolRead, QualificationResultRead


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
        qualification_status="pass",
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


def _eligible_input(**overrides) -> EligibilityInput:
    """Create an EligibilityInput that passes all 5 checks."""
    base = dict(
        strategy_id="strat-001",
        symbol="SOL/USDT",
        timeframe="1h",
        screening_status="core",
        qualification_status="pass",
        is_excluded=False,
        safe_mode_active=False,
        drift_active=False,
    )
    base.update(overrides)
    return EligibilityInput(**base)


# ═══════════════════════════════════════════════════════════════════════
# PROMOTION GATE ENGINE TESTS (stateless, no DB)
# ═══════════════════════════════════════════════════════════════════════


class TestCheck1ScreeningStatus:
    def test_core_passes(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(screening_status="core"))
        assert out.checks[0].passed is True

    def test_watch_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(screening_status="watch"))
        assert out.checks[0].passed is False
        assert out.checks[0].reason == EligibilityBlockReason.SCREENING_NOT_CORE

    def test_excluded_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(screening_status="excluded"))
        assert out.checks[0].passed is False


class TestCheck2QualificationStatus:
    def test_pass_passes(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(qualification_status="pass"))
        assert out.checks[1].passed is True

    def test_unchecked_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(qualification_status="unchecked"))
        assert out.checks[1].passed is False
        assert out.checks[1].reason == EligibilityBlockReason.QUALIFICATION_NOT_PASS

    def test_fail_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(qualification_status="fail"))
        assert out.checks[1].passed is False


class TestCheck3NotExcluded:
    def test_not_excluded_passes(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(is_excluded=False))
        assert out.checks[2].passed is True

    def test_excluded_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(is_excluded=True))
        assert out.checks[2].passed is False
        assert out.checks[2].reason == EligibilityBlockReason.SYMBOL_EXCLUDED


class TestCheck4SafeMode:
    def test_normal_passes(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(safe_mode_active=False))
        assert out.checks[3].passed is True

    def test_active_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(safe_mode_active=True))
        assert out.checks[3].passed is False
        assert out.checks[3].reason == EligibilityBlockReason.SAFE_MODE_ACTIVE


class TestCheck5NoDrift:
    def test_no_drift_passes(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(drift_active=False))
        assert out.checks[4].passed is True

    def test_drift_fails(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(drift_active=True))
        assert out.checks[4].passed is False
        assert out.checks[4].reason == EligibilityBlockReason.RUNTIME_DRIFT_ACTIVE


class TestAggregateEligibility:
    def test_all_pass_produces_eligible(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input())
        assert out.all_passed is True
        assert out.decision == PromotionEligibility.ELIGIBLE_FOR_PAPER
        assert out.block_reason is None

    def test_screening_fail_produces_paper_fail(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(screening_status="watch"))
        assert out.all_passed is False
        assert out.decision == PromotionEligibility.PAPER_FAIL
        assert out.block_reason == EligibilityBlockReason.SCREENING_NOT_CORE

    def test_safe_mode_produces_paper_hold(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(safe_mode_active=True))
        assert out.decision == PromotionEligibility.PAPER_HOLD

    def test_drift_produces_quarantine_candidate(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input(drift_active=True))
        assert out.decision == PromotionEligibility.QUARANTINE_CANDIDATE

    def test_five_checks_always(self):
        gate = PromotionGate()
        out = gate.evaluate(_eligible_input())
        assert len(out.checks) == 5

    def test_first_fail_sets_block_reason(self):
        """When multiple checks fail, first failure determines decision."""
        gate = PromotionGate()
        inp = _eligible_input(
            screening_status="watch",
            qualification_status="fail",
        )
        out = gate.evaluate(inp)
        assert out.block_reason == EligibilityBlockReason.SCREENING_NOT_CORE

    def test_multiple_failures_all_recorded(self):
        """All check results are recorded even when some fail."""
        gate = PromotionGate()
        inp = _eligible_input(
            screening_status="watch",
            qualification_status="fail",
            safe_mode_active=True,
        )
        out = gate.evaluate(inp)
        failed = [c for c in out.checks if not c.passed]
        assert len(failed) == 3  # screening, qualification, safe_mode


# ═══════════════════════════════════════════════════════════════════════
# MODEL TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestPaperObservationModel:
    def test_creation(self):
        obs = PaperObservation(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            metrics_snapshot='{"sharpe": 1.2}',
            observation_status=ObservationStatus.RECORDED,
            observed_at=datetime.now(timezone.utc),
        )
        assert obs.strategy_id == "strat-001"
        assert obs.observation_status == ObservationStatus.RECORDED

    def test_observation_status_enum(self):
        assert len(ObservationStatus) == 3
        assert ObservationStatus.RECORDED.value == "recorded"
        assert ObservationStatus.SKIPPED_SAFE_MODE.value == "skipped_safe_mode"
        assert ObservationStatus.SKIPPED_DRIFT.value == "skipped_drift"


class TestPromotionDecisionModel:
    def test_creation(self):
        dec = PromotionDecision(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            decision=PromotionEligibility.ELIGIBLE_FOR_PAPER,
            suppressed=False,
            decided_at=datetime.now(timezone.utc),
        )
        assert dec.decision == PromotionEligibility.ELIGIBLE_FOR_PAPER
        assert dec.suppressed is False

    def test_promotion_eligibility_enum(self):
        assert len(PromotionEligibility) == 6
        assert PromotionEligibility.UNCHECKED.value == "unchecked"
        assert PromotionEligibility.ELIGIBLE_FOR_PAPER.value == "eligible_for_paper"
        assert PromotionEligibility.PAPER_HOLD.value == "paper_hold"
        assert PromotionEligibility.PAPER_PASS.value == "paper_pass"
        assert PromotionEligibility.PAPER_FAIL.value == "paper_fail"
        assert PromotionEligibility.QUARANTINE_CANDIDATE.value == "quarantine_candidate"

    def test_eligibility_block_reason_enum(self):
        assert len(EligibilityBlockReason) == 5
        assert EligibilityBlockReason.SCREENING_NOT_CORE.value == "screening_not_core"
        assert EligibilityBlockReason.QUALIFICATION_NOT_PASS.value == "qualification_not_pass"
        assert EligibilityBlockReason.SYMBOL_EXCLUDED.value == "symbol_excluded"
        assert EligibilityBlockReason.SAFE_MODE_ACTIVE.value == "safe_mode_active"
        assert EligibilityBlockReason.RUNTIME_DRIFT_ACTIVE.value == "runtime_drift_active"


# ═══════════════════════════════════════════════════════════════════════
# SCHEMA TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestPaperShadowSchemas:
    def test_paper_observation_read(self):
        now = datetime.now(timezone.utc)
        data = {
            "id": "obs-001",
            "strategy_id": "strat-001",
            "symbol": "SOL/USDT",
            "timeframe": "1h",
            "metrics_snapshot": '{"sharpe": 1.2}',
            "observation_status": ObservationStatus.RECORDED,
            "source_qualification_result_id": "qr-001",
            "observation_window_fingerprint": None,
            "detail": None,
            "observed_at": now,
        }
        sr = PaperObservationRead(**data)
        assert sr.symbol == "SOL/USDT"
        assert sr.observation_status == ObservationStatus.RECORDED

    def test_promotion_decision_read(self):
        now = datetime.now(timezone.utc)
        data = {
            "id": "dec-001",
            "strategy_id": "strat-001",
            "symbol": "SOL/USDT",
            "timeframe": "1h",
            "decision": PromotionEligibility.ELIGIBLE_FOR_PAPER,
            "previous_decision": None,
            "reason": None,
            "eligibility_checks": None,
            "blocked_checks": None,
            "source_observation_id": None,
            "suppressed": False,
            "decided_by": "system",
            "decided_at": now,
        }
        dr = PromotionDecisionRead(**data)
        assert dr.decision == PromotionEligibility.ELIGIBLE_FOR_PAPER

    def test_eligibility_result_read(self):
        data = {
            "strategy_id": "strat-001",
            "symbol": "SOL/USDT",
            "timeframe": "1h",
            "checks": [
                {"check_name": "screening_status", "passed": True, "reason": None},
            ],
            "all_passed": True,
            "decision": PromotionEligibility.ELIGIBLE_FOR_PAPER,
            "block_reason": None,
        }
        er = EligibilityResultRead(**data)
        assert er.all_passed is True

    def test_symbol_read_has_promotion_eligibility_status(self):
        """SymbolRead schema includes promotion_eligibility_status."""
        fields = SymbolRead.model_fields
        assert "promotion_eligibility_status" in fields

    def test_qualification_result_read_has_failed_checks(self):
        """QualificationResultRead schema includes failed_checks."""
        fields = QualificationResultRead.model_fields
        assert "failed_checks" in fields


# ═══════════════════════════════════════════════════════════════════════
# SERVICE TESTS (mocked DB)
# ═══════════════════════════════════════════════════════════════════════


class TestRecordObservation:
    @pytest.mark.asyncio
    async def test_record_inserts_and_returns(self):
        db = _mock_db()
        svc = PaperShadowService(db)
        obs = await svc.record_observation(
            {
                "strategy_id": "strat-001",
                "symbol": "SOL/USDT",
                "timeframe": "1h",
                "metrics_snapshot": {"sharpe": 1.2, "dd": 10.5},
            }
        )
        assert obs.strategy_id == "strat-001"
        assert obs.observation_status == ObservationStatus.RECORDED
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_with_source_qualification(self):
        db = _mock_db()
        svc = PaperShadowService(db)
        obs = await svc.record_observation(
            {
                "strategy_id": "strat-001",
                "symbol": "SOL/USDT",
                "source_qualification_result_id": "qr-001",
            }
        )
        assert obs.source_qualification_result_id == "qr-001"


class TestEvaluateEligibility:
    @pytest.mark.asyncio
    async def test_core_pass_eligible(self):
        """CORE + PASS → ELIGIBLE_FOR_PAPER."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE, qualification_status="pass")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        out = await svc.evaluate_eligibility(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert out.all_passed is True
        assert out.decision == PromotionEligibility.ELIGIBLE_FOR_PAPER

    @pytest.mark.asyncio
    async def test_watch_pass_ineligible(self):
        """WATCH + PASS → PAPER_FAIL (not paper eligible)."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.WATCH, qualification_status="pass")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        out = await svc.evaluate_eligibility(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert out.all_passed is False
        assert out.decision == PromotionEligibility.PAPER_FAIL

    @pytest.mark.asyncio
    async def test_core_fail_blocked(self):
        """CORE + FAIL → PAPER_FAIL."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE, qualification_status="fail")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        out = await svc.evaluate_eligibility(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert out.decision == PromotionEligibility.PAPER_FAIL

    @pytest.mark.asyncio
    async def test_excluded_blocked(self):
        """EXCLUDED → PAPER_FAIL."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.EXCLUDED)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        out = await svc.evaluate_eligibility(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert out.decision == PromotionEligibility.PAPER_FAIL

    @pytest.mark.asyncio
    async def test_safe_mode_active_blocked(self):
        """Safe mode active → PAPER_HOLD."""
        db = _mock_db()
        sym = _make_symbol()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        out = await svc.evaluate_eligibility(
            "sym-001",
            "strat-001",
            "1h",
            safe_mode_active=True,
        )
        assert out.decision == PromotionEligibility.PAPER_HOLD

    @pytest.mark.asyncio
    async def test_drift_active_blocked(self):
        """Runtime drift active → QUARANTINE_CANDIDATE."""
        db = _mock_db()
        sym = _make_symbol()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        out = await svc.evaluate_eligibility(
            "sym-001",
            "strat-001",
            "1h",
            drift_active=True,
        )
        assert out.decision == PromotionEligibility.QUARANTINE_CANDIDATE

    @pytest.mark.asyncio
    async def test_nonexistent_symbol_raises(self):
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = PaperShadowService(db)
        with pytest.raises(ValueError, match="Symbol not found"):
            await svc.evaluate_eligibility("bad-id", "strat-001", "1h")


class TestEvaluateAndRecordDecision:
    @pytest.mark.asyncio
    async def test_records_decision_and_updates_symbol(self):
        """Decision is recorded and symbol.promotion_eligibility_status updated."""
        db = _mock_db()
        sym = _make_symbol()

        # First call: _get_symbol (via evaluate_eligibility)
        # Second call: _get_symbol (own lookup)
        # Third call: _get_latest_decision (returns None = no previous)
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count <= 2:
                mock.scalar_one_or_none.return_value = sym
            else:
                mock.scalar_one_or_none.return_value = None
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = PaperShadowService(db)
        dec = await svc.evaluate_and_record_decision(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert dec.decision == PromotionEligibility.ELIGIBLE_FOR_PAPER
        assert dec.suppressed is False
        assert sym.promotion_eligibility_status == "eligible_for_paper"
        # db.add called for the decision
        assert db.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_duplicate_suppression(self):
        """Same decision twice → second is suppressed."""
        db = _mock_db()
        sym = _make_symbol()

        prev_decision = PromotionDecision(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            decision=PromotionEligibility.ELIGIBLE_FOR_PAPER,
            decided_at=datetime.now(timezone.utc),
        )

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count <= 2:
                mock.scalar_one_or_none.return_value = sym
            else:
                # _get_latest_decision returns previous decision
                mock.scalar_one_or_none.return_value = prev_decision
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = PaperShadowService(db)
        dec = await svc.evaluate_and_record_decision(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert dec.suppressed is True
        assert dec.previous_decision == "eligible_for_paper"

    @pytest.mark.asyncio
    async def test_changed_decision_not_suppressed(self):
        """Different decision → not suppressed."""
        db = _mock_db()
        sym = _make_symbol(qualification_status="fail")

        prev_decision = PromotionDecision(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            decision=PromotionEligibility.ELIGIBLE_FOR_PAPER,
            decided_at=datetime.now(timezone.utc),
        )

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count <= 2:
                mock.scalar_one_or_none.return_value = sym
            else:
                mock.scalar_one_or_none.return_value = prev_decision
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = PaperShadowService(db)
        dec = await svc.evaluate_and_record_decision(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert dec.suppressed is False
        assert dec.decision == PromotionEligibility.PAPER_FAIL


# ═══════════════════════════════════════════════════════════════════════
# EXCLUDED QUALIFICATION BLOCKING
# ═══════════════════════════════════════════════════════════════════════


class TestExcludedQualificationBlocking:
    @pytest.mark.asyncio
    async def test_excluded_symbol_qualification_blocked(self):
        """qualify_and_record() raises ValueError for EXCLUDED symbols."""
        db = _mock_db()
        sym = _make_symbol(
            status=SymbolStatus.EXCLUDED,
            sector=AssetSector.MEME,
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = AssetService(db)
        inp = QualificationInput(
            strategy_id="strat-001",
            symbol="DOGE/USDT",
            total_bars=1000,
            warmup_bars_available=300,
            sharpe_ratio=1.0,
        )
        with pytest.raises(ValueError, match="EXCLUDED.*qualification calls blocked"):
            await svc.qualify_and_record("sym-001", inp)

    @pytest.mark.asyncio
    async def test_non_excluded_qualification_allowed(self):
        """qualify_and_record() works for non-EXCLUDED symbols."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = AssetService(db)
        inp = QualificationInput(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            total_bars=1000,
            warmup_bars_available=300,
            sharpe_ratio=1.0,
        )
        output = await svc.qualify_and_record("sym-001", inp)
        assert output.all_passed is True


# ═══════════════════════════════════════════════════════════════════════
# FAILED_CHECKS FIELD
# ═══════════════════════════════════════════════════════════════════════


class TestFailedChecksField:
    @pytest.mark.asyncio
    async def test_failed_checks_populated_on_failure(self):
        """QualificationResult.failed_checks contains all failed check names."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = AssetService(db)
        inp = QualificationInput(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            total_bars=100,  # below min_bars=500
            warmup_bars_available=50,  # below required=200
            sharpe_ratio=-1.0,  # negative
        )
        output = await svc.qualify_and_record("sym-001", inp)
        assert output.all_passed is False

        # Check the QualificationResult that was added to db
        added_obj = db.add.call_args_list[0][0][0]
        assert isinstance(added_obj, QualificationResult)
        failed = json.loads(added_obj.failed_checks)
        assert "warmup" in failed
        assert "min_bars" in failed
        assert "performance" in failed

    @pytest.mark.asyncio
    async def test_failed_checks_none_on_pass(self):
        """QualificationResult.failed_checks is None when all pass."""
        db = _mock_db()
        sym = _make_symbol(status=SymbolStatus.CORE)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sym
        db.execute.return_value = result_mock

        svc = AssetService(db)
        inp = QualificationInput(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            total_bars=1000,
            warmup_bars_available=300,
            sharpe_ratio=1.0,
        )
        await svc.qualify_and_record("sym-001", inp)

        added_obj = db.add.call_args_list[0][0][0]
        assert added_obj.failed_checks is None


# ═══════════════════════════════════════════════════════════════════════
# STATUS SEPARATION (screening / qualification / promotion)
# ═══════════════════════════════════════════════════════════════════════


class TestTripleStatusSeparation:
    def test_symbol_has_three_statuses(self):
        """Symbol model has screening, qualification, and promotion status fields."""
        sym = _make_symbol()
        assert hasattr(sym, "status")  # screening
        assert hasattr(sym, "qualification_status")
        assert hasattr(sym, "promotion_eligibility_status")

    def test_core_pass_eligible(self):
        """CORE + PASS → eligible_for_paper is a valid combination."""
        sym = _make_symbol(
            status=SymbolStatus.CORE,
            qualification_status="pass",
            promotion_eligibility_status="eligible_for_paper",
        )
        assert sym.status == SymbolStatus.CORE
        assert sym.qualification_status == "pass"
        assert sym.promotion_eligibility_status == "eligible_for_paper"

    def test_core_fail_paper_fail(self):
        """CORE + FAIL → paper_fail is valid."""
        sym = _make_symbol(
            status=SymbolStatus.CORE,
            qualification_status="fail",
            promotion_eligibility_status="paper_fail",
        )
        assert sym.qualification_status == "fail"
        assert sym.promotion_eligibility_status == "paper_fail"

    def test_watch_pass_paper_fail(self):
        """WATCH + PASS → paper_fail (screening not core)."""
        sym = _make_symbol(
            status=SymbolStatus.WATCH,
            qualification_status="pass",
            promotion_eligibility_status="paper_fail",
        )
        assert sym.status == SymbolStatus.WATCH
        assert sym.promotion_eligibility_status == "paper_fail"

    def test_all_statuses_independent(self):
        """Each status can be set independently."""
        sym = _make_symbol(
            status=SymbolStatus.CORE,
            qualification_status="pass",
            promotion_eligibility_status="paper_hold",
        )
        # Change one, others unaffected
        sym.qualification_status = "fail"
        assert sym.status == SymbolStatus.CORE  # unchanged
        assert sym.promotion_eligibility_status == "paper_hold"  # unchanged


# ═══════════════════════════════════════════════════════════════════════
# MIGRATION STRUCTURE
# ═══════════════════════════════════════════════════════════════════════


class TestMigrationStructure:
    def _load_migration(self):
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "alembic",
            "versions",
            "010_paper_shadow_tables.py",
        )
        spec = importlib.util.spec_from_file_location("m010", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_migration_010_revision_chain(self):
        m010 = self._load_migration()
        assert m010.revision == "010_paper_shadow"
        assert m010.down_revision == "009_qualification"

    def test_migration_010_has_upgrade_downgrade(self):
        m010 = self._load_migration()
        assert callable(m010.upgrade)
        assert callable(m010.downgrade)
