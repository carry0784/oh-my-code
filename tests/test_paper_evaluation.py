"""Tests for Phase 4C: Paper Evaluation — 6-rule engine, evaluation service,
promotion state wiring, internal state queries, and status separation.

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
)
from app.models.paper_shadow import (
    PaperObservation,
    PaperEvaluationRecord,
    PromotionDecision,
    PromotionEligibility,
    ObservationStatus,
)
from app.services.paper_evaluation import (
    PaperEvalInput,
    PaperEvalOutput,
    PaperEvalDecision,
    PaperEvalReason,
    PaperEvalThresholds,
    EvalRuleResult,
    PaperEvaluator,
)
from app.services.paper_evaluation_service import PaperEvaluationService
from app.schemas.paper_shadow_schema import PaperEvaluationRecordRead
from app.schemas.asset_schema import SymbolRead


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
        promotion_eligibility_status="eligible_for_paper",
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


def _pass_input(**overrides) -> PaperEvalInput:
    """Create a PaperEvalInput that passes all 6 rules."""
    base = dict(
        strategy_id="strat-001",
        symbol="SOL/USDT",
        timeframe="1h",
        total_observations=60,
        valid_observations=58,
        expected_observations=60,
        cumulative_return_pct=5.0,
        max_drawdown_pct=10.0,
        avg_turnover_annual=200.0,
        avg_slippage_pct=0.5,
        safe_mode_active=False,
        drift_active=False,
    )
    base.update(overrides)
    return PaperEvalInput(**base)


# ═══════════════════════════════════════════════════════════════════════
# PAPER EVALUATION ENGINE TESTS (stateless, no DB)
# ═══════════════════════════════════════════════════════════════════════


class TestRule1MinObservations:
    def test_sufficient_passes(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(valid_observations=50))
        assert out.rules[0].passed is True

    def test_insufficient_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(valid_observations=10))
        assert out.rules[0].passed is False
        assert out.rules[0].reason == PaperEvalReason.INSUFFICIENT_OBSERVATIONS

    def test_insufficient_produces_hold(self):
        """Insufficient observations → HOLD (not enough data yet)."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(valid_observations=10))
        assert out.decision == PaperEvalDecision.HOLD


class TestRule2CumulativePerformance:
    def test_positive_passes(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(cumulative_return_pct=5.0))
        assert out.rules[1].passed is True

    def test_slightly_negative_passes(self):
        """Small negative allowed (threshold is -10%)."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(cumulative_return_pct=-5.0))
        assert out.rules[1].passed is True

    def test_deeply_negative_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(cumulative_return_pct=-15.0))
        assert out.rules[1].passed is False
        assert out.rules[1].reason == PaperEvalReason.NEGATIVE_CUMULATIVE_RETURN

    def test_none_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(cumulative_return_pct=None))
        assert out.rules[1].passed is False


class TestRule3MaxDrawdown:
    def test_within_ceiling_passes(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(max_drawdown_pct=20.0))
        assert out.rules[2].passed is True

    def test_excessive_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(max_drawdown_pct=35.0))
        assert out.rules[2].passed is False
        assert out.rules[2].reason == PaperEvalReason.EXCESSIVE_DRAWDOWN

    def test_none_passes(self):
        """No drawdown data → pass (lenient)."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(max_drawdown_pct=None))
        assert out.rules[2].passed is True


class TestRule4Turnover:
    def test_within_ceiling_passes(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(avg_turnover_annual=200.0))
        assert out.rules[3].passed is True

    def test_excessive_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(avg_turnover_annual=400.0))
        assert out.rules[3].passed is False
        assert out.rules[3].reason == PaperEvalReason.EXCESSIVE_TURNOVER


class TestRule5Slippage:
    def test_within_ceiling_passes(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(avg_slippage_pct=1.0))
        assert out.rules[4].passed is True

    def test_excessive_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(avg_slippage_pct=3.0))
        assert out.rules[4].passed is False
        assert out.rules[4].reason == PaperEvalReason.EXCESSIVE_SLIPPAGE


class TestRule6Completeness:
    def test_complete_passes(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(valid_observations=55, expected_observations=60))
        assert out.rules[5].passed is True

    def test_incomplete_fails(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(valid_observations=40, expected_observations=60))
        assert out.rules[5].passed is False
        assert out.rules[5].reason == PaperEvalReason.OBSERVATION_INCOMPLETE


