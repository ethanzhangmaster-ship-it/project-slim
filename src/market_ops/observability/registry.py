"""Phase 2.2A Final: Observer Registry — declarative observer wiring.

Usage:
    registry = ObserverRegistry(bus)
    registry.register(WorkerObserver(store=obs), priority=100)
    registry.register(LatencyObserver(core, obs), priority=80)
    registry.register(QueueObserver(store=core), priority=50)
    registry.bootstrap()  # Subscribes all registered observers

Manager only calls registry.bootstrap(). Adding a new observer = one line.
"""

from __future__ import annotations

from typing import Any, Protocol

from .event_bus import EventBus


# Observer protocol: must have a _subscribe(bus) method OR accept bus in __init__
class Subscribable(Protocol):
    def _subscribe(self, bus: EventBus) -> None: ...


class ObserverRegistry:
    """Declarative registry that wires observers to the EventBus."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._entries: list[tuple[int, Any]] = []  # (priority, observer)

    def register(self, observer: Any, priority: int = 100) -> ObserverRegistry:
        """Register an observer with priority. Returns self for chaining."""
        self._entries.append((priority, observer))
        return self

    def bootstrap(self) -> None:
        """Wire all registered observers to the EventBus (sorted by priority)."""
        self._entries.sort(key=lambda x: x[0], reverse=True)

        for _priority, observer in self._entries:
            if hasattr(observer, "_subscribe"):
                observer._subscribe(self._bus)
            elif hasattr(self._bus, "subscribe"):
                # Observers that accept bus in __init__ are already subscribed
                pass

        print(f"[ObserverRegistry] Bootstrapped {len(self._entries)} observers")

    @property
    def count(self) -> int:
        return len(self._entries)