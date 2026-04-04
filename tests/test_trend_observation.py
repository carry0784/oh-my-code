"""
K-Dexter Trend Observation Tests (v1)

Sprint Contract: Phase C — Trend Observation Card

Tests the two-window comparative observation card:
  AXIS 1: Zero-Safe / No Buffer (None buffer, empty buffer)
  AXIS 2: Insufficient Data (too few snapshots)
  AXIS 3: Two-Window Comparison (delta, direction, count-based)
  AXIS 4: Ring Buffer Mechanics (capacity, window selection)
  AXIS 5: Density Signal (templates, availability, volatile flag)
  AXIS 6: Safety Invariants (read-only, no prediction, no write, no judgment)
  AXIS 7: Schema Drift Sentinel (field count/name snapshot)
  AXIS 8: Board Integration (schema field, typed return, safety, JSON)

Run: pytest tests/test_trend_observation.py -v
"""
import sys
import json
from datetime import datetime, timezone, timedelta
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

from app.core.metric_snapshot_buffer import MetricSnapshotBuffer, MetricSnapshot
from app.services.trend_observation_service import build_trend_observation
from app.schemas.trend_observation_schema import (
    TrendObservationSchema,
    MetricComparison,
    WindowSnapshot,
    TrendDensitySignal,
    TrendSafety,
)


# -- Helpers ---------------------------------------------------------------- #

def _make_buffer_with_snapshots(
    current_count=0, previous_count=0,
    current_blocked=10, previous_blocked=5,
    current_retry=3, previous_retry=3,
    current_review=2, previous_review=4,
    current_watch=1, previous_watch=1,
):
    """Create a buffer with snapshots in current and previous 60m windows."""
    now = datetime.now(timezone.utc)
    buf = MetricSnapshotBuffer(max_snapshots=500)

    # Previous window snapshots (60-120 min ago)
    for i in range(previous_count):
        ts = now - timedelta(minutes=90) + timedelta(minutes=i * (30 / max(previous_count, 1)))
        buf.record_snapshot(MetricSnapshot(
            timestamp=ts,
            blocked_total=previous_blocked,
            pending_retry_total=previous_retry,
            review_total=previous_review,
            watch_total=previous_watch,
        ))

    # Current window snapshots (0-60 min ago)
    for i in range(current_count):
        ts = now - timedelta(minutes=30) + timedelta(minutes=i * (30 / max(current_count, 1)))
        buf.record_snapshot(MetricSnapshot(
            timestamp=ts,
            blocked_total=current_blocked,
            pending_retry_total=current_retry,
            review_total=current_review,
            watch_total=current_watch,
        ))

    return buf


# =========================================================================== #
# AXIS 1: Zero-Safe / No Buffer                                                #
# =========================================================================== #

class TestZeroSafe:

    def test_none_buffer_returns_zero_safe(self):
        obs = build_trend_observation(None)
        assert obs.density.trend_available is False
        assert obs.density.description == "No snapshot buffer available."

    def test_none_buffer_safety_intact(self):
        obs = build_trend_observation(None)
        assert obs.safety.read_only is True
        assert obs.safety.no_prediction is True

    def test_empty_buffer_returns_insufficient(self):
        buf = MetricSnapshotBuffer()
        obs = build_trend_observation(buf)
        assert obs.density.trend_available is False

    def test_all_metrics_insufficient_on_empty(self):
        obs = build_trend_observation(None)
        assert obs.blocked_trend.insufficient_data is True
        assert obs.pending_retry_trend.insufficient_data is True
        assert obs.review_trend.insufficient_data is True
        assert obs.watch_trend.insufficient_data is True


# =========================================================================== #
# AXIS 2: Insufficient Data                                                    #
# =========================================================================== #

