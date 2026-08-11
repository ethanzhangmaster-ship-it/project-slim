"""V4.4 Production Runtime — schemas.

Production runtime data structures for task management, workflow,
scheduling, monitoring, and resource control.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ═══════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class WorkerType(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    IO = "io"


class WorkerStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"


class ResourceType(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    DISK = "disk"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DOWN = "down"


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    EVENT = "event"


class WorkflowState(str, Enum):
    """Workflow execution state machine."""
    IDLE = "idle"
    RUNNING = "running"
    WAIT_GPU = "wait_gpu"
    WAIT_IO = "wait_io"
    PAUSED = "paused"
    RETRYING = "retrying"
    ROLLING_BACK = "rolling_back"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OnErrorPolicy(str, Enum):
    """What to do when a task fails."""
    FAIL_WORKFLOW = "fail_workflow"   # Stop entire DAG
    SKIP_CONTINUE = "skip_continue"   # Skip failed task, continue DAG
    RETRY_THEN_SKIP = "retry_then_skip"  # Retry first, then skip
    RETRY_THEN_FAIL = "retry_then_fail"  # Retry first, then fail DAG


class ArtifactType(str, Enum):
    """AI artifact types."""
    CREATIVE_VIDEO = "creative_video"
    CREATIVE_IMAGE = "creative_image"
    PROMPT = "prompt"
    EMBEDDING = "embedding"
    MODEL_CHECKPOINT = "model_checkpoint"
    GENERATED_ASSET = "generated_asset"
    CONFIG = "config"
    REPORT = "report"


class ArtifactStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"
    DELETED = "deleted"


class SecretLevel(str, Enum):
    """Secret sensitivity levels."""
    LOW = "low"         # Non-sensitive config
    MEDIUM = "medium"   # API keys, tokens
    HIGH = "high"       # Credentials, private keys
    CRITICAL = "critical"  # Master keys, root tokens


# ═══════════════════════════════════════════════════
# Core Schemas
# ═══════════════════════════════════════════════════

@dataclass
class RuntimeTask:
    """A single task in the runtime system."""
    task_id: str = ""
    name: str = ""
    task_type: str = ""               # facebook_sync / reasoning / validation / etc.
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    worker_type: WorkerType = WorkerType.CPU
    dependencies: list[str] = field(default_factory=list)  # task_ids
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 1.0          # seconds
    timeout: float = 300.0            # seconds
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "type": self.task_type,
            "status": self.status.value,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "retry_count": self.retry_count,
            "error": self.error,
        }


@dataclass
class Worker:
    """A worker in the worker pool."""
    worker_id: str = ""
    worker_type: WorkerType = WorkerType.CPU
    status: WorkerStatus = WorkerStatus.IDLE
    current_task: RuntimeTask | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_runtime: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "type": self.worker_type.value,
            "status": self.status.value,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "cpu_usage": round(self.cpu_usage, 2),
            "memory_usage": round(self.memory_usage, 2),
        }


@dataclass
class ResourceState:
    """Current resource state."""
    resource_type: ResourceType = ResourceType.CPU
    total: float = 0.0
    used: float = 0.0
    available: float = 0.0
    usage_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.resource_type.value,
            "total": round(self.total, 2),
            "used": round(self.used, 2),
            "available": round(self.available, 2),
            "usage_pct": round(self.usage_pct * 100, 1),
        }


@dataclass
class HealthReport:
    """Health status for a service."""
    service_name: str = ""
    status: HealthStatus = HealthStatus.HEALTHY
    last_check: float = 0.0
    response_time: float = 0.0
    error_count: int = 0
    consecutive_failures: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service_name,
            "status": self.status.value,
            "response_time_ms": round(self.response_time * 1000, 1),
            "error_count": self.error_count,
            "consecutive_failures": self.consecutive_failures,
            "message": self.message,
        }


@dataclass
class RuntimeMetrics:
    """Collected runtime metrics."""
    timestamp: float = 0.0
    # Task metrics
    tasks_pending: int = 0
    tasks_running: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    # Performance
    avg_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    throughput: float = 0.0           # tasks/sec
    # Resources
    cpu_usage: float = 0.0
    gpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    # Queue
    queue_length: int = 0
    queue_wait_time: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "tasks": {
                "pending": self.tasks_pending,
                "running": self.tasks_running,
                "completed": self.tasks_completed,
                "failed": self.tasks_failed,
            },
            "performance": {
                "avg_latency_ms": round(self.avg_latency * 1000, 1),
                "p95_latency_ms": round(self.p95_latency * 1000, 1),
                "throughput": round(self.throughput, 2),
            },
            "resources": {
                "cpu": round(self.cpu_usage * 100, 1),
                "gpu": round(self.gpu_usage * 100, 1),
                "memory": round(self.memory_usage * 100, 1),
                "disk": round(self.disk_usage * 100, 1),
            },
            "queue": {
                "length": self.queue_length,
                "wait_time_ms": round(self.queue_wait_time * 1000, 1),
            },
        }


@dataclass
class Alert:
    """An alert generated by the alert manager."""
    alert_id: str = ""
    level: AlertLevel = AlertLevel.INFO
    service: str = ""
    message: str = ""
    timestamp: float = 0.0
    acknowledged: bool = False
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "service": self.service,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
        }


@dataclass
class Checkpoint:
    """A runtime checkpoint for recovery."""
    checkpoint_id: str = ""
    workflow_id: str = ""
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    task_states: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "created_at": self.created_at,
        }


@dataclass
class WorkflowNode:
    """A node in a workflow DAG."""
    task_name: str = ""
    task_type: str = ""
    dependencies: list[str] = field(default_factory=list)
    worker_type: WorkerType = WorkerType.CPU
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: float = 300.0
    max_retries: int = 3
    on_error: OnErrorPolicy = OnErrorPolicy.FAIL_WORKFLOW  # V4.4.1: error handling

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_name": self.task_name,
            "task_type": self.task_type,
            "dependencies": self.dependencies,
            "worker_type": self.worker_type.value,
            "on_error": self.on_error.value,
        }


@dataclass
class WorkflowStateData:
    """Current state of a workflow execution."""
    workflow_id: str = ""
    state: WorkflowState = WorkflowState.IDLE
    current_level: int = 0
    total_levels: int = 0
    completed_tasks: list[str] = field(default_factory=list)
    failed_tasks: list[str] = field(default_factory=list)
    skipped_tasks: list[str] = field(default_factory=list)
    started_at: float = 0.0
    updated_at: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def progress_pct(self) -> float:
        total = max(1, len(self.completed_tasks) + len(self.failed_tasks) + len(self.skipped_tasks))
        return len(self.completed_tasks) / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "state": self.state.value,
            "level": f"{self.current_level}/{self.total_levels}",
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "skipped": len(self.skipped_tasks),
            "progress_pct": round(self.progress_pct() * 100, 1),
        }


@dataclass
class RuntimeEvent:
    """An event in the event bus."""
    event_id: str = ""
    event_type: str = ""              # e.g., "knowledge_updated", "creative_uploaded"
    source: str = ""                   # Source service/module
    payload: Any = None
    timestamp: float = 0.0
    correlation_id: str = ""           # For tracing across events

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


@dataclass
class DistributedLock:
    """A distributed lock for preventing concurrent access."""
    lock_name: str = ""
    holder: str = ""                    # Who holds the lock
    acquired_at: float = 0.0
    expires_at: float = 0.0
    ttl: float = 60.0                   # Seconds
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        import time
        return time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "lock_name": self.lock_name,
            "holder": self.holder,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "is_expired": self.is_expired(),
        }


@dataclass
class Artifact:
    """An AI artifact with lifecycle management."""
    artifact_id: str = ""
    name: str = ""
    artifact_type: ArtifactType = ArtifactType.GENERATED_ASSET
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    version: str = "1.0.0"
    storage_path: str = ""              # Where it's stored
    size_bytes: int = 0
    checksum: str = ""                  # SHA256
    created_at: float = 0.0
    expires_at: float = 0.0             # 0 = never expires
    archived_at: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "type": self.artifact_type.value,
            "status": self.status.value,
            "version": self.version,
            "size_mb": round(self.size_bytes / 1024 / 1024, 2),
            "tags": self.tags,
        }


@dataclass
class Secret:
    """A managed secret/credential."""
    secret_id: str = ""
    key: str = ""                       # e.g., "FB_ACCESS_TOKEN"
    level: SecretLevel = SecretLevel.MEDIUM
    value_hash: str = ""                # SHA256 of value (never store raw)
    rotated_at: float = 0.0
    expires_at: float = 0.0             # 0 = never expires
    rotation_days: int = 90             # Auto-rotate every N days
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def needs_rotation(self) -> bool:
        import time
        if self.rotation_days <= 0 or self.expires_at <= 0:
            return False
        return time.time() > self.expires_at - (self.rotation_days * 86400 / 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "secret_id": self.secret_id,
            "key": self.key,
            "level": self.level.value,
            "rotated_at": self.rotated_at,
            "needs_rotation": self.needs_rotation(),
        }


@dataclass
class WorkflowDAG:
    """A complete workflow DAG."""
    workflow_id: str = ""
    name: str = ""
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (from, to)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
        }


@dataclass
class RuntimeReport:
    """Complete runtime execution report."""
    workflow_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    retries: int = 0
    alerts: list[Alert] = field(default_factory=list)
    metrics: RuntimeMetrics | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "duration_sec": round(self.completed_at - self.started_at, 1),
            "tasks": {
                "total": self.total_tasks,
                "completed": self.completed,
                "failed": self.failed,
                "skipped": self.skipped,
                "retries": self.retries,
            },
            "alerts": len(self.alerts),
            "errors": self.errors[:10],
        }