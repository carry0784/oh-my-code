"""
K-Dexter Observation Summary Tests

Sprint Contract: CARD-2026-0330-BOARD-OBS-UPGRADE (Level B)

Tests the observation summary service:
  AXIS 1: Pressure Decision Accuracy (LOW/MODERATE/HIGH/CRITICAL boundaries)
  AXIS 2: Stale Distribution (stale_by_tier aggregation)
  AXIS 3: Reason x Action Cross Table (matrix structure, sum consistency)
  AXIS 4: Top Priority Selection (MANUAL first, REVIEW second, max 5)
  AXIS 5: Safety Labels Guarantee (read_only, simulation_only, no_action_executed)
  AXIS 6: Dashboard Integration (observation_summary in board)
  AXIS 7: Edge Cases (empty, all normal, single tier, large volume)

Run: pytest tests/test_observation_summary.py -v
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

# ---------------------------------------------------------------------------
# Stub modules
# ---------------------------------------------------------------------------
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

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _past_iso(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


class _FakeLedger:
    """Minimal ledger mock."""
    def __init__(self, proposals: list[dict], stale_count: int = 0):
        self._data = proposals
        self._stale_count = stale_count

    def get_proposals(self) -> list[dict]:
        return self._data

    def get_board(self) -> dict:
        return {
            "total": len(self._data), "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": self._stale_count,
            "stale_threshold_seconds": 600.0, "guard_reason_top": [],
        }


# -- Imports ---------------------------------------------------------------- #

from app.services.observation_summary_service import (
    build_observation_summary,
    ObservationSummary,
    _determine_pressure,
    _build_reason_action_matrix,
    _select_top_priority,
    PRESSURE_LOW,
    PRESSURE_MODERATE,
    PRESSURE_HIGH,
    PRESSURE_CRITICAL,
)
from app.services.cleanup_simulation_service import (
    CleanupSimulationReport,
    ACTION_MANUAL,
    ACTION_REVIEW,
    ACTION_WATCH,
)


# =========================================================================== #
# AXIS 1: Pressure Decision Accuracy                                           #
# =========================================================================== #

class TestPressureDecision:
    """LOW/MODERATE/HIGH/CRITICAL boundary values."""

    def test_low_when_zero_candidates(self):
        report = CleanupSimulationReport(total_candidates=0)
        assert _determine_pressure(report) == PRESSURE_LOW

    def test_low_when_all_watch(self):
        report = CleanupSimulationReport(
            total_candidates=3,
            by_action_class={ACTION_WATCH: 3},
        )
        assert _determine_pressure(report) == PRESSURE_LOW

    def test_moderate_when_review_exists_no_manual(self):
        report = CleanupSimulationReport(
            total_candidates=4,
            by_action_class={ACTION_WATCH: 2, ACTION_REVIEW: 2},
        )
        assert _determine_pressure(report) == PRESSURE_MODERATE

    def test_high_when_manual_exists_below_50_pct(self):
        report = CleanupSimulationReport(
            total_candidates=5,
            by_action_class={ACTION_WATCH: 3, ACTION_MANUAL: 2},
        )
        assert _determine_pressure(report) == PRESSURE_HIGH

    def test_critical_when_manual_50_pct_or_more(self):
        report = CleanupSimulationReport(
            total_candidates=4,
            by_action_class={ACTION_WATCH: 1, ACTION_MANUAL: 3},
        )
        assert _determine_pressure(report) == PRESSURE_CRITICAL

    def test_critical_when_total_ge_10(self):
        report = CleanupSimulationReport(
            total_candidates=10,
            by_action_class={ACTION_WATCH: 10},
        )
        assert _determine_pressure(report) == PRESSURE_CRITICAL

    def test_critical_when_total_11_all_watch(self):
        """Even all WATCH, total >= 10 → CRITICAL."""
        report = CleanupSimulationReport(
            total_candidates=11,
            by_action_class={ACTION_WATCH: 11},
        )
        assert _determine_pressure(report) == PRESSURE_CRITICAL


# =========================================================================== #
# AXIS 2: Stale Distribution                                                   #
# =========================================================================== #

class TestStaleDistribution:
    """stale_by_tier aggregation from get_board()."""

    def test_stale_by_tier_all_tiers(self):
        action = _FakeLedger([], stale_count=3)
        execution = _FakeLedger([], stale_count=1)
        submit = _FakeLedger([], stale_count=2)

        summary = build_observation_summary(action, execution, submit)
        assert summary.stale_by_tier == {"agent": 3, "execution": 1, "submit": 2}
        assert summary.stale_total == 6

    def test_stale_by_tier_none_ledgers(self):
        summary = build_observation_summary(None, None, None)
        assert summary.stale_by_tier == {"agent": 0, "execution": 0, "submit": 0}
        assert summary.stale_total == 0

    def test_stale_by_tier_partial(self):
        action = _FakeLedger([], stale_count=5)
        summary = build_observation_summary(action_ledger=action)
        assert summary.stale_by_tier["agent"] == 5
        assert summary.stale_by_tier["execution"] == 0
        assert summary.stale_by_tier["submit"] == 0


# =========================================================================== #
# AXIS 3: Reason x Action Cross Table                                          #
# =========================================================================== #

class TestReasonActionMatrix:
    """Matrix structure and sum consistency."""

    def test_matrix_structure(self):
        """Each entry has reason, action, count."""
        report = CleanupSimulationReport(
            total_candidates=2,
            candidates=[
                {"reason_code": "STALE_AGENT", "action_class": "WATCH", "stale_age_seconds": 0},
                {"reason_code": "STALE_AGENT", "action_class": "WATCH", "stale_age_seconds": 0},
            ],
        )
        matrix = _build_reason_action_matrix(report)
        assert len(matrix) == 1
        assert matrix[0]["reason"] == "STALE_AGENT"
        assert matrix[0]["action"] == "WATCH"
        assert matrix[0]["count"] == 2

    def test_matrix_sum_equals_total(self):
        """Sum of matrix counts == total candidates."""
        report = CleanupSimulationReport(
            total_candidates=3,
            candidates=[
                {"reason_code": "STALE_AGENT", "action_class": "WATCH", "stale_age_seconds": 0},
                {"reason_code": "ORPHAN_EXEC_PARENT", "action_class": "REVIEW", "stale_age_seconds": 0},
                {"reason_code": "STALE_AND_ORPHAN", "action_class": "MANUAL_CLEANUP_CANDIDATE", "stale_age_seconds": 0},
            ],
        )
        matrix = _build_reason_action_matrix(report)
        total = sum(entry["count"] for entry in matrix)
        assert total == 3

    def test_matrix_multiple_reasons_same_action(self):
        """Different reasons with same action class → separate entries."""
        report = CleanupSimulationReport(
            total_candidates=2,
            candidates=[
                {"reason_code": "STALE_AGENT", "action_class": "WATCH", "stale_age_seconds": 0},
                {"reason_code": "STALE_EXECUTION", "action_class": "WATCH", "stale_age_seconds": 0},
            ],
        )
        matrix = _build_reason_action_matrix(report)
        assert len(matrix) == 2

    def test_empty_candidates_empty_matrix(self):
        report = CleanupSimulationReport(total_candidates=0, candidates=[])
        matrix = _build_reason_action_matrix(report)
        assert matrix == []


# =========================================================================== #
# AXIS 4: Top Priority Selection                                               #
# =========================================================================== #

class TestTopPrioritySelection:
    """MANUAL first, REVIEW second, max 5."""

    def test_manual_before_review(self):
        report = CleanupSimulationReport(
            total_candidates=3,
            candidates=[
                {"action_class": "WATCH", "stale_age_seconds": 999, "proposal_id": "P1"},
                {"action_class": "MANUAL_CLEANUP_CANDIDATE", "stale_age_seconds": 100, "proposal_id": "P2"},
                {"action_class": "REVIEW", "stale_age_seconds": 500, "proposal_id": "P3"},
            ],
        )
        top = _select_top_priority(report)
        assert top[0]["proposal_id"] == "P2"  # MANUAL first
        assert top[1]["proposal_id"] == "P3"  # REVIEW second

    def test_within_same_class_higher_age_first(self):
        report = CleanupSimulationReport(
            total_candidates=2,
            candidates=[
                {"action_class": "REVIEW", "stale_age_seconds": 100, "proposal_id": "P1"},
                {"action_class": "REVIEW", "stale_age_seconds": 900, "proposal_id": "P2"},
            ],
        )
        top = _select_top_priority(report)
        assert top[0]["proposal_id"] == "P2"  # Higher age first

    def test_max_5_items(self):
        candidates = [
            {"action_class": "WATCH", "stale_age_seconds": i, "proposal_id": f"P{i}"}
            for i in range(20)
        ]
        report = CleanupSimulationReport(total_candidates=20, candidates=candidates)
        top = _select_top_priority(report)
        assert len(top) == 5


# =========================================================================== #
# AXIS 5: Safety Labels Guarantee                                              #
# =========================================================================== #

class TestSafetyLabels:
    """read_only, simulation_only, no_action_executed always True."""

    def test_safety_labels_empty(self):
        summary = build_observation_summary()
        assert summary.read_only is True
        assert summary.simulation_only is True
        assert summary.no_action_executed is True

    def test_safety_labels_with_data(self):
        action = _FakeLedger([
            {"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(9999)}
        ], stale_count=1)
        summary = build_observation_summary(action_ledger=action)
        assert summary.read_only is True
        assert summary.simulation_only is True
        assert summary.no_action_executed is True

    def test_source_has_no_write_methods(self):
        import app.services.observation_summary_service as mod
        source = inspect.getsource(mod)
        assert ".propose_and_guard(" not in source
        assert ".record_receipt(" not in source
        assert ".transition_to(" not in source


# =========================================================================== #
# AXIS 6: Dashboard Integration                                                #
# =========================================================================== #

class TestDashboardIntegration:
    """observation_summary in 4-Tier Board."""

    def test_board_schema_has_observation_summary(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "observation_summary" in fields

    def test_board_service_populates_observation_summary(self):
        from app.services.four_tier_board_service import build_four_tier_board

        al = MagicMock()
        al.get_board.return_value = {
            "total": 1, "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": 1,
            "stale_threshold_seconds": 600.0, "guard_reason_top": [],
        }
        al.get_proposals.return_value = [
            {"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(700)}
        ]

        board = build_four_tier_board(action_ledger=al)
        assert hasattr(board.observation_summary, "cleanup_pressure")
        assert hasattr(board.observation_summary, "stale_total")
        assert hasattr(board.observation_summary, "safety")
        assert board.observation_summary.safety.simulation_only is True

    def test_board_observation_summary_has_safety_labels(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()  # all None
        safety = board.observation_summary.safety
        assert safety.read_only is True
        assert safety.simulation_only is True
        assert safety.no_action_executed is True


# =========================================================================== #
# AXIS 7: Edge Cases                                                           #
# =========================================================================== #

class TestEdgeCases:
    """Empty, all normal, single tier, large volume."""

    def test_all_none_returns_low_pressure(self):
        summary = build_observation_summary()
        assert summary.cleanup_pressure == PRESSURE_LOW
        assert summary.candidate_total == 0
        assert summary.orphan_total == 0

    def test_all_fresh_valid_lineage(self):
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}
        ])
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "AP-1",
             "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        ])
        summary = build_observation_summary(action, execution)
        assert summary.cleanup_pressure == PRESSURE_LOW
        assert summary.candidate_total == 0

    def test_single_tier_stale(self):
        action = _FakeLedger([
            {"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(700)}
        ], stale_count=1)
        summary = build_observation_summary(action_ledger=action)
        assert summary.stale_total >= 1
        assert summary.candidate_total >= 1

    def test_to_dict_serializable(self):
        import json
        summary = build_observation_summary()
        d = summary.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise

    def test_orphan_total_matches_cross_tier(self):
        """orphan_total matches detect_orphans total."""
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "AP-GONE",
             "status": "EXEC_GUARDED", "created_at": _now_iso()},
            {"proposal_id": "EP-2", "agent_proposal_id": "AP-ALSO-GONE",
             "status": "EXEC_GUARDED", "created_at": _now_iso()},
        ])
        summary = build_observation_summary(action, execution)
        assert summary.orphan_total == 2
