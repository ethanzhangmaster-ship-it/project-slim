"""
E15.2.3 — Config Provider Contract

Remote config operations (Firebase, local JSON, custom server).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ConfigProvider(ABC):
    """Provider contract for game configuration management.

    Supports: LocalConfigProvider, FirebaseRemoteConfigProvider, GameFactoryConfigServer.
    """

    name: str = "config"

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Read a config value."""
        ...

    @abstractmethod
    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Update a config value. Returns {success, key, old_value, new_value}."""
        ...

    @abstractmethod
    def rollback(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Rollback to a previous config version."""
        ...

    @abstractmethod
    def get_all(self, prefix: str = "") -> Dict[str, Any]:
        """Get all config values, optionally filtered by key prefix."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check config source connectivity."""
        ...


__all__ = ["ConfigProvider"]
