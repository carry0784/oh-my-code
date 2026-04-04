"""
Async Rate Limiter — Token Bucket
K-Dexter AOS — TCL Spec v1

Token bucket algorithm for exchange API call throttling.
Each adapter instantiates its own AsyncRateLimiter with exchange-specific limits.
"""

from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    """
    Token bucket rate limiter for exchange API calls.

    Args:
        max_calls: Maximum calls allowed per period.
        period:    Refill window in seconds (default: 1.0).
    """

    def __init__(self, max_calls: int, period: float = 1.0) -> None:
        if max_calls <= 0:
            raise ValueError(f"max_calls must be > 0, got {max_calls}")
        if period <= 0:
            raise ValueError(f"period must be > 0, got {period}")
        self._max = max_calls
        self._period = period
        self._tokens: float = float(max_calls)
        self._last_refill: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire one token. Blocks until available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                float(self._max),
                self._tokens + elapsed * (self._max / self._period),
            )
            self._last_refill = now

            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) * (self._period / self._max)
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

    @property
    def max_calls(self) -> int:
        return self._max

    @property
    def period(self) -> float:
        return self._period
