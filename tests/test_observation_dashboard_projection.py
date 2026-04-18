"""
Tests for ObservationDashboardProjection (Review 22).

Invariants verified:
  1. Read-only projection: projection exposes in-memory state only; getter
     return values do not share references with internal state.
  2. Authority note: every getter response carries the 22Z authority_note.
  3. Payload parity: ObservationAlertEmitter → EventBus → projection sees
     exactly the same fields Telegram sees (no schema divergence).
  4. Bounded memory: recent_events is capped at FEED_MAXLEN (20).
  5. Dedup: duplicate fingerprints suppressed even without Emitter dedup.
  6. Failure isolation: malformed payloads drop silently, handler never raises.
  7. No state mutation: projection consumes events only, does not publish or
     mutate anything on the bus.
"""
from __future__ import annotations

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.event_bus import EventBus, ObservationEvent, TOPIC_OBSERVATION
from app.services.observation_alert import (
    ObservationAlertEmitter,
    ObservationEventType,
)
from app.services.observation_dashboard_projection import (
    ObservationDashboardProjection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sample_payload(
    event_type: str = "LAYER_STATE_CHANGE",
    severity: str = "INFO",
    **overrides,
) -> dict:
    """Build a full ObservationEvent asdict-shaped payload."""
    base = asdict(ObservationEvent(
        event_type=event_type,
        severity=severity,
        ts_ms=1_700_000_000_000,
        window_id="2026W16-W1",
        receipt_layer="HEALTHY",
        engine_layer="VALID",
        system_layer_summary="EVALUATING",
        system_layer_detail="INSUFFICIENT_EVIDENCE",
        fail_closed_active=["fail_closed_rule_2", "fail_closed_rule_3"],
        pass_status="NOT_ACHIEVED",
        c1=False, c2=False, c3=True, c4=False,
        pass_blocked_reason="c1=FALSE ∧ c2=FALSE ∧ c4=FALSE",
        confusion_incident_count=0,
        consecutive_all_true_windows=0,
        trigger_code=None,
        trigger_reason=None,
        fingerprint="fp-" + event_type[:8],
    ))
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Empty state
# ---------------------------------------------------------------------------
def test_empty_projection_has_no_data():
    proj = ObservationDashboardProjection()
    status = proj.get_status()
    gate = proj.get_gate_panel()
    events = proj.get_recent_events()
    progress = proj.get_window_progress()

    assert status["has_data"] is False
    assert gate["has_data"] is False
    assert events["count"] == 0
    assert events["events"] == []
    assert progress["has_data"] is False


def test_empty_projection_still_has_authority_note():
    proj = ObservationDashboardProjection()
    for fn in (proj.get_status, proj.get_gate_panel, proj.get_recent_events,
               proj.get_window_progress):
        out = fn()
        assert "authority_note" in out
        assert "read-only projection" in out["authority_note"]
        assert "22Z" in out["authority_note"]


def test_empty_layered_fields_are_all_null():
    proj = ObservationDashboardProjection()
    status = proj.get_status()
    assert status["layered"]["receipt_layer"] is None
    assert status["layered"]["engine_layer"] is None
    assert status["layered"]["system_layer_summary"] is None
    assert status["layered"]["system_layer_detail"] is None
    assert status["layered"]["fail_closed_active"] is None
    assert status["layered"]["pass_status"] is None


def test_empty_gate_all_true_is_none_when_no_data():
    proj = ObservationDashboardProjection()
    assert proj.get_gate_panel()["all_true"] is None


# ---------------------------------------------------------------------------
# 2. Single event populates all 4 sections
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_single_event_populates_status_section():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload())

    status = proj.get_status()
    assert status["has_data"] is True
    assert status["window_id"] == "2026W16-W1"
    assert status["ts_ms"] == 1_700_000_000_000
    assert status["layered"]["receipt_layer"] == "HEALTHY"
    assert status["layered"]["engine_layer"] == "VALID"
    assert status["layered"]["system_layer_summary"] == "EVALUATING"
    assert status["layered"]["system_layer_detail"] == "INSUFFICIENT_EVIDENCE"
    assert status["layered"]["fail_closed_active"] == [
        "fail_closed_rule_2", "fail_closed_rule_3",
    ]
    assert status["layered"]["pass_status"] == "NOT_ACHIEVED"