class TestAggregateEvaluation:
    def test_all_pass_produces_pass(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input())
        assert out.all_passed is True
        assert out.decision == PaperEvalDecision.PASS
        assert out.failed_rules == []

    def test_any_fail_produces_fail(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(cumulative_return_pct=-15.0))
        assert out.all_passed is False
        assert out.decision == PaperEvalDecision.FAIL
        assert "cumulative_performance" in out.failed_rules

    def test_six_rules_always(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input())
        assert len(out.rules) == 6

    def test_metrics_summary_populated(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input())
        assert out.metrics_summary is not None
        assert "total_observations" in out.metrics_summary

    def test_multiple_failures_all_recorded(self):
        ev = PaperEvaluator()
        out = ev.evaluate(
            _pass_input(
                cumulative_return_pct=-15.0,
                max_drawdown_pct=35.0,
                avg_slippage_pct=3.0,
            )
        )
        assert len(out.failed_rules) == 3

    def test_first_fail_sets_primary_reason(self):
        ev = PaperEvaluator()
        out = ev.evaluate(
            _pass_input(
                cumulative_return_pct=-15.0,
                max_drawdown_pct=35.0,
            )
        )
        assert out.primary_reason == PaperEvalReason.NEGATIVE_CUMULATIVE_RETURN


class TestSystemGuards:
    def test_drift_active_produces_quarantine(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(drift_active=True))
        assert out.decision == PaperEvalDecision.QUARANTINE
        assert out.rules == []  # no rules evaluated

    def test_safe_mode_produces_hold(self):
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(safe_mode_active=True))
        assert out.decision == PaperEvalDecision.HOLD
        assert out.rules == []

    def test_drift_takes_priority_over_safe_mode(self):
        ev = PaperEvaluator()
        out = ev.evaluate(
            _pass_input(
                drift_active=True,
                safe_mode_active=True,
            )
        )
        assert out.decision == PaperEvalDecision.QUARANTINE


class TestCustomThresholds:
    def test_strict_observations_fails(self):
        t = PaperEvalThresholds(min_observation_count=100)
        ev = PaperEvaluator(thresholds=t)
        out = ev.evaluate(_pass_input(valid_observations=60))
        assert out.rules[0].passed is False

    def test_lenient_drawdown_passes(self):
        t = PaperEvalThresholds(max_drawdown_pct=60.0)
        ev = PaperEvaluator(thresholds=t)
        out = ev.evaluate(_pass_input(max_drawdown_pct=50.0))
        assert out.rules[2].passed is True


# ═══════════════════════════════════════════════════════════════════════
# MODEL TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestPaperEvaluationRecordModel:
    def test_creation(self):
        rec = PaperEvaluationRecord(
            strategy_id="strat-001",
            symbol="SOL/USDT",
            timeframe="1h",
            observation_count=60,
            valid_observation_count=58,
            expected_observation_count=60,
            all_passed=True,
            decision="pass",
            evaluated_at=datetime.now(timezone.utc),
        )
        assert rec.strategy_id == "strat-001"
        assert rec.decision == "pass"

    def test_paper_eval_decision_enum(self):
        assert len(PaperEvalDecision) == 5
        assert PaperEvalDecision.PENDING.value == "pending"
        assert PaperEvalDecision.HOLD.value == "hold"
        assert PaperEvalDecision.PASS.value == "pass"
        assert PaperEvalDecision.FAIL.value == "fail"
        assert PaperEvalDecision.QUARANTINE.value == "quarantine"

    def test_paper_eval_reason_enum(self):
        assert len(PaperEvalReason) == 6
        assert PaperEvalReason.INSUFFICIENT_OBSERVATIONS.value == "insufficient_observations"
        assert PaperEvalReason.EXCESSIVE_SLIPPAGE.value == "excessive_slippage"


# ═══════════════════════════════════════════════════════════════════════
# SCHEMA TESTS
# ═══════════════════════════════════════════════════════════════════════


class TestEvaluationSchemas:
    def test_paper_evaluation_record_read(self):
        now = datetime.now(timezone.utc)
        data = {
            "id": "eval-001",
            "strategy_id": "strat-001",
            "symbol": "SOL/USDT",
            "timeframe": "1h",
            "observation_count": 60,
            "valid_observation_count": 58,
            "expected_observation_count": 60,
            "observation_window_fingerprint": None,
            "cumulative_return_pct": 5.0,
            "max_drawdown_pct": 10.0,
            "avg_turnover_annual": 200.0,
            "avg_slippage_pct": 0.5,
            "rule_min_observations": True,
            "rule_cumulative_performance": True,
            "rule_max_drawdown": True,
            "rule_turnover": True,
            "rule_slippage": True,
            "rule_completeness": True,
            "all_passed": True,
            "decision": "pass",
            "primary_reason": None,
            "failed_rules": None,
            "metrics_summary": None,
            "source_qualification_result_id": None,
            "evaluated_at": now,
        }
        er = PaperEvaluationRecordRead(**data)
        assert er.all_passed is True
        assert er.decision == "pass"

    def test_symbol_read_has_paper_evaluation_status(self):
        """SymbolRead schema includes paper_evaluation_status."""
        fields = SymbolRead.model_fields
        assert "paper_evaluation_status" in fields


