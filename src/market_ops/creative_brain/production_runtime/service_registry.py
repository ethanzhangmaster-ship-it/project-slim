"""V4.4 Service Registry — service registration and discovery.

Register any module: Reasoning V2, Validation V3, Retriever V4.
Services can be discovered by name, type, or tags.
"""

from __future__ import annotations

import time
from typing import Any, Callable


class ServiceRegistry:
    """Central service registry for discovery and lifecycle management."""

    def __init__(self) -> None:
        self._services: dict[str, dict[str, Any]] = {}
        self._by_type: dict[str, set[str]] = {}      # service_type → {service_name}
        self._by_tag: dict[str, set[str]] = {}        # tag → {service_name}
        self._event_history: list[dict[str, Any]] = []

    def register(self, name: str, service_type: str,
                 instance: Any = None,
                 health_check: Callable[[], bool] | None = None,
                 tags: list[str] | None = None,
                 **metadata: Any) -> None:
        """Register a service.

        Args:
            name: Unique service name.
            service_type: Service type (e.g., reasoning, validation, retriever).
            instance: The service instance (optional).
            health_check: Health check function (optional).
            tags: Tags for discovery (optional).
            **metadata: Additional metadata.
        """
        if name in self._services:
            self._log_event("update", name)

        self._services[name] = {
            "name": name,
            "type": service_type,
            "instance": instance,
            "health_check": health_check,
            "tags": tags or [],
            "metadata": metadata,
            "registered_at": time.time(),
            "status": "registered",
            "version": metadata.get("version", "0.0.0"),
        }

        # Index by type
        if service_type not in self._by_type:
            self._by_type[service_type] = set()
        self._by_type[service_type].add(name)

        # Index by tags
        for tag in (tags or []):
            if tag not in self._by_tag:
                self._by_tag[tag] = set()
            self._by_tag[tag].add(name)

        self._log_event("register", name)

    def unregister(self, name: str) -> bool:
        """Unregister a service.

        Returns:
            True if the service was found and removed.
        """
        svc = self._services.pop(name, None)
        if svc is None:
            return False

        # Remove from type index
        svc_type = svc["type"]
        if svc_type in self._by_type:
            self._by_type[svc_type].discard(name)
            if not self._by_type[svc_type]:
                del self._by_type[svc_type]

        # Remove from tag index
        for tag in svc["tags"]:
            if tag in self._by_tag:
                self._by_tag[tag].discard(name)
                if not self._by_tag[tag]:
                    del self._by_tag[tag]

        self._log_event("unregister", name)
        return True

    def get(self, name: str) -> dict[str, Any] | None:
        """Get a service by name."""
        return self._services.get(name)

    def get_instance(self, name: str) -> Any | None:
        """Get a service instance by name."""
        svc = self._services.get(name)
        return svc["instance"] if svc else None

    def find_by_type(self, service_type: str) -> list[dict[str, Any]]:
        """Find all services of a given type."""
        names = self._by_type.get(service_type, set())
        return [self._services[n] for n in names if n in self._services]

    def find_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Find all services with a given tag."""
        names = self._by_tag.get(tag, set())
        return [self._services[n] for n in names if n in self._services]

    def find_by_tags(self, tags: list[str]) -> list[dict[str, Any]]:
        """Find services matching ALL given tags."""
        if not tags:
            return []
        result_sets = [self._by_tag.get(t, set()) for t in tags]
        intersection = result_sets[0]
        for s in result_sets[1:]:
            intersection = intersection & s
        return [self._services[n] for n in intersection if n in self._services]

    def list_services(self) -> list[dict[str, Any]]:
        """List all registered services."""
        return [
            {
                "name": s["name"],
                "type": s["type"],
                "status": s["status"],
                "version": s["version"],
                "tags": s["tags"],
                "registered_at": s["registered_at"],
            }
            for s in self._services.values()
        ]

    def list_types(self) -> list[str]:
        """List all registered service types."""
        return list(self._by_type.keys())

    def list_tags(self) -> list[str]:
        """List all registered tags."""
        return list(self._by_tag.keys())

    def update_status(self, name: str, status: str) -> bool:
        """Update a service's status."""
        svc = self._services.get(name)
        if svc is None:
            return False
        svc["status"] = status
        self._log_event("status_change", name, {"status": status})
        return True

    def update_metadata(self, name: str, **metadata: Any) -> bool:
        """Update a service's metadata."""
        svc = self._services.get(name)
        if svc is None:
            return False
        svc["metadata"].update(metadata)
        return True

    def get_count(self) -> int:
        """Get total number of registered services."""
        return len(self._services)

    def get_counts_by_type(self) -> dict[str, int]:
        """Get service count by type."""
        return {t: len(names) for t, names in self._by_type.items()}

    def health_check(self, name: str) -> bool:
        """Run health check on a registered service.

        Returns:
            True if healthy, False otherwise.
        """
        svc = self._services.get(name)
        if svc is None:
            return False
        check_fn = svc.get("health_check")
        if check_fn is None:
            return True  # No health check = assume healthy
        try:
            return check_fn()
        except Exception:
            return False

    def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all registered services."""
        return {name: self.health_check(name) for name in self._services}

    def get_event_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get service event history."""
        return self._event_history[-limit:]

    def _log_event(self, event: str, service_name: str,
                   extra: dict[str, Any] | None = None) -> None:
        """Log a service event."""
        self._event_history.append({
            "event": event,
            "service": service_name,
            "timestamp": time.time(),
            **(extra or {}),
        })