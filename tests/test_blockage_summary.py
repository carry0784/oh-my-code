"""
K-Dexter Pipeline Blockage Summary Observation Tests

Sprint Contract: Phase C — Pipeline Blockage Summary Card

Tests the blockage summary observation card:
  AXIS 1: Blockage Accuracy (counts, rates, totals)
  AXIS 2: Tier Distribution (per-tier blockage breakdown)
  AXIS 3: Reason Aggregation (top blocking reasons)
  AXIS 4: Density Signal (concentration, high-rate detection)
  AXIS 5: Safety Invariants (read-only, no prediction, no write)
  AXIS 6: Schema Drift Sentinel (field count/name snapshot)
  AXIS 7: Board Integration (schema field, typed return, safety, JSON)

Run: pytest tests/test_blockage_summary.py -v
"""

import sys
import json
from pathlib import Path
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


# -- Imports ---------------------------------------------------------------- #

from app.services.blockage_summary_service import build_blockage_summary
from app.schemas.blockage_summary_schema import (
    BlockageSummarySchema,
    TierBlockage,
    ReasonAggregation,
    BlockageDensitySignal,
    BlockageSafety,
)
from app.schemas.four_tier_board_schema import TierSummary


# -- Helpers ---------------------------------------------------------------- #


def _tier(name, number, total=0, blocked=0, reasons=None, connected=True):
    return TierSummary(
        tier_name=name,
        tier_number=number,
        total=total,
        blocked_count=blocked,
        guard_reason_top=reasons or [],
        connected=connected,
    )


def _empty_tiers():
    return (
        _tier("Agent", 1),
        _tier("Execution", 2),
        _tier("Submit", 3),
    )


def _blocked_tiers(
    agent_b=0,
    agent_t=0,
    exec_b=0,
    exec_t=0,
    sub_b=0,
    sub_t=0,
    agent_reasons=None,
    exec_reasons=None,
    sub_reasons=None,
):
    return (
        _tier("Agent", 1, total=agent_t, blocked=agent_b, reasons=agent_reasons),
        _tier("Execution", 2, total=exec_t, blocked=exec_b, reasons=exec_reasons),
        _tier("Submit", 3, total=sub_t, blocked=sub_b, reasons=sub_reasons),
    )


# =========================================================================== #
# AXIS 1: Blockage Accuracy                                                    #
# =========================================================================== #


