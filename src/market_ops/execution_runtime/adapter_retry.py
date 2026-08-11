"""E10.2 Phase 3 — Adapter Retry Engine.

Handles transient failures from platform adapters with
exponential backoff. Classifies errors to determine retry
strategy: retryable vs. terminal.
"""

from __future__ import annotations

import time
from typing import Callable, Any

from market_ops.execution_runtime.adapters.exceptions import (
    AdapterError,
    AdapterAuthenticationError,
    AdapterRateLimitError,
)


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, attempts: int, last_error: Exception) -> None:
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


class RetryDecision:
    """Decision from the retry policy."""

    def __init__(self, should_retry: bool, reason: str, backoff_seconds: float = 0.0) -> None:
        self.should_retry = should_retry
        self.reason = reason
        self.backoff_seconds = backoff_seconds


class RetryEngine:
    """Retry engine with exponential backoff.

    Classifies errors into retryable vs terminal:
      - Retryable: timeout, rate limit, network errors
      - Terminal: auth errors, permission errors

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum backoff delay cap.
        backoff_factor: Multiplier for exponential backoff.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor

    def execute(self, fn: Callable[[], Any]) -> Any:
        """Execute a function with retry logic.

        Args:
            fn: Callable to execute (e.g., lambda: adapter.update_budget(...)).

        Returns:
            The return value of fn on success.

        Raises:
            RetryExhaustedError: If all retries are exhausted.
            AdapterAuthenticationError: Immediately, no retry.
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_error = exc
                decision = self._decide(exc, attempt)

                if not decision.should_retry:
                    if attempt >= self._max_retries:
                        raise RetryExhaustedError(self._max_retries, last_error) from exc
                    raise

                if attempt < self._max_retries:
                    time.sleep(decision.backoff_seconds)

        raise RetryExhaustedError(self._max_retries, last_error or Exception("unknown"))

    def _decide(self, error: Exception, attempt: int) -> RetryDecision:
        """Determine retry strategy for an error.

        Args:
            error: The exception that occurred.
            attempt: Current attempt number (0-based).

        Returns:
            RetryDecision with should_retry and backoff.
        """
        # Terminal errors — never retry
        if isinstance(error, AdapterAuthenticationError):
            return RetryDecision(False, f"Auth error — not retryable: {error}")

        # Rate limit — retry with platform-specified delay
        if isinstance(error, AdapterRateLimitError):
            retry_after = getattr(error, "retry_after", 60)
            return RetryDecision(True, f"Rate limited — retrying after {retry_after}s", retry_after)

        # Timeout / network — retry with exponential backoff
        if isinstance(error, AdapterError):
            if "timeout" in str(error).lower() or "temporary" in str(error).lower():
                delay = self._calc_backoff(attempt)
                return RetryDecision(True, f"Transient error — retry {attempt+1}/{self._max_retries}", delay)

        # Generic error — retry with backoff if not last attempt
        if attempt < self._max_retries:
            delay = self._calc_backoff(attempt)
            return RetryDecision(True, f"Error — retry {attempt+1}/{self._max_retries}: {error}", delay)

        return RetryDecision(False, f"All retries exhausted: {error}")

    def _calc_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        delay = min(base_delay * backoff_factor^attempt, max_delay)
        """
        delay = self._base_delay * (self._backoff_factor ** attempt)
        return min(delay, self._max_delay)

    @property
    def max_retries(self) -> int:
        return self._max_retries