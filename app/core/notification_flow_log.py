"""
Card C-23: Notification Flow Log — In-memory ring buffer for flow execution results.

Purpose:
  Store FlowResult entries from execute_notification_flow() (C-22)
  so operators can review recent notification pipeline executions.

Design:
  - In-memory ring buffer (same pattern as ReceiptStore)
  - Stores compact summary, not raw debug data
  - Fail-closed: store errors never propagate
  - Read-only query interface
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


DEFAULT_MAX_ENTRIES = 50


@dataclass
class FlowLogEntry:
    """Compact summary of one notification flow execution."""

    log_id: str = ""
    executed_at: str = ""
    routing_ok: bool = False
    policy_action: str = ""
    policy_suppressed: bool = False
    policy_urgent: bool = False
    send_ok: bool = False
    channels_attempted: int = 0
    channels_delivered: int = 0
    receipt_id: str = ""
    error_count: int = 0
    top_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FlowLog:
    """In-memory ring buffer for flow execution results."""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._buffer: deque[FlowLogEntry] = deque(maxlen=max_entries)
        self._counter = 0

    def record(self, flow_result: Any) -> str:
        """
        Record a FlowResult. Returns log_id.
        Fail-closed: never raises.
        """
        try:
            self._counter += 1
            log_id = f"FL-{self._counter:04d}"

            if hasattr(flow_result, "executed_at"):
                entry = FlowLogEntry(
                    log_id=log_id,
                    executed_at=flow_result.executed_at,
                    routing_ok=flow_result.routing_ok,
                    policy_action=flow_result.policy_action,
                    policy_suppressed=flow_result.policy_suppressed,
                    policy_urgent=flow_result.policy_urgent,
                    send_ok=flow_result.send_ok,
                    channels_attempted=flow_result.channels_attempted,
                    channels_delivered=flow_result.channels_delivered,
                    receipt_id=flow_result.receipt_id,
                    error_count=len(getattr(flow_result, "errors", [])),
                    top_error=flow_result.errors[0] if flow_result.errors else "",
                )
            elif isinstance(flow_result, dict):
                errors = flow_result.get("errors", [])
                entry = FlowLogEntry(
                    log_id=log_id,
                    executed_at=flow_result.get("executed_at", ""),
                    routing_ok=flow_result.get("routing_ok", False),
                    policy_action=flow_result.get("policy_action", ""),
                    policy_suppressed=flow_result.get("policy_suppressed", False),
                    policy_urgent=flow_result.get("policy_urgent", False),
                    send_ok=flow_result.get("send_ok", False),
                    channels_attempted=flow_result.get("channels_attempted", 0),
                    channels_delivered=flow_result.get("channels_delivered", 0),
                    receipt_id=flow_result.get("receipt_id", ""),
                    error_count=len(errors),
                    top_error=errors[0] if errors else "",
                )
            else:
                entry = FlowLogEntry(log_id=log_id)

            self._buffer.append(entry)
            return log_id
        except Exception:
            return "FL-ERROR"

    def list_entries(self, limit: int = 10) -> list[dict]:
        """Return most recent entries (newest first)."""
        items = list(self._buffer)
        items.reverse()
        return [e.to_dict() for e in items[:limit]]

    def latest(self) -> Optional[dict]:
        if len(self._buffer) == 0:
            return None
        return self._buffer[-1].to_dict()

    def count(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()
