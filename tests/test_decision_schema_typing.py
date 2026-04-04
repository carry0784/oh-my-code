"""
K-Dexter Decision Schema Typing Tests

Sprint Contract: CARD-2026-0330-DECISION-SCHEMA-TYPING (Level B)

Tests the typed DecisionSummarySchema:
  AXIS 1: Enum Constraints (PostureEnum, RiskLevelEnum, PressureEnum)
  AXIS 2: DecisionSafety Sub-model (structurally fixed)
  AXIS 3: Schema Field Completeness
  AXIS 4: Dataclass ↔ Schema Conversion
  AXIS 5: Board Integration (typed, not dict)
  AXIS 6: Source/Derived Relationship (summary → card)

Run: pytest tests/test_decision_schema_typing.py -v
"""
import sys
import json
import inspect
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

from app.schemas.decision_summary_schema import (
    DecisionSummarySchema,
    DecisionSafety,
    PostureEnum,
    RiskLevelEnum,
    PressureEnum,
)
from app.services.operator_decision_service import (
    DecisionSummary,
    build_decision_summary,
    POSTURE_MONITOR,
    POSTURE_REVIEW,
    POSTURE_MANUAL_CHECK,
    POSTURE_URGENT_REVIEW,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
)
from app.services.observation_summary_service import (
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
# AXIS 1: Enum Constraints                                                     #
# =========================================================================== #

class TestEnumConstraints:

    def test_posture_enum_values(self):
        assert PostureEnum.MONITOR.value == "MONITOR"
        assert PostureEnum.REVIEW.value == "REVIEW"
        assert PostureEnum.MANUAL_CHECK.value == "MANUAL_CHECK"
        assert PostureEnum.URGENT_REVIEW.value == "URGENT_REVIEW"

    def test_risk_level_enum_values(self):
        assert RiskLevelEnum.LOW.value == "LOW"
        assert RiskLevelEnum.MEDIUM.value == "MEDIUM"
        assert RiskLevelEnum.HIGH.value == "HIGH"

    def test_pressure_enum_values(self):
        assert PressureEnum.LOW.value == "LOW"
        assert PressureEnum.MODERATE.value == "MODERATE"
        assert PressureEnum.HIGH.value == "HIGH"
        assert PressureEnum.CRITICAL.value == "CRITICAL"

    def test_posture_enum_count(self):
        assert len(PostureEnum) == 4

    def test_risk_enum_count(self):
        assert len(RiskLevelEnum) == 3

    def test_pressure_enum_count(self):
        assert len(PressureEnum) == 4

    def test_invalid_posture_rejected(self):
        with pytest.raises(Exception):
            DecisionSummarySchema(recommended_posture="INVALID_POSTURE")

    def test_invalid_risk_rejected(self):
        with pytest.raises(Exception):
            DecisionSummarySchema(risk_level="INVALID_RISK")

    def test_invalid_pressure_rejected(self):
        with pytest.raises(Exception):
            DecisionSummarySchema(cleanup_pressure="INVALID_PRESSURE")


# =========================================================================== #
# AXIS 2: DecisionSafety Sub-model                                             #
# =========================================================================== #

class TestDecisionSafety:

    def test_default_action_allowed_false(self):
        safety = DecisionSafety()
        assert safety.action_allowed is False

    def test_default_suggestion_only_true(self):
        safety = DecisionSafety()
        assert safety.suggestion_only is True

    def test_default_read_only_true(self):
        safety = DecisionSafety()
        assert safety.read_only is True

    def test_schema_default_has_safety(self):
        schema = DecisionSummarySchema()
        assert schema.safety.action_allowed is False
        assert schema.safety.suggestion_only is True
        assert schema.safety.read_only is True

    def test_safety_serializes(self):
        safety = DecisionSafety()
        d = safety.model_dump()
        assert d == {"action_allowed": False, "suggestion_only": True, "read_only": True}

    def test_schema_source_no_action_allowed_true(self):
        """Schema source must never set action_allowed=True."""
        import app.schemas.decision_summary_schema as mod
        source = inspect.getsource(mod)
        # Only default=False should appear, never True assignment
        assert "action_allowed=True" not in source
        assert "action_allowed = True" not in source


# =========================================================================== #
# AXIS 3: Schema Field Completeness                                            #
# =========================================================================== #

class TestSchemaFieldCompleteness:

    def test_has_posture(self):
        assert "recommended_posture" in DecisionSummarySchema.model_fields

    def test_has_risk_level(self):
        assert "risk_level" in DecisionSummarySchema.model_fields

    def test_has_reason_chain(self):
        assert "reason_chain" in DecisionSummarySchema.model_fields

    def test_has_explanation(self):
        assert "decision_explanation" in DecisionSummarySchema.model_fields

    def test_has_candidate_total(self):
        assert "candidate_total" in DecisionSummarySchema.model_fields

    def test_has_orphan_total(self):
        assert "orphan_total" in DecisionSummarySchema.model_fields

    def test_has_stale_total(self):
        assert "stale_total" in DecisionSummarySchema.model_fields

    def test_has_cleanup_pressure(self):
        assert "cleanup_pressure" in DecisionSummarySchema.model_fields

    def test_has_safety(self):
        assert "safety" in DecisionSummarySchema.model_fields

    def test_json_serializable(self):
        schema = DecisionSummarySchema()
        d = schema.model_dump()
        s = json.dumps(d)
        assert isinstance(s, str)


# =========================================================================== #
# AXIS 4: Dataclass ↔ Schema Conversion                                       #
# =========================================================================== #

class TestDataclassSchemaConversion:

    def test_to_schema_returns_typed(self):
        decision = build_decision_summary()
        schema = decision.to_schema()
        assert isinstance(schema, DecisionSummarySchema)

    def test_to_schema_posture_matches(self):
        decision = build_decision_summary()
        schema = decision.to_schema()
        assert schema.recommended_posture == decision.recommended_posture

    def test_to_schema_risk_matches(self):
        decision = build_decision_summary()
        schema = decision.to_schema()
        assert schema.risk_level == decision.risk_level

    def test_to_schema_reason_chain_matches(self):
        decision = build_decision_summary()
        schema = decision.to_schema()
        assert schema.reason_chain == decision.reason_chain

    def test_to_schema_safety_fixed(self):
        decision = build_decision_summary()
        schema = decision.to_schema()
        assert schema.safety.action_allowed is False
        assert schema.safety.suggestion_only is True
        assert schema.safety.read_only is True

    def test_to_schema_with_elevated_data(self):
        action = _FakeLedger([
            {"proposal_id": "AP-1", "status": "RECEIPTED", "created_at": _now_iso()}
        ])
        exec_proposals = [
            {"proposal_id": f"EP-{i}", "agent_proposal_id": f"AP-GONE-{i}",
             "status": "EXEC_GUARDED", "created_at": _past_iso(500)}
            for i in range(12)
        ]
        execution = _FakeLedger(exec_proposals, stale_count=12)
        decision = build_decision_summary(action, execution)
        schema = decision.to_schema()
        assert schema.recommended_posture == "URGENT_REVIEW"
        assert schema.risk_level == "HIGH"
        assert schema.safety.action_allowed is False

    def test_to_dict_still_works(self):
        """Backward compatibility: to_dict() still returns dict."""
        decision = build_decision_summary()
        d = decision.to_dict()
        assert isinstance(d, dict)
        assert "recommended_posture" in d


# =========================================================================== #
# AXIS 5: Board Integration (typed, not dict)                                  #
# =========================================================================== #

class TestBoardIntegrationTyped:

    def test_board_decision_summary_is_typed(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert isinstance(board.decision_summary, DecisionSummarySchema)

    def test_board_decision_summary_has_safety(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert isinstance(board.decision_summary.safety, DecisionSafety)
        assert board.decision_summary.safety.action_allowed is False

    def test_board_serializable_with_typed_summary(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        d = board.model_dump()
        s = json.dumps(d)
        assert "decision_summary" in d
        assert "safety" in d["decision_summary"]
        assert d["decision_summary"]["safety"]["action_allowed"] is False

    def test_board_schema_field_type(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        field = FourTierBoardResponse.model_fields["decision_summary"]
        assert field.annotation is DecisionSummarySchema


# =========================================================================== #
# AXIS 6: Source/Derived Relationship                                          #
# =========================================================================== #

class TestSourceDerivedRelationship:

    def test_card_derived_from_summary_posture(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.decision_card.posture_badge.posture == board.decision_summary.recommended_posture

    def test_card_derived_from_summary_risk(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.decision_card.risk_badge.risk_level == board.decision_summary.risk_level

    def test_card_safety_matches_summary_safety(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.decision_card.safety_bar.action_allowed == board.decision_summary.safety.action_allowed
        assert board.decision_card.safety_bar.read_only == board.decision_summary.safety.read_only

    def test_schema_docstring_declares_source(self):
        """Schema docstring must declare it is source of truth."""
        doc = DecisionSummarySchema.__doc__
        assert "source" in doc.lower() or "Source" in doc
