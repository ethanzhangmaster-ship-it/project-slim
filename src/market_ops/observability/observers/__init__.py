"""Phase 2.2A: Observers — single-responsibility event handlers.

Each observer subscribes to exactly one event type and does one thing:
  - WorkerObserver    — heartbeat tracking, offline detection
  - LatencyObserver   — records generation latency percentiles
  - QueueObserver     — polls queue depth (read-only, no event needed)
  - SnapshotObserver  — periodically snapshots core state

Phase 2.2B will add:
  - CostObserver      — tracks cost per task/blueprint/prompt
  - RetryObserver     — analyzes retry patterns
  - AlertObserver     — threshold-based alerting

All observers are read-only on core production data.
"""

from .worker_observer import WorkerObserver
from .latency_observer import LatencyObserver
from .queue_observer import QueueObserver
from .snapshot_observer import SnapshotObserver

__all__ = [
    "WorkerObserver",
    "LatencyObserver",
    "QueueObserver",
    "SnapshotObserver",
]