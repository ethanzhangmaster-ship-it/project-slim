"""V4.4 Cache Manager — caching for embeddings, results, and intermediate data.

Avoids recomputing: Retriever embeddings, Validation results, etc.
Supports TTL, max size, and LRU eviction.
"""

from __future__ import annotations

import time
from typing import Any


class CacheManager:
    """LRU cache with TTL support."""

    def __init__(self, enabled: bool = True, ttl: float = 3600.0,
                 max_size: int = 10000) -> None:
        self._enabled = enabled
        self._ttl = ttl
        self._max_size = max_size
        self._cache: dict[str, tuple[Any, float]] = {}  # key → (value, timestamp)
        self._access_times: dict[str, float] = {}  # key → last_access
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> Any | None:
        """Get a cached value.

        Returns None if not cached, expired, or cache disabled.
        """
        if not self._enabled:
            self._misses += 1
            return None

        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None

        value, timestamp = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            self._access_times.pop(key, None)
            self._misses += 1
            return None

        self._access_times[key] = time.time()
        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a cached value."""
        if not self._enabled:
            return

        # Evict if at capacity
        if len(self._cache) >= self._max_size:
            self._evict_lru()

        self._cache[key] = (value, time.time())
        self._access_times[key] = time.time()

    def delete(self, key: str) -> None:
        """Delete a cached entry."""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._access_times.clear()

    def has(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._access_times:
            return
        lru_key = min(self._access_times, key=lambda k: self._access_times[k])
        self._cache.pop(lru_key, None)
        self._access_times.pop(lru_key, None)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / max(total, 1)
        return {
            "enabled": self._enabled,
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value