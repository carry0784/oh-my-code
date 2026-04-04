"""
Card C-16: Receipt Persistence / Delivery Log

Purpose:
  Persist notification receipts in memory so delivery outcomes can be
  reviewed, handed off, and audited. No external DB dependency.

Design:
  - In-memory ring buffer with configurable max size
  - Each entry stores: receipt + snapshot summary + routing decision
  - Fail-closed: store errors never propagate
  - Read-only query interface (list, count, latest)
  - No state mutation beyond append-only receipt log
  - No hidden reasoning, no debug traces
  - Future cards may add file/DB persistence backends

Store contract:
  Input:  NotificationReceipt (from C-15) + snapshot summary
  Output: stored receipt_id
  Query:  list_receipts(), latest(), count()
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class StoredReceipt:
    """A persisted notification receipt with context."""

    receipt_id: str = ""
    stored_at: str = ""
    severity_tier: str = ""
    highest_incident: str = ""
    overall_status: str = ""
    channels_attempted: int = 0
    channels_delivered: int = 0
    channel_results: list[dict] = field(default_factory=list)
    triage_top: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Receipt Store
# ---------------------------------------------------------------------------

DEFAULT_MAX_SIZE = 100


class ReceiptStore:
    """
    In-memory ring buffer for notification receipts.

    Optional file backend (C-18): if provided, each receipt is also
    appended to a JSONL file for persistence across restarts.
    On init with file_backend, existing file entries are loaded into buffer.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, file_backend: Any = None) -> None:
        self._max_size = max_size
        self._buffer: deque[StoredReceipt] = deque(maxlen=max_size)
        self._file_backend = file_backend

        # C-18: Load existing receipts from file backend on init
        if file_backend is not None:
            try:
                existing = file_backend.load_all()
                for entry in existing[-max_size:]:
                    self._buffer.append(
                        StoredReceipt(
                            **{
                                k: v
                                for k, v in entry.items()
                                if k in StoredReceipt.__dataclass_fields__
                            }
                        )
                    )
            except Exception:
                pass  # fail-closed: skip loading on error

    def store(
        self,
        receipt: Any,
        snapshot: Optional[dict] = None,
    ) -> str:
        """
        Persist a notification receipt.

        Args:
            receipt: NotificationReceipt from C-15 (or dict with same shape)
            snapshot: Optional snapshot dict from C-13 for context

        Returns:
            receipt_id (str)

        Fail-closed: never raises.
        """
        try:
            now = datetime.now(timezone.utc)
            receipt_id = f"RX-{uuid.uuid4().hex[:8].upper()}"

            # Extract from receipt (supports both dataclass and dict)
            if hasattr(receipt, "severity_tier"):
                severity = receipt.severity_tier
                attempted = receipt.channels_attempted
                delivered = receipt.channels_delivered
                results = [
                    {"channel": r.channel, "delivered": r.delivered, "detail": r.detail}
                    for r in getattr(receipt, "results", [])
                ]
            elif isinstance(receipt, dict):
                severity = receipt.get("severity_tier", "unknown")
                attempted = receipt.get("channels_attempted", 0)
                delivered = receipt.get("channels_delivered", 0)
                results = receipt.get("results", [])
            else:
                severity = "unknown"
                attempted = 0
                delivered = 0
                results = []

            # Extract from snapshot
            highest = ""
            overall = ""
            triage = ""
            if snapshot and isinstance(snapshot, dict):
                highest = snapshot.get("highest_incident", "")
                overall = snapshot.get("overall_status", "")
                triage = snapshot.get("triage_top", "") or ""

            entry = StoredReceipt(
                receipt_id=receipt_id,
                stored_at=now.isoformat(),
                severity_tier=severity,
                highest_incident=highest,
                overall_status=overall,
                channels_attempted=attempted,
                channels_delivered=delivered,
                channel_results=results,
                triage_top=triage,
            )

            self._buffer.append(entry)

            # C-18: Persist to file backend if available
            if self._file_backend is not None:
                try:
                    self._file_backend.append(entry.to_dict())
                except Exception:
                    pass  # fail-closed: file write failure is non-fatal

            return receipt_id

        except Exception:
            return "RX-ERROR"

    def list_receipts(self, limit: int = 20) -> list[dict]:
        """Return most recent receipts (newest first), as dicts."""
        items = list(self._buffer)
        items.reverse()
        return [r.to_dict() for r in items[:limit]]

    def latest(self) -> Optional[dict]:
        """Return the most recent receipt, or None."""
        if len(self._buffer) == 0:
            return None
        return self._buffer[-1].to_dict()

    def count(self) -> int:
        """Total receipts stored."""
        return len(self._buffer)

    def clear(self) -> None:
        """Clear all stored receipts."""
        self._buffer.clear()
