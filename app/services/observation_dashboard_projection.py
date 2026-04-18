"""
Observation Dashboard Projection — Review 22 (22Z freeze 유지 상태에서 시각화 투영)

Scope:
  - 22Z canonical/state semantics를 변경하지 않는다.
  - Telegram 채널과 동일한 ObservationEvent payload를 소비하여 read-only 대시보드
    투영 상태만을 메모리에 유지한다.
  - 본 모듈은 state 생성기가 아니다 (NOT a state producer).
  - 본 모듈은 adjudication에 영향을 주지 않는다 (NOT mutating adjudication).
  - 투영 성공/실패는 판정 상태를 바꾸지 않는다.

Authority source (never mutated by this module):
  - data/evidence/system_state_20260418T220000Z.json  (22Z canonical)
  - docs/operations/exit_dashboard_checklist_v1.md     (운영 체크리스트)

Review 22 3원 구조:
  Authority     : 22Z canonical + exit_dashboard_checklist  (변경 불가)
  Push channel  : TelegramNotifier._on_observation          (즉시 보고)
  Visualization : ObservationDashboardProjection (이 모듈)  (read-only 투영)

Design contract (이 모듈이 지키는 4가지):
  1. Single payload source: TOPIC_OBSERVATION 외 다른 채널에 구독하지 않는다.
  2. Read-only projection: 외부에서 호출되는 getter 메서드는 복사본만 반환한다.
  3. Bounded memory: recent_events는 deque(maxlen=20), 무한 증가 금지.
  4. Authority note: 모든 getter 응답에 `authority_note` 필드를 포함하여,
     본 뷰가 권위 source가 아님을 명시한다.

Event flow:
    Operator/System → ObservationAlertEmitter.emit()
                    → EventBus.publish(TOPIC_OBSERVATION, asdict(ObservationEvent))
                    ├─ TelegramNotifier._on_observation() → Telegram
                    └─ ObservationDashboardProjection._on_observation() → in-memory snapshot

4개 view 섹션 (대시보드 4 카드):
  1. Current Layered Status  : receipt/engine/summary/detail + fail_closed + pass
  2. Conjunctive Gate Panel  : c1/c2/c3/c4 + pass_blocked_reason
  3. Recent Event Feed       : 최근 20개 event_type/severity/ts_ms/window_id/fingerprint
  4. Window Progress         : window_id / consecutive_all_true_windows /
                                confusion_incident_count / last_update
"""
from __future__ import annotations

import copy
import threading
import time
from collections import deque
from typing import Any

from app.core.logging import get_logger
from app.services.event_bus import EventBus, TOPIC_OBSERVATION

logger = get_logger(__name__)


# 이 문자열은 모든 read-only 응답에 부착된다. 22Z doctrine_restraint 준수:
# 본 뷰는 판정 권위가 아니라 투영임을 알리는 운영 라벨이다.
_AUTHORITY_NOTE = (
    "Dashboard is read-only projection. "
    "Canonical authority remains 22Z system_state + exit_dashboard_checklist_v1. "
    "Visualization success/failure never mutates adjudication state."
)

# 최근 이벤트 피드 한계 — Review 22 §4에 의해 20으로 고정.
_RECENT_FEED_MAXLEN = 20

# Layered-status 응답에 노출되는 22Z 언어 필드 (canonical에서 변형 없이 전달).
_LAYERED_STATUS_FIELDS = (
    "receipt_layer",
    "engine_layer",
    "system_layer_summary",
    "system_layer_detail",
    "fail_closed_active",
    "pass_status",
)

# Conjunctive-gate 응답 필드.
_GATE_FIELDS = ("c1", "c2", "c3", "c4", "pass_blocked_reason")

# Window-progress 응답 필드.
_WINDOW_PROGRESS_FIELDS = (
    "window_id",
    "consecutive_all_true_windows",
    "confusion_incident_count",
)

# Recent-event-feed 에 저장하는 헤드라인 필드 (전체 payload는 저장하지 않는다).
_FEED_HEADLINE_FIELDS = (
    "event_type",
    "severity",
    "ts_ms",
    "window_id",
    "trigger_code",
    "trigger_reason",
    "fingerprint",
)


