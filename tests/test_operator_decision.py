"""
K-Dexter Operator Decision Tests

Sprint Contract: CARD-2026-0330-OPERATOR-DECISION (Level B)

Tests the operator decision guidance service:
  AXIS 1: Posture Decision Accuracy (MONITOR/REVIEW/MANUAL_CHECK/URGENT_REVIEW)
  AXIS 2: Risk Level Accuracy (LOW/MEDIUM/HIGH boundaries)
  AXIS 3: Reason Chain Accuracy (traceable, complete)
  AXIS 4: Explanation Quality (readable, no action verbs)
  AXIS 5: Safety Labels (action_allowed=False, suggestion_only, read_only)
  AXIS 6: Dashboard Integration (decision_summary in board)
  AXIS 7: Edge Cases (empty, all normal, extreme)

Run: pytest tests/test_operator_decision.py -v
"""

import sys
import inspect
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_STUB_MODULES = [
    "app.core.database",
    "app.models",
    "app.models.order",
    "app.models.position",
    "app.models.signal",
    "app.models.trade",
    "app.models.asset_snapshot",
    "app.exchanges",
    "app.exchanges.factory",
    "app.exchanges.base",
    "app.exchanges.binance",
    "app.services.order_service",
    "app.services.position_service",
    "app.services.signal_service",
    "ccxt",
    "ccxt.async_support",
    "redis",
    "celery",
    "asyncpg",
    "kdexter",
    "kdexter.ledger",
    "kdexter.ledger.forbidden_ledger",
    "kdexter.audit",
    "kdexter.audit.evidence_store",
    "kdexter.state_machine",
    "kdexter.state_machine.security_state",
]
for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# -- Helpers ---------------------------------------------------------------- #


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _past_iso(seconds_ago):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


class _FakeLedger:
    def __init__(self, proposals=None, stale_count=0):
        self._data = proposals or []
        self._stale_count = stale_count

    def get_proposals(self):
        return self._data

    def get_board(self):
        return {
            "total": len(self._data),
            "receipted_count": 0,
            "blocked_count": 0,
            "failed_count": 0,
            "orphan_count": 0,
            "stale_count": self._stale_count,
            "stale_threshold_seconds": 600.0,
            "guard_reason_top": [],
        }


# -- Imports ---------------------------------------------------------------- #

from app.services.operator_decision_service import (
    build_decision_summary,
    DecisionSummary,
    _determine_posture,
    _determine_risk_level,
    _build_reason_chain,
    POSTURE_MONITOR,
    POSTURE_REVIEW,
    POSTURE_MANUAL_CHECK,
    POSTURE_URGENT_REVIEW,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
)
from app.services.observation_summary_service import (
    ObservationSummary,
    PRESSURE_LOW,
    PRESSURE_MODERATE,
    PRESSURE_HIGH,
    PRESSURE_CRITICAL,
)


# =========================================================================== #
# AXIS 1: Posture Decision Accuracy                                            #
# =========================================================================== #


class TestPostureDecision:
    def test_monitor_on_low_pressure(self):
        assert _determine_posture(PRESSURE_LOW) == POSTURE_MONITOR

    def test_review_on_moderate_pressure(self):
        assert _determine_posture(PRESSURE_MODERATE) == POSTURE_REVIEW

    def test_manual_check_on_high_pressure(self):
        assert _determine_posture(PRESSURE_HIGH) == POSTURE_MANUAL_CHECK

    def test_urgent_review_on_critical_pressure(self):
        assert _determine_posture(PRESSURE_CRITICAL) == POSTURE_URGENT_REVIEW

    def test_unknown_pressure_defaults_to_monitor(self):
        assert _determine_posture("UNKNOWN") == POSTURE_MONITOR

    def test_integration_low_pressure(self):
        """Full pipeline: all normal → MONITOR."""
        action = _FakeLedger(
            [{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}]
        )
        decision = build_decision_summary(action_ledger=action)
        assert decision.recommended_posture == POSTURE_MONITOR


# =========================================================================== #
# AXIS 2: Risk Level Accuracy                                                  #
# =========================================================================== #


class TestRiskLevel:
    def test_low_on_normal(self):
        assert _determine_risk_level(PRESSURE_LOW, 0, 0) == RISK_LOW

    def test_low_with_small_candidates(self):
        assert _determine_risk_level(PRESSURE_MODERATE, 0, 2) == RISK_LOW

    def test_medium_on_high_pressure(self):
        assert _determine_risk_level(PRESSURE_HIGH, 0, 0) == RISK_MEDIUM

    def test_medium_on_orphan_present(self):
        assert _determine_risk_level(PRESSURE_LOW, 1, 0) == RISK_MEDIUM

    def test_medium_on_candidates_3_to_9(self):
        assert _determine_risk_level(PRESSURE_LOW, 0, 5) == RISK_MEDIUM

    def test_high_on_critical_pressure(self):
        assert _determine_risk_level(PRESSURE_CRITICAL, 0, 0) == RISK_HIGH

    def test_high_on_candidates_ge_10(self):
        assert _determine_risk_level(PRESSURE_LOW, 0, 10) == RISK_HIGH


