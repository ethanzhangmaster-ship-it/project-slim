"""E10.2 Adapter Exceptions — Standardized error types for platform adapters.

All adapter implementations should raise these exceptions so the
ExecutionEngine can handle failures uniformly.
"""

from __future__ import annotations


class AdapterError(Exception):
    """Base exception for all adapter-level errors."""

    def __init__(self, message: str, platform: str = "", raw_response: dict | None = None) -> None:
        super().__init__(message)
        self.platform = platform
        self.raw_response = raw_response or {}


class AdapterNotFoundError(AdapterError):
    """Raised when no adapter is registered for a platform."""

    def __init__(self, platform: str) -> None:
        super().__init__(f"No adapter registered for platform: {platform}", platform=platform)


class AdapterAuthenticationError(AdapterError):
    """Raised when adapter fails to authenticate with the platform."""

    def __init__(self, platform: str, message: str = "Authentication failed") -> None:
        super().__init__(message, platform=platform)


class AdapterRateLimitError(AdapterError):
    """Raised when platform rate limit is exceeded."""

    def __init__(self, platform: str, retry_after: int = 60) -> None:
        super().__init__(f"Rate limit exceeded on {platform}", platform=platform)
        self.retry_after = retry_after
