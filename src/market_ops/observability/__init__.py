"""Phase 2.2A Final: Production Observability — Domain Event Architecture.

Worker 只负责 publish(Event)，Observer 通过 subscribe 监听。
完全解耦核心业务逻辑与可观测性。

Layers:
    events.py            — BaseEvent (frozen, versioned) + 8 event types
    event_bus.py         — sync/async publish, priority observers, PublishContext, replay log
    registry.py          — ObserverRegistry: declarative bootstrap
    observability_store.py — 独立 SQLite 存储（只读核心数据）
    snapshot_service.py  — 聚合器 + memory cache, Dashboard 唯一数据源
    dashboard.py         — 只读 SnapshotService.current

    observers/           — 单一职责
        worker_observer.py   — 心跳、离线检测
        latency_observer.py  — P50/P90/P95/P99
        queue_observer.py    — 队列深度、等待时间
        snapshot_observer.py — 事件驱动快照

Phase 2.2B: CostObserver, RetryObserver, AlertObserver, CSV/JSON export
Phase 2.2C: Prometheus, OpenTelemetry, Kafka, Webhook
"""

from .events import (
    BaseEvent,
    WorkerRegistered, WorkerHeartbeat, WorkerOffline,
    TaskStarted, TaskFinished, TaskFailed,
    PipelineStarted, PipelineFinished,
    ALL_EVENTS,
)
from .event_bus import EventBus, PublishContext, LoggerMiddleware, MetricsMiddleware
from .observability_store import ObservabilityStore
from .registry import ObserverRegistry
from .snapshot_service import SnapshotService
from .dashboard import GenerationDashboard
from .observers import (
    WorkerObserver, LatencyObserver, QueueObserver, SnapshotObserver,
)

# Backward compat aliases
WorkerMonitor = WorkerObserver
LatencyMonitor = LatencyObserver
QueueMetrics = QueueObserver

__all__ = [
    # Events
    "BaseEvent",
    "WorkerRegistered", "WorkerHeartbeat", "WorkerOffline",
    "TaskStarted", "TaskFinished", "TaskFailed",
    "PipelineStarted", "PipelineFinished",
    "ALL_EVENTS",
    # Bus
    "EventBus", "PublishContext", "LoggerMiddleware", "MetricsMiddleware",
    # Registry
    "ObserverRegistry",
    # Store
    "ObservabilityStore",
    # Service
    "SnapshotService",
    # Dashboard
    "GenerationDashboard",
    # Observers
    "WorkerObserver", "LatencyObserver", "QueueObserver", "SnapshotObserver",
    # Backward compat
    "WorkerMonitor", "LatencyMonitor", "QueueMetrics",
]