@pytest.mark.asyncio
async def test_single_event_populates_gate_section():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload())

    gate = proj.get_gate_panel()
    assert gate["has_data"] is True
    assert gate["gate"]["c1"] is False
    assert gate["gate"]["c2"] is False
    assert gate["gate"]["c3"] is True
    assert gate["gate"]["c4"] is False
    assert gate["gate"]["pass_blocked_reason"] == "c1=FALSE ∧ c2=FALSE ∧ c4=FALSE"
    assert gate["all_true"] is False  # not all c1..c4 true


@pytest.mark.asyncio
async def test_gate_all_true_when_all_four_conditions_pass():
    proj = ObservationDashboardProjection()
    payload = _sample_payload(
        event_type="C_GATE_CHANGE",
        c1=True, c2=True, c3=True, c4=True,
        pass_blocked_reason="NONE",
        fingerprint="fp-all-true",
    )
    await proj._on_observation(TOPIC_OBSERVATION, payload)
    gate = proj.get_gate_panel()
    assert gate["all_true"] is True


@pytest.mark.asyncio
async def test_gate_all_true_is_none_with_missing_c_values():
    proj = ObservationDashboardProjection()
    payload = _sample_payload(
        event_type="CONSECUTIVE_WINDOWS_INC",
        c1=None, c2=None, c3=None, c4=None,
        fingerprint="fp-no-c",
    )
    await proj._on_observation(TOPIC_OBSERVATION, payload)
    gate = proj.get_gate_panel()
    # Partial/missing conjunction → unknown (not falsely reported as False)
    assert gate["all_true"] is None


@pytest.mark.asyncio
async def test_single_event_populates_feed():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(
        event_type="T1_CONFUSION_INCIDENT",
        severity="ALERT",
        trigger_code="T1",
        trigger_reason="receipt_in_system confusion detected",
        fingerprint="fp-t1",
    ))

    feed = proj.get_recent_events()
    assert feed["count"] == 1
    assert feed["maxlen"] == 20
    entry = feed["events"][0]
    assert entry["event_type"] == "T1_CONFUSION_INCIDENT"
    assert entry["severity"] == "ALERT"
    assert entry["trigger_code"] == "T1"
    assert entry["trigger_reason"] == "receipt_in_system confusion detected"
    assert entry["window_id"] == "2026W16-W1"
    assert entry["fingerprint"] == "fp-t1"


@pytest.mark.asyncio
async def test_single_event_populates_window_progress():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(
        window_id="2026W17-W3",
        consecutive_all_true_windows=2,
        confusion_incident_count=1,
    ))

    progress = proj.get_window_progress()
    assert progress["has_data"] is True
    assert progress["progress"]["window_id"] == "2026W17-W3"
    assert progress["progress"]["consecutive_all_true_windows"] == 2
    assert progress["progress"]["confusion_incident_count"] == 1


# ---------------------------------------------------------------------------
# 3. Feed ordering + maxlen
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recent_feed_is_newest_first():
    proj = ObservationDashboardProjection()
    for i in range(3):
        await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(
            event_type=f"LAYER_STATE_CHANGE",
            ts_ms=1_700_000_000_000 + i,
            window_id=f"W{i}",
            fingerprint=f"fp-{i}",
        ))
    feed = proj.get_recent_events()
    assert feed["count"] == 3
    # Newest at index 0
    assert feed["events"][0]["window_id"] == "W2"
    assert feed["events"][1]["window_id"] == "W1"
    assert feed["events"][2]["window_id"] == "W0"


@pytest.mark.asyncio
async def test_feed_respects_maxlen():
    proj = ObservationDashboardProjection(feed_maxlen=5)
    for i in range(10):
        await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(
            event_type="LAYER_STATE_CHANGE",
            ts_ms=1_700_000_000_000 + i,
            window_id=f"W{i}",
            fingerprint=f"fp-{i}",
        ))
    feed = proj.get_recent_events(limit=20)
    assert feed["count"] == 5
    assert feed["maxlen"] == 5
    # Only the 5 most recent survive
    window_ids = [e["window_id"] for e in feed["events"]]
    assert window_ids == ["W9", "W8", "W7", "W6", "W5"]


