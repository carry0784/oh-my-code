"""
K-Dexter Observation Summary Schema Tests

Sprint Contract: CARD-2026-0331-OBSERVATION-SCHEMA-TYPING (Level B)

Tests the typed observation summary schema:
  AXIS 1: PressureEnum Constraints
  AXIS 2: ObservationSafety Structural Fixation
  AXIS 3: Schema Field Contracts (types, defaults, nested models)
  AXIS 4: Dataclass-to-Schema Conversion (to_schema fidelity)
  AXIS 5: Board Integration (typed field in FourTierBoardResponse)
  AXIS 6: Source/Derived Layer Relationship
  AXIS 7: Schema Drift Sentinel (snapshot contract)

Run: pytest tests/test_observation_summary_schema.py -v
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

from app.schemas.observation_summary_schema import (
    ObservationSummarySchema,
    ObservationSafety,
    ReasonActionEntry,
    TopPriorityCandidate,
)
from app.schemas.decision_summary_schema import PressureEnum
from app.services.observation_summary_service import (
    build_observation_summary,
    ObservationSummary,
    PRESSURE_LOW,
    PRESSURE_MODERATE,
    PRESSURE_HIGH,
    PRESSURE_CRITICAL,
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
# AXIS 1: PressureEnum Constraints                                            #
# =========================================================================== #

class TestPressureEnumConstraints:

    def test_pressure_enum_has_four_values(self):
        values = {e.value for e in PressureEnum}
        assert values == {"LOW", "MODERATE", "HIGH", "CRITICAL"}

    def test_schema_default_pressure_is_low(self):
        schema = ObservationSummarySchema()
        assert schema.cleanup_pressure == "LOW"

    def test_schema_accepts_all_pressure_values(self):
        for pressure in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            schema = ObservationSummarySchema(cleanup_pressure=pressure)
            assert schema.cleanup_pressure == pressure

    def test_schema_rejects_invalid_pressure(self):
        with pytest.raises(Exception):
            ObservationSummarySchema(cleanup_pressure="INVALID")

    def test_pressure_enum_reused_from_decision_schema(self):
        """PressureEnum is shared between observation and decision schemas."""
        from app.schemas.decision_summary_schema import PressureEnum as DecPressure
        from app.schemas.observation_summary_schema import PressureEnum as ObsPressure
        # They should be the exact same class (imported, not duplicated)
        assert DecPressure is ObsPressure


# =========================================================================== #
# AXIS 2: ObservationSafety Structural Fixation                               #
# =========================================================================== #

class TestObservationSafety:

    def test_default_safety_all_true(self):
        safety = ObservationSafety()
        assert safety.read_only is True
        assert safety.simulation_only is True
        assert safety.no_action_executed is True

    def test_schema_default_safety_all_true(self):
        schema = ObservationSummarySchema()
        assert schema.safety.read_only is True
        assert schema.safety.simulation_only is True
        assert schema.safety.no_action_executed is True

    def test_safety_has_exactly_four_fields(self):
        fields = set(ObservationSafety.model_fields.keys())
        assert fields == {"read_only", "simulation_only", "no_action_executed", "no_prediction"}

    def test_safety_serializes_correctly(self):
        safety = ObservationSafety()
        d = safety.model_dump()
        assert d == {
            "read_only": True,
            "simulation_only": True,
            "no_action_executed": True,
            "no_prediction": True,
        }

    def test_safety_from_json_roundtrip(self):
        safety = ObservationSafety()
        j = safety.model_dump_json()
        restored = ObservationSafety.model_validate_json(j)
        assert restored.read_only is True
        assert restored.simulation_only is True
        assert restored.no_action_executed is True


# =========================================================================== #
# AXIS 3: Schema Field Contracts                                               #
# =========================================================================== #

class TestSchemaFieldContracts:

    def test_default_schema_has_zero_counts(self):
        schema = ObservationSummarySchema()
        assert schema.stale_total == 0
        assert schema.orphan_total == 0
        assert schema.candidate_total == 0

    def test_default_stale_by_tier_is_empty_dict(self):
        schema = ObservationSummarySchema()
        assert schema.stale_by_tier == {}

    def test_default_matrix_is_empty_list(self):
        schema = ObservationSummarySchema()
        assert schema.reason_action_matrix == []

    def test_default_top_priority_is_empty_list(self):
        schema = ObservationSummarySchema()
        assert schema.top_priority_candidates == []

    def test_reason_action_entry_fields(self):
        entry = ReasonActionEntry(reason="STALE_AGENT", action="WATCH", count=2)
        assert entry.reason == "STALE_AGENT"
        assert entry.action == "WATCH"
        assert entry.count == 2

    def test_top_priority_candidate_fields(self):
        candidate = TopPriorityCandidate(
            proposal_id="AP-1", tier="agent", action_class="REVIEW",
            reason_code="STALE_AGENT", is_stale=True, is_orphan=False,
            stale_age_seconds=900.0, current_status="GUARDED",
            explanation="Stale in agent tier.",
        )
        assert candidate.proposal_id == "AP-1"
        assert candidate.is_stale is True
        assert candidate.stale_age_seconds == 900.0

    def test_schema_serializes_to_json(self):
        schema = ObservationSummarySchema(
            cleanup_pressure="MODERATE",
            stale_total=3,
            orphan_total=1,
            candidate_total=4,
            stale_by_tier={"agent": 2, "execution": 1},
            reason_action_matrix=[
                ReasonActionEntry(reason="STALE_AGENT", action="REVIEW", count=2),
            ],
        )
        j = json.loads(schema.model_dump_json())
        assert j["cleanup_pressure"] == "MODERATE"
        assert j["stale_total"] == 3
        assert j["safety"]["read_only"] is True

    def test_schema_fields_complete_set(self):
        expected = {
            "cleanup_pressure", "stale_total", "orphan_total", "candidate_total",
            "stale_by_tier", "reason_action_matrix", "top_priority_candidates",
            "safety",
        }
        actual = set(ObservationSummarySchema.model_fields.keys())
        assert expected == actual

    def test_use_enum_values_enabled(self):
        """model_config has use_enum_values=True for JSON serialization."""
        config = ObservationSummarySchema.model_config
        assert config.get("use_enum_values") is True


# =========================================================================== #
# AXIS 4: Dataclass-to-Schema Conversion                                      #
# =========================================================================== #

class TestDataclassToSchema:

    def test_to_schema_returns_observation_summary_schema(self):
        obs = ObservationSummary()
        schema = obs.to_schema()
        assert isinstance(schema, ObservationSummarySchema)

    def test_to_schema_preserves_pressure(self):
        obs = ObservationSummary(cleanup_pressure=PRESSURE_MODERATE)
        schema = obs.to_schema()
        assert schema.cleanup_pressure == "MODERATE"

    def test_to_schema_preserves_counts(self):
        obs = ObservationSummary(stale_total=5, orphan_total=2, candidate_total=7)
        schema = obs.to_schema()
        assert schema.stale_total == 5
        assert schema.orphan_total == 2
        assert schema.candidate_total == 7

    def test_to_schema_preserves_stale_by_tier(self):
        obs = ObservationSummary(stale_by_tier={"agent": 3, "execution": 1})
        schema = obs.to_schema()
        assert schema.stale_by_tier == {"agent": 3, "execution": 1}

    def test_to_schema_converts_matrix_entries(self):
        obs = ObservationSummary(reason_action_matrix=[
            {"reason": "STALE_AGENT", "action": "WATCH", "count": 2},
        ])
        schema = obs.to_schema()
        assert len(schema.reason_action_matrix) == 1
        entry = schema.reason_action_matrix[0]
        assert isinstance(entry, ReasonActionEntry)
        assert entry.reason == "STALE_AGENT"
        assert entry.count == 2

    def test_to_schema_converts_top_priority(self):
        obs = ObservationSummary(top_priority_candidates=[
            {"proposal_id": "AP-1", "tier": "agent", "action_class": "REVIEW",
             "reason_code": "STALE_AGENT", "is_stale": True, "is_orphan": False,
             "stale_age_seconds": 900.0, "current_status": "GUARDED",
             "explanation": "Test."},
        ])
        schema = obs.to_schema()
        assert len(schema.top_priority_candidates) == 1
        candidate = schema.top_priority_candidates[0]
        assert isinstance(candidate, TopPriorityCandidate)
        assert candidate.proposal_id == "AP-1"

    def test_to_schema_safety_always_true(self):
        obs = ObservationSummary()
        schema = obs.to_schema()
        assert schema.safety.read_only is True
        assert schema.safety.simulation_only is True
        assert schema.safety.no_action_executed is True

    def test_to_dict_still_works(self):
        """Backward compatibility: to_dict() still returns a plain dict."""
        obs = ObservationSummary(cleanup_pressure=PRESSURE_HIGH, stale_total=3)
        d = obs.to_dict()
        assert isinstance(d, dict)
        assert d["cleanup_pressure"] == "HIGH"
        assert d["stale_total"] == 3

    def test_to_schema_from_live_build(self):
        """to_schema on a live build_observation_summary result."""
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(700)}
        ], stale_count=1)
        obs = build_observation_summary(action_ledger=action)
        schema = obs.to_schema()
        assert isinstance(schema, ObservationSummarySchema)
        assert schema.stale_total >= 1
        assert schema.candidate_total >= 1


# =========================================================================== #
# AXIS 5: Board Integration                                                    #
# =========================================================================== #

class TestBoardIntegration:

    def test_board_schema_has_typed_observation_summary(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        field_info = FourTierBoardResponse.model_fields["observation_summary"]
        assert field_info.annotation is ObservationSummarySchema

    def test_board_service_returns_typed_observation(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert isinstance(board.observation_summary, ObservationSummarySchema)

    def test_board_observation_safety_intact(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        safety = board.observation_summary.safety
        assert safety.read_only is True
        assert safety.simulation_only is True
        assert safety.no_action_executed is True

    def test_board_observation_pressure_is_typed(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        # Must be one of the valid pressure values
        assert board.observation_summary.cleanup_pressure in {"LOW", "MODERATE", "HIGH", "CRITICAL"}

    def test_board_serializes_observation_to_json(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        obs = j["observation_summary"]
        assert "cleanup_pressure" in obs
        assert "safety" in obs
        assert obs["safety"]["read_only"] is True


# =========================================================================== #
# AXIS 6: Source/Derived Layer Relationship                                    #
# =========================================================================== #

class TestSourceDerivedRelationship:

    def test_observation_is_source_decision_is_derived(self):
        """Observation (L4) feeds Decision (L5) — verify data flow."""
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "GUARDED", "created_at": _past_iso(700)}
        ], stale_count=1)
        obs = build_observation_summary(action_ledger=action)

        from app.services.operator_decision_service import build_decision_summary
        decision = build_decision_summary(action_ledger=action)

        # Decision's counts should reflect observation's counts
        assert decision.stale_total == obs.stale_total
        assert decision.orphan_total == obs.orphan_total
        assert decision.candidate_total == obs.candidate_total

    def test_observation_pressure_flows_to_decision(self):
        """Observation pressure feeds decision posture mapping."""
        action = _FakeLedger([
            {"proposal_id": f"AP-{i}", "status": "GUARDED", "created_at": _past_iso(1200)}
            for i in range(4)
        ], stale_count=4)
        obs = build_observation_summary(action_ledger=action)
        from app.services.operator_decision_service import build_decision_summary
        decision = build_decision_summary(action_ledger=action)
        assert decision.cleanup_pressure == obs.cleanup_pressure

    def test_schema_layers_are_independent_models(self):
        """ObservationSummarySchema and DecisionSummarySchema are separate classes."""
        from app.schemas.decision_summary_schema import DecisionSummarySchema
        assert ObservationSummarySchema is not DecisionSummarySchema

    def test_pressure_enum_shared_not_duplicated(self):
        """Both schemas share the same PressureEnum."""
        obs_schema = ObservationSummarySchema()
        from app.schemas.decision_summary_schema import DecisionSummarySchema
        dec_schema = DecisionSummarySchema()
        # Both default to LOW via same enum
        assert obs_schema.cleanup_pressure == dec_schema.cleanup_pressure


# =========================================================================== #
# AXIS 7: Schema Drift Sentinel                                                #
# =========================================================================== #

class TestSchemaDriftSentinel:
    """Snapshot-style tests to detect unintended schema changes."""

    def test_observation_schema_field_count(self):
        """ObservationSummarySchema has exactly 8 fields."""
        assert len(ObservationSummarySchema.model_fields) == 8

    def test_observation_safety_field_count(self):
        """ObservationSafety has exactly 4 fields."""
        assert len(ObservationSafety.model_fields) == 4

    def test_reason_action_entry_field_count(self):
        """ReasonActionEntry has exactly 3 fields."""
        assert len(ReasonActionEntry.model_fields) == 3

    def test_top_priority_candidate_field_count(self):
        """TopPriorityCandidate has exactly 9 fields."""
        assert len(TopPriorityCandidate.model_fields) == 9

    def test_schema_field_names_snapshot(self):
        """Exact field names must match this snapshot."""
        expected = {
            "cleanup_pressure", "stale_total", "orphan_total", "candidate_total",
            "stale_by_tier", "reason_action_matrix", "top_priority_candidates",
            "safety",
        }
        assert set(ObservationSummarySchema.model_fields.keys()) == expected

    def test_safety_field_names_snapshot(self):
        expected = {"read_only", "simulation_only", "no_action_executed", "no_prediction"}
        assert set(ObservationSafety.model_fields.keys()) == expected
