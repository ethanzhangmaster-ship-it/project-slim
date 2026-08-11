"""Phase 2.2A: Snapshot Observer — periodically snapshots core state.

Subscribes to:
  - PipelineStarted → snapshot initial state
  - TaskFinished     → snapshot success count
  - TaskFailed       → snapshot failure count

No polling needed — snapshots are event-driven.
"""

from __future__ import annotations

from ..event_bus import EventBus
from ..events import TaskFinished, TaskFailed, PipelineStarted, PipelineFinished
from ..observability_store import ObservabilityStore


class SnapshotObserver:
    """Event-driven state snapshots for trend analysis."""

    def __init__(self, core_store, obs_store: ObservabilityStore) -> None:
        self._core = core_store
        self._obs = obs_store

    def _subscribe(self, bus: EventBus) -> None:
        bus.subscribe(TaskFinished, self._on_task_finished)
        bus.subscribe(TaskFailed, self._on_task_failed)
        bus.subscribe(PipelineStarted, self._on_pipeline_started)
        bus.subscribe(PipelineFinished, self._on_pipeline_finished)

    def _on_task_finished(self, event: TaskFinished) -> None:
        self._obs.record_snapshot("image_generated", 1)

    def _on_task_failed(self, event: TaskFailed) -> None:
        self._obs.record_snapshot("image_failed", 1)

    def _on_pipeline_started(self, event: PipelineStarted) -> None:
        self._obs.record_snapshot("pipeline_started", 1, f"batch={event.batch_id}")

    def _on_pipeline_finished(self, event: PipelineFinished) -> None:
        self._obs.record_snapshot("pipeline_finished", 1, f"batch={event.batch_id}")
        self._obs.record_snapshot("pipeline_duration", event.duration_seconds)

    def snapshot_full(self) -> None:
        """Take a full snapshot of current core state."""
        core = self._core.get_stats()
        self._obs.snapshot_current_state(core)