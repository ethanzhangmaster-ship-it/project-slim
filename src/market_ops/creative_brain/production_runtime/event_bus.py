"""V4.4.1 Event Bus — decoupled publish/subscribe system.

Modules no longer call each other directly. Instead:
  Knowledge Updated → publish event → Validation → Lifecycle → Policy → Generation

Supports: publish, subscribe, unsubscribe, wildcard subscriptions.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .schemas import RuntimeEvent


class EventBus:
    """Decoupled publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[RuntimeEvent], None]]] = {}
        self._event_history: list[RuntimeEvent] = []
        self._max_history: int = 1000
        self._correlation_counter: int = 0

    def subscribe(self, event_type: str,
                  handler: Callable[[RuntimeEvent], None]) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Event type to listen for. Supports '*' for all events.
            handler: Callable(RuntimeEvent) → None.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str,
                    handler: Callable[[RuntimeEvent], None]) -> bool:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]
            return True
        return False

    def publish(self, event_type: str, source: str = "",
                payload: Any = None, correlation_id: str = "") -> RuntimeEvent:
        """Publish an event to all subscribers.

        Args:
            event_type: Event type (e.g., 'knowledge_updated').
            source: Source module/service name.
            payload: Event data.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            The published RuntimeEvent.
        """
        event = RuntimeEvent(
            event_id=str(uuid.uuid4())[:8],
            event_type=event_type,
            source=source,
            payload=payload,
            timestamp=time.time(),
            correlation_id=correlation_id or self._new_correlation_id(),
        )

        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Notify exact subscribers
        handlers = self._subscribers.get(event_type, [])
        # Notify wildcard subscribers
        handlers = handlers + self._subscribers.get("*", [])

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                pass  # Don't let one subscriber failure block others

        return event

    def publish_chain(self, events: list[tuple[str, str, Any]]) -> str:
        """Publish a chain of events with shared correlation ID.

        Args:
            events: List of (event_type, source, payload) tuples.

        Returns:
            Correlation ID linking all events.
        """
        cid = self._new_correlation_id()
        for event_type, source, payload in events:
            self.publish(event_type, source, payload, correlation_id=cid)
        return cid

    def get_subscribers(self, event_type: str) -> int:
        """Get subscriber count for an event type."""
        return len(self._subscribers.get(event_type, []))

    def get_subscribed_types(self) -> list[str]:
        """Get all event types with subscribers."""
        return list(self._subscribers.keys())

    def get_history(self, event_type: str | None = None,
                    limit: int = 50) -> list[RuntimeEvent]:
        """Get recent event history."""
        if event_type:
            return [e for e in self._event_history if e.event_type == event_type][-limit:]
        return self._event_history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        type_counts: dict[str, int] = {}
        for e in self._event_history:
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1

        return {
            "total_events": len(self._event_history),
            "subscriber_count": sum(len(v) for v in self._subscribers.values()),
            "subscribed_types": len(self._subscribers),
            "events_by_type": dict(sorted(type_counts.items(), key=lambda x: -x[1])[:10]),
        }

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    def clear_subscribers(self) -> None:
        """Clear all subscribers."""
        self._subscribers.clear()

    def _new_correlation_id(self) -> str:
        """Generate a new correlation ID."""
        self._correlation_counter += 1
        return f"corr_{self._correlation_counter}_{int(time.time())}"