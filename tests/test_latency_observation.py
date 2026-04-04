"""
K-Dexter Latency Observation Tests (v1)

Sprint Contract: Phase C — Latency Observation Card

Tests the per-tier latency observation card:
  AXIS 1: Zero-Safe / Partial-Safe (None ledgers, empty ledgers)
  AXIS 2: Per-Tier Elapsed Calculation (min, max, median)
  AXIS 3: Excluded / Sample Handling (parse failure, negative, limit)
  AXIS 4: Density Signal (templates, tier count, slowest)
  AXIS 5: Safety Invariants (read-only, no prediction, no write)
  AXIS 6: Schema Drift Sentinel (field count/name snapshot)
  AXIS 7: Board Integration (schema field, typed return, safety, JSON)

Run: pytest tests/test_latency_observation.py -v
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

from app.services.latency_observation_service import build_latency_observation
from app.schemas.latency_observation_schema import (
    LatencyObservationSchema,
    TierLatency,
    LatencyDensitySignal,
    LatencySafety,
)


# -- Helpers ---------------------------------------------------------------- #


class FakeLedger:
    """Minimal ledger mock that returns proposal dicts."""

    def __init__(self, proposals=None):
        self._proposals = proposals or []

    def get_proposals(self):
        return self._proposals


class FakeOrderExecutor:
    """Minimal order executor mock that returns history dicts."""

    def __init__(self, history=None):
        self._history = history or []

    def get_history(self):
        return self._history


def _make_proposal(created_at, receipt_timestamp=None, receipt_key="created_at"):
    """Build a proposal dict with optional receipt."""
    p = {"proposal_id": "P-1", "created_at": created_at}
    if receipt_timestamp is not None:
        p["receipt"] = {receipt_key: receipt_timestamp}
    return p


def _make_order(created_at, executed_at=None):
    """Build an order dict."""
    o = {"order_id": "OX-1", "created_at": created_at}
    if executed_at is not None:
        o["executed_at"] = executed_at
    return o


# =========================================================================== #
# AXIS 1: Zero-Safe / Partial-Safe                                             #
# =========================================================================== #


class TestZeroSafe:
    def test_all_none_returns_zero_safe(self):
        obs = build_latency_observation(None, None, None, None)
        assert obs.agent_latency.measured is False
        assert obs.execution_latency.measured is False
        assert obs.submit_latency.measured is False
        assert obs.order_latency.measured is False

    def test_all_none_density_no_measurements(self):
        obs = build_latency_observation(None, None, None, None)
        assert obs.density.has_measurements is False
        assert obs.density.description == "No latency measurements available."

    def test_empty_ledger_returns_unmeasured(self):
        obs = build_latency_observation(
            action_ledger=FakeLedger([]),
            execution_ledger=FakeLedger([]),
            submit_ledger=FakeLedger([]),
            order_executor=FakeOrderExecutor([]),
        )
        assert obs.agent_latency.measured is False
        assert obs.agent_latency.sample_size == 0

    def test_partial_ledgers_only_measures_available(self):
        """Only agent ledger provided; others are None."""
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:05Z")]
        obs = build_latency_observation(
            action_ledger=FakeLedger(proposals),
        )
        assert obs.agent_latency.measured is True
        assert obs.execution_latency.measured is False
        assert obs.submit_latency.measured is False
        assert obs.order_latency.measured is False

    def test_proposals_without_receipt_not_measured(self):
        """Proposals without receipt should not contribute to measurement."""
        proposals = [_make_proposal("2026-03-31T00:00:00Z")]  # no receipt
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.measured is False
        assert obs.agent_latency.excluded_count == 0  # no receipt = skip, not exclude


# =========================================================================== #
# AXIS 2: Per-Tier Elapsed Calculation                                         #
# =========================================================================== #


class TestPerTierElapsed:
    def test_agent_tier_single_measurement(self):
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:03Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.measured is True
        assert obs.agent_latency.sample_size == 1
        assert obs.agent_latency.median_seconds == 3.0
        assert obs.agent_latency.min_seconds == 3.0
        assert obs.agent_latency.max_seconds == 3.0

    def test_agent_tier_multiple_measurements(self):
        proposals = [
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:01Z"),
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:05Z"),
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:03Z"),
        ]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.sample_size == 3
        assert obs.agent_latency.min_seconds == 1.0
        assert obs.agent_latency.max_seconds == 5.0
        assert obs.agent_latency.median_seconds == 3.0

    def test_execution_tier_uses_execution_ready_at(self):
        proposals = [
            _make_proposal(
                "2026-03-31T00:00:00Z", "2026-03-31T00:00:02Z", receipt_key="execution_ready_at"
            ),
        ]
        obs = build_latency_observation(execution_ledger=FakeLedger(proposals))
        assert obs.execution_latency.measured is True
        assert obs.execution_latency.median_seconds == 2.0

    def test_submit_tier_uses_submit_ready_at(self):
        proposals = [
            _make_proposal(
                "2026-03-31T00:00:00Z", "2026-03-31T00:00:04Z", receipt_key="submit_ready_at"
            ),
        ]
        obs = build_latency_observation(submit_ledger=FakeLedger(proposals))
        assert obs.submit_latency.measured is True
        assert obs.submit_latency.median_seconds == 4.0

    def test_order_tier_uses_executed_at(self):
        history = [_make_order("2026-03-31T00:00:00Z", "2026-03-31T00:00:01.5Z")]
        obs = build_latency_observation(order_executor=FakeOrderExecutor(history))
        assert obs.order_latency.measured is True
        assert obs.order_latency.median_seconds == 1.5

    def test_median_even_count(self):
        """Median of even-count list is average of two middle values."""
        proposals = [
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:02Z"),
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:04Z"),
        ]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.median_seconds == 3.0

    def test_zero_elapsed_is_valid(self):
        """Elapsed == 0 is valid (start == end)."""
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:00Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.measured is True
        assert obs.agent_latency.median_seconds == 0.0

    def test_tier_names_correct(self):
        obs = build_latency_observation(None, None, None, None)
        assert obs.agent_latency.tier_name == "Agent"
        assert obs.agent_latency.tier_number == 1
        assert obs.execution_latency.tier_name == "Execution"
        assert obs.execution_latency.tier_number == 2
        assert obs.submit_latency.tier_name == "Submit"
        assert obs.submit_latency.tier_number == 3
        assert obs.order_latency.tier_name == "Orders"
        assert obs.order_latency.tier_number == 4


# =========================================================================== #
# AXIS 3: Excluded / Sample Handling                                           #
# =========================================================================== #


class TestExcludedSampleHandling:
    def test_unparseable_start_excluded(self):
        proposals = [_make_proposal("NOT-A-DATE", "2026-03-31T00:00:03Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.measured is False
        assert obs.agent_latency.excluded_count == 1

    def test_unparseable_end_excluded(self):
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "GARBAGE")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.excluded_count == 1

    def test_negative_elapsed_excluded(self):
        """End before start → excluded."""
        proposals = [_make_proposal("2026-03-31T00:00:05Z", "2026-03-31T00:00:00Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.excluded_count == 1
        assert obs.agent_latency.measured is False

    def test_missing_receipt_timestamp_excluded(self):
        """Receipt exists but lacks the expected timestamp key."""
        proposals = [
            {
                "proposal_id": "P-1",
                "created_at": "2026-03-31T00:00:00Z",
                "receipt": {"other_field": "value"},
            }
        ]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.excluded_count == 1

    def test_sample_limited_flag(self):
        """More than 200 proposals → sample_limited=True."""
        proposals = [
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:01Z") for _ in range(250)
        ]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.sample_limited is True
        assert obs.agent_latency.sample_size == 200

    def test_under_limit_not_flagged(self):
        proposals = [
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:01Z") for _ in range(50)
        ]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.sample_limited is False
        assert obs.agent_latency.sample_size == 50

    def test_mixed_valid_and_excluded(self):
        """Valid + excluded should only count valid in sample_size."""
        proposals = [
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:03Z"),
            _make_proposal("BAD", "2026-03-31T00:00:03Z"),
            _make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:05Z"),
        ]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.agent_latency.sample_size == 2
        assert obs.agent_latency.excluded_count == 1
        assert obs.agent_latency.measured is True


# =========================================================================== #
# AXIS 4: Density Signal                                                       #
# =========================================================================== #


class TestDensitySignal:
    def test_no_measurements_description(self):
        obs = build_latency_observation(None, None, None, None)
        assert obs.density.description == "No latency measurements available."
        assert obs.density.has_measurements is False
        assert obs.density.tiers_measured == 0

    def test_single_tier_description(self):
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:02Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.density.has_measurements is True
        assert obs.density.tiers_measured == 1
        assert "1 tier(s) measured" in obs.density.description
        assert "Agent" in obs.density.description

    def test_multi_tier_description_shows_slowest(self):
        agent_proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:01Z")]
        exec_proposals = [
            _make_proposal(
                "2026-03-31T00:00:00Z", "2026-03-31T00:00:10Z", receipt_key="execution_ready_at"
            ),
        ]
        obs = build_latency_observation(
            action_ledger=FakeLedger(agent_proposals),
            execution_ledger=FakeLedger(exec_proposals),
        )
        assert obs.density.tiers_measured == 2
        assert obs.density.slowest_tier == "Execution"
        assert obs.density.slowest_median == 10.0
        assert "2 tier(s) measured" in obs.density.description
        assert "Execution" in obs.density.description

    def test_density_signal_is_typed(self):
        obs = build_latency_observation(None, None, None, None)
        assert isinstance(obs.density, LatencyDensitySignal)


# =========================================================================== #
# AXIS 5: Safety Invariants                                                    #
# =========================================================================== #


class TestSafetyInvariants:
    def test_safety_all_true_empty(self):
        obs = build_latency_observation(None, None, None, None)
        assert obs.safety.read_only is True
        assert obs.safety.simulation_only is True
        assert obs.safety.no_action_executed is True
        assert obs.safety.no_prediction is True

    def test_safety_all_true_with_data(self):
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:03Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        assert obs.safety.read_only is True
        assert obs.safety.no_prediction is True

    def test_safety_has_four_fields(self):
        fields = set(LatencySafety.model_fields.keys())
        assert fields == {"read_only", "simulation_only", "no_action_executed", "no_prediction"}

    def test_source_has_no_write_methods(self):
        import inspect
        import app.services.latency_observation_service as mod

        source = inspect.getsource(mod)
        forbidden = [
            "propose_and_guard",
            "record_receipt",
            "transition_to",
            ".delete(",
            ".write(",
            "enqueue(",
        ]
        for keyword in forbidden:
            assert keyword not in source, f"Forbidden keyword '{keyword}' in source"

    def test_source_has_no_prediction_keywords(self):
        import inspect
        import app.services.latency_observation_service as mod

        source = inspect.getsource(mod)
        forbidden = [
            "predict",
            "forecast",
            "score(",
            "auto_promote",
            "auto_escalate",
            "auto_judge",
            "SLA",
            "threshold",
        ]
        for keyword in forbidden:
            assert keyword not in source, f"Prediction keyword '{keyword}' in source"

    def test_source_has_no_judgment_words(self):
        """v1 constraint: no slow/fast/degraded/alert/warning in source."""
        import inspect
        import app.services.latency_observation_service as mod

        source = inspect.getsource(mod)
        forbidden = [
            '"slow"',
            '"fast"',
            '"degraded"',
            '"alert"',
            '"warning"',
            '"breach"',
            '"target"',
            '"normal"',
            '"abnormal"',
        ]
        for keyword in forbidden:
            assert keyword not in source, f"Judgment word {keyword} in source"

    def test_serializes_to_json(self):
        proposals = [_make_proposal("2026-03-31T00:00:00Z", "2026-03-31T00:00:03Z")]
        obs = build_latency_observation(action_ledger=FakeLedger(proposals))
        j = json.loads(obs.model_dump_json())
        assert "agent_latency" in j
        assert "safety" in j
        assert j["safety"]["no_prediction"] is True
        assert j["agent_latency"]["measured"] is True


# =========================================================================== #
# AXIS 6: Schema Drift Sentinel                                                #
# =========================================================================== #


class TestSchemaDriftSentinel:
    def test_latency_observation_field_count(self):
        assert len(LatencyObservationSchema.model_fields) == 6

    def test_latency_observation_field_names(self):
        expected = {
            "agent_latency",
            "execution_latency",
            "submit_latency",
            "order_latency",
            "density",
            "safety",
        }
        assert set(LatencyObservationSchema.model_fields.keys()) == expected

    def test_tier_latency_field_count(self):
        assert len(TierLatency.model_fields) == 9

    def test_tier_latency_field_names(self):
        expected = {
            "tier_name",
            "tier_number",
            "measured",
            "sample_size",
            "excluded_count",
            "sample_limited",
            "min_seconds",
            "max_seconds",
            "median_seconds",
        }
        assert set(TierLatency.model_fields.keys()) == expected

    def test_density_signal_field_count(self):
        assert len(LatencyDensitySignal.model_fields) == 5

    def test_safety_field_count(self):
        assert len(LatencySafety.model_fields) == 4


# =========================================================================== #
# AXIS 7: Board Integration                                                    #
# =========================================================================== #


class TestBoardIntegration:
    def test_board_schema_has_latency_observation(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse

        assert "latency_observation" in FourTierBoardResponse.model_fields

    def test_board_schema_latency_is_typed(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse

        field_info = FourTierBoardResponse.model_fields["latency_observation"]
        assert field_info.annotation is LatencyObservationSchema

    def test_board_service_returns_typed_latency(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert isinstance(board.latency_observation, LatencyObservationSchema)

    def test_board_latency_safety_intact(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.latency_observation.safety.read_only is True
        assert board.latency_observation.safety.no_prediction is True

    def test_board_serializes_latency_to_json(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        assert "latency_observation" in j
        assert "agent_latency" in j["latency_observation"]
        assert j["latency_observation"]["safety"]["no_prediction"] is True

    def test_board_latency_empty_is_zero_safe(self):
        from app.services.four_tier_board_service import build_four_tier_board

        board = build_four_tier_board()
        assert board.latency_observation.agent_latency.measured is False
        assert board.latency_observation.agent_latency.sample_size == 0
        assert board.latency_observation.density.has_measurements is False
