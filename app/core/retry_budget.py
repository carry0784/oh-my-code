"""
Card C-36: Retry Budget Limit

Purpose:
  Enforce a bounded retry budget that limits total retry attempts
  within a time window, preventing retry storms.

Design:
  - Sliding window budget: max N retries per T seconds
  - Per-channel and global budget tracking
  - Read-only budget check: does not execute retries
  - Fail-closed: budget errors → deny retry
  - No daemon, scheduler, background worker
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from collections import deque


DEFAULT_GLOBAL_BUDGET = 20      # max 20 retries per window
DEFAULT_CHANNEL_BUDGET = 10     # max 10 retries per channel per window
DEFAULT_WINDOW_SECONDS = 3600   # 1 hour window


@dataclass
class BudgetCheck:
    """Result of a budget check."""
    allowed: bool
    reason: str
    global_used: int = 0
    global_limit: int = 0
    channel_used: int = 0
    channel_limit: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RetryBudget:
    """
    Sliding window retry budget tracker.

    Limits total retry attempts within configurable time windows
    to prevent retry storms.
    """

    def __init__(
        self,
        global_budget: int = DEFAULT_GLOBAL_BUDGET,
        channel_budget: int = DEFAULT_CHANNEL_BUDGET,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        self._global_budget = global_budget
        self._channel_budget = channel_budget
        self._window_seconds = window_seconds
        self._global_log: deque[datetime] = deque()
        self._channel_logs: dict[str, deque[datetime]] = {}

    def check(self, channel: str) -> BudgetCheck:
        """
        Check if a retry attempt is within budget.

        Fail-closed: errors → deny.
        """
        try:
            return self._check_impl(channel)
        except Exception:
            return BudgetCheck(
                allowed=False,
                reason="budget_check_error",
            )

    def _check_impl(self, channel: str) -> BudgetCheck:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self._window_seconds)

        # Prune expired entries
        self._prune(cutoff)

        global_used = len(self._global_log)
        ch_log = self._channel_logs.get(channel, deque())
        channel_used = len(ch_log)

        # Check global budget
        if global_used >= self._global_budget:
            return BudgetCheck(
                allowed=False,
                reason=f"global_budget_exhausted ({global_used}/{self._global_budget})",
                global_used=global_used,
                global_limit=self._global_budget,
                channel_used=channel_used,
                channel_limit=self._channel_budget,
            )

        # Check channel budget
        if channel_used >= self._channel_budget:
            return BudgetCheck(
                allowed=False,
                reason=f"channel_budget_exhausted ({channel_used}/{self._channel_budget})",
                global_used=global_used,
                global_limit=self._global_budget,
                channel_used=channel_used,
                channel_limit=self._channel_budget,
            )

        return BudgetCheck(
            allowed=True,
            reason="within_budget",
            global_used=global_used,
            global_limit=self._global_budget,
            channel_used=channel_used,
            channel_limit=self._channel_budget,
        )

    def record(self, channel: str) -> None:
        """Record a retry attempt against the budget."""
        try:
            now = datetime.now(timezone.utc)
            self._global_log.append(now)
            if channel not in self._channel_logs:
                self._channel_logs[channel] = deque()
            self._channel_logs[channel].append(now)
        except Exception:
            pass  # fail-closed

    def _prune(self, cutoff: datetime) -> None:
        """Remove entries older than cutoff."""
        while self._global_log and self._global_log[0] < cutoff:
            self._global_log.popleft()
        for ch in list(self._channel_logs.keys()):
            log = self._channel_logs[ch]
            while log and log[0] < cutoff:
                log.popleft()
            if not log:
                del self._channel_logs[ch]

    def reset(self) -> None:
        """Reset all budget tracking."""
        self._global_log.clear()
        self._channel_logs.clear()

    def summary(self) -> dict[str, Any]:
        """Get budget summary."""
        try:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=self._window_seconds)
            self._prune(cutoff)
            channels = {}
            for ch, log in self._channel_logs.items():
                channels[ch] = len(log)
            return {
                "global_used": len(self._global_log),
                "global_limit": self._global_budget,
                "channel_limit": self._channel_budget,
                "window_seconds": self._window_seconds,
                "channels": channels,
            }
        except Exception:
            return {"global_used": 0, "error": True}