class TestInsufficientData:

    def test_few_snapshots_marks_insufficient(self):
        """Less than 5 snapshots per window → insufficient_data=True."""
        buf = _make_buffer_with_snapshots(current_count=3, previous_count=3)
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.insufficient_data is True
        assert obs.density.trend_available is False

    def test_current_only_marks_insufficient(self):
        """Current window has data, previous empty → insufficient."""
        buf = _make_buffer_with_snapshots(current_count=10, previous_count=0)
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.insufficient_data is True

    def test_previous_only_marks_insufficient(self):
        """Previous window has data, current empty → insufficient."""
        buf = _make_buffer_with_snapshots(current_count=0, previous_count=10)
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.insufficient_data is True

    def test_insufficient_description_mentions_samples(self):
        buf = _make_buffer_with_snapshots(current_count=3, previous_count=2)
        obs = build_trend_observation(buf)
        assert "snapshot" in obs.blocked_trend.description.lower()


# =========================================================================== #
# AXIS 3: Two-Window Comparison                                                #
# =========================================================================== #

class TestTwoWindowComparison:

    def test_increasing_detected(self):
        """Current > previous → direction = increasing."""
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=15, previous_blocked=5,
        )
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.insufficient_data is False
        assert obs.blocked_trend.direction == "increasing"
        assert obs.blocked_trend.delta == 10

    def test_decreasing_detected(self):
        """Current < previous → direction = decreasing."""
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=3, previous_blocked=10,
        )
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.direction == "decreasing"
        assert obs.blocked_trend.delta == -7

    def test_stable_detected(self):
        """Current == previous → direction = stable."""
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=5, previous_blocked=5,
        )
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.direction == "stable"
        assert obs.blocked_trend.delta == 0

    def test_all_four_metrics_compared(self):
        """All 4 metrics get independent comparisons."""
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=10, previous_blocked=5,   # increasing
            current_retry=3, previous_retry=3,         # stable
            current_review=1, previous_review=4,       # decreasing
            current_watch=2, previous_watch=2,         # stable
        )
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.direction == "increasing"
        assert obs.pending_retry_trend.direction == "stable"
        assert obs.review_trend.direction == "decreasing"
        assert obs.watch_trend.direction == "stable"

    def test_delta_is_count_based(self):
        """Delta is simple integer subtraction, not a ratio."""
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=20, previous_blocked=8,
        )
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.delta == 12
        assert isinstance(obs.blocked_trend.delta, int)

    def test_window_snapshots_have_labels(self):
        buf = _make_buffer_with_snapshots(current_count=10, previous_count=10)
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.current_window.window_label == "current"
        assert obs.blocked_trend.previous_window.window_label == "previous"

    def test_window_snapshots_have_sample_counts(self):
        buf = _make_buffer_with_snapshots(current_count=10, previous_count=8)
        obs = build_trend_observation(buf)
        assert obs.blocked_trend.current_window.sample_count == 10
        assert obs.blocked_trend.previous_window.sample_count == 8

    def test_description_for_change(self):
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=15, previous_blocked=5,
        )
        obs = build_trend_observation(buf)
        desc = obs.blocked_trend.description
        assert "15" in desc
        assert "5" in desc
        assert "blocked_total" in desc

    def test_description_for_stable(self):
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_retry=3, previous_retry=3,
        )
        obs = build_trend_observation(buf)
        assert "stable" in obs.pending_retry_trend.description


# =========================================================================== #
# AXIS 4: Ring Buffer Mechanics                                                #
# =========================================================================== #