@pytest.mark.asyncio
async def test_recent_events_limit_parameter():
    proj = ObservationDashboardProjection()
    for i in range(7):
        await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(
            ts_ms=1_700_000_000_000 + i,
            window_id=f"W{i}",
            fingerprint=f"fp-{i}",
        ))
    # limit clamps to actual count when smaller
    feed = proj.get_recent_events(limit=3)
    assert feed["count"] == 3
    assert [e["window_id"] for e in feed["events"]] == ["W6", "W5", "W4"]


# ---------------------------------------------------------------------------
# 4. Dedup (defense-in-depth even if Emitter dedups first)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_fingerprint_is_suppressed_in_feed():
    proj = ObservationDashboardProjection()
    payload = _sample_payload(fingerprint="fp-dup")
    await proj._on_observation(TOPIC_OBSERVATION, payload)
    await proj._on_observation(TOPIC_OBSERVATION, payload)
    feed = proj.get_recent_events()
    assert feed["count"] == 1
    stats = proj.stats()
    assert stats["received"] == 1
    assert stats["feed_deduped"] == 1


@pytest.mark.asyncio
async def test_missing_fingerprint_does_not_dedup():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(fingerprint=None))
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(fingerprint=None))
    feed = proj.get_recent_events()
    # Without a fingerprint, each event is accepted — dedup is best-effort.
    assert feed["count"] == 2


# ---------------------------------------------------------------------------
# 5. Malformed payload handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_dict_payload_is_dropped():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, "not a dict")
    assert proj.stats()["dropped_malformed"] == 1
    assert proj.get_status()["has_data"] is False


@pytest.mark.asyncio
async def test_missing_event_type_is_dropped():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, {"ts_ms": 1, "severity": "INFO"})
    assert proj.stats()["dropped_malformed"] == 1
    assert proj.get_status()["has_data"] is False


@pytest.mark.asyncio
async def test_handler_does_not_raise_on_weird_input():
    proj = ObservationDashboardProjection()
    # Should swallow every kind of bad input
    await proj._on_observation(TOPIC_OBSERVATION, None)
    await proj._on_observation(TOPIC_OBSERVATION, [])
    await proj._on_observation(TOPIC_OBSERVATION, 42)
    assert proj.stats()["dropped_malformed"] >= 3


# ---------------------------------------------------------------------------
# 6. Read-only guarantee
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_getter_returns_independent_copy():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload())

    status_a = proj.get_status()
    # Mutate the returned dict
    status_a["layered"]["receipt_layer"] = "MUTATED"
    status_a["layered"]["fail_closed_active"].append("tampered")

    # Second read must not see the tampering
    status_b = proj.get_status()
    assert status_b["layered"]["receipt_layer"] == "HEALTHY"
    assert "tampered" not in (status_b["layered"]["fail_closed_active"] or [])


@pytest.mark.asyncio
async def test_feed_events_are_independent_copies():
    proj = ObservationDashboardProjection()
    await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(fingerprint="fp-a"))
    feed_a = proj.get_recent_events()
    feed_a["events"][0]["event_type"] = "TAMPERED"
    feed_b = proj.get_recent_events()
    assert feed_b["events"][0]["event_type"] == "LAYER_STATE_CHANGE"


