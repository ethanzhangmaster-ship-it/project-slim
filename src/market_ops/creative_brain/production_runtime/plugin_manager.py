"""V4.4 Plugin Manager — hot-swappable module registration.

Any module can be registered as a plugin:
  Reasoning V2, Validation V3, Retriever V4, etc.

Plugins support: register, load, unload, enable, disable, hot-swap.
"""

from __future__ import annotations

import time
from typing import Any, Callable


class PluginManager:
    """Plugin system for hot-swappable modules."""

    def __init__(self) -> None:
        self._plugins: dict[str, dict[str, Any]] = {}
        self._hooks: dict[str, list[Callable]] = {}  # hook_name → [handlers]
        self._load_order: list[str] = []  # plugin load order
        self._event_history: list[dict[str, Any]] = []

    def register(self, name: str, plugin_class: type | Callable,
                 version: str = "0.0.0",
                 dependencies: list[str] | None = None,
                 config: dict[str, Any] | None = None,
                 **metadata: Any) -> None:
        """Register a plugin.

        Args:
            name: Unique plugin name.
            plugin_class: Class or factory function to instantiate.
            version: Plugin version.
            dependencies: Plugin names this plugin depends on.
            config: Plugin configuration.
            **metadata: Additional metadata.
        """
        if name in self._plugins:
            self._log_event("re-register", name)

        self._plugins[name] = {
            "name": name,
            "plugin_class": plugin_class,
            "version": version,
            "dependencies": dependencies or [],
            "config": config or {},
            "metadata": metadata,
            "instance": None,
            "loaded": False,
            "enabled": True,
            "registered_at": time.time(),
            "loaded_at": 0.0,
        }
        self._log_event("register", name)

    def load(self, name: str) -> Any:
        """Load (instantiate) a plugin.

        Args:
            name: Plugin name.

        Returns:
            The plugin instance, or None if load failed.
        """
        plugin = self._plugins.get(name)
        if plugin is None:
            return None

        # Load dependencies first
        for dep in plugin["dependencies"]:
            if dep not in self._plugins:
                raise ValueError(f"Missing dependency '{dep}' for plugin '{name}'")
            if not self._plugins[dep]["loaded"]:
                self.load(dep)

        # Instantiate
        try:
            cls = plugin["plugin_class"]
            if callable(cls) and not isinstance(cls, type):
                instance = cls(**plugin["config"])
            else:
                instance = cls(**plugin["config"])
            plugin["instance"] = instance
            plugin["loaded"] = True
            plugin["loaded_at"] = time.time()
            self._load_order.append(name)
            self._log_event("load", name)
            return instance
        except Exception as e:
            self._log_event("load_failed", name, {"error": str(e)})
            raise

    def unload(self, name: str) -> bool:
        """Unload a plugin.

        Args:
            name: Plugin name.

        Returns:
            True if unloaded successfully.
        """
        plugin = self._plugins.get(name)
        if plugin is None:
            return False

        # Check if any loaded plugins depend on this one
        for pname, p in self._plugins.items():
            if p["loaded"] and name in p["dependencies"]:
                raise RuntimeError(f"Cannot unload '{name}': required by '{pname}'")

        plugin["instance"] = None
        plugin["loaded"] = False
        if name in self._load_order:
            self._load_order.remove(name)
        self._log_event("unload", name)
        return True

    def hot_swap(self, name: str, new_class: type | Callable,
                 new_version: str = "0.0.0",
                 new_config: dict[str, Any] | None = None) -> Any:
        """Hot-swap a plugin with a new version without downtime.

        Args:
            name: Plugin name to replace.
            new_class: New plugin class or factory.
            new_version: New version string.
            new_config: New configuration.

        Returns:
            The new plugin instance.
        """
        old_config = self._plugins[name]["config"] if name in self._plugins else {}

        # Unload old version
        if name in self._plugins and self._plugins[name]["loaded"]:
            self.unload(name)

        # Update registration
        self._plugins[name] = {
            "name": name,
            "plugin_class": new_class,
            "version": new_version,
            "dependencies": self._plugins.get(name, {}).get("dependencies", []),
            "config": new_config or old_config,
            "metadata": self._plugins.get(name, {}).get("metadata", {}),
            "instance": None,
            "loaded": False,
            "enabled": True,
            "registered_at": time.time(),
            "loaded_at": 0.0,
        }

        self._log_event("hot_swap", name, {"version": new_version})
        return self.load(name)

    def enable(self, name: str) -> bool:
        """Enable a plugin."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin["enabled"] = True
            self._log_event("enable", name)
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a plugin (unloads it)."""
        plugin = self._plugins.get(name)
        if plugin:
            plugin["enabled"] = False
            if plugin["loaded"]:
                self.unload(name)
            self._log_event("disable", name)
            return True
        return False

    def get_instance(self, name: str) -> Any | None:
        """Get the loaded instance of a plugin."""
        plugin = self._plugins.get(name)
        return plugin["instance"] if plugin else None

    def get_plugin(self, name: str) -> dict[str, Any] | None:
        """Get plugin metadata."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return None
        return {
            "name": plugin["name"],
            "version": plugin["version"],
            "loaded": plugin["loaded"],
            "enabled": plugin["enabled"],
            "dependencies": plugin["dependencies"],
            "registered_at": plugin["registered_at"],
        }

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all registered plugins."""
        return [self.get_plugin(p) for p in self._plugins]

    def list_loaded(self) -> list[str]:
        """List loaded plugin names in load order."""
        return [p for p in self._load_order if self._plugins[p]["loaded"]]

    def add_hook(self, hook_name: str, handler: Callable) -> None:
        """Register a hook handler.

        Args:
            hook_name: Hook event name.
            handler: Callable to invoke when hook fires.
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(handler)

    def remove_hook(self, hook_name: str, handler: Callable) -> bool:
        """Remove a hook handler."""
        if hook_name in self._hooks and handler in self._hooks[hook_name]:
            self._hooks[hook_name].remove(handler)
            return True
        return False

    def fire_hook(self, hook_name: str, *args: Any, **kwargs: Any) -> list[Any]:
        """Fire a hook, calling all registered handlers.

        Returns:
            List of handler return values.
        """
        results = []
        for handler in self._hooks.get(hook_name, []):
            try:
                results.append(handler(*args, **kwargs))
            except Exception:
                pass
        return results

    def get_hooks(self) -> list[str]:
        """Get all registered hook names."""
        return list(self._hooks.keys())

    def load_all(self) -> dict[str, Any]:
        """Load all enabled plugins in dependency order.

        Returns:
            {plugin_name: instance}
        """
        loaded = {}
        # Sort by dependency count
        enabled = [p for p in self._plugins.values() if p["enabled"]]
        enabled.sort(key=lambda p: len(p["dependencies"]))

        for plugin in enabled:
            if not plugin["loaded"]:
                try:
                    instance = self.load(plugin["name"])
                    loaded[plugin["name"]] = instance
                except Exception:
                    pass

        return loaded

    def get_event_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get plugin event history."""
        return self._event_history[-limit:]

    def _log_event(self, event: str, plugin_name: str,
                   extra: dict[str, Any] | None = None) -> None:
        """Log a plugin event."""
        self._event_history.append({
            "event": event,
            "plugin": plugin_name,
            "timestamp": time.time(),
            **(extra or {}),
        })