"""V4.4.1 Rate Limiter — API rate limiting for external services.

Prevents hammering:
  Facebook API: 1000 req/min
  Google API: 100 req/sec
  OpenAI: 60 req/min

Supports: token bucket, sliding window, per-service limits.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class RateLimiter:
    """Rate limiter to prevent API abuse."""

    def __init__(self) -> None:
        # Per-service limits: {service_name: {"max_requests": N, "window_seconds": S}}
        self._limits: dict[str, dict[str, Any]] = {}
        # Token bucket: {service_name: {"tokens": N, "last_refill": timestamp}}
        self._buckets: dict[str, dict[str, Any]] = {}
        # Sliding window: {service_name: [timestamps]}
        self._windows: dict[str, list[float]] = defaultdict(list)
        # Stats
        self._allowed: dict[str, int] = defaultdict(int)
        self._rejected: dict[str, int] = defaultdict(int)

    def set_limit(self, service: str, max_requests: int,
                  window_seconds: float = 60.0) -> None:
        """Set a rate limit for a service.

        Args:
            service: Service name (e.g., 'facebook_api', 'google_ads').
            max_requests: Maximum requests allowed in the window.
            window_seconds: Time window in seconds.
        """
        self._limits[service] = {
            "max_requests": max_requests,
            "window_seconds": window_seconds,
        }
        self._buckets[service] = {
            "tokens": max_requests,
            "last_refill": time.time(),
        }

    def remove_limit(self, service: str) -> None:
        """Remove a rate limit."""
        self._limits.pop(service, None)
        self._buckets.pop(service, None)
        self._windows.pop(service, None)

    def allow(self, service: str, cost: int = 1) -> bool:
        """Check if a request is allowed.

        Args:
            service: Service name.
            cost: Token cost (default 1, can be higher for expensive operations).

        Returns:
            True if allowed, False if rate limited.
        """
        if service not in self._limits:
            self._allowed[service] += 1
            return True  # No limit set

        limit = self._limits[service]

        # Refill bucket
        bucket = self._buckets[service]
        now = time.time()
        elapsed = now - bucket["last_refill"]
        refill_rate = limit["max_requests"] / limit["window_seconds"]
        bucket["tokens"] = min(
            limit["max_requests"],
            bucket["tokens"] + elapsed * refill_rate,
        )
        bucket["last_refill"] = now

        if bucket["tokens"] >= cost:
            bucket["tokens"] -= cost
            self._allowed[service] += 1
            return True

        self._rejected[service] += 1
        return False

    def wait_and_allow(self, service: str, cost: int = 1,
                       timeout: float = 30.0) -> bool:
        """Wait until a request is allowed or timeout.

        Returns:
            True if allowed, False if timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.allow(service, cost):
                return True
            time.sleep(0.1)
        return False

    def get_remaining(self, service: str) -> int:
        """Get remaining requests for a service."""
        if service not in self._limits:
            return -1  # Unlimited
        bucket = self._buckets.get(service)
        if bucket is None:
            return 0
        # Refill before checking
        limit = self._limits[service]
        now = time.time()
        elapsed = now - bucket["last_refill"]
        refill_rate = limit["max_requests"] / limit["window_seconds"]
        tokens = min(
            limit["max_requests"],
            bucket["tokens"] + elapsed * refill_rate,
        )
        return int(tokens)

    def get_reset_time(self, service: str) -> float:
        """Get seconds until the bucket is fully refilled."""
        if service not in self._limits:
            return 0.0
        limit = self._limits[service]
        bucket = self._buckets[service]
        tokens_needed = limit["max_requests"] - bucket["tokens"]
        if tokens_needed <= 0:
            return 0.0
        refill_rate = limit["max_requests"] / limit["window_seconds"]
        return tokens_needed / refill_rate

    def get_stats(self, service: str | None = None) -> dict[str, Any]:
        """Get rate limit statistics."""
        if service:
            return {
                "service": service,
                "limit": self._limits.get(service, {}),
                "remaining": self.get_remaining(service),
                "allowed": self._allowed.get(service, 0),
                "rejected": self._rejected.get(service, 0),
                "reset_in_sec": round(self.get_reset_time(service), 1),
            }

        return {
            svc: {
                "limit": self._limits.get(svc, {}),
                "remaining": self.get_remaining(svc),
                "allowed": self._allowed.get(svc, 0),
                "rejected": self._rejected.get(svc, 0),
            }
            for svc in self._limits
        }

    def get_summary(self) -> dict[str, Any]:
        """Get overall rate limiter summary."""
        total_allowed = sum(self._allowed.values())
        total_rejected = sum(self._rejected.values())
        return {
            "services": len(self._limits),
            "total_allowed": total_allowed,
            "total_rejected": total_rejected,
            "reject_rate": round(
                total_rejected / max(1, total_allowed + total_rejected), 3
            ),
            "per_service": {
                svc: {
                    "remaining": self.get_remaining(svc),
                    "rejected": self._rejected.get(svc, 0),
                }
                for svc in self._limits
            },
        }

    def reset(self) -> None:
        """Reset all rate limit counters."""
        self._allowed.clear()
        self._rejected.clear()
        for svc in self._limits:
            self._buckets[svc] = {
                "tokens": self._limits[svc]["max_requests"],
                "last_refill": time.time(),
            }