# ═══════════════════════════════════════════════════════════════════════
# SERVICE TESTS — INTERNAL STATE QUERIES
# ═══════════════════════════════════════════════════════════════════════


class TestInternalStateQueries:
    @pytest.mark.asyncio
    async def test_safe_mode_normal_returns_false(self):
        """When safe mode is NORMAL → not active."""
        from app.models.safe_mode import SafeModeState, SafeModeStatus

        db = _mock_db()
        status = MagicMock()
        status.current_state = SafeModeState.NORMAL
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = status
        db.execute.return_value = result_mock

        svc = PaperEvaluationService(db)
        assert await svc.is_safe_mode_active() is False

    @pytest.mark.asyncio
    async def test_safe_mode_sm3_returns_true(self):
        """When safe mode is SM3 → active."""
        from app.models.safe_mode import SafeModeState, SafeModeStatus

        db = _mock_db()
        status = MagicMock()
        status.current_state = SafeModeState.SM3_RECOVERY_ONLY
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = status
        db.execute.return_value = result_mock

        svc = PaperEvaluationService(db)
        assert await svc.is_safe_mode_active() is True

    @pytest.mark.asyncio
    async def test_safe_mode_no_record_returns_false(self):
        """No safe mode record → NORMAL (first boot)."""
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = PaperEvaluationService(db)
        assert await svc.is_safe_mode_active() is False

    @pytest.mark.asyncio
    async def test_drift_none_returns_false(self):
        """No unprocessed drift → not active."""
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 0
        db.execute.return_value = result_mock

        svc = PaperEvaluationService(db)
        assert await svc.has_unprocessed_drift() is False

    @pytest.mark.asyncio
    async def test_drift_some_returns_true(self):
        """Unprocessed drift events → active."""
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 3
        db.execute.return_value = result_mock

        svc = PaperEvaluationService(db)
        assert await svc.has_unprocessed_drift() is True


# ═══════════════════════════════════════════════════════════════════════
# SERVICE TESTS — EVALUATE AND RECORD
# ═══════════════════════════════════════════════════════════════════════


class TestEvaluateAndRecord:
    @pytest.mark.asyncio
    async def test_pass_updates_symbol_evaluation_status(self):
        """Passing evaluation updates Symbol.paper_evaluation_status."""
        db = _mock_db()
        sym = _make_symbol()

        # Create a mock observation with valid passing metrics
        obs = MagicMock()
        obs.observation_status = ObservationStatus.RECORDED
        obs.metrics_snapshot = json.dumps(
            {
                "return_pct": 5.0,
                "drawdown_pct": 10.0,
                "turnover_annual": 100.0,
                "slippage_pct": 0.5,
            }
        )

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count <= 2:
                # Symbol lookups
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 3:
                # Safe mode check
                mock.scalar_one_or_none.return_value = None  # NORMAL
            elif call_count == 4:
                # Drift check
                mock.scalar_one.return_value = 0  # no drift
            else:
                # Observation aggregation — return one valid observation
                mock.scalars.return_value.all.return_value = [obs]
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        # min_observation_count=1 (we have 1 obs), completeness needs expected=1
        ev = PaperEvaluator(PaperEvalThresholds(min_observation_count=1))
        svc = PaperEvaluationService(db)
        record = await svc.evaluate_and_record(
            "sym-001",
            "strat-001",
            "1h",
            evaluator=ev,
            expected_observations=1,
        )
        assert record.decision == "pass"
        assert sym.paper_evaluation_status == "pass"

    @pytest.mark.asyncio
    async def test_fail_updates_symbol_evaluation_status(self):
        """Failing evaluation updates Symbol.paper_evaluation_status."""
        db = _mock_db()
        sym = _make_symbol()

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count <= 2:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = None
            elif call_count == 4:
                mock.scalar_one.return_value = 0
            else:
                # Return observations with bad metrics
                obs = MagicMock()
                obs.observation_status = ObservationStatus.RECORDED
                obs.metrics_snapshot = json.dumps(
                    {
                        "return_pct": -20.0,
                        "drawdown_pct": 40.0,
                    }
                )
                obs_list = [obs] * 60
                mock.scalars.return_value.all.return_value = obs_list
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        svc = PaperEvaluationService(db)
        record = await svc.evaluate_and_record(
            "sym-001",
            "strat-001",
            "1h",
        )
        assert record.decision == "fail"
        assert sym.paper_evaluation_status == "fail"

    @pytest.mark.asyncio
    async def test_nonexistent_symbol_raises(self):
        db = _mock_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = PaperEvaluationService(db)
        with pytest.raises(ValueError, match="Symbol not found"):
            await svc.evaluate_and_record("bad-id", "strat-001", "1h")

    @pytest.mark.asyncio
    async def test_record_is_appended(self):
        """Evaluation record is inserted via db.add."""
        db = _mock_db()
        sym = _make_symbol()

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count <= 2:
                mock.scalar_one_or_none.return_value = sym
            elif call_count == 3:
                mock.scalar_one_or_none.return_value = None
            elif call_count == 4:
                mock.scalar_one.return_value = 0
            else:
                mock.scalars.return_value.all.return_value = []
            return mock

        db.execute = AsyncMock(side_effect=execute_side_effect)

        ev = PaperEvaluator(PaperEvalThresholds(min_observation_count=0))
        svc = PaperEvaluationService(db)
        await svc.evaluate_and_record("sym-001", "strat-001", "1h", evaluator=ev)
        assert db.add.call_count >= 1
        added_obj = db.add.call_args_list[0][0][0]
        assert isinstance(added_obj, PaperEvaluationRecord)


