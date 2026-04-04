"""
Card C-37: Retry Metrics

Purpose:
  Collect and expose retry execution metrics for operator visibility.

Design:
  - Lightweight in-memory counters
  - Per-channel and global counters
  - success / failure / skipped / budget_denied / gate_denied
  - Read-only summary endpoint
  - Fail-closed: metric errors → safe defaults
  - No daemon, scheduler, background worker
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict


@dataclass
class RetryMetricsSummary:
    """Compact retry metrics summary."""

    total_attempts: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_budget_denied: int = 0
    total_gate_denied: int = 0
    total_passes: int = 0
    last_pass_at: str = ""
    channels: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetryMetrics:
    """
    In-memory retry metrics collector.

    Tracks retry execution outcomes for operator review.
    """

    def __init__(self) -> None:
        self._total_attempts = 0
        self._total_succeeded = 0
        self._total_failed = 0
        self._total_skipped = 0
        self._total_budget_denied = 0
        self._total_gate_denied = 0
        self._total_passes = 0
        self._last_pass_at = ""
        self._channel_attempts: dict[str, int] = defaultdict(int)
        self._channel_succeeded: dict[str, int] = defaultdict(int)
        self._channel_failed: dict[str, int] = defaultdict(int)

    def record_attempt(self, channel: str, success: bool) -> None:
        """Record a retry attempt outcome."""
        try:
            self._total_attempts += 1
            self._channel_attempts[channel] += 1
            if success:
                self._total_succeeded += 1
                self._channel_succeeded[channel] += 1
            else:
                self._total_failed += 1
                self._channel_failed[channel] += 1
        except Exception:
            pass

    def record_skip(self, reason: str = "") -> None:
        """Record a skipped retry."""
        try:
            self._total_skipped += 1
        except Exception:
            pass

    def record_budget_denied(self) -> None:
        """Record a budget-denied retry."""
        try:
            self._total_budget_denied += 1
        except Exception:
            pass

    def record_gate_denied(self) -> None:
        """Record a gate-denied retry pass."""
        try:
            self._total_gate_denied += 1
        except Exception:
            pass

    def record_pass(self) -> None:
        """Record a completed retry pass."""
        try:
            self._total_passes += 1
            self._last_pass_at = datetime.now(timezone.utc).isoformat()
        except Exception:
            pass

    def summary(self) -> RetryMetricsSummary:
        """Get current metrics summary. Fail-closed."""
        try:
            channels = {}
            for ch in set(
                list(self._channel_attempts.keys())
                + list(self._channel_succeeded.keys())
                + list(self._channel_failed.keys())
            ):
                channels[ch] = {
                    "attempts": self._channel_attempts.get(ch, 0),
                    "succeeded": self._channel_succeeded.get(ch, 0),
                    "failed": self._channel_failed.get(ch, 0),
                }
            return RetryMetricsSummary(
                total_attempts=self._total_attempts,
                total_succeeded=self._total_succeeded,
                total_failed=self._total_failed,
                total_skipped=self._total_skipped,
                total_budget_denied=self._total_budget_denied,
                total_gate_denied=self._total_gate_denied,
                total_passes=self._total_passes,
                last_pass_at=self._last_pass_at,
                channels=channels,
            )
        except Exception:
            return RetryMetricsSummary()

    def reset(self) -> None:
        """Reset all metrics."""
        self._total_attempts = 0
        self._total_succeeded = 0
        self._total_failed = 0
        self._total_skipped = 0
        self._total_budget_denied = 0
        self._total_gate_denied = 0
        self._total_passes = 0
        self._last_pass_at = ""
        self._channel_attempts.clear()
        self._channel_succeeded.clear()
        self._channel_failed.clear()
