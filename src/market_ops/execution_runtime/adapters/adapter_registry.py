"""E10.2 Adapter Registry — Factory for platform-specific adapters.

Decouples ExecutionEngine from concrete adapter implementations.
At runtime, adapters are registered and retrieved by platform name.

Usage:
    registry = AdapterRegistry()
    registry.register("facebook", FacebookAdsAdapter())
    adapter = registry.get("facebook")
"""

from __future__ import annotations

from market_ops.execution_runtime.adapters.base_adapter import PlatformAdapter
from market_ops.execution_runtime.adapters.exceptions import AdapterNotFoundError


class AdapterRegistry:
    """Registry for platform adapter instances.

    Thread-safe for single-threaded use (Python GIL).
    Multi-threaded safety not required for E10.2 Phase 1.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, platform: str, adapter: PlatformAdapter) -> None:
        """Register an adapter for a platform.

        Args:
            platform: Platform identifier (e.g., 'facebook', 'google_ads').
            adapter: Concrete PlatformAdapter instance.
        """
        self._adapters[platform.lower()] = adapter

    def get(self, platform: str) -> PlatformAdapter:
        """Retrieve an adapter by platform name.

        Args:
            platform: Platform identifier.

        Returns:
            Registered PlatformAdapter instance.

        Raises:
            AdapterNotFoundError: If no adapter is registered for the platform.
        """
        adapter = self._adapters.get(platform.lower())
        if adapter is None:
            raise AdapterNotFoundError(platform)
        return adapter

    def unregister(self, platform: str) -> None:
        """Remove a registered adapter.

        Args:
            platform: Platform identifier to remove.
        """
        self._adapters.pop(platform.lower(), None)

    def list_platforms(self) -> list[str]:
        """Return all registered platform identifiers."""
        return list(self._adapters.keys())

    def has_adapter(self, platform: str) -> bool:
        """Check if an adapter is registered for a platform."""
        return platform.lower() in self._adapters

    @property
    def count(self) -> int:
        """Number of registered adapters."""
        return len(self._adapters)
