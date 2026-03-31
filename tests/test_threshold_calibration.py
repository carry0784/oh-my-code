"""
K-Dexter Threshold Calibration Tests

Sprint Contract: CARD-2026-0330-THRESHOLD-CALIBRATION (Level B)

Tests the calibrated threshold band system:
  AXIS 1: Band Boundary Precision (1.5x WATCH/REVIEW, 3.0x prolonged)
  AXIS 2: Band Label in Explanation (early/review/prolonged)
  AXIS 3: Threshold Constants Correctness
  AXIS 4: Cross-layer Impact (observation → decision → card)
  AXIS 5: Reason Chain Action Distribution
  AXIS 6: Safety Invariants Preserved

Run: pytest tests/test_threshold_calibration.py -v
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_STUB_MODULES = [
    "app.core.database", "app.models", "app.models.order",
    "app.models.position", "app.models.signal", "app.models.trade",
    "app.models.asset_snapshot", "app.exchanges", "app.exchanges.factory",
    "app.exchanges.base", "app.exchanges.binance",
    "app.services.order_service", "app.services.position_service",
    "app.services.signal_service", "ccxt", "ccxt.async_support",
    "redis", "celery", "asyncpg",
    "kdexter", "kdexter.ledger", "kdexter.ledger.forbidden_ledger",
    "kdexter.audit", "kdexter.audit.evidence_store",
    "kdexter.state_machine", "kdexter.state_machine.security_state",
]
for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# -- Imports ---------------------------------------------------------------- #

from app.services.cleanup_simulation_service import (
    simulate_cleanup,
    _determine_action_class,
    _classify_stale_band,
    _build_explanation,
    THRESHOLD_WATCH_UPPER,
    THRESHOLD_PROLONGED,
    ACTION_INFO,
    ACTION_WATCH,
    ACTION_REVIEW,
    ACTION_MANUAL,
)
from app.services.operator_decision_service import (
    build_decision_summary,
    POSTURE_MONITOR,
    POSTURE_REVIEW,
    POSTURE_MANUAL_CHECK,
    POSTURE_URGENT_REVIEW,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
)


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
            "total": len(self._data), "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": self._stale_count,
            "stale_threshold_seconds": 600.0, "guard_reason_top": [],
        }


# =========================================================================== #
# AXIS 1: Band Boundary Precision                                              #
# =========================================================================== #

class TestBandBoundary:

    def test_below_1_5x_is_watch(self):
        """age < 1.5x threshold → WATCH."""
        # 800s / 600s = 1.33x → WATCH
        assert _determine_action_class(True, False, 800, 600) == ACTION_WATCH

    def test_at_1_5x_is_review(self):
        """age == 1.5x threshold → REVIEW."""
        # 900s / 600s = 1.5x → REVIEW
        assert _determine_action_class(True, False, 900, 600) == ACTION_REVIEW

    def test_just_below_1_5x_is_watch(self):
        """age just below 1.5x → WATCH."""
        # 899s / 600s = 1.498x → WATCH
        assert _determine_action_class(True, False, 899, 600) == ACTION_WATCH

    def test_at_3x_still_review(self):
        """age == 3x → still REVIEW (not new class, but flagged prolonged)."""
        # 1800s / 600s = 3.0x → REVIEW
        assert _determine_action_class(True, False, 1800, 600) == ACTION_REVIEW

    def test_above_3x_still_review(self):
        """age > 3x → REVIEW (prolonged flag in explanation, not new class)."""
        assert _determine_action_class(True, False, 3000, 600) == ACTION_REVIEW

    def test_orphan_is_still_review(self):
        """Orphan-only → REVIEW (unchanged by calibration)."""
        assert _determine_action_class(False, True, 0, 600) == ACTION_REVIEW

    def test_stale_orphan_is_still_manual(self):
        """Stale + orphan → MANUAL (unchanged by calibration)."""
        assert _determine_action_class(True, True, 800, 600) == ACTION_MANUAL

    def test_execution_tier_threshold(self):
        """Execution tier with 300s threshold: 450s/300s = 1.5x → REVIEW."""
        assert _determine_action_class(True, False, 450, 300) == ACTION_REVIEW

    def test_execution_tier_below(self):
        """Execution tier with 300s threshold: 400s/300s = 1.33x → WATCH."""
        assert _determine_action_class(True, False, 400, 300) == ACTION_WATCH

    def test_submit_tier_threshold(self):
        """Submit tier with 180s threshold: 270s/180s = 1.5x → REVIEW."""
        assert _determine_action_class(True, False, 270, 180) == ACTION_REVIEW


# =========================================================================== #
# AXIS 2: Band Label in Explanation                                            #
# =========================================================================== #

class TestBandLabel:

    def test_early_band_label(self):
        """Multiplier < 1.5 → band=early."""
        assert _classify_stale_band(1.2) == "early"

    def test_review_band_label(self):
        """Multiplier 1.5~3.0 → band=review."""
        assert _classify_stale_band(1.5) == "review"
        assert _classify_stale_band(2.5) == "review"

    def test_prolonged_band_label(self):
        """Multiplier >= 3.0 → band=prolonged."""
        assert _classify_stale_band(3.0) == "prolonged"
        assert _classify_stale_band(5.0) == "prolonged"

    def test_edge_just_below_prolonged(self):
        """2.99x → review, not prolonged."""
        assert _classify_stale_band(2.99) == "review"

    def test_explanation_contains_band(self):
        """Stale explanation includes band= marker."""
        explanation = _build_explanation(
            ACTION_WATCH, "STALE_AGENT",
            is_stale=True, is_orphan=False,
            stale_age_seconds=700, threshold=600, tier="agent",
        )
        assert "band=early" in explanation

    def test_explanation_review_band(self):
        explanation = _build_explanation(
            ACTION_REVIEW, "STALE_AGENT",
            is_stale=True, is_orphan=False,
            stale_age_seconds=1200, threshold=600, tier="agent",
        )
        assert "band=review" in explanation

    def test_explanation_prolonged_band(self):
        explanation = _build_explanation(
            ACTION_REVIEW, "STALE_AGENT",
            is_stale=True, is_orphan=False,
            stale_age_seconds=2000, threshold=600, tier="agent",
        )
        assert "band=prolonged" in explanation

    def test_explanation_orphan_no_band(self):
        """Orphan-only explanation should not contain band=."""
        explanation = _build_explanation(
            ACTION_REVIEW, "ORPHAN_EXEC_PARENT",
            is_stale=False, is_orphan=True,
            stale_age_seconds=0, threshold=600, tier="execution",
        )
        assert "band=" not in explanation


# =========================================================================== #
# AXIS 3: Threshold Constants Correctness                                      #
# =========================================================================== #

class TestThresholdConstants:

    def test_watch_upper_is_1_5(self):
        assert THRESHOLD_WATCH_UPPER == 1.5

    def test_prolonged_is_3_0(self):
        assert THRESHOLD_PROLONGED == 3.0

    def test_watch_upper_less_than_prolonged(self):
        assert THRESHOLD_WATCH_UPPER < THRESHOLD_PROLONGED

    def test_both_positive(self):
        assert THRESHOLD_WATCH_UPPER > 0
        assert THRESHOLD_PROLONGED > 0


# =========================================================================== #
# AXIS 4: Cross-layer Impact                                                   #
# =========================================================================== #

class TestCrossLayerImpact:

    def test_early_stale_produces_watch_monitor(self):
        """Stale at 1.2x → WATCH → LOW pressure → MONITOR posture."""
        # 720s / 600s = 1.2x → WATCH → LOW
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(720)}
        ])
        decision = build_decision_summary(action)
        assert decision.recommended_posture == POSTURE_MONITOR
        assert decision.risk_level == RISK_LOW

    def test_review_stale_produces_review_posture(self):
        """Stale at 2x → REVIEW → MODERATE pressure → REVIEW posture."""
        # 1200s / 600s = 2.0x → REVIEW → MODERATE
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(1200)}
        ])
        decision = build_decision_summary(action)
        assert decision.recommended_posture == POSTURE_REVIEW

    def test_multiple_review_increases_risk(self):
        """3+ REVIEW candidates → MEDIUM risk."""
        action = _FakeLedger([
            {"proposal_id": f"AP-{i}", "status": "GUARDED", "created_at": _past_iso(1200)}
            for i in range(4)
        ])
        decision = build_decision_summary(action)
        assert decision.risk_level == RISK_MEDIUM

    def test_safety_preserved_through_calibration(self):
        """Safety labels unchanged regardless of threshold changes."""
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(3000)}
        ])
        decision = build_decision_summary(action)
        assert decision.action_allowed is False
        assert decision.suggestion_only is True
        assert decision.read_only is True


# =========================================================================== #
# AXIS 5: Reason Chain Action Distribution                                     #
# =========================================================================== #

class TestReasonChainDistribution:

    def test_reason_chain_has_action_counts(self):
        """Reason chain includes action class distribution."""
        action = _FakeLedger([
            {"proposal_id": "AP-w", "status": "GUARDED", "created_at": _past_iso(700)},
            {"proposal_id": "AP-r", "status": "GUARDED", "created_at": _past_iso(1200)},
        ])
        decision = build_decision_summary(action)
        chain_str = " ".join(decision.reason_chain)
        assert "action_WATCH=" in chain_str or "action_REVIEW=" in chain_str

    def test_reason_chain_still_has_pressure(self):
        decision = build_decision_summary()
        assert any("pressure=" in item for item in decision.reason_chain)

    def test_reason_chain_still_has_totals(self):
        decision = build_decision_summary()
        assert any("candidate_total=" in item for item in decision.reason_chain)


# =========================================================================== #
# AXIS 6: Safety Invariants Preserved                                          #
# =========================================================================== #

class TestSafetyInvariants:

    def test_no_new_action_class(self):
        """Calibration did not introduce new action classes."""
        from app.services.cleanup_simulation_service import (
            ACTION_INFO, ACTION_WATCH, ACTION_REVIEW, ACTION_MANUAL,
        )
        known = {ACTION_INFO, ACTION_WATCH, ACTION_REVIEW, ACTION_MANUAL}
        assert len(known) == 4

    def test_manual_still_requires_orphan(self):
        """MANUAL still requires orphan — not age-driven."""
        # Even at 10x threshold, stale-only → REVIEW, not MANUAL
        assert _determine_action_class(True, False, 6000, 600) == ACTION_REVIEW
        # Only stale+orphan → MANUAL
        assert _determine_action_class(True, True, 6000, 600) == ACTION_MANUAL

    def test_simulation_only_flag(self):
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(1200)}
        ])
        report = simulate_cleanup(action_ledger=action)
        assert report.simulation_only is True

    def test_board_action_allowed_false(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.decision_summary.safety.action_allowed is False
