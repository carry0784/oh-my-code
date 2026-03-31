"""
K-Dexter Decision Card Tests

Sprint Contract: CARD-2026-0330-DECISION-BOARD-VISUAL (Level B)

Tests the decision card visualization layer:
  AXIS 1: PostureBadge Accuracy (4 posture → 4 severity)
  AXIS 2: RiskBadge Accuracy (3 risk → 3 severity)
  AXIS 3: ReasonCompact (3-line limit, truncation, content)
  AXIS 4: SafetyBar Fixed Values (action_allowed=False always)
  AXIS 5: DecisionCard Integration + Serialization
  AXIS 6: Board Integration + Backward Compatibility

Run: pytest tests/test_decision_card.py -v
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

from app.schemas.decision_card_schema import (
    DecisionCard,
    PostureBadge,
    RiskBadge,
    ReasonCompact,
    SafetyBar,
)
from app.services.decision_card_service import (
    build_decision_card,
    _build_reason_compact,
    _POSTURE_SEVERITY,
    _POSTURE_LABEL,
    _RISK_SEVERITY,
    _RISK_LABEL,
    _REASON_COMPACT_LIMIT,
)
from app.services.operator_decision_service import (
    DecisionSummary,
    build_decision_summary,
    POSTURE_MONITOR,
    POSTURE_REVIEW,
    POSTURE_MANUAL_CHECK,
    POSTURE_URGENT_REVIEW,
    POSTURE_DESCRIPTIONS,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
)


# -- Helpers ---------------------------------------------------------------- #

def _make_decision(**kwargs) -> DecisionSummary:
    """Create a DecisionSummary with overrides."""
    defaults = dict(
        recommended_posture=POSTURE_MONITOR,
        risk_level=RISK_LOW,
        reason_chain=["pressure=LOW", "candidate_total=0", "orphan_total=0", "stale_total=0"],
        decision_explanation="Normal operating state. Risk level: LOW. No cleanup candidates identified.",
        candidate_total=0,
        orphan_total=0,
        stale_total=0,
        cleanup_pressure="LOW",
        action_allowed=False,
        suggestion_only=True,
        read_only=True,
    )
    defaults.update(kwargs)
    return DecisionSummary(**defaults)


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
# AXIS 1: PostureBadge Accuracy                                                #
# =========================================================================== #

class TestPostureBadge:

    def test_monitor_severity_info(self):
        decision = _make_decision(recommended_posture=POSTURE_MONITOR)
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "info"
        assert card.posture_badge.label == "Monitor"

    def test_review_severity_warning(self):
        decision = _make_decision(recommended_posture=POSTURE_REVIEW)
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "warning"
        assert card.posture_badge.label == "Review"

    def test_manual_check_severity_caution(self):
        decision = _make_decision(recommended_posture=POSTURE_MANUAL_CHECK)
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "caution"
        assert card.posture_badge.label == "Manual Check"

    def test_urgent_review_severity_critical(self):
        decision = _make_decision(recommended_posture=POSTURE_URGENT_REVIEW)
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "critical"
        assert card.posture_badge.label == "Urgent Review"

    def test_description_from_posture_descriptions(self):
        for posture, expected_desc in POSTURE_DESCRIPTIONS.items():
            decision = _make_decision(recommended_posture=posture)
            card = build_decision_card(decision)
            assert card.posture_badge.description == expected_desc

    def test_unknown_posture_defaults_to_info(self):
        decision = _make_decision(recommended_posture="UNKNOWN_POSTURE")
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "info"
        assert card.posture_badge.label == "Monitor"

    def test_all_postures_covered(self):
        """Every known posture has a severity and label mapping."""
        known = [POSTURE_MONITOR, POSTURE_REVIEW, POSTURE_MANUAL_CHECK, POSTURE_URGENT_REVIEW]
        for posture in known:
            assert posture in _POSTURE_SEVERITY
            assert posture in _POSTURE_LABEL


# =========================================================================== #
# AXIS 2: RiskBadge Accuracy                                                   #
# =========================================================================== #

class TestRiskBadge:

    def test_low_risk_info(self):
        decision = _make_decision(risk_level=RISK_LOW)
        card = build_decision_card(decision)
        assert card.risk_badge.severity == "info"
        assert card.risk_badge.label == "Low Risk"

    def test_medium_risk_warning(self):
        decision = _make_decision(risk_level=RISK_MEDIUM)
        card = build_decision_card(decision)
        assert card.risk_badge.severity == "warning"
        assert card.risk_badge.label == "Medium Risk"

    def test_high_risk_critical(self):
        decision = _make_decision(risk_level=RISK_HIGH)
        card = build_decision_card(decision)
        assert card.risk_badge.severity == "critical"
        assert card.risk_badge.label == "High Risk"

    def test_unknown_risk_defaults_to_info(self):
        decision = _make_decision(risk_level="UNKNOWN_RISK")
        card = build_decision_card(decision)
        assert card.risk_badge.severity == "info"
        assert card.risk_badge.label == "Low Risk"

    def test_all_risks_covered(self):
        """Every known risk level has a severity and label mapping."""
        known = [RISK_LOW, RISK_MEDIUM, RISK_HIGH]
        for risk in known:
            assert risk in _RISK_SEVERITY
            assert risk in _RISK_LABEL


# =========================================================================== #
# AXIS 3: ReasonCompact (3-line limit, truncation, content)                    #
# =========================================================================== #

class TestReasonCompact:

    def test_empty_chain(self):
        compact = _build_reason_compact([])
        assert compact.lines == []
        assert compact.total_reasons == 0
        assert compact.truncated is False

    def test_under_limit(self):
        chain = ["pressure=LOW", "candidate_total=0"]
        compact = _build_reason_compact(chain)
        assert compact.lines == chain
        assert compact.total_reasons == 2
        assert compact.truncated is False

    def test_at_limit(self):
        chain = ["pressure=HIGH", "candidate_total=5", "orphan_total=2"]
        compact = _build_reason_compact(chain)
        assert len(compact.lines) == 3
        assert compact.truncated is False

    def test_over_limit_truncated(self):
        chain = ["pressure=HIGH", "candidate_total=5", "orphan_total=2",
                 "stale_total=3", "stale_agent=2", "stale_submit=1"]
        compact = _build_reason_compact(chain)
        assert len(compact.lines) == _REASON_COMPACT_LIMIT
        assert compact.total_reasons == 6
        assert compact.truncated is True

    def test_preserves_order(self):
        chain = ["pressure=CRITICAL", "candidate_total=12", "orphan_total=5"]
        compact = _build_reason_compact(chain)
        assert compact.lines[0] == "pressure=CRITICAL"
        assert compact.lines[1] == "candidate_total=12"

    def test_limit_is_three(self):
        assert _REASON_COMPACT_LIMIT == 3


# =========================================================================== #
# AXIS 4: SafetyBar Fixed Values                                               #
# =========================================================================== #

class TestSafetyBar:

    def test_action_allowed_always_false(self):
        decision = _make_decision()
        card = build_decision_card(decision)
        assert card.safety_bar.action_allowed is False

    def test_suggestion_only_always_true(self):
        decision = _make_decision()
        card = build_decision_card(decision)
        assert card.safety_bar.suggestion_only is True

    def test_read_only_always_true(self):
        decision = _make_decision()
        card = build_decision_card(decision)
        assert card.safety_bar.read_only is True

    def test_labels_contain_no_action(self):
        decision = _make_decision()
        card = build_decision_card(decision)
        labels = card.safety_bar.labels
        assert any("No action" in label for label in labels)
        assert any("Suggestion only" in label for label in labels)
        assert any("Read-only" in label for label in labels)

    def test_safety_bar_ignores_input_action_allowed(self):
        """Even if DecisionSummary somehow had action_allowed=True,
        the card safety bar is structurally False."""
        decision = _make_decision()
        # Simulate hypothetical corruption (should never happen)
        decision.action_allowed = True
        card = build_decision_card(decision)
        # SafetyBar is structurally fixed, NOT derived from input
        assert card.safety_bar.action_allowed is False

    def test_source_no_action_allowed_true(self):
        """Service source must never set action_allowed=True."""
        import app.services.decision_card_service as mod
        source = inspect.getsource(mod)
        assert "action_allowed=True" not in source
        assert "action_allowed = True" not in source

    def test_source_no_write_methods(self):
        """Service source must not call any write methods."""
        import app.services.decision_card_service as mod
        source = inspect.getsource(mod)
        assert ".propose_and_guard(" not in source
        assert ".record_receipt(" not in source
        assert ".transition_to(" not in source


# =========================================================================== #
# AXIS 5: DecisionCard Integration + Serialization                             #
# =========================================================================== #

class TestDecisionCardIntegration:

    def test_card_from_monitor_low(self):
        decision = _make_decision()
        card = build_decision_card(decision)
        assert card.posture_badge.posture == POSTURE_MONITOR
        assert card.risk_badge.risk_level == RISK_LOW
        assert card.explanation != ""

    def test_card_from_urgent_high(self):
        decision = _make_decision(
            recommended_posture=POSTURE_URGENT_REVIEW,
            risk_level=RISK_HIGH,
            reason_chain=["pressure=CRITICAL", "candidate_total=15",
                          "orphan_total=3", "stale_total=8", "stale_submit=5"],
            candidate_total=15,
            orphan_total=3,
            stale_total=8,
        )
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "critical"
        assert card.risk_badge.severity == "critical"
        assert card.reason_compact.truncated is True
        assert card.candidate_total == 15
        assert card.orphan_total == 3
        assert card.stale_total == 8

    def test_json_serializable(self):
        decision = _make_decision()
        card = build_decision_card(decision)
        d = card.model_dump()
        assert isinstance(d, dict)
        s = json.dumps(d)
        assert isinstance(s, str)

    def test_card_preserves_explanation(self):
        explanation = "Test explanation with risk level info."
        decision = _make_decision(decision_explanation=explanation)
        card = build_decision_card(decision)
        assert card.explanation == explanation

    def test_full_pipeline_empty_ledgers(self):
        """End-to-end: build_decision_summary → build_decision_card."""
        decision = build_decision_summary()
        card = build_decision_card(decision)
        assert card.posture_badge.posture == POSTURE_MONITOR
        assert card.risk_badge.risk_level == RISK_LOW
        assert card.safety_bar.action_allowed is False

    def test_full_pipeline_with_stale(self):
        """End-to-end with stale data → elevated card."""
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
        card = build_decision_card(decision)
        assert card.posture_badge.severity == "critical"
        assert card.risk_badge.severity == "critical"
        assert card.safety_bar.action_allowed is False


# =========================================================================== #
# AXIS 6: Board Integration + Backward Compatibility                           #
# =========================================================================== #

class TestBoardIntegration:

    def test_board_schema_has_decision_card(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "decision_card" in fields

    def test_board_still_has_decision_summary_dict(self):
        """Backward compatibility: decision_summary dict still present."""
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        fields = FourTierBoardResponse.model_fields
        assert "decision_summary" in fields

    def test_board_populates_decision_card(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.decision_card is not None
        assert board.decision_card.posture_badge.posture == POSTURE_MONITOR
        assert board.decision_card.risk_badge.risk_level == RISK_LOW
        assert board.decision_card.safety_bar.action_allowed is False

    def test_board_decision_card_and_summary_consistent(self):
        """decision_card and decision_summary must agree on posture/risk."""
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.decision_card.posture_badge.posture == board.decision_summary.recommended_posture
        assert board.decision_card.risk_badge.risk_level == board.decision_summary.risk_level

    def test_board_decision_card_serializable(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        d = board.model_dump()
        s = json.dumps(d)
        assert "decision_card" in d
        assert "posture_badge" in d["decision_card"]
