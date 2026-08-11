"""E10.2 Platform Adapter Layer — External platform integration foundation.

Provides:
  - PlatformAdapter: abstract base for all external adapters
  - AdapterRegistry: factory for selecting adapters by platform
  - AdapterResult: unified response contract
  - Adapter exceptions for error handling
  - FacebookAdsAdapter: Facebook Graph API integration (Phase 2)

No real platform SDK imports in this package.
"""

from .base_adapter import PlatformAdapter, AdapterResult
from .adapter_registry import AdapterRegistry
from .exceptions import AdapterError, AdapterNotFoundError, AdapterAuthenticationError, AdapterRateLimitError
from .mock_adapter import MockPlatformAdapter
from .facebook import FacebookAdsAdapter, FacebookConfig, FacebookClient, FacebookMapper

__all__ = [
    "PlatformAdapter",
    "AdapterResult",
    "AdapterRegistry",
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterAuthenticationError",
    "AdapterRateLimitError",
    "MockPlatformAdapter",
    "FacebookAdsAdapter",
    "FacebookConfig",
    "FacebookClient",
    "FacebookMapper",
]
