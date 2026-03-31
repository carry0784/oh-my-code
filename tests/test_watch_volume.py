"""
K-Dexter WATCH Volume Observation Tests

Sprint Contract: Phase C — WATCH Volume Observation Card

Tests the WATCH volume observation card (symmetric to REVIEW Volume):
  AXIS 1: Volume Accuracy (watch count, ratio, total alignment)
  AXIS 2: Tier Distribution (per-tier WATCH breakdown)
  AXIS 3: Reason Distribution (per-reason-code WATCH breakdown)
  AXIS 4: Band Distribution (early/review/prolonged breakdown)
  AXIS 5: Density Signal (concentration, prolonged detection)
  AXIS 6: Safety Invariants (read-only, no prediction, no write)
  AXIS 7: Schema Drift Sentinel (field count/name snapshot)
  AXIS 8: Board Integration (schema field, typed return, safety, JSON)

Run: pytest tests/test_watch_volume.py -v
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

from app.services.watch_volume_service import build_watch_volume
from app.schemas.watch_volume_schema import (
    WatchVolumeSchema,
    WatchTierDistribution,
    WatchReasonDistribution,
    WatchBandDistribution,
    WatchDensitySignal,
    WatchVolumeSafety,
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


def _agent_ledger_with_stale(count, age_seconds=700):
    """Create agent ledger with stale proposals. Default 700s = 1.17x → WATCH band."""
    proposals = [
        {"proposal_id": f"AP-{i}", "status": "GUARDED",
         "created_at": _past_iso(age_seconds)}
        for i in range(count)
    ]
    return _FakeLedger(proposals, stale_count=count)


def _exec_ledger_with_stale(count, age_seconds=350):
    """Create execution ledger with stale proposals (threshold=300s). 350s=1.17x → WATCH."""
    proposals = [
        {"proposal_id": f"EP-{i}", "status": "EXEC_GUARDED",
         "created_at": _past_iso(age_seconds),
         "agent_proposal_id": f"AP-{i}"}
        for i in range(count)
    ]
    return _FakeLedger(proposals, stale_count=count)


# =========================================================================== #
# AXIS 1: Volume Accuracy                                                     #
# =========================================================================== #

class TestWatchVolumeAccuracy:

    def test_zero_candidates_zero_watch(self):
        vol = build_watch_volume()
        assert vol.watch_total == 0
        assert vol.candidate_total == 0
        assert vol.watch_ratio == 0.0

    def test_stale_above_1x_becomes_watch(self):
        """Agent stale at 700s (1.17x of 600) → WATCH."""
        action = _agent_ledger_with_stale(1, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.watch_total >= 1

    def test_watch_ratio_calculation(self):
        """watch_ratio = watch_total / candidate_total."""
        action = _agent_ledger_with_stale(2, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        if vol.candidate_total > 0:
            expected_ratio = vol.watch_total / vol.candidate_total
            assert abs(vol.watch_ratio - round(expected_ratio, 3)) < 0.01

    def test_candidate_total_matches_simulation(self):
        action = _agent_ledger_with_stale(3, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.candidate_total >= 3

    def test_review_candidates_not_counted_as_watch(self):
        """Stale at 900s (1.5x) → REVIEW, not WATCH."""
        action = _agent_ledger_with_stale(1, age_seconds=900)
        vol = build_watch_volume(action_ledger=action)
        assert vol.watch_total == 0


# =========================================================================== #
# AXIS 2: Tier Distribution                                                    #
# =========================================================================== #

class TestWatchTierDistribution:

    def test_agent_tier_counted(self):
        action = _agent_ledger_with_stale(2, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.by_tier.agent >= 2

    def test_execution_tier_counted(self):
        action = _agent_ledger_with_stale(1, age_seconds=700)
        execution = _exec_ledger_with_stale(1, age_seconds=350)
        vol = build_watch_volume(action_ledger=action, execution_ledger=execution)
        assert vol.by_tier.execution >= 1

    def test_empty_tiers_are_zero(self):
        vol = build_watch_volume()
        assert vol.by_tier.agent == 0
        assert vol.by_tier.execution == 0
        assert vol.by_tier.submit == 0

    def test_tier_sum_equals_watch_total(self):
        action = _agent_ledger_with_stale(3, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        tier_sum = vol.by_tier.agent + vol.by_tier.execution + vol.by_tier.submit
        assert tier_sum == vol.watch_total

    def test_tier_distribution_is_typed(self):
        vol = build_watch_volume()
        assert isinstance(vol.by_tier, WatchTierDistribution)


# =========================================================================== #
# AXIS 3: Reason Distribution                                                  #
# =========================================================================== #

class TestWatchReasonDistribution:

    def test_stale_agent_reason_counted(self):
        action = _agent_ledger_with_stale(2, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.by_reason.stale_agent >= 2

    def test_empty_reasons_are_zero(self):
        vol = build_watch_volume()
        assert vol.by_reason.stale_agent == 0
        assert vol.by_reason.stale_execution == 0
        assert vol.by_reason.orphan_exec_parent == 0

    def test_reason_sum_equals_watch_total(self):
        action = _agent_ledger_with_stale(3, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        reason_sum = (
            vol.by_reason.stale_agent + vol.by_reason.stale_execution
            + vol.by_reason.stale_submit + vol.by_reason.orphan_exec_parent
            + vol.by_reason.orphan_submit_parent + vol.by_reason.stale_and_orphan
        )
        assert reason_sum == vol.watch_total

    def test_reason_distribution_is_typed(self):
        vol = build_watch_volume()
        assert isinstance(vol.by_reason, WatchReasonDistribution)


# =========================================================================== #
# AXIS 4: Band Distribution                                                    #
# =========================================================================== #

class TestWatchBandDistribution:

    def test_early_band_at_1_17x(self):
        """700s / 600s = 1.17x → early band."""
        action = _agent_ledger_with_stale(1, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.by_band.early >= 1

    def test_empty_bands_are_zero(self):
        vol = build_watch_volume()
        assert vol.by_band.early == 0
        assert vol.by_band.review == 0
        assert vol.by_band.prolonged == 0

    def test_band_distribution_is_typed(self):
        vol = build_watch_volume()
        assert isinstance(vol.by_band, WatchBandDistribution)

    def test_band_sum_matches_stale_watch_candidates(self):
        """Band counts should sum to number of stale WATCH candidates."""
        action = _agent_ledger_with_stale(3, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        band_sum = vol.by_band.early + vol.by_band.review + vol.by_band.prolonged
        stale_watch = vol.by_reason.stale_agent + vol.by_reason.stale_execution + vol.by_reason.stale_submit
        assert band_sum == stale_watch


# =========================================================================== #
# AXIS 5: Density Signal                                                       #
# =========================================================================== #

class TestWatchDensitySignal:

    def test_no_candidates_description(self):
        vol = build_watch_volume()
        assert vol.density.description == "No WATCH candidates."
        assert vol.density.is_concentrated is False

    def test_concentrated_when_single_tier_dominant(self):
        """3 in agent, 0 in others → 100% → concentrated."""
        action = _agent_ledger_with_stale(3, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        if vol.watch_total > 0:
            assert vol.density.is_concentrated is True
            assert vol.density.dominant_tier == "agent"

    def test_dominant_ratio_calculated(self):
        action = _agent_ledger_with_stale(2, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        if vol.watch_total > 0:
            assert vol.density.dominant_ratio > 0

    def test_no_prolonged_for_watch_candidates(self):
        """WATCH candidates at 1.17x should not be in prolonged band."""
        action = _agent_ledger_with_stale(1, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.density.has_prolonged is False

    def test_density_signal_is_typed(self):
        vol = build_watch_volume()
        assert isinstance(vol.density, WatchDensitySignal)

    def test_description_includes_count(self):
        action = _agent_ledger_with_stale(2, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        if vol.watch_total > 0:
            assert "WATCH candidate" in vol.density.description


# =========================================================================== #
# AXIS 6: Safety Invariants                                                    #
# =========================================================================== #

class TestWatchSafetyInvariants:

    def test_safety_all_true_empty(self):
        vol = build_watch_volume()
        assert vol.safety.read_only is True
        assert vol.safety.simulation_only is True
        assert vol.safety.no_action_executed is True
        assert vol.safety.no_prediction is True

    def test_safety_all_true_with_data(self):
        action = _agent_ledger_with_stale(3, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        assert vol.safety.read_only is True
        assert vol.safety.no_prediction is True

    def test_safety_has_four_fields(self):
        fields = set(WatchVolumeSafety.model_fields.keys())
        assert fields == {"read_only", "simulation_only", "no_action_executed", "no_prediction"}

    def test_source_has_no_write_methods(self):
        import inspect
        import app.services.watch_volume_service as mod
        source = inspect.getsource(mod)
        forbidden = ["propose_and_guard", "record_receipt", "transition_to",
                      ".delete(", ".remove(", ".write("]
        for keyword in forbidden:
            assert keyword not in source, f"Forbidden keyword '{keyword}' in source"

    def test_source_has_no_prediction_keywords(self):
        import inspect
        import app.services.watch_volume_service as mod
        source = inspect.getsource(mod)
        forbidden = ["predict", "forecast", "score(", "auto_promote",
                      "auto_escalate", "auto_judge"]
        for keyword in forbidden:
            assert keyword not in source, f"Prediction keyword '{keyword}' in source"

    def test_serializes_to_json(self):
        action = _agent_ledger_with_stale(2, age_seconds=700)
        vol = build_watch_volume(action_ledger=action)
        j = json.loads(vol.model_dump_json())
        assert "watch_total" in j
        assert "safety" in j
        assert j["safety"]["no_prediction"] is True


# =========================================================================== #
# AXIS 7: Schema Drift Sentinel                                                #
# =========================================================================== #

class TestWatchSchemaDriftSentinel:

    def test_watch_volume_field_count(self):
        assert len(WatchVolumeSchema.model_fields) == 8

    def test_watch_volume_field_names(self):
        expected = {
            "watch_total", "candidate_total", "watch_ratio",
            "by_tier", "by_reason", "by_band", "density", "safety",
        }
        assert set(WatchVolumeSchema.model_fields.keys()) == expected

    def test_tier_distribution_field_count(self):
        assert len(WatchTierDistribution.model_fields) == 3

    def test_reason_distribution_field_count(self):
        assert len(WatchReasonDistribution.model_fields) == 6

    def test_band_distribution_field_count(self):
        assert len(WatchBandDistribution.model_fields) == 3

    def test_density_signal_field_count(self):
        assert len(WatchDensitySignal.model_fields) == 6

    def test_safety_field_count(self):
        assert len(WatchVolumeSafety.model_fields) == 4


# =========================================================================== #
# AXIS 8: Board Integration                                                    #
# =========================================================================== #

class TestWatchBoardIntegration:

    def test_board_schema_has_watch_volume(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        assert "watch_volume" in FourTierBoardResponse.model_fields

    def test_board_schema_watch_volume_is_typed(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        field_info = FourTierBoardResponse.model_fields["watch_volume"]
        assert field_info.annotation is WatchVolumeSchema

    def test_board_service_returns_typed_watch_volume(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert isinstance(board.watch_volume, WatchVolumeSchema)

    def test_board_watch_volume_safety_intact(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.watch_volume.safety.read_only is True
        assert board.watch_volume.safety.no_prediction is True

    def test_board_watch_volume_with_data(self):
        from app.services.four_tier_board_service import build_four_tier_board
        action = _agent_ledger_with_stale(2, age_seconds=700)
        board = build_four_tier_board(action_ledger=action)
        assert board.watch_volume.watch_total >= 2

    def test_board_serializes_watch_volume_to_json(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        assert "watch_volume" in j
        assert "watch_total" in j["watch_volume"]
        assert j["watch_volume"]["safety"]["no_prediction"] is True

    def test_board_watch_volume_empty_is_zero_safe(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.watch_volume.watch_total == 0
        assert board.watch_volume.candidate_total == 0
        assert board.watch_volume.watch_ratio == 0.0