# ---------------------------------------------------------------------------
# 7. Parity with Emitter (same payload reaches Telegram and projection)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emitter_payload_matches_projection_input():
    """The payload the projection sees must be identical to what Telegram
    would see. Tests the invariant: single payload source, two renderers.
    """
    published: list[tuple[str, dict]] = []

    class _RecordingBus:
        async def publish(self, topic, payload):
            # Emitter calls asdict(event) before publishing
            published.append((topic, payload))
            return 1

    bus = _RecordingBus()
    emitter = ObservationAlertEmitter(bus)

    ok = await emitter.emit(
        ObservationEventType.T1_CONFUSION_INCIDENT,
        state={
            "window_id": "2026W16-W1",
            "receipt_layer": "HEALTHY",
            "engine_layer": "VALID",
            "system_layer_summary": "EVALUATING",
            "system_layer_detail": "INSUFFICIENT_EVIDENCE",
            "fail_closed_active": ["fail_closed_rule_2", "fail_closed_rule_3"],
            "pass_status": "NOT_ACHIEVED",
            "c1": False, "c2": False, "c3": True, "c4": False,
            "pass_blocked_reason": "c1=FALSE ∧ c2=FALSE ∧ c4=FALSE",
            "confusion_incident_count": 1,
            "consecutive_all_true_windows": 0,
            "trigger_reason": "receipt_in_system confusion detected",
        },
    )
    assert ok is True
    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_OBSERVATION

    # Feed that same payload into the projection and verify every surfaced
    # field matches exactly.
    proj = ObservationDashboardProjection()
    await proj._on_observation(topic, payload)

    status = proj.get_status()
    gate = proj.get_gate_panel()
    feed = proj.get_recent_events()
    progress = proj.get_window_progress()

    # Layered status parity
    assert status["layered"]["receipt_layer"] == payload["receipt_layer"]
    assert status["layered"]["engine_layer"] == payload["engine_layer"]
    assert status["layered"]["system_layer_summary"] == payload["system_layer_summary"]
    assert status["layered"]["system_layer_detail"] == payload["system_layer_detail"]
    assert status["layered"]["fail_closed_active"] == payload["fail_closed_active"]
    assert status["layered"]["pass_status"] == payload["pass_status"]

    # Gate parity
    for k in ("c1", "c2", "c3", "c4", "pass_blocked_reason"):
        assert gate["gate"][k] == payload[k]

    # Window progress parity
    assert progress["progress"]["window_id"] == payload["window_id"]
    assert (
        progress["progress"]["consecutive_all_true_windows"]
        == payload["consecutive_all_true_windows"]
    )
    assert (
        progress["progress"]["confusion_incident_count"]
        == payload["confusion_incident_count"]
    )

    # Feed headline parity
    assert feed["events"][0]["event_type"] == payload["event_type"]
    assert feed["events"][0]["severity"] == payload["severity"]
    assert feed["events"][0]["trigger_code"] == "T1"
    assert feed["events"][0]["fingerprint"] == payload["fingerprint"]


# ---------------------------------------------------------------------------
# 8. Bus attach registers the subscription
# ---------------------------------------------------------------------------
def test_attach_to_bus_subscribes_topic_observation():
    proj = ObservationDashboardProjection()
    bus = MagicMock(spec=EventBus)
    proj.attach_to_bus(bus)

    bus.subscribe.assert_called_once()
    call = bus.subscribe.call_args
    topics, callback = call.args
    assert TOPIC_OBSERVATION in topics
    assert callable(callback)


# ---------------------------------------------------------------------------
# 9. Stats diagnostics
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stats_report_received_count():
    proj = ObservationDashboardProjection()
    for i in range(4):
        await proj._on_observation(TOPIC_OBSERVATION, _sample_payload(
            fingerprint=f"fp-{i}",
        ))
    stats = proj.stats()
    assert stats["received"] == 4
    assert stats["feed_deduped"] == 0
    assert stats["dropped_malformed"] == 0
    assert stats["feed_len"] == 4


# ---------------------------------------------------------------------------
# 10. Ts-ms fallback when payload missing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ts_ms_fallback_when_missing():
    proj = ObservationDashboardProjection()
    payload = _sample_payload(fingerprint="fp-no-ts")
    payload.pop("ts_ms", None)
    await proj._on_observation(TOPIC_OBSERVATION, payload)
    status = proj.get_status()
    assert isinstance(status["ts_ms"], int)
    assert status["ts_ms"] > 0


# ---------------------------------------------------------------------------
# 11. Non-string ts_ms is replaced by server clock
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_int_ts_ms_replaced():
    proj = ObservationDashboardProjection()
    payload = _sample_payload(fingerprint="fp-bad-ts", ts_ms="not-an-int")
    await proj._on_observation(TOPIC_OBSERVATION, payload)
    feed = proj.get_recent_events()
    assert isinstance(feed["events"][0]["ts_ms"], int)
