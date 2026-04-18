"""
Observation Alert Helper — Review 21 (22Z freeze 유지 상태에서 운영 알림 채널)

Scope:
  - 이벤트 발생 즉시 Telegram으로 보고하기 위한 emit 헬퍼.
  - 22Z canonical/state semantics를 변경하지 않는다.
  - Telegram 전송 성공/실패가 adjudication/state를 바꾸지 않는다.

Authority source (never mutated by this module):
  - data/evidence/system_state_20260418T220000Z.json  (22Z canonical)
  - docs/operations/exit_dashboard_checklist_v1.md     (운영 체크리스트)

This module is NOT doctrine. It is an operational notification utility.
New state vocabulary is PROHIBITED here — all fields use 22Z judgment language.

Event types (Review 21 관측 규칙):
  T1_CONFUSION_INCIDENT       — layer_confusion_incident_ledger_v1 신규 entry
  T2_C4_UNSTABLE              — 3회 이상 연속 window에서 c4 == FALSE
  T3_FAIL_CLOSED_MISFIRE      — fail_closed rule의 명백한 오판 (FP/FN)
  T4_SUMMARY_DETAIL_CONFLICT  — same window 내 summary ↔ detail 충돌
  LAYER_STATE_CHANGE          — Receipt/Engine/Summary/Detail 변경
  FAIL_CLOSED_CHANGE          — fail_closed_active 변경
  C_GATE_CHANGE               — c1/c2/c3/c4 값 변경
  PASS_STATUS_CHANGE          — PASS status 변경
  CONFUSION_INCIDENT_INC      — confusion_incident_count 증가
  CONSECUTIVE_WINDOWS_INC     — consecutive_all_true_windows 증가
  CONSECUTIVE_WINDOWS_RESET   — consecutive_all_true_windows == 0으로 리셋
  WINDOW_SUMMARY              — window 종료 1회 요약 (Lane 2)

Severity mapping (Review 21 3등급):
  ALERT : T1, T2, T3, T4, CONFUSION_INCIDENT_INC
  WARN  : FAIL_CLOSED_CHANGE (still active), C_GATE_CHANGE (→FALSE),
          PASS_STATUS_CHANGE (→NOT_ACHIEVED), CONSECUTIVE_WINDOWS_RESET
  INFO  : LAYER_STATE_CHANGE, C_GATE_CHANGE (→TRUE),
          CONSECUTIVE_WINDOWS_INC, WINDOW_SUMMARY, PASS_STATUS_CHANGE (→*)
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from enum import Enum
from typing import Any

from app.core.logging import get_logger
from app.services.event_bus import (
    EventBus,
    ObservationEvent,
    TOPIC_OBSERVATION,
)

logger = get_logger(__name__)


class ObservationEventType(str, Enum):
    """22Z observation event types (Review 21 관측 규칙).

    str subclass so it serializes cleanly via EventBus JSON dump.
    """
    # T1~T4 reopen triggers (ALERT)
    T1_CONFUSION_INCIDENT = "T1_CONFUSION_INCIDENT"
    T2_C4_UNSTABLE = "T2_C4_UNSTABLE"
    T3_FAIL_CLOSED_MISFIRE = "T3_FAIL_CLOSED_MISFIRE"
    T4_SUMMARY_DETAIL_CONFLICT = "T4_SUMMARY_DETAIL_CONFLICT"
    # State transitions
    LAYER_STATE_CHANGE = "LAYER_STATE_CHANGE"
    FAIL_CLOSED_CHANGE = "FAIL_CLOSED_CHANGE"
    C_GATE_CHANGE = "C_GATE_CHANGE"
    PASS_STATUS_CHANGE = "PASS_STATUS_CHANGE"
    CONFUSION_INCIDENT_INC = "CONFUSION_INCIDENT_INC"
    CONSECUTIVE_WINDOWS_INC = "CONSECUTIVE_WINDOWS_INC"
    CONSECUTIVE_WINDOWS_RESET = "CONSECUTIVE_WINDOWS_RESET"
    WINDOW_SUMMARY = "WINDOW_SUMMARY"


# Severity mapping (Review 21 Section 3 해석 규칙)
_SEVERITY_MAP: dict[str, str] = {
    # ALERT
    ObservationEventType.T1_CONFUSION_INCIDENT.value: "ALERT",
    ObservationEventType.T2_C4_UNSTABLE.value: "ALERT",
    ObservationEventType.T3_FAIL_CLOSED_MISFIRE.value: "ALERT",
    ObservationEventType.T4_SUMMARY_DETAIL_CONFLICT.value: "ALERT",
    ObservationEventType.CONFUSION_INCIDENT_INC.value: "ALERT",
    # WARN
    ObservationEventType.FAIL_CLOSED_CHANGE.value: "WARN",
    ObservationEventType.CONSECUTIVE_WINDOWS_RESET.value: "WARN",
    # INFO (default)
    ObservationEventType.LAYER_STATE_CHANGE.value: "INFO",
    ObservationEventType.C_GATE_CHANGE.value: "INFO",
    ObservationEventType.PASS_STATUS_CHANGE.value: "INFO",
    ObservationEventType.CONSECUTIVE_WINDOWS_INC.value: "INFO",
    ObservationEventType.WINDOW_SUMMARY.value: "INFO",
}

# Trigger-code mapping for T1~T4 (Review 16 reopen triggers)
_TRIGGER_CODE_MAP: dict[str, str] = {
    ObservationEventType.T1_CONFUSION_INCIDENT.value: "T1",
    ObservationEventType.T2_C4_UNSTABLE.value: "T2",
    ObservationEventType.T3_FAIL_CLOSED_MISFIRE.value: "T3",
    ObservationEventType.T4_SUMMARY_DETAIL_CONFLICT.value: "T4",
}


def severity_of(event_type: str) -> str:
    """Return "ALERT" | "WARN" | "INFO" for the given event_type.

    Unknown types default to INFO (conservative — won't spam as ALERT).
    """
    return _SEVERITY_MAP.get(event_type, "INFO")


def _stable_fingerprint(event_type: str, state: dict[str, Any]) -> str:
    """Compute a stable fingerprint for dedup (Review 21 계획 C).

    Fingerprint key = event_type + (subset of state fields that define identity).
    Values that change every call (ts_ms, fingerprint itself) are excluded.

    Returns 16-char hex digest.
    """
    identity_keys = (
        "window_id",
        "receipt_layer",
        "engine_layer",
        "system_layer_summary",
        "system_layer_detail",
        "fail_closed_active",
        "pass_status",
        "c1", "c2", "c3", "c4",
        "pass_blocked_reason",
        "confusion_incident_count",
        "consecutive_all_true_windows",
        "trigger_code",
        "trigger_reason",
    )
    sub = {k: state.get(k) for k in identity_keys}
    payload = json.dumps(
        {"event_type": event_type, "state": sub},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class ObservationAlertEmitter:
    """Thin helper around EventBus for 22Z observation alerts.

    Features (Review 21 계획 C — 전송 안전장치):
      - In-memory fingerprint dedup (TTL-based).
      - Automatic severity mapping from event_type.
      - ObservationEvent packaging using 22Z language ONLY.
      - Publish failures logged but NOT propagated (state unaffected).

    Usage:
        emitter = ObservationAlertEmitter(bus)
        await emitter.emit(
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
                "trigger_reason": "receipt_in_system confusion detected by operator",
            },
        )
    """

    DEFAULT_DEDUP_TTL_SEC = 300.0  # 5 minutes — conservative, prevents storm

    def __init__(self, bus: EventBus, dedup_ttl_sec: float | None = None) -> None:
        self._bus = bus
        self._dedup_ttl = (
            dedup_ttl_sec if dedup_ttl_sec is not None else self.DEFAULT_DEDUP_TTL_SEC
        )
        # fingerprint -> expiry_ts
        self._seen: dict[str, float] = {}
        # stats
        self._emitted = 0
        self._deduped = 0
        self._publish_failed = 0

    # ---- Dedup ----
    def _is_duplicate(self, fingerprint: str) -> bool:
        now = time.time()
        # Garbage-collect expired fingerprints (bounded work — rare storms)
        if len(self._seen) > 1024:
            self._seen = {fp: exp for fp, exp in self._seen.items() if exp > now}
        exp = self._seen.get(fingerprint)
        if exp is not None and exp > now:
            return True
        self._seen[fingerprint] = now + self._dedup_ttl
        return False

    # ---- Public emit ----
    async def emit(
        self,
        event_type: ObservationEventType | str,
        state: dict[str, Any] | None = None,
        *,
        severity_override: str | None = None,
        ts_ms: int | None = None,
    ) -> bool:
        """Publish an ObservationEvent to TOPIC_OBSERVATION.

        Returns True if published (subscribers may have received it), False if
        suppressed (duplicate within TTL) or failed to publish (logged).

        A failure here NEVER mutates system state — caller must treat False as
        "notification dropped" and continue with authoritative checklist update.
        """
        et = event_type.value if isinstance(event_type, ObservationEventType) else str(event_type)
        state = dict(state or {})
        ts_ms = ts_ms if ts_ms is not None else int(time.time() * 1000)

        # Dedup fingerprint
        fingerprint = _stable_fingerprint(et, state)
        if self._is_duplicate(fingerprint):
            self._deduped += 1
            logger.debug("observation_alert_deduped", event_type=et, fingerprint=fingerprint)
            return False

        severity = severity_override or severity_of(et)
        trigger_code = _TRIGGER_CODE_MAP.get(et)

        fc = state.get("fail_closed_active")
        if isinstance(fc, (set, tuple)):
            fc = list(fc)

        event = ObservationEvent(
            event_type=et,
            severity=severity,
            ts_ms=ts_ms,
            window_id=state.get("window_id"),
            receipt_layer=state.get("receipt_layer"),
            engine_layer=state.get("engine_layer"),
            system_layer_summary=state.get("system_layer_summary"),
            system_layer_detail=state.get("system_layer_detail"),
            fail_closed_active=fc,
            pass_status=state.get("pass_status"),
            c1=state.get("c1"),
            c2=state.get("c2"),
            c3=state.get("c3"),
            c4=state.get("c4"),
            pass_blocked_reason=state.get("pass_blocked_reason"),
            confusion_incident_count=state.get("confusion_incident_count"),
            consecutive_all_true_windows=state.get("consecutive_all_true_windows"),
            trigger_code=trigger_code,
            trigger_reason=state.get("trigger_reason"),
            fingerprint=fingerprint,
        )

        try:
            await self._bus.publish(TOPIC_OBSERVATION, asdict(event))
            self._emitted += 1
            logger.info(
                "observation_alert_emitted",
                event_type=et, severity=severity, fingerprint=fingerprint,
            )
            return True
        except Exception as exc:
            self._publish_failed += 1
            logger.warning(
                "observation_alert_publish_failed",
                event_type=et, error=repr(exc)[:200],
            )
            # Per Review 21 계획 C — failure is bounded. Do NOT re-raise.
            return False

    # ---- Stats ----
    def stats(self) -> dict[str, int]:
        return {
            "emitted": self._emitted,
            "deduped": self._deduped,
            "publish_failed": self._publish_failed,
            "tracked_fingerprints": len(self._seen),
        }
