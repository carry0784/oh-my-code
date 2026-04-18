"""
Tests for observation_alert + telegram observation formatting (Review 21).

Verifies (계획 C 안전장치):
  - Fingerprint dedup (same state within TTL → suppressed)
  - Severity mapping (T1~T4 + CONFUSION_INCIDENT_INC → ALERT; FAIL_CLOSED_CHANGE → WARN; WINDOW_SUMMARY → INFO)
  - Publish failure isolation (bus raises → emit returns False, no exception)
  - Message format contains all 22Z judgment-language fields
  - NO new state vocabulary (messages reference only 22Z fields)
  - Telegram failure does not mutate state (success/failure is pure notification)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.event_bus import (
    EventBus,
    ObservationEvent,
    TOPIC_OBSERVATION,
)
from app.services.observation_alert import (
    ObservationAlertEmitter,
    ObservationEventType,
    _stable_fingerprint,
    severity_of,
)
from app.services.telegram_notifier import _format_observation


# ---------------------------------------------------------------------------
# severity_of mapping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("event_type,expected", [
    (ObservationEventType.T1_CONFUSION_INCIDENT.value, "ALERT"),
    (ObservationEventType.T2_C4_UNSTABLE.value, "ALERT"),
    (ObservationEventType.T3_FAIL_CLOSED_MISFIRE.value, "ALERT"),
    (ObservationEventType.T4_SUMMARY_DETAIL_CONFLICT.value, "ALERT"),
    (ObservationEventType.CONFUSION_INCIDENT_INC.value, "ALERT"),
    (ObservationEventType.FAIL_CLOSED_CHANGE.value, "WARN"),
    (ObservationEventType.CONSECUTIVE_WINDOWS_RESET.value, "WARN"),
    (ObservationEventType.LAYER_STATE_CHANGE.value, "INFO"),
    (ObservationEventType.WINDOW_SUMMARY.value, "INFO"),
    ("UNKNOWN_EVENT_TYPE", "INFO"),  # conservative default
])
def test_severity_mapping(event_type, expected):
    assert severity_of(event_type) == expected


# ---------------------------------------------------------------------------
# Fingerprint dedup
# ---------------------------------------------------------------------------
def test_fingerprint_stable_for_same_state():
    state = {
        "window_id": "2026W16-W1",
        "c1": False, "c2": False, "c3": True, "c4": False,
        "fail_closed_active": ["fail_closed_rule_2", "fail_closed_rule_3"],
    }
    fp1 = _stable_fingerprint("LAYER_STATE_CHANGE", state)
    fp2 = _stable_fingerprint("LAYER_STATE_CHANGE", dict(state))
    assert fp1 == fp2
    assert len(fp1) == 16


def test_fingerprint_changes_with_state():
    base = {"window_id": "W1", "c1": False}
    fp1 = _stable_fingerprint("LAYER_STATE_CHANGE", base)
    fp2 = _stable_fingerprint("LAYER_STATE_CHANGE", {**base, "c1": True})
    assert fp1 != fp2


def test_fingerprint_changes_with_event_type():
    state = {"window_id": "W1"}
    fp1 = _stable_fingerprint("LAYER_STATE_CHANGE", state)
    fp2 = _stable_fingerprint("WINDOW_SUMMARY", state)
    assert fp1 != fp2


# ---------------------------------------------------------------------------
# Emitter dedup behavior
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emitter_dedups_within_ttl():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(return_value=1)

    emitter = ObservationAlertEmitter(bus, dedup_ttl_sec=60.0)
    state = {
        "window_id": "2026W16-W1",
        "receipt_layer": "HEALTHY",
        "system_layer_summary": "EVALUATING",
        "c1": False, "c2": False, "c3": True, "c4": False,
        "confusion_incident_count": 0,
    }

    ok1 = await emitter.emit(ObservationEventType.LAYER_STATE_CHANGE, state=state)
    ok2 = await emitter.emit(ObservationEventType.LAYER_STATE_CHANGE, state=state)

    assert ok1 is True
    assert ok2 is False  # deduped
    assert bus.publish.await_count == 1
    stats = emitter.stats()
    assert stats["emitted"] == 1
    assert stats["deduped"] == 1


@pytest.mark.asyncio
async def test_emitter_does_not_dedup_different_states():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(return_value=1)

    emitter = ObservationAlertEmitter(bus, dedup_ttl_sec=60.0)
    s1 = {"window_id": "W1", "c1": False}
    s2 = {"window_id": "W2", "c1": False}  # different window_id

    ok1 = await emitter.emit(ObservationEventType.LAYER_STATE_CHANGE, state=s1)
    ok2 = await emitter.emit(ObservationEventType.LAYER_STATE_CHANGE, state=s2)

    assert ok1 is True
    assert ok2 is True
    assert bus.publish.await_count == 2


# ---------------------------------------------------------------------------
# Emitter severity / trigger mapping
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emitter_maps_t1_to_alert_and_trigger_code():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(return_value=1)

    emitter = ObservationAlertEmitter(bus)
    await emitter.emit(
        ObservationEventType.T1_CONFUSION_INCIDENT,
        state={
            "window_id": "W1",
            "confusion_incident_count": 1,
            "trigger_reason": "test",
        },
    )

    assert bus.publish.await_count == 1
    call = bus.publish.await_args_list[0]
    topic, payload = call.args
    assert topic == TOPIC_OBSERVATION
    assert payload["event_type"] == "T1_CONFUSION_INCIDENT"
    assert payload["severity"] == "ALERT"
    assert payload["trigger_code"] == "T1"
    assert payload["trigger_reason"] == "test"


@pytest.mark.asyncio
async def test_emitter_severity_override():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(return_value=1)

    emitter = ObservationAlertEmitter(bus)
    await emitter.emit(
        ObservationEventType.WINDOW_SUMMARY,
        state={"window_id": "W1"},
        severity_override="ALERT",
    )

    call = bus.publish.await_args_list[0]
    _, payload = call.args
    assert payload["severity"] == "ALERT"  # overridden from default INFO


# ---------------------------------------------------------------------------
# Publish failure isolation (Review 21 계획 C — failure must not propagate)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emit_returns_false_on_publish_failure():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(side_effect=RuntimeError("redis down"))

    emitter = ObservationAlertEmitter(bus)
    # Must NOT raise
    ok = await emitter.emit(
        ObservationEventType.T1_CONFUSION_INCIDENT,
        state={"window_id": "W1"},
    )
    assert ok is False
    stats = emitter.stats()
    assert stats["publish_failed"] == 1
    assert stats["emitted"] == 0


# ---------------------------------------------------------------------------
# Message formatter (telegram_notifier._format_observation)
# ---------------------------------------------------------------------------
def _sample_state(event_type: str, severity: str, extra: dict | None = None) -> dict:
    base = {
        "event_type": event_type,
        "severity": severity,
        "ts_ms": 1710000000000,
        "window_id": "2026W16-W1",
        "receipt_layer": "HEALTHY",
        "engine_layer": "VALID",
        "system_layer_summary": "EVALUATING",
        "system_layer_detail": "INSUFFICIENT_EVIDENCE",
        "fail_closed_active": ["fail_closed_rule_2", "fail_closed_rule_3"],
        "pass_status": "NOT_ACHIEVED",
        "c1": False, "c2": False, "c3": True, "c4": False,
        "pass_blocked_reason": "c1=FALSE ∧ c2=FALSE ∧ c4=FALSE",
        "confusion_incident_count": 0,
        "consecutive_all_true_windows": 0,
    }
    if extra:
        base.update(extra)
    return base


def test_format_observation_includes_all_fields():
    payload = _sample_state("LAYER_STATE_CHANGE", "INFO")
    msg = _format_observation(payload)

    # Header
    assert "[K-DEXTER OBS]" in msg
    assert "INFO" in msg

    # 22Z judgment language required fields
    assert "receipt:" in msg
    assert "HEALTHY" in msg
    assert "engine:" in msg
    assert "VALID" in msg
    assert "summary:" in msg
    assert "EVALUATING" in msg
    assert "detail:" in msg
    assert "INSUFFICIENT_EVIDENCE" in msg
    assert "fail_closed:" in msg
    assert "fail_closed_rule_2" in msg
    assert "pass:" in msg
    assert "NOT_ACHIEVED" in msg
    assert "c1/c2/c3/c4:" in msg
    assert "FALSE" in msg and "TRUE" in msg
    assert "reason:" in msg
    assert "incidents:" in msg
    assert "consecutive_true_windows:" in msg

    # Authority disclaimer (must be present — notification only)
    assert "authority" in msg.lower()
    assert "22Z" in msg


def test_format_observation_alert_includes_trigger():
    payload = _sample_state(
        "T1_CONFUSION_INCIDENT", "ALERT",
        extra={
            "trigger_code": "T1",
            "trigger_reason": "receipt_in_system confusion detected",
        },
    )
    msg = _format_observation(payload)
    assert "ALERT" in msg
    assert "T1_CONFUSION_INCIDENT" in msg
    assert "T1" in msg
    assert "receipt_in_system confusion detected" in msg


def test_format_observation_warn_uses_warn_emoji():
    payload = _sample_state("FAIL_CLOSED_CHANGE", "WARN")
    msg = _format_observation(payload)
    assert "WARN" in msg


def test_format_observation_handles_missing_fields():
    # Even with mostly-None fields, formatter must not crash
    sparse = {
        "event_type": "LAYER_STATE_CHANGE",
        "severity": "INFO",
        "ts_ms": 1710000000000,
    }
    msg = _format_observation(sparse)
    assert "[K-DEXTER OBS]" in msg
    assert "INFO" in msg
    assert "?" in msg  # sentinel for unknown fields


def test_format_observation_no_forbidden_vocabulary():
    """Review 22Z doctrine_restraint: EVALUATING → PASS-근접 번역 금지.

    Check for PASS-adjacent vocabulary that would mistranslate EVALUATING /
    INSUFFICIENT_EVIDENCE / PASS_BLOCKED as "approaching PASS" or "successful".
    Note: "NOT_ACHIEVED" legitimately contains the substring "achieved" so we
    use phrase-level checks rather than raw substring matches.
    """
    import re
    payload = _sample_state("LAYER_STATE_CHANGE", "INFO")
    msg = _format_observation(payload)
    lower = msg.lower()
    # Multi-word phrases — straightforward substring check.
    forbidden_phrases = [
        "approaching pass", "close to pass", "near pass", "almost pass",
        "is mature", "is ready", "is successful", "system ready",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in lower, f"forbidden phrase found: {phrase!r}"
    # Standalone words — use word boundaries to avoid false positives like
    # "achieved" inside "NOT_ACHIEVED".
    forbidden_tokens = ["mature", "ready", "success", "successful"]
    for token in forbidden_tokens:
        assert not re.search(rf"\b{token}\b", lower), (
            f"forbidden token found as word: {token!r}"
        )
    # PASS_BLOCKED / NOT_ACHIEVED / EVALUATING / INSUFFICIENT_EVIDENCE are
    # the legitimate 22Z vocabulary and MUST be faithfully rendered.
    assert "NOT_ACHIEVED" in msg
    assert "EVALUATING" in msg
    assert "INSUFFICIENT_EVIDENCE" in msg


# ---------------------------------------------------------------------------
# TelegramNotifier _on_observation — priority mapping (Review 21 계획 D)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_telegram_notifier_on_observation_priority_mapping():
    """ALERT → CRITICAL, WARN → WARNING, INFO → INFO."""
    from app.services.telegram_notifier import (
        TelegramNotifier,
        PRIORITY_CRITICAL,
        PRIORITY_WARNING,
        PRIORITY_INFO,
    )

    notifier = TelegramNotifier(token="x", chat_id="y", enabled=False)
    # Capture priority at send time
    captured: list[int] = []

    async def _fake_send(text: str, priority: int = PRIORITY_INFO, **kwargs) -> bool:
        # Accept **kwargs so the fake matches the new send() signature which
        # includes an explicit parse_mode=None for observation events.
        captured.append(priority)
        return True

    notifier.send = _fake_send  # type: ignore[assignment]

    await notifier._on_observation(TOPIC_OBSERVATION, _sample_state("T1_CONFUSION_INCIDENT", "ALERT"))
    await notifier._on_observation(TOPIC_OBSERVATION, _sample_state("FAIL_CLOSED_CHANGE", "WARN"))
    await notifier._on_observation(TOPIC_OBSERVATION, _sample_state("WINDOW_SUMMARY", "INFO"))
    await notifier._on_observation(TOPIC_OBSERVATION, _sample_state("UNKNOWN", "NOT_A_REAL_SEVERITY"))

    assert captured == [PRIORITY_CRITICAL, PRIORITY_WARNING, PRIORITY_INFO, PRIORITY_INFO]


# ---------------------------------------------------------------------------
# Integration: emit → bus payload roundtrip → formatter
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emit_payload_is_formatter_compatible():
    """Payload published by emitter must render cleanly via _format_observation."""
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock(return_value=1)

    emitter = ObservationAlertEmitter(bus)
    await emitter.emit(
        ObservationEventType.T2_C4_UNSTABLE,
        state={
            "window_id": "2026W16-W3",
            "receipt_layer": "HEALTHY",
            "engine_layer": "VALID",
            "system_layer_summary": "EVALUATING",
            "system_layer_detail": "INSUFFICIENT_EVIDENCE",
            "fail_closed_active": ["fail_closed_rule_2", "fail_closed_rule_3"],
            "pass_status": "NOT_ACHIEVED",
            "c1": False, "c2": False, "c3": True, "c4": False,
            "pass_blocked_reason": "c4=FALSE sustained 3 windows",
            "confusion_incident_count": 0,
            "consecutive_all_true_windows": 0,
            "trigger_reason": "c4 FALSE for 3 consecutive windows observed",
        },
    )

    topic, payload = bus.publish.await_args_list[0].args
    assert topic == TOPIC_OBSERVATION
    msg = _format_observation(payload)
    assert "T2_C4_UNSTABLE" in msg
    assert "T2" in msg
    assert "c4 FALSE for 3 consecutive windows observed" in msg


# ---------------------------------------------------------------------------
# ObservationEvent dataclass sanity
# ---------------------------------------------------------------------------
def test_observation_event_dataclass_default_nones():
    ev = ObservationEvent(
        event_type="LAYER_STATE_CHANGE",
        severity="INFO",
        ts_ms=1710000000000,
    )
    assert ev.window_id is None
    assert ev.receipt_layer is None
    assert ev.fail_closed_active is None
    assert ev.fingerprint is None


# ---------------------------------------------------------------------------
# Fixture for asyncio
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Module-wide event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
