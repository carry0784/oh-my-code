"""Feature Cache — minimal symbol×timeframe indicator result cache.

Phase 5A of CR-048.  Provides:
  - In-memory cache keyed by (symbol, timeframe, bar_ts)
  - Cache contract: get/put/invalidate/clear
  - TTL-based expiration
  - Cache hit/miss stats for observability

Correctness over performance:
  - Single-process in-memory dict (no Redis dependency yet)
  - TTL invalidation on read
  - Manual invalidation API
  - Thread-unsafe (async single-threaded context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ── Cache Key ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FeatureCacheKey:
    """Unique cache key for a computed feature set.

    revision_token ties cache entries to a specific feature pack version.
    When the feature pack changes, entries with the old token are stale.
    """

    symbol: str
    timeframe: str
    bar_ts: str  # ISO timestamp of the bar
    revision_token: str = ""  # feature pack fingerprint / version


# ── Cache Entry ────────────────────────────────────────────────────────


@dataclass
class FeatureCacheEntry:
    """Cached feature computation result."""

    key: FeatureCacheKey
    features: dict  # {"rsi": 65.2, "adx": 28.1, ...}
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


# ── Cache Stats ────────────────────────────────────────────────────────


@dataclass
class FeatureCacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0
    current_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# ── Feature Cache ──────────────────────────────────────────────────────


class FeatureCache:
    """Minimal in-memory feature cache with TTL.

    Cache contract:
      - get(key) -> dict | None  (returns features or None on miss/expired)
      - put(key, features, ttl_seconds) -> None
      - invalidate(symbol, timeframe) -> int  (removed count)
      - invalidate_symbol(symbol) -> int  (all timeframes)
      - clear() -> int  (removed count)
      - stats() -> FeatureCacheStats
    """

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self._store: dict[FeatureCacheKey, FeatureCacheEntry] = {}
        self._default_ttl = default_ttl_seconds
        self._stats = FeatureCacheStats()

    def get(self, key: FeatureCacheKey) -> dict | None:
        """Get cached features. Returns None on miss or expired."""
        entry = self._store.get(key)
        if entry is None:
            self._stats.misses += 1
            return None

        # TTL check
        if entry.expires_at is not None:
            now = datetime.now(timezone.utc)
            if now >= entry.expires_at:
                del self._store[key]
                self._stats.evictions += 1
                self._stats.misses += 1
                self._stats.current_size = len(self._store)
                return None

        self._stats.hits += 1
        return entry.features

    def put(
        self,
        key: FeatureCacheKey,
        features: dict,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store features in cache with TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None

        self._store[key] = FeatureCacheEntry(
            key=key,
            features=features,
            computed_at=now,
            expires_at=expires_at,
        )
        self._stats.current_size = len(self._store)

    def invalidate(self, symbol: str, timeframe: str) -> int:
        """Remove all entries for a specific symbol+timeframe.

        Returns count of removed entries.
        """
        to_remove = [k for k in self._store if k.symbol == symbol and k.timeframe == timeframe]
        for k in to_remove:
            del self._store[k]
        count = len(to_remove)
        self._stats.invalidations += count
        self._stats.current_size = len(self._store)
        return count

    def invalidate_revision(self, revision_token: str) -> int:
        """Remove all entries with a specific revision token.

        Use when a feature pack version changes — all cached computations
        under the old revision become stale.
        """
        to_remove = [k for k in self._store if k.revision_token == revision_token]
        for k in to_remove:
            del self._store[k]
        count = len(to_remove)
        self._stats.invalidations += count
        self._stats.current_size = len(self._store)
        return count

    def invalidate_symbol(self, symbol: str) -> int:
        """Remove all entries for a symbol across all timeframes."""
        to_remove = [k for k in self._store if k.symbol == symbol]
        for k in to_remove:
            del self._store[k]
        count = len(to_remove)
        self._stats.invalidations += count
        self._stats.current_size = len(self._store)
        return count

    def clear(self) -> int:
        """Clear entire cache. Returns count of removed entries."""
        count = len(self._store)
        self._store.clear()
        self._stats.invalidations += count
        self._stats.current_size = 0
        return count

    def stats(self) -> FeatureCacheStats:
        """Return current cache statistics."""
        self._stats.current_size = len(self._store)
        return self._stats

    def size(self) -> int:
        """Current number of entries."""
        return len(self._store)