class TestBlockageAccuracy:
    def test_zero_proposals_zero_blockage(self):
        summary = build_blockage_summary(*_empty_tiers())
        assert summary.total_blocked == 0
        assert summary.total_proposals == 0
        assert summary.overall_blockage_rate == 0.0

    def test_blocked_count_aggregated(self):
        tiers = _blocked_tiers(agent_b=3, agent_t=10, exec_b=2, exec_t=5)
        summary = build_blockage_summary(*tiers)
        assert summary.total_blocked == 5
        assert summary.total_proposals == 15

    def test_overall_rate_calculation(self):
        tiers = _blocked_tiers(agent_b=5, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.overall_blockage_rate == 0.5

    def test_disconnected_tier_excluded(self):
        agent = _tier("Agent", 1, total=10, blocked=5, connected=True)
        execution = _tier("Execution", 2, total=0, blocked=0, connected=False)
        submit = _tier("Submit", 3, total=0, blocked=0, connected=False)
        summary = build_blockage_summary(agent, execution, submit)
        assert summary.total_blocked == 5
        assert summary.total_proposals == 10

    def test_all_blocked_rate_is_one(self):
        tiers = _blocked_tiers(agent_b=10, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.overall_blockage_rate == 1.0


# =========================================================================== #
# AXIS 2: Tier Distribution                                                    #
# =========================================================================== #


class TestTierDistribution:
    def test_three_tiers_present(self):
        summary = build_blockage_summary(*_empty_tiers())
        assert len(summary.by_tier) == 3

    def test_tier_names_correct(self):
        summary = build_blockage_summary(*_empty_tiers())
        names = [t.tier_name for t in summary.by_tier]
        assert names == ["Agent", "Execution", "Submit"]

    def test_per_tier_counts(self):
        tiers = _blocked_tiers(agent_b=3, agent_t=10, exec_b=1, exec_t=8, sub_b=2, sub_t=6)
        summary = build_blockage_summary(*tiers)
        assert summary.by_tier[0].blocked_count == 3
        assert summary.by_tier[1].blocked_count == 1
        assert summary.by_tier[2].blocked_count == 2

    def test_per_tier_rate(self):
        tiers = _blocked_tiers(agent_b=5, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.by_tier[0].blockage_rate == 0.5

    def test_tier_blockage_is_typed(self):
        summary = build_blockage_summary(*_empty_tiers())
        for t in summary.by_tier:
            assert isinstance(t, TierBlockage)


# =========================================================================== #
# AXIS 3: Reason Aggregation                                                   #
# =========================================================================== #


class TestReasonAggregation:
    def test_reasons_aggregated_across_tiers(self):
        tiers = _blocked_tiers(
            agent_b=2,
            agent_t=5,
            agent_reasons=["CHECK_A: 2"],
            exec_b=1,
            exec_t=3,
            exec_reasons=["CHECK_A: 1", "CHECK_B: 1"],
        )
        summary = build_blockage_summary(*tiers)
        reason_dict = {r.reason: r.count for r in summary.top_reasons}
        assert reason_dict.get("CHECK_A", 0) == 3
        assert reason_dict.get("CHECK_B", 0) == 1

    def test_no_reasons_when_no_blocks(self):
        summary = build_blockage_summary(*_empty_tiers())
        assert len(summary.top_reasons) == 0

    def test_reasons_ordered_by_count(self):
        tiers = _blocked_tiers(
            agent_b=5,
            agent_t=10,
            agent_reasons=["HIGH: 5", "LOW: 1"],
        )
        summary = build_blockage_summary(*tiers)
        if len(summary.top_reasons) >= 2:
            assert summary.top_reasons[0].count >= summary.top_reasons[1].count

    def test_reason_aggregation_is_typed(self):
        tiers = _blocked_tiers(agent_b=1, agent_t=5, agent_reasons=["X: 1"])
        summary = build_blockage_summary(*tiers)
        for r in summary.top_reasons:
            assert isinstance(r, ReasonAggregation)


# =========================================================================== #
# AXIS 4: Density Signal                                                       #
# =========================================================================== #


class TestDensitySignal:
    def test_no_blocks_description(self):
        summary = build_blockage_summary(*_empty_tiers())
        assert summary.density.description == "No blocked proposals."
        assert summary.density.is_concentrated is False

    def test_concentrated_when_single_tier_dominant(self):
        """All blocks in agent → 100% → concentrated."""
        tiers = _blocked_tiers(agent_b=5, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.density.is_concentrated is True
        assert summary.density.dominant_tier == "Agent"

    def test_not_concentrated_when_spread(self):
        """Blocks spread across tiers → not concentrated."""
        tiers = _blocked_tiers(agent_b=2, agent_t=10, exec_b=2, exec_t=10, sub_b=2, sub_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.density.is_concentrated is False

    def test_high_blockage_detected(self):
        """Agent 8/10 = 80% → high blockage."""
        tiers = _blocked_tiers(agent_b=8, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.density.has_high_blockage is True

    def test_no_high_blockage_at_low_rate(self):
        """Agent 1/10 = 10% → not high."""
        tiers = _blocked_tiers(agent_b=1, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.density.has_high_blockage is False

    def test_density_signal_is_typed(self):
        summary = build_blockage_summary(*_empty_tiers())
        assert isinstance(summary.density, BlockageDensitySignal)

    def test_description_includes_count(self):
        tiers = _blocked_tiers(agent_b=3, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert "3 blocked" in summary.density.description


# =========================================================================== #
# AXIS 5: Safety Invariants                                                    #
# =========================================================================== #


class TestSafetyInvariants:
    def test_safety_all_true_empty(self):
        summary = build_blockage_summary(*_empty_tiers())
        assert summary.safety.read_only is True
        assert summary.safety.simulation_only is True
        assert summary.safety.no_action_executed is True
        assert summary.safety.no_prediction is True

    def test_safety_all_true_with_data(self):
        tiers = _blocked_tiers(agent_b=5, agent_t=10)
        summary = build_blockage_summary(*tiers)
        assert summary.safety.read_only is True
        assert summary.safety.no_prediction is True

    def test_safety_has_four_fields(self):
        fields = set(BlockageSafety.model_fields.keys())
        assert fields == {"read_only", "simulation_only", "no_action_executed", "no_prediction"}

    def test_source_has_no_write_methods(self):
        import inspect
        import app.services.blockage_summary_service as mod

        source = inspect.getsource(mod)
        forbidden = [
            "propose_and_guard",
            "record_receipt",
            "transition_to",
            ".delete(",
            ".remove(",
            ".write(",
        ]
        for keyword in forbidden:
            assert keyword not in source, f"Forbidden keyword '{keyword}' in source"

    def test_source_has_no_prediction_keywords(self):
        import inspect
        import app.services.blockage_summary_service as mod

        source = inspect.getsource(mod)
        forbidden = ["predict", "forecast", "score(", "auto_promote", "auto_escalate", "auto_judge"]
        for keyword in forbidden:
            assert keyword not in source, f"Prediction keyword '{keyword}' in source"

    def test_serializes_to_json(self):
        tiers = _blocked_tiers(agent_b=2, agent_t=10)
        summary = build_blockage_summary(*tiers)
        j = json.loads(summary.model_dump_json())
        assert "total_blocked" in j
        assert "safety" in j
        assert j["safety"]["no_prediction"] is True


# =========================================================================== #
# AXIS 6: Schema Drift Sentinel                                                #
# =========================================================================== #


class TestSchemaDriftSentinel:
    def test_blockage_summary_field_count(self):
        assert len(BlockageSummarySchema.model_fields) == 7

    def test_blockage_summary_field_names(self):
        expected = {
            "total_blocked",
            "total_proposals",
            "overall_blockage_rate",
            "by_tier",
            "top_reasons",
            "density",
            "safety",
        }
        assert set(BlockageSummarySchema.model_fields.keys()) == expected

    def test_tier_blockage_field_count(self):
        assert len(TierBlockage.model_fields) == 4

    def test_reason_aggregation_field_count(self):
        assert len(ReasonAggregation.model_fields) == 2

    def test_density_signal_field_count(self):
        assert len(BlockageDensitySignal.model_fields) == 6

    def test_safety_field_count(self):
        assert len(BlockageSafety.model_fields) == 4


# =========================================================================== #
# AXIS 7: Board Integration                                                    #
# =========================================================================== #


class TestBoardIntegration:
    def test_board_schema_has_blockage_summary(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse

        assert "blockage_summary" in FourTierBoardResponse.model_fields

    def test_board_schema_blockage_is_typed(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse

        field_info = FourTierBoardResponse.model_fields["blockage_summary"]
        assert field_info.annotation is BlockageSummarySchema

    def test_board_service_returns_typed_blockage(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert isinstance(board.blockage_summary, BlockageSummarySchema)

    def test_board_blockage_safety_intact(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.blockage_summary.safety.read_only is True
        assert board.blockage_summary.safety.no_prediction is True

    def test_board_serializes_blockage_to_json(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        assert "blockage_summary" in j
        assert "total_blocked" in j["blockage_summary"]
        assert j["blockage_summary"]["safety"]["no_prediction"] is True

    def test_board_blockage_empty_is_zero_safe(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.blockage_summary.total_blocked == 0
        assert board.blockage_summary.total_proposals == 0
        assert board.blockage_summary.overall_blockage_rate == 0.0
