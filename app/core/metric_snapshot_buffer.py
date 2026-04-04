"""
K-Dexter Metric Snapshot Ring Buffer

Volatile in-memory buffer that stores periodic count-based metric snapshots.
Used by Trend Observation to compare current vs. previous time windows.

Properties:
  - In-memory only — restart clears all history
  - Fixed-size ring buffer — oldest entries evicted when full
  - Read-only consumers — only record_snapshot() writes
  - No persistence, no external dependencies

This is NOT a storage layer. It is a volatile observation buffer.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional


@dataclass(frozen=True)
class MetricSnapshot:
    """Single point-in-time metric snapshot."""

    timestamp: datetime
    blocked_total: int = 0
    pending_retry_total: int = 0
    review_total: int = 0
    watch_total: int = 0


class MetricSnapshotBuffer:
    """
    Volatile ring buffer for metric snapshots.

    Stores up to `max_snapshots` entries. Oldest entries are evicted
    when the buffer is full. All data is lost on process restart.

    Usage:
        buffer = MetricSnapshotBuffer()
        buffer.record_snapshot(MetricSnapshot(timestamp=..., blocked_total=5, ...))
        current, previous = buffer.get_windows(window_minutes=60)
    """

    def __init__(self, max_snapshots: int = 240):
        """
        Initialize buffer.

        Default 240 snapshots = 2 hours of 30-second intervals,
        or 4 hours of 1-minute intervals.
        """
        self._buffer: deque[MetricSnapshot] = deque(maxlen=max_snapshots)
        self._started_at: datetime = datetime.now(timezone.utc)

    @property
    def started_at(self) -> datetime:
        """When this buffer was created (process start proxy)."""
        return self._started_at

    @property
    def count(self) -> int:
        """Number of snapshots in buffer."""
        return len(self._buffer)

    def record_snapshot(self, snapshot: MetricSnapshot) -> None:
        """Record a new metric snapshot. Only write path."""
        self._buffer.append(snapshot)

    def get_windows(
        self,
        window_minutes: int = 60,
        now: Optional[datetime] = None,
    ) -> tuple[list[MetricSnapshot], list[MetricSnapshot]]:
        """
        Get snapshots for current and previous windows.

        Returns (current_window, previous_window) where:
          current_window  = snapshots from (now - window_minutes) to now
          previous_window = snapshots from (now - 2*window_minutes) to (now - window_minutes)

        Both lists may be empty if insufficient history.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        window = timedelta(minutes=window_minutes)
        current_start = now - window
        previous_start = now - (2 * window)

        current = []
        previous = []

        for snap in self._buffer:
            if current_start <= snap.timestamp <= now:
                current.append(snap)
            elif previous_start <= snap.timestamp < current_start:
                previous.append(snap)

        return current, previous

    def list_snapshots(self, limit: int = 100) -> list[MetricSnapshot]:
        """List most recent snapshots (read-only). For debugging/testing."""
        return list(self._buffer)[-limit:]
