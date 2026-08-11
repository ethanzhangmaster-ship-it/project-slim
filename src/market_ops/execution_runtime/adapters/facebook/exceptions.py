"""E10.2 Facebook Adapter Exceptions.

Maps Facebook Graph API error responses to the standardized
E10.2 adapter exception hierarchy. All exceptions inherit from
AdapterError so the ExecutionEngine can handle them uniformly.

Error mapping:
    OAuth / token expired  → AdapterAuthenticationError
    Rate limit (code 4)    → AdapterRateLimitError
    Invalid resource (404) → AdapterResourceError
    Timeout / network      → AdapterTimeoutError
"""

from __future__ import annotations

from market_ops.execution_runtime.adapters.exceptions import (
    AdapterError,
    AdapterAuthenticationError,
    AdapterRateLimitError,
)

PLATFORM = "facebook"


class FacebookAdapterError(AdapterError):
    """Base exception for Facebook adapter errors."""

    def __init__(self, message: str, raw_response: dict | None = None) -> None:
        super().__init__(message, platform=PLATFORM, raw_response=raw_response)


class FacebookAuthError(AdapterAuthenticationError):
    """Facebook OAuth / token expired / permission denied."""

    def __init__(self, message: str = "Facebook authentication failed", raw_response: dict | None = None) -> None:
        super().__init__(platform=PLATFORM, message=message)
        self.raw_response = raw_response or {}


class FacebookRateLimitError(AdapterRateLimitError):
    """Facebook rate limit exceeded (error code 4 or 17)."""

    def __init__(self, retry_after: int = 60, raw_response: dict | None = None) -> None:
        super().__init__(platform=PLATFORM, retry_after=retry_after)
        self.raw_response = raw_response or {}


class FacebookResourceError(FacebookAdapterError):
    """Resource not found or invalid campaign/adset/ad ID."""

    def __init__(self, resource_id: str, message: str = "Resource not found", raw_response: dict | None = None) -> None:
        super().__init__(f"{message}: {resource_id}", raw_response=raw_response)
        self.resource_id = resource_id


class FacebookTimeoutError(FacebookAdapterError):
    """Facebook API request timeout or network failure."""

    def __init__(self, operation: str, timeout: int = 30, raw_response: dict | None = None) -> None:
        super().__init__(f"Request timeout ({timeout}s) during: {operation}", raw_response=raw_response)
        self.operation = operation
        self.timeout = timeout


class FacebookAPIError(FacebookAdapterError):
    """Generic Facebook Graph API error with error code."""

    def __init__(self, code: int, message: str, raw_response: dict | None = None) -> None:
        super().__init__(f"Facebook API error [{code}]: {message}", raw_response=raw_response)
        self.error_code = code


# ── Error code mapping ────────────────────────────────────

_FACEBOOK_ERROR_MAP: dict[int, type[FacebookAdapterError]] = {
    1:   FacebookAPIError,       # Unknown error
    2:   FacebookTimeoutError,   # Temporary / service
    4:   FacebookRateLimitError,  # Rate limit
    10:  FacebookAuthError,      # Permission denied
    17:  FacebookRateLimitError,  # User request limit
    100: FacebookResourceError,  # Invalid parameter
    102: FacebookAuthError,      # Session expired
    190: FacebookAuthError,      # OAuth / access token
    200: FacebookAuthError,      # Permission error
    263: FacebookResourceError,  # External ID not found
    368: FacebookTimeoutError,   # Temporarily blocked
    800: FacebookRateLimitError,  # App rate limit
}


def map_facebook_error(error_code: int, error_message: str, raw_response: dict | None = None) -> FacebookAdapterError:
    """Map a Facebook error code to the appropriate exception class.

    Args:
        error_code: Facebook Graph API error code.
        error_message: Human-readable error message.
        raw_response: Full API response dict for debugging.

    Returns:
        Instantiated FacebookAdapterError subclass.
    """
    exc_cls = _FACEBOOK_ERROR_MAP.get(error_code, FacebookAPIError)
    if exc_cls is FacebookResourceError:
        return exc_cls(str(error_code), error_message, raw_response)
    if exc_cls is FacebookTimeoutError:
        return exc_cls(error_message, raw_response=raw_response)
    if exc_cls is FacebookRateLimitError:
        return exc_cls(raw_response=raw_response)
    if exc_cls is FacebookAuthError:
        return exc_cls(error_message, raw_response=raw_response)
    return exc_cls(error_code, error_message, raw_response)