"""
K-Dexter Board Contract Governance Tests

Sprint Contract: Phase B/C — Observation Constitution Enforcement

Enforces Observation Constitution rules:
  AXIS 1: Board Dict-Free (OC-09: no dict fields in board schema)
  AXIS 2: Safety Invariant Standard (OC-04/OC-05: correct safety fields per layer)
  AXIS 3: Schema Governance (OC-10/OC-11: drift sentinel, field inventory)
  AXIS 4: Observation-Decision Firewall (OC-01/OC-02: no cross-layer violations)
  AXIS 5: to_dict Policy (OC-15: no new external usage)
  AXIS 6: Board Field Inventory (OC-14: complete typed field coverage)
  AXIS 7: Schema Versioning (OC-16~OC-21: additive-only, backward compat)
  AXIS 8: to_dict Retirement Tracking (OC-15 inventory enforcement)

Run: pytest tests/test_board_contract_governance.py -v
"""
import sys
import inspect
from pathlib import Path
from typing import get_origin
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


# =========================================================================== #
# AXIS 1: Board Dict-Free (OC-09)                                             #
# =========================================================================== #

class TestBoardDictFree:
    """OC-09: All board fields MUST be typed schema — no dict fields."""

    def test_no_dict_fields_in_board_response(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        for name, field_info in FourTierBoardResponse.model_fields.items():
            annotation = field_info.annotation
            # Direct dict type
            assert annotation is not dict, \
                f"Field '{name}' is dict — must be typed schema (OC-09)"

    def test_no_list_dict_fields_in_board_response(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        for name, field_info in FourTierBoardResponse.model_fields.items():
            annotation = field_info.annotation
            origin = get_origin(annotation)
            if origin is list:
                args = getattr(annotation, "__args__", ())
                if args:
                    assert args[0] is not dict, \
                        f"Field '{name}' is list[dict] — must be list[TypedModel] (OC-09)"

    def test_orphan_detail_is_typed(self):
        from app.schemas.four_tier_board_schema import (
            FourTierBoardResponse, OrphanDetail,
        )
        field_info = FourTierBoardResponse.model_fields["cross_tier_orphan_detail"]
        args = getattr(field_info.annotation, "__args__", ())
        assert args and args[0] is OrphanDetail

    def test_cleanup_action_summary_is_typed(self):
        from app.schemas.four_tier_board_schema import (
            FourTierBoardResponse, CleanupActionSummary,
        )
        assert FourTierBoardResponse.model_fields["cleanup_action_summary"].annotation is CleanupActionSummary


# =========================================================================== #
# AXIS 2: Safety Invariant Standard (OC-04 / OC-05)                           #
# =========================================================================== #

class TestSafetyInvariantStandard:

    def test_observation_safety_has_four_fields(self):
        """OC-04: Observation safety = 4 fields."""
        from app.schemas.observation_summary_schema import ObservationSafety
        expected = {"read_only", "simulation_only", "no_action_executed", "no_prediction"}
        assert set(ObservationSafety.model_fields.keys()) == expected

    def test_review_volume_safety_has_four_fields(self):
        """OC-04: ReviewVolume safety matches observation standard."""
        from app.schemas.review_volume_schema import ReviewVolumeSafety
        expected = {"read_only", "simulation_only", "no_action_executed", "no_prediction"}
        assert set(ReviewVolumeSafety.model_fields.keys()) == expected

    def test_decision_safety_has_three_fields(self):
        """OC-05: Decision safety = 3 fields."""
        from app.schemas.decision_summary_schema import DecisionSafety
        expected = {"action_allowed", "suggestion_only", "read_only"}
        assert set(DecisionSafety.model_fields.keys()) == expected

    def test_observation_safety_defaults_all_true(self):
        from app.schemas.observation_summary_schema import ObservationSafety
        s = ObservationSafety()
        assert s.read_only is True
        assert s.simulation_only is True
        assert s.no_action_executed is True
        assert s.no_prediction is True

    def test_decision_safety_action_allowed_false(self):
        from app.schemas.decision_summary_schema import DecisionSafety
        s = DecisionSafety()
        assert s.action_allowed is False

    def test_observation_and_review_safety_aligned(self):
        """OC-04: All observation-layer safeties have identical field sets."""
        from app.schemas.observation_summary_schema import ObservationSafety
        from app.schemas.review_volume_schema import ReviewVolumeSafety
        from app.schemas.watch_volume_schema import WatchVolumeSafety
        from app.schemas.blockage_summary_schema import BlockageSafety
        from app.schemas.retry_pressure_schema import RetryPressureSafety
        from app.schemas.latency_observation_schema import LatencySafety
        from app.schemas.trend_observation_schema import TrendSafety
        obs_fields = set(ObservationSafety.model_fields.keys())
        rev_fields = set(ReviewVolumeSafety.model_fields.keys())
        watch_fields = set(WatchVolumeSafety.model_fields.keys())
        blockage_fields = set(BlockageSafety.model_fields.keys())
        retry_fields = set(RetryPressureSafety.model_fields.keys())
        latency_fields = set(LatencySafety.model_fields.keys())
        trend_fields = set(TrendSafety.model_fields.keys())
        assert obs_fields == rev_fields
        assert obs_fields == watch_fields
        assert obs_fields == blockage_fields
        assert obs_fields == retry_fields
        assert obs_fields == latency_fields
        assert obs_fields == trend_fields


# =========================================================================== #
# AXIS 3: Schema Governance (OC-10 / OC-11)                                   #
# =========================================================================== #

class TestSchemaGovernance:

    def test_board_response_field_count(self):
        """Drift sentinel: FourTierBoardResponse field count."""
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        assert len(FourTierBoardResponse.model_fields) == 24

    def test_board_response_field_names_snapshot(self):
        """Drift sentinel: exact field names."""
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        expected = {
            "agent_tier", "execution_tier", "submit_tier", "order_tier",
            "derived_flags", "top_block_reasons_all", "recent_lineage",
            "cross_tier_orphan_count", "cross_tier_orphan_detail",
            "cleanup_candidate_count", "cleanup_action_summary",
            "cleanup_simulation_only", "observation_summary",
            "decision_summary", "decision_card", "review_volume",
            "watch_volume", "blockage_summary", "retry_pressure",
            "latency_observation", "trend_observation",
            "total_guard_checks", "seal_chain_complete", "generated_at",
        }
        assert set(FourTierBoardResponse.model_fields.keys()) == expected

    def test_orphan_detail_field_count(self):
        from app.schemas.four_tier_board_schema import OrphanDetail
        assert len(OrphanDetail.model_fields) == 6

    def test_cleanup_action_summary_field_count(self):
        from app.schemas.four_tier_board_schema import CleanupActionSummary
        assert len(CleanupActionSummary.model_fields) == 4

    def test_all_schemas_have_use_enum_values_if_enums(self):
        """OC-12: Schemas with enums must have use_enum_values=True."""
        from app.schemas.observation_summary_schema import ObservationSummarySchema
        from app.schemas.decision_summary_schema import DecisionSummarySchema
        from app.schemas.review_volume_schema import ReviewVolumeSchema
        from app.schemas.watch_volume_schema import WatchVolumeSchema
        from app.schemas.blockage_summary_schema import BlockageSummarySchema
        from app.schemas.retry_pressure_schema import RetryPressureSchema
        for schema in [ObservationSummarySchema, DecisionSummarySchema, ReviewVolumeSchema, WatchVolumeSchema, BlockageSummarySchema, RetryPressureSchema]:
            assert schema.model_config.get("use_enum_values") is True, \
                f"{schema.__name__} missing use_enum_values=True (OC-12)"


# =========================================================================== #
# AXIS 4: Observation-Decision Firewall (OC-01 / OC-02)                       #
# =========================================================================== #

class TestObservationDecisionFirewall:

    def test_observation_schema_does_not_import_decision(self):
        """OC-02: Observation schema must not import from decision layer."""
        import app.schemas.observation_summary_schema as mod
        source = inspect.getsource(mod)
        # PressureEnum import from decision_summary_schema is allowed (shared enum).
        # But actual decision-layer class imports are forbidden.
        assert "import DecisionSummarySchema" not in source
        assert "import DecisionSafety" not in source

    def test_review_volume_does_not_import_decision(self):
        """OC-02: Review volume must not import from decision layer."""
        import app.schemas.review_volume_schema as mod
        source = inspect.getsource(mod)
        assert "DecisionSummarySchema" not in source
        assert "DecisionSafety" not in source

    def test_observation_service_does_not_import_decision_service(self):
        """OC-02: Observation service must not import from decision service."""
        import app.services.observation_summary_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_review_volume_service_does_not_import_decision_service(self):
        import app.services.review_volume_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_watch_volume_does_not_import_decision(self):
        """OC-02: Watch volume must not import from decision layer."""
        import app.schemas.watch_volume_schema as mod
        source = inspect.getsource(mod)
        assert "import DecisionSummarySchema" not in source
        assert "import DecisionSafety" not in source

    def test_watch_volume_service_does_not_import_decision_service(self):
        import app.services.watch_volume_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_blockage_summary_does_not_import_decision(self):
        """OC-02: Blockage summary must not import from decision layer."""
        import app.schemas.blockage_summary_schema as mod
        source = inspect.getsource(mod)
        assert "import DecisionSummarySchema" not in source
        assert "import DecisionSafety" not in source

    def test_blockage_service_does_not_import_decision_service(self):
        import app.services.blockage_summary_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_retry_pressure_does_not_import_decision(self):
        import app.schemas.retry_pressure_schema as mod
        source = inspect.getsource(mod)
        assert "import DecisionSummarySchema" not in source
        assert "import DecisionSafety" not in source

    def test_retry_pressure_service_does_not_import_decision_service(self):
        import app.services.retry_pressure_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_observation_has_no_action_allowed_field(self):
        """OC-03: action_allowed is only in Decision, not Observation."""
        from app.schemas.observation_summary_schema import ObservationSafety
        assert "action_allowed" not in ObservationSafety.model_fields

    def test_review_volume_has_no_action_allowed_field(self):
        from app.schemas.review_volume_schema import ReviewVolumeSafety
        assert "action_allowed" not in ReviewVolumeSafety.model_fields

    def test_watch_volume_has_no_action_allowed_field(self):
        from app.schemas.watch_volume_schema import WatchVolumeSafety
        assert "action_allowed" not in WatchVolumeSafety.model_fields

    def test_blockage_summary_has_no_action_allowed_field(self):
        from app.schemas.blockage_summary_schema import BlockageSafety
        assert "action_allowed" not in BlockageSafety.model_fields

    def test_retry_pressure_has_no_action_allowed_field(self):
        from app.schemas.retry_pressure_schema import RetryPressureSafety
        assert "action_allowed" not in RetryPressureSafety.model_fields

    def test_latency_observation_does_not_import_decision(self):
        import app.schemas.latency_observation_schema as mod
        source = inspect.getsource(mod)
        assert "import DecisionSummarySchema" not in source
        assert "import DecisionSafety" not in source

    def test_latency_observation_service_does_not_import_decision_service(self):
        import app.services.latency_observation_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_latency_observation_has_no_action_allowed_field(self):
        from app.schemas.latency_observation_schema import LatencySafety
        assert "action_allowed" not in LatencySafety.model_fields

    def test_trend_observation_does_not_import_decision(self):
        import app.schemas.trend_observation_schema as mod
        source = inspect.getsource(mod)
        assert "import DecisionSummarySchema" not in source
        assert "import DecisionSafety" not in source

    def test_trend_observation_service_does_not_import_decision_service(self):
        import app.services.trend_observation_service as mod
        source = inspect.getsource(mod)
        assert "operator_decision_service" not in source

    def test_trend_observation_has_no_action_allowed_field(self):
        from app.schemas.trend_observation_schema import TrendSafety
        assert "action_allowed" not in TrendSafety.model_fields


# =========================================================================== #
# AXIS 5: to_dict Policy (OC-15)                                              #
# =========================================================================== #

class TestToDictPolicy:

    def test_board_service_does_not_use_obs_to_dict(self):
        """OC-15: Board service uses to_schema(), not to_dict() for observation."""
        import app.services.four_tier_board_service as mod
        source = inspect.getsource(mod)
        assert "obs_summary.to_dict()" not in source

    def test_board_service_does_not_use_decision_to_dict(self):
        """OC-15: Board service uses to_schema(), not to_dict() for decision."""
        import app.services.four_tier_board_service as mod
        source = inspect.getsource(mod)
        assert "decision.to_dict()" not in source

    def test_board_service_uses_to_schema(self):
        import app.services.four_tier_board_service as mod
        source = inspect.getsource(mod)
        assert "to_schema()" in source


# =========================================================================== #
# AXIS 6: Board Field Inventory (OC-14)                                        #
# =========================================================================== #

class TestBoardFieldInventory:

    def test_board_builds_without_error(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board is not None

    def test_board_json_serializable(self):
        import json
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        assert "agent_tier" in j
        assert "observation_summary" in j
        assert "review_volume" in j
        assert "cleanup_action_summary" in j
        assert "cross_tier_orphan_detail" in j

    def test_board_all_typed_fields_populated(self):
        from app.services.four_tier_board_service import build_four_tier_board
        from app.schemas.observation_summary_schema import ObservationSummarySchema
        from app.schemas.decision_summary_schema import DecisionSummarySchema
        from app.schemas.review_volume_schema import ReviewVolumeSchema
        from app.schemas.four_tier_board_schema import CleanupActionSummary

        board = build_four_tier_board()
        assert isinstance(board.observation_summary, ObservationSummarySchema)
        assert isinstance(board.decision_summary, DecisionSummarySchema)
        assert isinstance(board.review_volume, ReviewVolumeSchema)
        assert isinstance(board.cleanup_action_summary, CleanupActionSummary)
        assert isinstance(board.cross_tier_orphan_detail, list)


# =========================================================================== #
# AXIS 7: Schema Versioning (OC-16 ~ OC-21)                                   #
# =========================================================================== #

class TestSchemaVersioning:

    def test_all_board_fields_have_defaults(self):
        """OC-19: Every board field must have a default (additive-safe).
        Required fields (tier summaries, derived_flags) are structural — exempt."""
        from pydantic.fields import PydanticUndefined
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        _STRUCTURAL_REQUIRED = {
            "agent_tier", "execution_tier", "submit_tier",
            "order_tier", "derived_flags",
        }
        for name, field_info in FourTierBoardResponse.model_fields.items():
            if name in _STRUCTURAL_REQUIRED:
                continue
            has_default = (
                field_info.default is not PydanticUndefined
                or field_info.default_factory is not None
            )
            assert has_default, \
                f"Field '{name}' has no default — violates additive-only rule (OC-19)"

    def test_board_can_be_constructed_with_required_only(self):
        """OC-16/OC-20: Board must be constructable with only structural required fields."""
        from app.schemas.four_tier_board_schema import (
            FourTierBoardResponse, TierSummary, OrderTierSummary, DerivedFlags,
        )
        board = FourTierBoardResponse(
            agent_tier=TierSummary(tier_name="Agent", tier_number=1),
            execution_tier=TierSummary(tier_name="Execution", tier_number=2),
            submit_tier=TierSummary(tier_name="Submit", tier_number=3),
            order_tier=OrderTierSummary(),
            derived_flags=DerivedFlags(),
        )
        assert board is not None

    def test_observation_schema_all_fields_have_defaults(self):
        """OC-16: ObservationSummarySchema fields all have defaults."""
        from app.schemas.observation_summary_schema import ObservationSummarySchema
        for name, field_info in ObservationSummarySchema.model_fields.items():
            assert field_info.default is not None or field_info.default_factory is not None, \
                f"ObservationSummarySchema.{name} has no default (OC-16)"

    def test_decision_schema_all_fields_have_defaults(self):
        """OC-16: DecisionSummarySchema fields all have defaults."""
        from app.schemas.decision_summary_schema import DecisionSummarySchema
        for name, field_info in DecisionSummarySchema.model_fields.items():
            assert field_info.default is not None or field_info.default_factory is not None, \
                f"DecisionSummarySchema.{name} has no default (OC-16)"

    def test_review_volume_schema_all_fields_have_defaults(self):
        """OC-16: ReviewVolumeSchema fields all have defaults."""
        from app.schemas.review_volume_schema import ReviewVolumeSchema
        for name, field_info in ReviewVolumeSchema.model_fields.items():
            assert field_info.default is not None or field_info.default_factory is not None, \
                f"ReviewVolumeSchema.{name} has no default (OC-16)"

    def test_no_any_type_in_board_schema(self):
        """OC-09/OC-19: No 'Any' type allowed in board fields."""
        from typing import Any
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        for name, field_info in FourTierBoardResponse.model_fields.items():
            assert field_info.annotation is not Any, \
                f"Field '{name}' is Any — must be typed (OC-09)"

    def test_enum_schemas_use_enum_values(self):
        """OC-12/OC-18: All schemas with enums must serialize as values."""
        from app.schemas.observation_summary_schema import ObservationSummarySchema
        from app.schemas.decision_summary_schema import DecisionSummarySchema
        from app.schemas.review_volume_schema import ReviewVolumeSchema
        for schema in [ObservationSummarySchema, DecisionSummarySchema, ReviewVolumeSchema]:
            assert schema.model_config.get("use_enum_values") is True, \
                f"{schema.__name__} missing use_enum_values (OC-18)"


# =========================================================================== #
# AXIS 8: to_dict Retirement Tracking (OC-15 inventory)                        #
# =========================================================================== #

class TestToDictRetirement:

    def test_board_service_zero_to_dict(self):
        """OC-15: Board service must have zero to_dict() calls."""
        import app.services.four_tier_board_service as mod
        source = inspect.getsource(mod)
        assert ".to_dict()" not in source

    def test_observation_service_has_to_schema(self):
        """OC-15: Observation service must provide to_schema()."""
        import app.services.observation_summary_service as mod
        source = inspect.getsource(mod)
        assert "def to_schema(" in source

    def test_decision_service_has_to_schema(self):
        """OC-15: Decision service must provide to_schema()."""
        import app.services.operator_decision_service as mod
        source = inspect.getsource(mod)
        assert "def to_schema(" in source

    def test_review_volume_returns_typed_schema(self):
        """OC-15: Review volume service returns typed schema directly."""
        import app.services.review_volume_service as mod
        source = inspect.getsource(mod)
        assert "ReviewVolumeSchema" in source

    def test_no_new_to_dict_in_observation_schemas(self):
        """OC-15: No to_dict() method in observation schema modules."""
        import app.schemas.observation_summary_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source

    def test_no_new_to_dict_in_review_volume_schema(self):
        """OC-15: No to_dict() method in review volume schema module."""
        import app.schemas.review_volume_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source

    def test_no_new_to_dict_in_watch_volume_schema(self):
        """OC-15: No to_dict() method in watch volume schema module."""
        import app.schemas.watch_volume_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source

    def test_no_new_to_dict_in_blockage_summary_schema(self):
        """OC-15: No to_dict() method in blockage summary schema module."""
        import app.schemas.blockage_summary_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source

    def test_no_new_to_dict_in_retry_pressure_schema(self):
        """OC-15: No to_dict() method in retry pressure schema module."""
        import app.schemas.retry_pressure_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source

    def test_no_new_to_dict_in_latency_observation_schema(self):
        """OC-15: No to_dict() method in latency observation schema module."""
        import app.schemas.latency_observation_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source

    def test_no_new_to_dict_in_trend_observation_schema(self):
        """OC-15: No to_dict() method in trend observation schema module."""
        import app.schemas.trend_observation_schema as mod
        source = inspect.getsource(mod)
        assert "def to_dict(" not in source
