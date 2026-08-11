"""Phase 2.2A Final: Domain Events — BaseEvent with version + frozen.

All events are immutable (frozen=True):
  - Cannot be modified after creation
  - Safe for concurrent observers
  - Supports event versioning for forward compatibility

Unified BaseEvent fields:
  - event_id, timestamp, event_type, version (common to all events)
  - Easy serialization, logging, replay, auditing
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"evt_{uuid.uuid4().hex[:12]}"


# ═══════════════════════════════════════════════════════════
# Base Event
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BaseEvent:
    """All domain events inherit from this. Immutable (frozen)."""
    event_id: str = field(default_factory=_new_id)
    timestamp: str = field(default_factory=_now)
    event_type: str = ""
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.event_type:
            object.__setattr__(self, "event_type", self.__class__.__name__)

    def to_dict(self) -> dict:
        """Serialize to dict for logging/replay. Includes all fields."""
        import dataclasses
        return dataclasses.asdict(self)


# ═══════════════════════════════════════════════════════════
# Worker Events
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WorkerRegistered(BaseEvent):
    """Worker has been created and registered."""
    worker_id: str = ""


@dataclass(frozen=True)
class WorkerHeartbeat(BaseEvent):
    """Periodic heartbeat from a worker (every ~10s)."""
    worker_id: str = ""
    status: str = ""  # "IDLE" | "RUNNING"
    current_task: str = ""
    last_error: str = ""


@dataclass(frozen=True)
class WorkerOffline(BaseEvent):
    """Worker detected as offline (no heartbeat > 30s)."""
    worker_id: str = ""
    last_heartbeat: str = ""


# ═══════════════════════════════════════════════════════════
# Task Events
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TaskStarted(BaseEvent):
    """Worker has started processing a task."""
    task_id: str = ""
    worker_id: str = ""
    creative_id: str = ""


@dataclass(frozen=True)
class TaskFinished(BaseEvent):
    """Task completed successfully."""
    task_id: str = ""
    worker_id: str = ""
    creative_id: str = ""
    generation_time: float = 0.0
    cost: float = 0.0
    image_path: str = ""


@dataclass(frozen=True)
class TaskFailed(BaseEvent):
    """Task failed (will retry or permanently fail)."""
    task_id: str = ""
    worker_id: str = ""
    creative_id: str = ""
    error: str = ""
    final_status: str = ""  # "RETRY" | "FAILED"


# ═══════════════════════════════════════════════════════════
# System Events
# ═══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PipelineStarted(BaseEvent):
    """A batch generation pipeline has started."""
    batch_id: str = ""
    total_tasks: int = 0


@dataclass(frozen=True)
class PipelineFinished(BaseEvent):
    """A batch generation pipeline has completed."""
    batch_id: str = ""
    total_succeeded: int = 0
    total_failed: int = 0
    total_cost: float = 0.0
    duration_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════

ALL_EVENTS = [
    WorkerRegistered,
    WorkerHeartbeat,
    WorkerOffline,
    TaskStarted,
    TaskFinished,
    TaskFailed,
    PipelineStarted,
    PipelineFinished,
]