# =========================================================================== #
# AXIS 3: Reason Chain Accuracy                                                #
# =========================================================================== #


class TestReasonChain:
    def test_chain_contains_pressure(self):
        obs = ObservationSummary(cleanup_pressure=PRESSURE_HIGH)
        chain = _build_reason_chain(obs)
        assert any("pressure=HIGH" in item for item in chain)

    def test_chain_contains_totals(self):
        obs = ObservationSummary(candidate_total=5, orphan_total=2, stale_total=3)
        chain = _build_reason_chain(obs)
        assert any("candidate_total=5" in item for item in chain)
        assert any("orphan_total=2" in item for item in chain)
        assert any("stale_total=3" in item for item in chain)

    def test_chain_includes_tier_stale_if_nonzero(self):
        obs = ObservationSummary(stale_by_tier={"agent": 2, "execution": 0, "submit": 1})
        chain = _build_reason_chain(obs)
        assert any("stale_agent=2" in item for item in chain)
        assert any("stale_submit=1" in item for item in chain)
        assert not any("stale_execution=0" in item for item in chain)


# =========================================================================== #
# AXIS 4: Explanation Quality                                                  #
# =========================================================================== #


class TestExplanationQuality:
    def test_explanation_not_empty(self):
        decision = build_decision_summary()
        assert decision.decision_explanation != ""

    def test_explanation_no_execute_verb(self):
        """Explanation must not contain execution-inducing verbs."""
        action = _FakeLedger(
            [{"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(9999)}],
            stale_count=1,
        )
        decision = build_decision_summary(action_ledger=action)
        explanation_lower = decision.decision_explanation.lower()
        assert "execute" not in explanation_lower
        assert "perform" not in explanation_lower
        assert "clean up" not in explanation_lower
        assert "delete" not in explanation_lower
        assert "remove" not in explanation_lower

    def test_explanation_includes_risk_level(self):
        decision = build_decision_summary()
        assert "Risk level" in decision.decision_explanation


# =========================================================================== #
# AXIS 5: Safety Labels                                                        #
# =========================================================================== #


class TestSafetyLabels:
    def test_action_allowed_always_false_empty(self):
        decision = build_decision_summary()
        assert decision.action_allowed is False

    def test_action_allowed_always_false_with_data(self):
        action = _FakeLedger(
            [{"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(9999)}],
            stale_count=1,
        )
        decision = build_decision_summary(action_ledger=action)
        assert decision.action_allowed is False
        assert decision.suggestion_only is True
        assert decision.read_only is True

    def test_source_no_write_methods(self):
        import app.services.operator_decision_service as mod

        source = inspect.getsource(mod)
        assert ".propose_and_guard(" not in source
        assert ".record_receipt(" not in source
        assert ".transition_to(" not in source

    def test_source_no_action_allowed_true(self):
        """Source must never set action_allowed=True."""
        import app.services.operator_decision_service as mod

        source = inspect.getsource(mod)
        # Check that action_allowed is only ever set to False
        assert "action_allowed=True" not in source
        assert "action_allowed = True" not in source


# =========================================================================== #
# AXIS 6: Dashboard Integration                                                #
# =========================================================================== #


class TestDashboardIntegration:
    def test_board_schema_has_decision_summary(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse

        fields = FourTierBoardResponse.model_fields
        assert "decision_summary" in fields

    def test_board_populates_decision_summary(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert hasattr(board.decision_summary, "recommended_posture")
        assert hasattr(board.decision_summary, "risk_level")
        assert hasattr(board.decision_summary, "safety")
        assert board.decision_summary.safety.action_allowed is False

    def test_board_decision_has_reason_chain(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert hasattr(board.decision_summary, "reason_chain")
        assert isinstance(board.decision_summary.reason_chain, list)


# =========================================================================== #
# AXIS 7: Edge Cases                                                           #
# =========================================================================== #


class TestEdgeCases:
    def test_all_none_returns_monitor_low(self):
        decision = build_decision_summary()
        assert decision.recommended_posture == POSTURE_MONITOR
        assert decision.risk_level == RISK_LOW
        assert decision.action_allowed is False

    def test_to_dict_serializable(self):
        import json

        decision = build_decision_summary()
        d = decision.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)

    def test_heavy_stale_orphan_gives_urgent(self):
        """Many stale + orphans → CRITICAL pressure → URGENT_REVIEW."""
        action = _FakeLedger(
            [{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}]
        )
        # 10+ stale execution proposals with broken lineage
        exec_proposals = [
            {
                "proposal_id": f"EP-{i}",
                "agent_proposal_id": f"AP-GONE-{i}",
                "status": "EXEC_GUARDED",
                "created_at": _past_iso(500),
            }
            for i in range(12)
        ]
        execution = _FakeLedger(exec_proposals, stale_count=12)
        decision = build_decision_summary(action, execution)
        assert decision.recommended_posture == POSTURE_URGENT_REVIEW
        assert decision.risk_level == RISK_HIGH
        assert decision.action_allowed is False