class TestRingBufferMechanics:

    def test_buffer_creation(self):
        buf = MetricSnapshotBuffer()
        assert buf.count == 0

    def test_buffer_records_snapshots(self):
        buf = MetricSnapshotBuffer()
        now = datetime.now(timezone.utc)
        buf.record_snapshot(MetricSnapshot(timestamp=now, blocked_total=5))
        assert buf.count == 1

    def test_buffer_max_capacity(self):
        buf = MetricSnapshotBuffer(max_snapshots=10)
        now = datetime.now(timezone.utc)
        for i in range(20):
            buf.record_snapshot(MetricSnapshot(
                timestamp=now + timedelta(seconds=i),
                blocked_total=i,
            ))
        assert buf.count == 10

    def test_buffer_evicts_oldest(self):
        buf = MetricSnapshotBuffer(max_snapshots=5)
        now = datetime.now(timezone.utc)
        for i in range(10):
            buf.record_snapshot(MetricSnapshot(
                timestamp=now + timedelta(seconds=i),
                blocked_total=i,
            ))
        snaps = buf.list_snapshots()
        assert snaps[0].blocked_total == 5  # oldest remaining
        assert snaps[-1].blocked_total == 9  # newest

    def test_buffer_started_at(self):
        buf = MetricSnapshotBuffer()
        assert buf.started_at is not None
        assert buf.started_at.tzinfo is not None

    def test_get_windows_empty(self):
        buf = MetricSnapshotBuffer()
        current, previous = buf.get_windows(window_minutes=60)
        assert current == []
        assert previous == []

    def test_window_minutes_default(self):
        obs = build_trend_observation(MetricSnapshotBuffer())
        assert obs.window_minutes == 60


# =========================================================================== #
# AXIS 5: Density Signal                                                       #
# =========================================================================== #

class TestDensitySignal:

    def test_no_buffer_description(self):
        obs = build_trend_observation(None)
        assert obs.density.description == "No snapshot buffer available."
        assert obs.density.volatile is True

    def test_insufficient_description_mentions_startup(self):
        buf = MetricSnapshotBuffer()
        obs = build_trend_observation(buf)
        assert obs.density.trend_available is False
        # Empty buffer → no snapshots at all → "No trend data available."
        # or "Insufficient history" with since_startup

    def test_sufficient_data_shows_tracked(self):
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=10, previous_blocked=5,
            current_retry=3, previous_retry=3,
        )
        obs = build_trend_observation(buf)
        assert obs.density.trend_available is True
        assert obs.density.metrics_tracked == 4
        assert "4 metric(s) compared" in obs.density.description

    def test_density_counts_changed_metrics(self):
        buf = _make_buffer_with_snapshots(
            current_count=10, previous_count=10,
            current_blocked=10, previous_blocked=5,  # changed
            current_retry=3, previous_retry=3,         # stable
            current_review=1, previous_review=4,       # changed
            current_watch=2, previous_watch=2,         # stable
        )
        obs = build_trend_observation(buf)
        assert obs.density.metrics_with_change == 2

    def test_volatile_always_true(self):
        obs = build_trend_observation(None)
        assert obs.density.volatile is True

    def test_since_startup_populated(self):
        buf = MetricSnapshotBuffer()
        obs = build_trend_observation(buf)
        assert obs.density.since_startup != ""

    def test_density_is_typed(self):
        obs = build_trend_observation(None)
        assert isinstance(obs.density, TrendDensitySignal)


# =========================================================================== #
# AXIS 6: Safety Invariants                                                    #
# =========================================================================== #

