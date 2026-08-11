"""V4.4 Config Manager — unified configuration management.

Supports: YAML, JSON, ENV, defaults.
Single source of truth for all runtime config.
"""

from __future__ import annotations

import os
from typing import Any


class ConfigManager:
    """Unified configuration manager for production runtime."""

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._defaults = {
            "scheduler": {
                "timezone": "Asia/Shanghai",
                "facebook_sync": "0 6 * * *",
                "knowledge_update": "0 8 * * *",
                "validation": "0 9 * * *",
                "lifecycle": "0 9 * * *",
                "policy": "0 10 * * *",
                "creative_generation": "0 11 * * *",
                "upload": "0 12 * * *",
            },
            "retry": {
                "max_retries": 3,
                "base_delay": 1.0,
                "max_delay": 60.0,
                "backoff_multiplier": 2.0,
            },
            "worker_pool": {
                "cpu_workers": 4,
                "gpu_workers": 2,
                "io_workers": 8,
                "max_concurrent_tasks": 50,
            },
            "resources": {
                "cpu_limit": 0.9,
                "gpu_limit": 0.95,
                "memory_limit": 0.85,
                "disk_limit": 0.90,
            },
            "health": {
                "check_interval": 30.0,
                "timeout": 5.0,
                "max_consecutive_failures": 3,
            },
            "alert": {
                "enabled": True,
                "channels": ["log"],
                "min_level": "warning",
            },
            "cache": {
                "enabled": True,
                "ttl": 3600,
                "max_size": 10000,
            },
            "checkpoint": {
                "enabled": True,
                "interval": 300,
                "max_checkpoints": 10,
            },
            "runtime": {
                "max_runtime_seconds": 86400,
                "graceful_shutdown_timeout": 30,
            },
        }

    def load_defaults(self) -> ConfigManager:
        """Load default configuration."""
        self._config = self._defaults.copy()
        return self

    def load_dict(self, config: dict[str, Any]) -> ConfigManager:
        """Load configuration from a dict."""
        self._config = self._deep_merge(self._defaults.copy(), config)
        return self

    def load_env(self, prefix: str = "RUNTIME_") -> ConfigManager:
        """Load configuration from environment variables.

        Example: RUNTIME_RETRY_MAX_RETRIES=5 → config["retry"]["max_retries"] = 5
        """
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            # RUNTIME_RETRY_MAX_RETRIES → ["retry", "max_retries"]
            path = key[len(prefix):].lower().split("_")
            self._set_nested(path, self._coerce_value(value))
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-separated key."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value by dot-separated key."""
        keys = key.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def get_all(self) -> dict[str, Any]:
        """Get all configuration."""
        return self._config.copy()

    def get_section(self, section: str) -> dict[str, Any]:
        """Get a config section."""
        return self._config.get(section, {}).copy()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dicts."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _set_nested(self, path: list[str], value: Any) -> None:
        """Set a value in nested dict by path."""
        target = self._config
        for key in path[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        if path:
            target[path[-1]] = value

    def _coerce_value(self, value: str) -> Any:
        """Coerce string value to appropriate type."""
        # Try int
        try:
            return int(value)
        except ValueError:
            pass
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        # Try bool
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        return value