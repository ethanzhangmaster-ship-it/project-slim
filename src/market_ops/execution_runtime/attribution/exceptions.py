"""E10.2 Phase 4 — Attribution Exceptions.

Standardized error types for attribution platform failures.
Maps to the same hierarchy as adapter exceptions for uniform
error handling in the ExecutionEngine.
"""

from __future__ import annotations


class AttributionError(Exception):
    """Base exception for attribution errors."""

    def __init__(self, message: str, source: str = "", raw_response: dict | None = None) -> None:
        super().__init__(message)
        self.source = source
        self.raw_response = raw_response or {}


class AttributionAuthError(AttributionError):
    """Authentication or API key failure."""

    def __init__(self, source: str, message: str = "Authentication failed") -> None:
        super().__init__(message, source=source)


class AttributionRateLimitError(AttributionError):
    """Rate limit exceeded."""

    def __init__(self, source: str, retry_after: int = 60) -> None:
        super().__init__(f"Rate limit exceeded for {source}", source=source)
        self.retry_after = retry_after


class AttributionTimeoutError(AttributionError):
    """API timeout or network failure."""

    def __init__(self, source: str, timeout: int = 30) -> None:
        super().__init__(f"Timeout ({timeout}s) from {source}", source=source)
        self.timeout = timeout


class AttributionDataError(AttributionError):
    """Invalid or missing data in attribution response."""

    def __init__(self, source: str, field: str = "") -> None:
        msg = f"Missing or invalid data from {source}"
        if field:
            msg += f": {field}"
        super().__init__(msg, source=source)
        self.field = field


class AttributionUnavailableError(AttributionError):
    """Attribution platform not configured or unavailable."""

    def __init__(self, source: str) -> None:
        super().__init__(f"Attribution source '{source}' is not available", source=source)