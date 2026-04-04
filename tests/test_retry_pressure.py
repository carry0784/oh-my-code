"""
K-Dexter Retry Pressure Observation Tests

Sprint Contract: Phase C — Retry Pressure Observation Card

Tests the retry pressure observation card:
  AXIS 1: Backlog Accuracy (counts, ratios, totals)
  AXIS 2: Status Distribution (pending/cancelled/executed/expired)
  AXIS 3: Channel Distribution (per-channel pending breakdown)
  AXIS 4: Density Signal (pending detection, channel concentration)
  AXIS 5: Safety Invariants (read-only, no prediction, no write)
  AXIS 6: Schema Drift Sentinel (field count/name snapshot)
  AXIS 7: Board Integration (schema field, typed return, safety, JSON)

Run: pytest tests/test_retry_pressure.py -v
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

from app.services.retry_pressure_service import build_retry_pressure
from app.schemas.retry_pressure_schema import (
    RetryPressureSchema,
    RetryStatusDistribution,
    RetryChannelDistribution,
    RetrySeverityDistribution,
    RetryDensitySignal,
    RetryPressureSafety,
)
from app.core.retry_plan_store import RetryPlanStore


# -- Helpers ---------------------------------------------------------------- #

def _empty_store():
    return RetryPlanStore(max_plans=100, ttl_seconds=3600)


def _store_with_plans(plans):
    """Create store and manually inject plans (bypass enqueue for test control)."""
    from app.core.retry_plan_store import RetryPlan
    store = RetryPlanStore(max_plans=200, ttl_seconds=3600)
    for p in plans:
        plan = RetryPlan(
            retry_id=p.get("retry_id", f"R-{len(store._plans)}"),
            created_at=p.get("created_at", "2026-03-31T00:00:00Z"),
            incident=p.get("incident", "INC-1"),
            channel=p.get("channel", "slack"),
            reason=p.get("reason", "test"),
            status=p.get("status", "pending"),
            severity_tier=p.get("severity_tier", "medium"),
        )
        store._plans.append(plan)
    return store


def _pending_plans(count, channel="slack", severity="medium"):
    return [
        {"status": "pending", "channel": channel, "severity_tier": severity}
        for _ in range(count)
    ]


# =========================================================================== #
# AXIS 1: Backlog Accuracy                                                     #
# =========================================================================== #

class TestBacklogAccuracy:

    def test_none_store_zero_pressure(self):
        pressure = build_retry_pressure(None)
        assert pressure.total_plans == 0
        assert pressure.pending_count == 0
        assert pressure.backlog_ratio == 0.0

    def test_empty_store_zero_pressure(self):
        pressure = build_retry_pressure(_empty_store())
        assert pressure.total_plans == 0
        assert pressure.pending_count == 0

    def test_pending_count_correct(self):
        store = _store_with_plans(_pending_plans(5))
        pressure = build_retry_pressure(store)
        assert pressure.pending_count == 5
        assert pressure.total_plans == 5

    def test_backlog_ratio_calculation(self):
        plans = _pending_plans(3) + [{"status": "executed"}, {"status": "expired"}]
        store = _store_with_plans(plans)
        pressure = build_retry_pressure(store)
        assert pressure.total_plans == 5
        assert pressure.pending_count == 3
        assert abs(pressure.backlog_ratio - 0.6) < 0.01

    def test_all_executed_zero_backlog(self):
        plans = [{"status": "executed"} for _ in range(3)]
        store = _store_with_plans(plans)
        pressure = build_retry_pressure(store)
        assert pressure.pending_count == 0
        assert pressure.backlog_ratio == 0.0


# =========================================================================== #
# AXIS 2: Status Distribution                                                  #
# =========================================================================== #

class TestStatusDistribution:

    def test_all_statuses_counted(self):
        plans = [
            {"status": "pending"},
            {"status": "pending"},
            {"status": "cancelled"},
            {"status": "executed"},
            {"status": "expired"},
        ]
        store = _store_with_plans(plans)
        pressure = build_retry_pressure(store)
        assert pressure.by_status.pending == 2
        assert pressure.by_status.cancelled == 1
        assert pressure.by_status.executed == 1
        assert pressure.by_status.expired == 1

    def test_empty_status_all_zero(self):
        pressure = build_retry_pressure(_empty_store())
        assert pressure.by_status.pending == 0
        assert pressure.by_status.cancelled == 0
        assert pressure.by_status.executed == 0
        assert pressure.by_status.expired == 0

    def test_status_distribution_is_typed(self):
        pressure = build_retry_pressure(None)
        assert isinstance(pressure.by_status, RetryStatusDistribution)


# =========================================================================== #
# AXIS 3: Channel Distribution                                                 #
# =========================================================================== #

class TestChannelDistribution:

    def test_single_channel_counted(self):
        store = _store_with_plans(_pending_plans(3, channel="slack"))
        pressure = build_retry_pressure(store)
        assert len(pressure.by_channel) == 1
        assert pressure.by_channel[0].channel == "slack"
        assert pressure.by_channel[0].count == 3

    def test_multiple_channels(self):
        plans = _pending_plans(2, channel="slack") + _pending_plans(1, channel="email")
        store = _store_with_plans(plans)
        pressure = build_retry_pressure(store)
        assert len(pressure.by_channel) == 2
        channels = {c.channel: c.count for c in pressure.by_channel}
        assert channels["slack"] == 2
        assert channels["email"] == 1

    def test_only_pending_in_channel_distribution(self):
        """Executed plans should not appear in channel distribution."""
        plans = _pending_plans(2, channel="slack") + [{"status": "executed", "channel": "email"}]
        store = _store_with_plans(plans)
        pressure = build_retry_pressure(store)
        channels = {c.channel for c in pressure.by_channel}
        assert "email" not in channels

    def test_channel_distribution_is_typed(self):
        store = _store_with_plans(_pending_plans(1))
        pressure = build_retry_pressure(store)
        for c in pressure.by_channel:
            assert isinstance(c, RetryChannelDistribution)


# =========================================================================== #
# AXIS 4: Density Signal                                                       #
# =========================================================================== #

class TestDensitySignal:

    def test_no_plans_description(self):
        pressure = build_retry_pressure(None)
        assert pressure.density.description == "No retry plans."
        assert pressure.density.has_pending is False

    def test_has_pending_flag(self):
        store = _store_with_plans(_pending_plans(2))
        pressure = build_retry_pressure(store)
        assert pressure.density.has_pending is True

    def test_concentrated_when_single_channel(self):
        """All pending in one channel → concentrated."""
        store = _store_with_plans(_pending_plans(5, channel="slack"))
        pressure = build_retry_pressure(store)
        assert pressure.density.is_channel_concentrated is True
        assert pressure.density.dominant_channel == "slack"

    def test_not_concentrated_when_spread(self):
        plans = _pending_plans(2, channel="slack") + _pending_plans(2, channel="email") + _pending_plans(2, channel="pager")
        store = _store_with_plans(plans)
        pressure = build_retry_pressure(store)
        assert pressure.density.is_channel_concentrated is False

    def test_density_signal_is_typed(self):
        pressure = build_retry_pressure(None)
        assert isinstance(pressure.density, RetryDensitySignal)

    def test_description_includes_count(self):
        store = _store_with_plans(_pending_plans(3))
        pressure = build_retry_pressure(store)
        assert "3" in pressure.density.description
        assert "pending" in pressure.density.description


# =========================================================================== #
# AXIS 5: Safety Invariants                                                    #
# =========================================================================== #

class TestSafetyInvariants:

    def test_safety_all_true_empty(self):
        pressure = build_retry_pressure(None)
        assert pressure.safety.read_only is True
        assert pressure.safety.simulation_only is True
        assert pressure.safety.no_action_executed is True
        assert pressure.safety.no_prediction is True

    def test_safety_all_true_with_data(self):
        store = _store_with_plans(_pending_plans(5))
        pressure = build_retry_pressure(store)
        assert pressure.safety.read_only is True
        assert pressure.safety.no_prediction is True

    def test_safety_has_four_fields(self):
        fields = set(RetryPressureSafety.model_fields.keys())
        assert fields == {"read_only", "simulation_only", "no_action_executed", "no_prediction"}

    def test_source_has_no_write_methods(self):
        import inspect
        import app.services.retry_pressure_service as mod
        source = inspect.getsource(mod)
        forbidden = ["propose_and_guard", "record_receipt", "transition_to",
                      ".delete(", ".write(", "enqueue("]
        for keyword in forbidden:
            assert keyword not in source, f"Forbidden keyword '{keyword}' in source"

    def test_source_has_no_prediction_keywords(self):
        import inspect
        import app.services.retry_pressure_service as mod
        source = inspect.getsource(mod)
        forbidden = ["predict", "forecast", "score(", "auto_promote",
                      "auto_escalate", "auto_judge"]
        for keyword in forbidden:
            assert keyword not in source, f"Prediction keyword '{keyword}' in source"

    def test_serializes_to_json(self):
        store = _store_with_plans(_pending_plans(2))
        pressure = build_retry_pressure(store)
        j = json.loads(pressure.model_dump_json())
        assert "total_plans" in j
        assert "safety" in j
        assert j["safety"]["no_prediction"] is True


# =========================================================================== #
# AXIS 6: Schema Drift Sentinel                                                #
# =========================================================================== #

class TestSchemaDriftSentinel:

    def test_retry_pressure_field_count(self):
        assert len(RetryPressureSchema.model_fields) == 8

    def test_retry_pressure_field_names(self):
        expected = {
            "total_plans", "pending_count", "backlog_ratio",
            "by_status", "by_channel", "by_severity", "density", "safety",
        }
        assert set(RetryPressureSchema.model_fields.keys()) == expected

    def test_status_distribution_field_count(self):
        assert len(RetryStatusDistribution.model_fields) == 4

    def test_channel_distribution_field_count(self):
        assert len(RetryChannelDistribution.model_fields) == 2

    def test_severity_distribution_field_count(self):
        assert len(RetrySeverityDistribution.model_fields) == 2

    def test_density_signal_field_count(self):
        assert len(RetryDensitySignal.model_fields) == 6

    def test_safety_field_count(self):
        assert len(RetryPressureSafety.model_fields) == 4


# =========================================================================== #
# AXIS 7: Board Integration                                                    #
# =========================================================================== #

class TestBoardIntegration:

    def test_board_schema_has_retry_pressure(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        assert "retry_pressure" in FourTierBoardResponse.model_fields

    def test_board_schema_retry_pressure_is_typed(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        field_info = FourTierBoardResponse.model_fields["retry_pressure"]
        assert field_info.annotation is RetryPressureSchema

    def test_board_service_returns_typed_retry_pressure(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert isinstance(board.retry_pressure, RetryPressureSchema)

    def test_board_retry_pressure_safety_intact(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.retry_pressure.safety.read_only is True
        assert board.retry_pressure.safety.no_prediction is True

    def test_board_serializes_retry_pressure_to_json(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        assert "retry_pressure" in j
        assert "total_plans" in j["retry_pressure"]
        assert j["retry_pressure"]["safety"]["no_prediction"] is True

    def test_board_retry_pressure_empty_is_zero_safe(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.retry_pressure.total_plans == 0
        assert board.retry_pressure.pending_count == 0
        assert board.retry_pressure.backlog_ratio == 0.0
