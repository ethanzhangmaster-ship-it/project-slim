"""E10.2 Facebook Ads Adapter — Facebook Graph API integration.

Provides:
  - FacebookAdsAdapter: implements PlatformAdapter for Facebook
  - FacebookClient: HTTP client for Graph API
  - FacebookMapper: E10.1 ActionType → Facebook API params
  - FacebookConfig: credential and runtime configuration
  - Facebook-specific exceptions

In sandbox mode (default), no real API calls are made.
"""

from .facebook_adapter import FacebookAdsAdapter
from .facebook_client import FacebookClient
from .facebook_config import FacebookConfig
from .facebook_mapper import FacebookMapper
from .exceptions import (
    FacebookAdapterError,
    FacebookAuthError,
    FacebookRateLimitError,
    FacebookResourceError,
    FacebookTimeoutError,
    FacebookAPIError,
)

__all__ = [
    "FacebookAdsAdapter",
    "FacebookClient",
    "FacebookConfig",
    "FacebookMapper",
    "FacebookAdapterError",
    "FacebookAuthError",
    "FacebookRateLimitError",
    "FacebookResourceError",
    "FacebookTimeoutError",
    "FacebookAPIError",
]