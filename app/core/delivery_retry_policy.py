"""
Card C-29: Delivery Retry Policy — Retry eligibility and receipt tracking.

Purpose:
  Determine whether a failed notification delivery is eligible for retry,
  and track retry attempts in receipts.

Design:
  delivery result → retry eligibility check → retry receipt

  - Read-only eligibility check: no state mutation in check
  - Retry counter: tracks attempts per channel per incident
  - Max retries: configurable cap (default 3)
  - Cooldown: minimum time between retries (default 60s)
  - Fail-closed: retry policy errors → no retry (safe default)
  - No hidden reasoning, no debug traces

Retry eligibility rules:
  1. Channel must have delivered=False in result
  2. Failure detail must NOT contain "not configured" (permanent failure)
  3. Retry count must be below max_retries
  4. Time since last attempt must exceed cooldown
  5. Policy action must not be "suppress"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_COOLDOWN_S = 60

# Permanent failure patterns — these should never be retried
_PERMANENT_FAILURE_PATTERNS = frozenset(
    {
        "not configured",
        "stub",
        "structurally unsupported",
    }
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RetryEligibility:
    """Result of a retry eligibility check for one channel."""

    channel: str
    eligible: bool
    reason: str
    attempt_number: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES


@dataclass
class RetryReceipt:
    """Record of a retry decision."""

    channel: str
    attempted: bool
    attempt_number: int
    eligible: bool
    reason: str
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Retry state tracker
# ---------------------------------------------------------------------------


@dataclass
class _ChannelRetryState:
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Delivery Retry Policy
# ---------------------------------------------------------------------------


class DeliveryRetryPolicy:
    """
    Stateful retry policy for failed notification deliveries.

    Tracks per-channel retry attempts. Determines eligibility
    based on failure type, retry count, and cooldown.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        cooldown_seconds: int = DEFAULT_RETRY_COOLDOWN_S,
    ) -> None:
        self._max_retries = max_retries
        self._cooldown = cooldown_seconds
        self._state: dict[str, _ChannelRetryState] = {}

    def check_eligibility(
        self,
        channel: str,
        delivered: bool,
        detail: str = "",
        policy_action: str = "send",
    ) -> RetryEligibility:
        """
        Check if a failed delivery is eligible for retry.

        Args:
            channel: Channel name (e.g. "external", "slack")
            delivered: Whether delivery succeeded
            detail: Failure detail string
            policy_action: Current policy action

        Returns:
            RetryEligibility with eligible flag and reason.

        Fail-closed: errors → not eligible.
        """
        try:
            return self._check_impl(channel, delivered, detail, policy_action)
        except Exception:
            return RetryEligibility(
                channel=channel,
                eligible=False,
                reason="eligibility_check_error",
            )

    def _check_impl(
        self,
        channel: str,
        delivered: bool,
        detail: str,
        policy_action: str,
    ) -> RetryEligibility:
        now = datetime.now(timezone.utc)
        state = self._state.get(channel, _ChannelRetryState())

        # Rule 1: Already delivered → no retry needed
        if delivered:
            return RetryEligibility(
                channel=channel,
                eligible=False,
                reason="already_delivered",
                attempt_number=state.attempts,
                max_retries=self._max_retries,
            )

        # Rule 2: Suppressed → no retry
        if policy_action == "suppress":
            return RetryEligibility(
                channel=channel,
                eligible=False,
                reason="suppressed_by_policy",
                attempt_number=state.attempts,
                max_retries=self._max_retries,
            )

        # Rule 3: Permanent failure → no retry
        detail_lower = detail.lower()
        for pattern in _PERMANENT_FAILURE_PATTERNS:
            if pattern in detail_lower:
                return RetryEligibility(
                    channel=channel,
                    eligible=False,
                    reason=f"permanent_failure: {pattern}",
                    attempt_number=state.attempts,
                    max_retries=self._max_retries,
                )

        # Rule 4: Max retries exceeded
        if state.attempts >= self._max_retries:
            return RetryEligibility(
                channel=channel,
                eligible=False,
                reason=f"max_retries_exceeded ({state.attempts}/{self._max_retries})",
                attempt_number=state.attempts,
                max_retries=self._max_retries,
            )

        # Rule 5: Cooldown not elapsed
        if state.last_attempt_at is not None:
            elapsed = (now - state.last_attempt_at).total_seconds()
            if elapsed < self._cooldown:
                return RetryEligibility(
                    channel=channel,
                    eligible=False,
                    reason=f"cooldown ({int(self._cooldown - elapsed)}s remaining)",
                    attempt_number=state.attempts,
                    max_retries=self._max_retries,
                )

        # Eligible
        return RetryEligibility(
            channel=channel,
            eligible=True,
            reason="eligible_for_retry",
            attempt_number=state.attempts + 1,
            max_retries=self._max_retries,
        )

    def record_attempt(self, channel: str) -> RetryReceipt:
        """
        Record a retry attempt for a channel.
        Call this after actually performing a retry.
        """
        now = datetime.now(timezone.utc)
        if channel not in self._state:
            self._state[channel] = _ChannelRetryState()

        self._state[channel].attempts += 1
        self._state[channel].last_attempt_at = now

        return RetryReceipt(
            channel=channel,
            attempted=True,
            attempt_number=self._state[channel].attempts,
            eligible=True,
            reason="retry_attempted",
            timestamp=now.isoformat(),
        )

    def clear_channel(self, channel: str) -> None:
        """Clear retry state for a channel (e.g. after successful delivery)."""
        self._state.pop(channel, None)

    def reset(self) -> None:
        """Reset all retry state."""
        self._state.clear()

    def get_state(self, channel: str) -> dict:
        """Get current retry state for a channel."""
        s = self._state.get(channel, _ChannelRetryState())
        return {
            "attempts": s.attempts,
            "last_attempt_at": s.last_attempt_at.isoformat() if s.last_attempt_at else None,
        }