# ═══════════════════════════════════════════════════════════════════════
# STATUS SEPARATION (quad-status)
# ═══════════════════════════════════════════════════════════════════════


class TestQuadStatusSeparation:
    def test_symbol_has_four_statuses(self):
        """Symbol model has screening, qualification, promotion, and evaluation status."""
        sym = _make_symbol()
        assert hasattr(sym, "status")  # screening
        assert hasattr(sym, "qualification_status")
        assert hasattr(sym, "promotion_eligibility_status")
        assert hasattr(sym, "paper_evaluation_status")

    def test_core_pass_eligible_pass(self):
        """CORE + PASS + ELIGIBLE + PASS is the full lifecycle."""
        sym = _make_symbol(
            status=SymbolStatus.CORE,
            qualification_status="pass",
            promotion_eligibility_status="eligible_for_paper",
            paper_evaluation_status="pass",
        )
        assert sym.status == SymbolStatus.CORE
        assert sym.qualification_status == "pass"
        assert sym.promotion_eligibility_status == "eligible_for_paper"
        assert sym.paper_evaluation_status == "pass"

    def test_core_pass_eligible_fail(self):
        """Paper evaluation fail while eligible."""
        sym = _make_symbol(
            paper_evaluation_status="fail",
        )
        assert sym.paper_evaluation_status == "fail"

    def test_statuses_independent(self):
        """Each status can be set independently."""
        sym = _make_symbol()
        sym.paper_evaluation_status = "fail"
        assert sym.qualification_status == "pass"  # unchanged
        assert sym.promotion_eligibility_status == "eligible_for_paper"  # unchanged


# ═══════════════════════════════════════════════════════════════════════
# PROMOTION STATE WIRING
# ═══════════════════════════════════════════════════════════════════════


class TestPromotionStateWiring:
    def test_eligible_plus_hold(self):
        """ELIGIBLE_FOR_PAPER + observation insufficient → HOLD."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(valid_observations=5))
        assert out.decision == PaperEvalDecision.HOLD

    def test_eligible_plus_pass(self):
        """ELIGIBLE_FOR_PAPER + criteria met → PASS."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input())
        assert out.decision == PaperEvalDecision.PASS

    def test_eligible_plus_fail(self):
        """ELIGIBLE_FOR_PAPER + criteria not met → FAIL."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(cumulative_return_pct=-20.0))
        assert out.decision == PaperEvalDecision.FAIL

    def test_drift_overrides_evaluation(self):
        """Even with good metrics, drift → QUARANTINE."""
        ev = PaperEvaluator()
        out = ev.evaluate(_pass_input(drift_active=True))
        assert out.decision == PaperEvalDecision.QUARANTINE


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
            "011_paper_evaluation_tables.py",
        )
        spec = importlib.util.spec_from_file_location("m011", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_migration_011_revision_chain(self):
        m011 = self._load_migration()
        assert m011.revision == "011_paper_evaluation"
        assert m011.down_revision == "010_paper_shadow"

    def test_migration_011_has_upgrade_downgrade(self):
        m011 = self._load_migration()
        assert callable(m011.upgrade)
        assert callable(m011.downgrade)
