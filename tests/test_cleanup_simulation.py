"""
K-Dexter Cleanup Simulation Tests

Sprint Contract: CARD-2026-0330-CLEANUP-SIM (Level B)

Tests the cleanup simulation & operator action policy:
  AXIS 1: Candidate Classification Accuracy (stale/orphan → correct action class)
  AXIS 2: Reason Code Accuracy (6 standard codes correctly assigned)
  AXIS 3: Action Class Decision Logic (4-tier boundary values)
  AXIS 4: Impact Simulation (by_tier, by_action, by_reason aggregation)
  AXIS 5: Read-Only Guarantee (no write methods, simulation_only=True)
  AXIS 6: Dashboard Integration (cleanup_candidate_count in board)
  AXIS 7: Edge Cases (empty ledgers, all normal, partial observation)

Run: pytest tests/test_cleanup_simulation.py -v
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
    """Minimal ledger mock returning proposals from get_proposals()."""
    def __init__(self, proposals: list[dict]):
        self._data = proposals

    def get_proposals(self) -> list[dict]:
        return self._data

    def get_board(self) -> dict:
        return {
            "total": len(self._data), "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": 0,
            "stale_threshold_seconds": 600.0, "guard_reason_top": [],
        }


# -- Imports ---------------------------------------------------------------- #

from app.services.cleanup_simulation_service import (
    simulate_cleanup,
    CleanupCandidate,
    CleanupSimulationReport,
    _determine_action_class,
    _determine_reason_code,
    _build_explanation,
    ACTION_INFO,
    ACTION_WATCH,
    ACTION_REVIEW,
    ACTION_MANUAL,
    ACTION_POSTURE,
    REASON_STALE_AGENT,
    REASON_STALE_EXECUTION,
    REASON_STALE_SUBMIT,
    REASON_ORPHAN_EXEC_PARENT,
    REASON_ORPHAN_SUBMIT_PARENT,
    REASON_STALE_AND_ORPHAN,
    _VALID_REASON_CODES,
    _TERMINAL_STATES_BY_TIER,
)


# =========================================================================== #
# AXIS 1: Candidate Classification Accuracy                                    #
# =========================================================================== #

class TestCandidateClassification:
    """stale/orphan proposals correctly classified."""

    def test_stale_only_becomes_watch_or_review(self):
        """Stale-only proposal gets WATCH (< 1.5x threshold) or REVIEW (>= 1.5x)."""
        # Agent with 700s age (threshold 600 → < 1.5x=900 → WATCH)
        action = _FakeLedger([
            {"proposal_id": "AP-stale", "status": "GUARDED", "created_at": _past_iso(700)}
        ])
        report = simulate_cleanup(action_ledger=action)
        assert report.total_candidates == 1
        assert report.candidates[0]["action_class"] == ACTION_WATCH

    def test_very_stale_becomes_review(self):
        """Stale proposal with age >= 1.5x threshold gets REVIEW."""
        # Agent with 1300s age (threshold 600 → >= 1.5x=900 → REVIEW)
        action = _FakeLedger([
            {"proposal_id": "AP-very-stale", "status": "GUARDED", "created_at": _past_iso(1300)}
        ])
        report = simulate_cleanup(action_ledger=action)
        assert report.total_candidates == 1
        assert report.candidates[0]["action_class"] == ACTION_REVIEW

    def test_orphan_only_becomes_review(self):
        """Orphan-only proposal gets REVIEW."""
        # Execution orphan: parent AP-GONE doesn't exist in action
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-orphan", "agent_proposal_id": "AP-GONE",
             "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution)
        orphan_candidates = [c for c in report.candidates if c["is_orphan"]]
        assert len(orphan_candidates) >= 1
        assert orphan_candidates[0]["action_class"] == ACTION_REVIEW

    def test_stale_and_orphan_becomes_manual(self):
        """Both stale + orphan → MANUAL_CLEANUP_CANDIDATE."""
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        # EP-both: old (stale) + parent missing (orphan)
        execution = _FakeLedger([
            {"proposal_id": "EP-both", "agent_proposal_id": "AP-GONE",
             "status": "EXEC_GUARDED", "created_at": _past_iso(400)}
        ])
        report = simulate_cleanup(
            action_ledger=action, execution_ledger=execution,
            execution_stale_threshold=300.0,
        )
        both_candidates = [c for c in report.candidates if c["proposal_id"] == "EP-both"]
        assert len(both_candidates) == 1
        assert both_candidates[0]["is_stale"] is True
        assert both_candidates[0]["is_orphan"] is True
        assert both_candidates[0]["action_class"] == ACTION_MANUAL

    def test_normal_proposal_not_candidate(self):
        """Fresh proposal with valid lineage → not a candidate."""
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}
        ])
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "AP-1",
             "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution)
        assert report.total_candidates == 0


# =========================================================================== #
# AXIS 2: Reason Code Accuracy                                                #
# =========================================================================== #

class TestReasonCodeAccuracy:
    """6 standard reason codes correctly assigned."""

    def test_stale_agent_reason(self):
        action = _FakeLedger([
            {"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(700)}
        ])
        report = simulate_cleanup(action_ledger=action)
        assert report.candidates[0]["reason_code"] == REASON_STALE_AGENT

    def test_stale_execution_reason(self):
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-s", "agent_proposal_id": "AP-1",
             "status": "EXEC_GUARDED", "created_at": _past_iso(400)}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution,
                                  execution_stale_threshold=300.0)
        stale_exec = [c for c in report.candidates if c["proposal_id"] == "EP-s"]
        assert len(stale_exec) == 1
        assert stale_exec[0]["reason_code"] == REASON_STALE_EXECUTION

    def test_orphan_exec_parent_reason(self):
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-o", "agent_proposal_id": "AP-MISSING",
             "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution)
        orphans = [c for c in report.candidates if c["is_orphan"]]
        assert any(c["reason_code"] == REASON_ORPHAN_EXEC_PARENT for c in orphans)

    def test_orphan_submit_parent_reason(self):
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "AP-1",
             "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        ])
        submit = _FakeLedger([
            {"proposal_id": "SP-o", "execution_proposal_id": "EP-MISSING",
             "status": "SUBMIT_GUARDED", "created_at": _now_iso()}
        ])
        report = simulate_cleanup(execution_ledger=execution, submit_ledger=submit)
        orphans = [c for c in report.candidates if c["is_orphan"]]
        assert any(c["reason_code"] == REASON_ORPHAN_SUBMIT_PARENT for c in orphans)

    def test_stale_and_orphan_reason(self):
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-so", "agent_proposal_id": "AP-GONE",
             "status": "EXEC_GUARDED", "created_at": _past_iso(400)}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution,
                                  execution_stale_threshold=300.0)
        both = [c for c in report.candidates if c["proposal_id"] == "EP-so"]
        assert both[0]["reason_code"] == REASON_STALE_AND_ORPHAN

    def test_all_reason_codes_are_valid(self):
        """All reason codes in _VALID_REASON_CODES are exactly 6."""
        assert len(_VALID_REASON_CODES) == 6


# =========================================================================== #
# AXIS 3: Action Class Decision Logic                                          #
# =========================================================================== #

class TestActionClassDecisionLogic:
    """4-tier boundary value tests for _determine_action_class."""

    def test_info_when_neither_stale_nor_orphan(self):
        assert _determine_action_class(False, False, 0, 600) == ACTION_INFO

    def test_watch_when_stale_below_1_5x(self):
        # 700s / 600s = 1.17x → < 1.5x → WATCH
        assert _determine_action_class(True, False, 700, 600) == ACTION_WATCH

    def test_review_when_stale_at_1_5x(self):
        """At exactly 1.5x threshold → REVIEW."""
        # 900s / 600s = 1.5x → >= 1.5x → REVIEW
        assert _determine_action_class(True, False, 900, 600) == ACTION_REVIEW

    def test_watch_just_below_1_5x(self):
        """Just below 1.5x → still WATCH."""
        # 899s / 600s = 1.498x → < 1.5x → WATCH
        assert _determine_action_class(True, False, 899, 600) == ACTION_WATCH

    def test_review_when_orphan_only(self):
        assert _determine_action_class(False, True, 0, 600) == ACTION_REVIEW

    def test_manual_when_both(self):
        assert _determine_action_class(True, True, 700, 600) == ACTION_MANUAL

    def test_review_when_stale_above_1_5x(self):
        assert _determine_action_class(True, False, 1500, 600) == ACTION_REVIEW


# =========================================================================== #
# AXIS 4: Impact Simulation                                                    #
# =========================================================================== #

class TestImpactSimulation:
    """by_tier, by_action_class, by_reason aggregation accuracy."""

    def test_by_tier_aggregation(self):
        """Candidates from multiple tiers → correct tier counts."""
        action = _FakeLedger([
            {"proposal_id": "AP-s1", "status": "GUARDED", "created_at": _past_iso(700)},
            {"proposal_id": "AP-s2", "status": "GUARDED", "created_at": _past_iso(800)},
        ])
        execution = _FakeLedger([
            {"proposal_id": "EP-s1", "agent_proposal_id": "AP-s1",
             "status": "EXEC_GUARDED", "created_at": _past_iso(400)}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution,
                                  execution_stale_threshold=300.0)
        assert report.by_tier.get("agent", 0) == 2
        assert report.by_tier.get("execution", 0) >= 1

    def test_by_action_class_aggregation(self):
        """Action class counts sum to total_candidates."""
        action = _FakeLedger([
            {"proposal_id": "AP-s1", "status": "GUARDED", "created_at": _past_iso(700)},
            {"proposal_id": "AP-s2", "status": "GUARDED", "created_at": _past_iso(1300)},
        ])
        report = simulate_cleanup(action_ledger=action)
        total_from_actions = sum(report.by_action_class.values())
        assert total_from_actions == report.total_candidates

    def test_by_reason_aggregation(self):
        """Reason counts sum to total_candidates."""
        action = _FakeLedger([
            {"proposal_id": "AP-s1", "status": "GUARDED", "created_at": _past_iso(700)},
        ])
        report = simulate_cleanup(action_ledger=action)
        total_from_reasons = sum(report.by_reason.values())
        assert total_from_reasons == report.total_candidates

    def test_write_impact_always_zero(self):
        """write_impact is always 0 regardless of candidates."""
        action = _FakeLedger([
            {"proposal_id": "AP-s1", "status": "GUARDED", "created_at": _past_iso(9999)},
        ])
        report = simulate_cleanup(action_ledger=action)
        assert report.write_impact == 0
        assert report.terminal_impact == 0
        assert report.simulation_only is True


# =========================================================================== #
# AXIS 5: Read-Only Guarantee                                                  #
# =========================================================================== #

class TestReadOnlyGuarantee:
    """Cleanup simulation service is strictly read-only."""

    def test_source_has_no_propose_and_guard(self):
        import app.services.cleanup_simulation_service as mod
        source = inspect.getsource(mod)
        assert ".propose_and_guard(" not in source

    def test_source_has_no_record_receipt(self):
        import app.services.cleanup_simulation_service as mod
        source = inspect.getsource(mod)
        assert ".record_receipt(" not in source

    def test_source_has_no_transition_to(self):
        import app.services.cleanup_simulation_service as mod
        source = inspect.getsource(mod)
        assert ".transition_to(" not in source

    def test_simulation_only_always_true(self):
        """Even empty simulation → simulation_only=True."""
        report = simulate_cleanup()
        assert report.simulation_only is True
        assert report.write_impact == 0
        assert report.terminal_impact == 0


# =========================================================================== #
# AXIS 6: Dashboard Integration                                                #
# =========================================================================== #

class TestDashboardIntegration:
    """Cleanup results appear in 4-Tier Board."""

    def test_board_schema_has_cleanup_fields(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "cleanup_candidate_count" in fields
        assert "cleanup_action_summary" in fields

    def test_board_service_populates_cleanup(self):
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
        assert hasattr(board, "cleanup_candidate_count")
        assert isinstance(board.cleanup_candidate_count, int)
        assert hasattr(board, "cleanup_action_summary")

    def test_board_cleanup_count_matches_simulation(self):
        """Board cleanup_candidate_count matches simulate_cleanup total."""
        from app.services.four_tier_board_service import build_four_tier_board

        al = MagicMock()
        al.get_board.return_value = {
            "total": 2, "receipted_count": 0, "blocked_count": 0,
            "failed_count": 0, "orphan_count": 0, "stale_count": 2,
            "stale_threshold_seconds": 600.0, "guard_reason_top": [],
        }
        al.get_proposals.return_value = [
            {"proposal_id": "AP-s1", "status": "GUARDED", "created_at": _past_iso(700)},
            {"proposal_id": "AP-s2", "status": "GUARDED", "created_at": _past_iso(800)},
        ]

        board = build_four_tier_board(action_ledger=al)
        sim = simulate_cleanup(action_ledger=_FakeLedger(al.get_proposals.return_value))
        assert board.cleanup_candidate_count == sim.total_candidates


# =========================================================================== #
# AXIS 7: Edge Cases                                                           #
# =========================================================================== #

class TestEdgeCases:
    """Empty ledgers, all normal, partial observation."""

    def test_all_none_returns_empty_report(self):
        report = simulate_cleanup()
        assert report.total_candidates == 0
        assert report.candidates == []
        assert report.simulation_only is True

    def test_all_fresh_no_orphan_zero_candidates(self):
        """All proposals fresh + valid lineage → zero candidates."""
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}
        ])
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "agent_proposal_id": "AP-1",
             "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        ])
        submit = _FakeLedger([
            {"proposal_id": "SP-1", "execution_proposal_id": "EP-1",
             "status": "SUBMIT_RECEIPTED", "created_at": _now_iso()}
        ])
        report = simulate_cleanup(action, execution, submit)
        assert report.total_candidates == 0

    def test_report_to_dict_serializable(self):
        """Report.to_dict() returns JSON-serializable dict."""
        import json
        report = simulate_cleanup()
        d = report.to_dict()
        assert isinstance(d, dict)
        json.dumps(d)  # must not raise

    def test_candidate_to_dict(self):
        c = CleanupCandidate(
            proposal_id="AP-1", tier="agent",
            action_class=ACTION_WATCH, reason_code=REASON_STALE_AGENT,
            is_stale=True, is_orphan=False,
            stale_age_seconds=700.0, current_status="GUARDED",
        )
        d = c.to_dict()
        assert d["proposal_id"] == "AP-1"
        assert d["action_class"] == "WATCH"

    def test_custom_thresholds_respected(self):
        """Custom stale thresholds override defaults."""
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(100)}
        ])
        # Default threshold 600 → not stale; custom 50 → stale
        report_default = simulate_cleanup(action_ledger=action, agent_stale_threshold=600.0)
        report_custom = simulate_cleanup(action_ledger=action, agent_stale_threshold=50.0)
        assert report_default.total_candidates == 0
        assert report_custom.total_candidates == 1

    def test_terminal_agent_not_stale_candidate(self):
        """RECEIPTED agent proposal is never a stale candidate (terminal exclusion)."""
        action = _FakeLedger([
            {"proposal_id": "AP-done", "status": "RECEIPTED", "created_at": _past_iso(9999)}
        ])
        report = simulate_cleanup(action_ledger=action)
        stale_candidates = [c for c in report.candidates if c["is_stale"] and c["proposal_id"] == "AP-done"]
        assert len(stale_candidates) == 0

    def test_terminal_exec_blocked_not_stale_candidate(self):
        """EXEC_BLOCKED execution proposal is never a stale candidate."""
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-blocked", "agent_proposal_id": "AP-1",
             "status": "EXEC_BLOCKED", "created_at": _past_iso(9999)}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution)
        stale_execs = [c for c in report.candidates if c["is_stale"] and c["proposal_id"] == "EP-blocked"]
        assert len(stale_execs) == 0

    def test_terminal_submit_failed_not_stale_candidate(self):
        """SUBMIT_FAILED submit proposal is never a stale candidate."""
        execution = _FakeLedger([
            {"proposal_id": "EP-1", "status": "EXEC_RECEIPTED", "created_at": _now_iso()}
        ])
        submit = _FakeLedger([
            {"proposal_id": "SP-fail", "execution_proposal_id": "EP-1",
             "status": "SUBMIT_FAILED", "created_at": _past_iso(9999)}
        ])
        report = simulate_cleanup(execution_ledger=execution, submit_ledger=submit)
        stale_submits = [c for c in report.candidates if c["is_stale"] and c["proposal_id"] == "SP-fail"]
        assert len(stale_submits) == 0


# =========================================================================== #
# AXIS 8: Explanation & Posture (C inspector recommendation)                   #
# =========================================================================== #

class TestExplanationAndPosture:
    """Explanation field and operator posture for interpretability."""

    def test_stale_candidate_has_explanation(self):
        """Stale candidate includes human-readable explanation."""
        action = _FakeLedger([
            {"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(700)}
        ])
        report = simulate_cleanup(action_ledger=action)
        assert report.candidates[0]["explanation"] != ""
        assert "Stale" in report.candidates[0]["explanation"]

    def test_orphan_candidate_has_explanation(self):
        """Orphan candidate explanation mentions missing parent."""
        action = _FakeLedger([{"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}])
        execution = _FakeLedger([
            {"proposal_id": "EP-o", "agent_proposal_id": "AP-GONE",
             "status": "EXEC_GUARDED", "created_at": _now_iso()}
        ])
        report = simulate_cleanup(action_ledger=action, execution_ledger=execution)
        orphans = [c for c in report.candidates if c["is_orphan"]]
        assert len(orphans) >= 1
        assert "parent" in orphans[0]["explanation"].lower() or "orphan" in orphans[0]["explanation"].lower()

    def test_explanation_includes_posture(self):
        """Explanation includes the operator posture guidance."""
        action = _FakeLedger([
            {"proposal_id": "AP-s", "status": "GUARDED", "created_at": _past_iso(700)}
        ])
        report = simulate_cleanup(action_ledger=action)
        assert "Posture:" in report.candidates[0]["explanation"]

    def test_action_posture_covers_all_classes(self):
        """ACTION_POSTURE has descriptions for all 4 action classes."""
        assert ACTION_INFO in ACTION_POSTURE
        assert ACTION_WATCH in ACTION_POSTURE
        assert ACTION_REVIEW in ACTION_POSTURE
        assert ACTION_MANUAL in ACTION_POSTURE

    def test_terminal_states_by_tier_matches_ledgers(self):
        """_TERMINAL_STATES_BY_TIER mirrors actual Ledger terminal states."""
        assert _TERMINAL_STATES_BY_TIER["agent"] == frozenset({"BLOCKED", "RECEIPTED", "FAILED"})
        assert _TERMINAL_STATES_BY_TIER["execution"] == frozenset({"EXEC_BLOCKED", "EXEC_RECEIPTED", "EXEC_FAILED"})
        assert _TERMINAL_STATES_BY_TIER["submit"] == frozenset({"SUBMIT_BLOCKED", "SUBMIT_RECEIPTED", "SUBMIT_FAILED"})

    def test_board_schema_has_simulation_only_label(self):
        """Board schema includes cleanup_simulation_only=True for UI clarity."""
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "cleanup_simulation_only" in fields
        # Default must be True
        default_val = fields["cleanup_simulation_only"].default
        assert default_val is True