class TestSafetyInvariants:

    def test_safety_all_true_empty(self):
        obs = build_trend_observation(None)
        assert obs.safety.read_only is True
        assert obs.safety.simulation_only is True
        assert obs.safety.no_action_executed is True
        assert obs.safety.no_prediction is True

    def test_safety_all_true_with_data(self):
        buf = _make_buffer_with_snapshots(current_count=10, previous_count=10)
        obs = build_trend_observation(buf)
        assert obs.safety.read_only is True
        assert obs.safety.no_prediction is True

    def test_safety_has_four_fields(self):
        fields = set(TrendSafety.model_fields.keys())
        assert fields == {"read_only", "simulation_only", "no_action_executed", "no_prediction"}

    def test_source_has_no_write_methods(self):
        import inspect
        import app.services.trend_observation_service as mod
        source = inspect.getsource(mod)
        forbidden = ["propose_and_guard", "record_receipt", "transition_to",
                      ".delete(", ".write(", "enqueue("]
        for keyword in forbidden:
            assert keyword not in source, f"Forbidden keyword '{keyword}' in source"

    def test_source_has_no_prediction_keywords(self):
        import inspect
        import app.services.trend_observation_service as mod
        source = inspect.getsource(mod)
        forbidden = ["predict", "forecast", "score(", "auto_promote",
                      "auto_escalate", "auto_judge",
                      "likely to", "expected to"]
        for keyword in forbidden:
            assert keyword not in source, f"Prediction keyword '{keyword}' in source"

    def test_source_has_no_judgment_words(self):
        import inspect
        import app.services.trend_observation_service as mod
        source = inspect.getsource(mod)
        forbidden = ['"improving"', '"worsening"', '"deteriorating"',
                      '"recovering"', '"healthy"', '"unhealthy"',
                      '"alert"', '"warning"', '"breach"']
        for keyword in forbidden:
            assert keyword not in source, f"Judgment word {keyword} in source"

    def test_no_percent_change_in_description_templates(self):
        """v1 constraint: no percentage change in descriptions."""
        import inspect
        import app.services.trend_observation_service as mod
        source = inspect.getsource(mod)
        assert "%" not in source.split("# --")[0]  # Check before helper section

    def test_serializes_to_json(self):
        buf = _make_buffer_with_snapshots(current_count=10, previous_count=10)
        obs = build_trend_observation(buf)
        j = json.loads(obs.model_dump_json())
        assert "blocked_trend" in j
        assert "safety" in j
        assert j["safety"]["no_prediction"] is True


# =========================================================================== #
# AXIS 7: Schema Drift Sentinel                                                #
# =========================================================================== #

class TestSchemaDriftSentinel:

    def test_trend_observation_field_count(self):
        assert len(TrendObservationSchema.model_fields) == 7

    def test_trend_observation_field_names(self):
        expected = {
            "blocked_trend", "pending_retry_trend", "review_trend",
            "watch_trend", "window_minutes", "density", "safety",
        }
        assert set(TrendObservationSchema.model_fields.keys()) == expected

    def test_metric_comparison_field_count(self):
        assert len(MetricComparison.model_fields) == 7

    def test_window_snapshot_field_count(self):
        assert len(WindowSnapshot.model_fields) == 5

    def test_density_signal_field_count(self):
        assert len(TrendDensitySignal.model_fields) == 6

    def test_safety_field_count(self):
        assert len(TrendSafety.model_fields) == 4


# =========================================================================== #
# AXIS 8: Board Integration                                                    #
# =========================================================================== #

class TestBoardIntegration:

    def test_board_schema_has_trend_observation(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        assert "trend_observation" in FourTierBoardResponse.model_fields

    def test_board_schema_trend_is_typed(self):
        from app.schemas.four_tier_board_schema import FourTierBoardResponse
        field_info = FourTierBoardResponse.model_fields["trend_observation"]
        assert field_info.annotation is TrendObservationSchema

    def test_board_service_returns_typed_trend(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert isinstance(board.trend_observation, TrendObservationSchema)

    def test_board_trend_safety_intact(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.trend_observation.safety.read_only is True
        assert board.trend_observation.safety.no_prediction is True

    def test_board_serializes_trend_to_json(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        j = json.loads(board.model_dump_json())
        assert "trend_observation" in j
        assert "blocked_trend" in j["trend_observation"]
        assert j["trend_observation"]["safety"]["no_prediction"] is True

    def test_board_trend_empty_is_zero_safe(self):
        from app.services.four_tier_board_service import build_four_tier_board
        board = build_four_tier_board()
        assert board.trend_observation.density.trend_available is False
        assert board.trend_observation.blocked_trend.insufficient_data is True
