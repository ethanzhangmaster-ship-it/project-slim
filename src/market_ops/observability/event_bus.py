"""Phase 2.2A Final: Event Bus — priority, context, replay, middleware.

Supports:
  - publish(event)          — synchronous, ordered by observer priority
  - publish_async(event)    — fire-and-forget (thread pool)
  - bus.use(middleware)     — middleware chain with PublishContext
  - bus.replay(file_path)   — replay events from append-only log

Observers are registered with priority (higher = earlier execution).
PublishContext carries TraceID, CorrelationID for distributed tracing.
"""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Type

# Subscriber: (event) -> None
Subscriber = Callable[[Any], None]

# Middleware: (event, context, next_handler) -> None
Middleware = Callable[[Any, "PublishContext", Callable[[], None]], None]


# ═══════════════════════════════════════════════════════════
# Publish Context
# ═══════════════════════════════════════════════════════════

@dataclass
class PublishContext:
    """Carries trace context through the middleware + observer chain."""
    trace_id: str = field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    correlation_id: str = ""
    request_id: str = ""
    span_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(cls, correlation_id: str = "", request_id: str = "") -> "PublishContext":
        return cls(correlation_id=correlation_id, request_id=request_id,
                   span_id=f"span_{uuid.uuid4().hex[:8]}")


# ═══════════════════════════════════════════════════════════
# Event Bus
# ═══════════════════════════════════════════════════════════

class EventBus:
    """Thread-safe event bus with priority, context, middleware, replay."""

    def __init__(
        self,
        max_workers: int = 4,
        replay_log: str | Path | None = None,
    ) -> None:
        # (priority, callback) — sorted by priority desc on delivery
        self._subscribers: dict[Type[Any], list[tuple[int, Subscriber]]] = {}
        self._middleware: list[Middleware] = []
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="evtbus")
        self._replay_log = Path(replay_log) if replay_log else None

    # ── Middleware ──

    def use(self, middleware: Middleware) -> EventBus:
        """Register a middleware. Returns self for chaining."""
        with self._lock:
            self._middleware.append(middleware)
        return self

    # ── Subscribe ──

    def subscribe(self, event_type: Type[Any], callback: Subscriber,
                  priority: int = 100) -> None:
        """Register a callback with priority (higher = earlier execution)."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append((priority, callback))
            # Keep sorted by priority descending
            self._subscribers[event_type].sort(key=lambda x: x[0], reverse=True)

    def unsubscribe(self, event_type: Type[Any], callback: Subscriber) -> None:
        """Remove a previously registered callback."""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    (p, cb) for p, cb in self._subscribers[event_type] if cb != callback
                ]

    # ── Publish (sync) ──

    def publish(self, event: Any, correlation_id: str = "") -> None:
        """Publish synchronously through middleware → observers (priority order)."""
        event_type = type(event)
        ctx = PublishContext.create(correlation_id=correlation_id)

        with self._lock:
            entries = list(self._subscribers.get(event_type, []))
            middlewares = list(self._middleware)

        def _deliver():
            for _priority, cb in entries:
                try:
                    cb(event)
                except Exception as e:
                    print(f"[EventBus] Observer error for {event_type.__name__}: {e}")

        # Run through middleware chain
        if middlewares:
            self._run_middleware(event, ctx, middlewares, _deliver)
        else:
            _deliver()

        # Append to replay log
        self._append_replay(event)

    # ── Publish (async) ──

    def publish_async(self, event: Any, correlation_id: str = "") -> None:
        """Fire-and-forget async publish."""
        self._executor.submit(self._publish_async_safe, event, correlation_id)

    def _publish_async_safe(self, event: Any, correlation_id: str) -> None:
        try:
            self.publish(event, correlation_id=correlation_id)
        except Exception as e:
            print(f"[EventBus] Async publish error: {e}")

    # ── Middleware runner ──

    def _run_middleware(self, event: Any, ctx: PublishContext,
                        middlewares: list[Middleware],
                        final_handler: Callable[[], None]) -> None:
        """Execute middleware chain, then final handler."""
        if not middlewares:
            final_handler()
            return

        def _next(idx: int = 0):
            if idx < len(middlewares):
                middlewares[idx](event, ctx, lambda: _next(idx + 1))
            else:
                final_handler()

        _next(0)

    # ── Replay ──

    def _append_replay(self, event: Any) -> None:
        """Append event to replay log (JSON lines format)."""
        if self._replay_log is None:
            return
        try:
            d = event.to_dict() if hasattr(event, "to_dict") else {"event_type": type(event).__name__}
            with open(self._replay_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[EventBus] Replay log error: {e}")

    def replay(self, file_path: str | Path | None = None) -> int:
        """Replay events from log file. Returns count of replayed events."""
        path = Path(file_path) if file_path else self._replay_log
        if path is None or not path.exists():
            return 0

        count = 0
        from .events import ALL_EVENTS
        event_map = {e.__name__: e for e in ALL_EVENTS}

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event_type_name = data.get("event_type", "")
                    event_cls = event_map.get(event_type_name)
                    if event_cls:
                        # Reconstruct event (best-effort, only BaseEvent fields)
                        kwargs = {k: v for k, v in data.items()
                                  if k in event_cls.__dataclass_fields__}
                        event = event_cls(**kwargs)
                        self.publish(event)
                        count += 1
                except Exception as e:
                    print(f"[EventBus] Replay error: {e}")

        return count

    # ── Query ──

    def subscriber_count(self, event_type: Type[Any] | None = None) -> int:
        with self._lock:
            if event_type is not None:
                return len(self._subscribers.get(event_type, []))
            return sum(len(v) for v in self._subscribers.values())

    def middleware_count(self) -> int:
        with self._lock:
            return len(self._middleware)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)


# ═══════════════════════════════════════════════════════════
# Built-in Middleware
# ═══════════════════════════════════════════════════════════

class LoggerMiddleware:
    """Logs every event to console with trace context."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

    def __call__(self, event: Any, ctx: PublishContext,
                 next_handler: Callable[[], None]) -> None:
        if self.verbose:
            print(f"[EventBus] {event.event_type} id={event.event_id} "
                  f"trace={ctx.trace_id}")
        next_handler()


class MetricsMiddleware:
    """Tracks event counts per type."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def __call__(self, event: Any, ctx: PublishContext,
                 next_handler: Callable[[], None]) -> None:
        with self._lock:
            self._counts[event.event_type] = self._counts.get(event.event_type, 0) + 1
        next_handler()

    def get_counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)