class ObservationDashboardProjection:
    """TOPIC_OBSERVATION subscriber — maintains read-only dashboard state.

    Thread-safety: getter methods can be called from the HTTP request handler
    thread while `_on_observation()` runs in the EventBus listener task. We use
    a short mutex around state updates/reads. The critical section is tiny
    (copy dict fields), so lock contention is negligible.

    Lifecycle:
        proj = ObservationDashboardProjection()
        proj.attach_to_bus(bus)
        await bus.start_listening()
        ...
        status = proj.get_status()          # {authority_note, ts_ms, ...}
        gate   = proj.get_gate_panel()
        feed   = proj.get_recent_events(limit=20)
        prog   = proj.get_window_progress()

    Failure isolation:
        - Malformed payloads are logged and dropped; listener continues.
        - Visualization failure NEVER bubbles up to notifier or state machine.
    """

    AUTHORITY_NOTE = _AUTHORITY_NOTE
    FEED_MAXLEN = _RECENT_FEED_MAXLEN

    def __init__(self, feed_maxlen: int | None = None) -> None:
        self._lock = threading.Lock()
        self._feed_maxlen = feed_maxlen if feed_maxlen is not None else _RECENT_FEED_MAXLEN
        # Latest snapshot: copy of whole ObservationEvent payload (dict). May be None
        # until the first observation is received.
        self._current: dict[str, Any] | None = None
        # Bounded deque (newest at index 0 via appendleft).
        self._recent: deque[dict[str, Any]] = deque(maxlen=self._feed_maxlen)
        # Monotonic clock for 'received elapsed' hints in the UI.
        self._last_update_ts_ms: int | None = None
        # Lightweight fingerprint-dedup in the projection too — Emitter already
        # dedupes, but if someone publishes directly to the bus without going
        # through the Emitter, we still suppress duplicate feed rows. Keeps a
        # bounded set of the most recent fingerprints (same as _recent's keys).
        self._seen_fingerprints: deque[str] = deque(maxlen=self._feed_maxlen * 2)
        # Stats (diagnostic only).
        self._received = 0
        self._feed_deduped = 0
        self._dropped_malformed = 0

    # ---------------- Bus wiring ----------------
    def attach_to_bus(self, bus: EventBus) -> None:
        """Subscribe to TOPIC_OBSERVATION. Caller then invokes bus.start_listening()."""
        bus.subscribe([TOPIC_OBSERVATION], self._on_observation)

    # ---------------- Subscriber handler ----------------
    async def _on_observation(self, topic: str, payload: dict[str, Any]) -> None:  # noqa: ARG002
        """EventBus callback. Never raises — all failures logged and dropped.

        Payload shape expected = asdict(ObservationEvent). See event_bus.py.
        """
        try:
            if not isinstance(payload, dict):
                self._dropped_malformed += 1
                logger.warning(
                    "observation_dashboard_drop_nondict",
                    payload_type=type(payload).__name__,
                )
                return

            # Only event_type is strictly required to be renderable. Everything
            # else may be None per the ObservationEvent schema.
            event_type = payload.get("event_type")
            if not event_type:
                self._dropped_malformed += 1
                logger.warning("observation_dashboard_drop_no_event_type")
                return

            fingerprint = payload.get("fingerprint")
            # ts_ms: take from payload if present, else server clock (fallback only).
            ts_ms = payload.get("ts_ms")
            if not isinstance(ts_ms, int):
                ts_ms = int(time.time() * 1000)

            with self._lock:
                # In-projection dedup (defense-in-depth; Emitter is primary).
                if fingerprint and fingerprint in self._seen_fingerprints:
                    self._feed_deduped += 1
                    logger.debug(
                        "observation_dashboard_dedup",
                        event_type=event_type, fingerprint=fingerprint,
                    )
                    return

                self._received += 1
                self._last_update_ts_ms = ts_ms

                # Record full snapshot (copy so later mutation elsewhere doesn't leak).
                self._current = copy.deepcopy(payload)

                # Feed headline entry (compact; full payload is in _current).
                feed_entry = {k: payload.get(k) for k in _FEED_HEADLINE_FIELDS}
                feed_entry["ts_ms"] = ts_ms  # normalized
                self._recent.appendleft(feed_entry)

                if fingerprint:
                    self._seen_fingerprints.append(fingerprint)

        except Exception as exc:  # noqa: BLE001 — containment boundary
            self._dropped_malformed += 1
            logger.warning(
                "observation_dashboard_handler_failed",
                error=str(exc)[:200],
            )

    # ---------------- Read-only getters ----------------
    def get_status(self) -> dict[str, Any]:
        """Section 1: Current Layered Status card.

        Returns:
            {
              authority_note: "...",
              ts_ms: int | None,
              window_id: str | None,
              has_data: bool,
              layered: {
                receipt_layer, engine_layer,
                system_layer_summary, system_layer_detail,
                fail_closed_active, pass_status,
              }
            }
        """
        with self._lock:
            current = self._current
            ts_ms = self._last_update_ts_ms
            if current is None:
                return {
                    "authority_note": _AUTHORITY_NOTE,
                    "ts_ms": None,
                    "window_id": None,
                    "has_data": False,
                    "layered": {f: None for f in _LAYERED_STATUS_FIELDS},
                }
            layered = {f: copy.deepcopy(current.get(f)) for f in _LAYERED_STATUS_FIELDS}
            return {
                "authority_note": _AUTHORITY_NOTE,
                "ts_ms": ts_ms,
                "window_id": current.get("window_id"),
                "has_data": True,
                "layered": layered,
            }

    def get_gate_panel(self) -> dict[str, Any]:
        """Section 2: Conjunctive Gate Panel (c1 ∧ c2 ∧ c3 ∧ c4)."""
        with self._lock:
            current = self._current
            ts_ms = self._last_update_ts_ms
            if current is None:
                return {
                    "authority_note": _AUTHORITY_NOTE,
                    "ts_ms": None,
                    "window_id": None,
                    "has_data": False,
                    "gate": {f: None for f in _GATE_FIELDS},
                    "all_true": None,
                }
            gate = {f: current.get(f) for f in _GATE_FIELDS}
            c_values = [gate["c1"], gate["c2"], gate["c3"], gate["c4"]]
            # all_true only meaningful when all four are explicit bool.
            if all(isinstance(v, bool) for v in c_values):
                all_true = all(c_values)
            else:
                all_true = None
            return {
                "authority_note": _AUTHORITY_NOTE,
                "ts_ms": ts_ms,
                "window_id": current.get("window_id"),
                "has_data": True,
                "gate": gate,
                "all_true": all_true,
            }

    def get_recent_events(self, limit: int | None = None) -> dict[str, Any]:
        """Section 3: Recent Event Feed (newest first)."""
        if limit is None or limit > self._feed_maxlen:
            limit = self._feed_maxlen
        if limit < 0:
            limit = 0
        with self._lock:
            # deque already newest-first (appendleft); slice copies.
            events = [copy.deepcopy(e) for e in list(self._recent)[:limit]]
            return {
                "authority_note": _AUTHORITY_NOTE,
                "count": len(events),
                "maxlen": self._feed_maxlen,
                "events": events,
            }

    def get_window_progress(self) -> dict[str, Any]:
        """Section 4: Window Progress Panel."""
        with self._lock:
            current = self._current
            ts_ms = self._last_update_ts_ms
            if current is None:
                return {
                    "authority_note": _AUTHORITY_NOTE,
                    "ts_ms": None,
                    "has_data": False,
                    "progress": {f: None for f in _WINDOW_PROGRESS_FIELDS},
                }
            progress = {f: current.get(f) for f in _WINDOW_PROGRESS_FIELDS}
            return {
                "authority_note": _AUTHORITY_NOTE,
                "ts_ms": ts_ms,
                "has_data": True,
                "progress": progress,
            }

    def stats(self) -> dict[str, int]:
        """Diagnostic stats (not an authority view — no authority_note)."""
        with self._lock:
            return {
                "received": self._received,
                "feed_deduped": self._feed_deduped,
                "dropped_malformed": self._dropped_malformed,
                "feed_len": len(self._recent),
                "feed_maxlen": self._feed_maxlen,
                "seen_fingerprints_tracked": len(self._seen_fingerprints),
            }
