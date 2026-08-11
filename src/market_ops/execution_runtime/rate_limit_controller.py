"""E10.2 Phase 3 — Rate Limit Controller.

Token bucket algorithm for controlling API request rate to
external platforms. Prevents "Too Many Calls" errors from
platform Graph APIs.

Usage:
    controller = RateLimitController(capacity=100, refill_rate=10.0)
    if controller.allow():
        make_api_call()
    else:
        wait_for_quota()
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RateLimitStatus:
    """Current rate limit state."""
    available: float
    capacity: float
    refill_rate: float
    blocked: bool
    wait_seconds: float = 0.0


class RateLimitController:
    """Token bucket rate limiter.

    Tokens refill at a constant rate. Each API call consumes one
    token. When bucket is empty, requests are blocked until tokens
    refill.

    Args:
        capacity: Maximum tokens in bucket (burst capacity).
        refill_rate: Tokens added per second.
    """

    def __init__(self, capacity: float = 100.0, refill_rate: float = 10.0) -> None:
        self._capacity = float(capacity)
        self._refill_rate = float(refill_rate)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._total_allowed: int = 0
        self._total_blocked: int = 0

    def allow(self) -> bool:
        """Check if a request is allowed now.

        Consumes one token if available.

        Returns:
            True if request is allowed, False if blocked.
        """
        self._refill()

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            self._total_allowed += 1
            return True

        self._total_blocked += 1
        return False

    def wait_for_quota(self, timeout: float = 30.0) -> bool:
        """Wait until a token is available.

        Blocks the caller until a token is available or timeout.

        Args:
            timeout: Max seconds to wait.

        Returns:
            True if quota acquired, False if timeout.
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.allow():
                return True
            # Sleep until next token refill
            wait = max(0.01, (1.0 - self._tokens) / self._refill_rate)
            time.sleep(min(wait, 0.1))

        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    @property
    def status(self) -> RateLimitStatus:
        """Current rate limit state."""
        self._refill()
        return RateLimitStatus(
            available=self._tokens,
            capacity=self._capacity,
            refill_rate=self._refill_rate,
            blocked=self._tokens < 1.0,
            wait_seconds=max(0.0, (1.0 - self._tokens) / self._refill_rate) if self._tokens < 1.0 else 0.0,
        )

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens

    @property
    def total_allowed(self) -> int:
        return self._total_allowed

    @property
    def total_blocked(self) -> int:
        return self._total_blocked

    def reset(self) -> None:
        """Reset the bucket to full capacity."""
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._total_allowed = 0
        self._total_blocked = 0