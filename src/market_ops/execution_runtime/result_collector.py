"""E10.1 Result Collector — Execution result standardization and history.

Transforms raw ExecutionResult into structured ExecutionRecord
and PerformanceSnapshot for downstream Feedback Loop.

No real platform API calls. No modification to ExecutionEngine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionResult,
    ExecutionRecord,
    PerformanceSnapshot,
    CollectionEventType,
    ExecutionStatus,
    ActionType,
)
from market_ops.execution_runtime.performance_tracker import PerformanceTracker


class ResultCollector:
    """Collects and standardizes execution results.

    Usage:
        collector = ResultCollector()
        record = collector.collect(result)
        snapshot = collector.snapshot(record)
        history = collector.get_history(task_id)
    """

    def __init__(self, tracker: PerformanceTracker | None = None) -> None:
        self.tracker = tracker or PerformanceTracker()
        self._records: dict[str, ExecutionRecord] = {}
        self._snapshots: dict[str, PerformanceSnapshot] = {}
        self._events: list[dict[str, Any]] = []

    def collect(self, result: ExecutionResult) -> ExecutionRecord:
        """Normalize an ExecutionResult into an ExecutionRecord.

        Args:
            result: Raw execution result from ExecutionEngine.

        Returns:
            Structured ExecutionRecord with full lifecycle metadata.
        """
        self._log_event(CollectionEventType.RESULT_COLLECTED.value, result.task_id)

        action_type = result.metrics.get("action_type", ActionType.WATCH.value)
        target_platform = result.metrics.get("target_platform", "")

        # Derive approval status from result status
        approval_status = "APPROVED"
        if result.status == ExecutionStatus.PENDING_APPROVAL.value:
            approval_status = "PENDING"
        elif result.status == ExecutionStatus.FAILED.value:
            approval_status = "REJECTED"

        # Compute duration if both times are ISO strings
        duration_ms = 0
        start_time = result.metrics.get("start_time", "")
        end_time = result.completed_at
        if start_time and end_time:
            try:
                t0 = datetime.fromisoformat(start_time)
                t1 = datetime.fromisoformat(end_time)
                duration_ms = int((t1 - t0).total_seconds() * 1000)
            except ValueError:
                duration_ms = 0

        # Preserve actual_change inside platform_response for downstream snapshot()
        platform_response = dict(result.platform_response)
        platform_response["actual_change"] = result.actual_change

        record = ExecutionRecord(
            task_id=result.task_id,
            action_type=action_type,
            target_platform=target_platform,
            start_time=start_time or result.completed_at,
            end_time=end_time,
            final_status=result.status,
            approval_status=approval_status,
            execution_duration_ms=duration_ms,
            platform_response=platform_response,
            error_message=result.error_message,
        )
        self._records[record.record_id] = record
        return record

    def snapshot(self, record: ExecutionRecord) -> PerformanceSnapshot:
        """Generate a PerformanceSnapshot from an ExecutionRecord.

        Args:
            record: The execution record to derive metrics from.

        Returns:
            PerformanceSnapshot with simulated business metrics.
        """
        self._log_event(CollectionEventType.PERFORMANCE_UPDATED.value, record.task_id)

        # Build a transient ExecutionResult for the tracker
        transient = ExecutionResult(
            task_id=record.task_id,
            status=record.final_status,
            actual_change=record.platform_response.get("actual_change", {"before": 0.0, "after": 0.0}),
            metrics={"action_type": record.action_type},
        )
        snap = self.tracker.snapshot(transient)
        self._snapshots[snap.snapshot_id] = snap
        return snap

    def get_history(self, task_id: str) -> list[ExecutionRecord]:
        """Get all execution records for a given task.

        Args:
            task_id: The task ID to query.

        Returns:
            List of ExecutionRecord, newest first.
        """
        records = [r for r in self._records.values() if r.task_id == task_id]
        return sorted(records, key=lambda r: r.start_time, reverse=True)

    def get_snapshots_for_task(self, task_id: str) -> list[PerformanceSnapshot]:
        """Get all performance snapshots for a given task.

        Args:
            task_id: The task ID to query.

        Returns:
            List of PerformanceSnapshot, newest first.
        """
        snaps = [s for s in self._snapshots.values() if s.task_id == task_id]
        return sorted(snaps, key=lambda s: s.recorded_at, reverse=True)

    @property
    def records(self) -> list[ExecutionRecord]:
        """All collected execution records."""
        return list(self._records.values())

    @property
    def snapshots(self) -> list[PerformanceSnapshot]:
        """All generated performance snapshots."""
        return list(self._snapshots.values())

    @property
    def events(self) -> list[dict[str, Any]]:
        """All collection events."""
        return list(self._events)

    def _log_event(self, event_type: str, task_id: str) -> None:
        """Record a collection event."""
        self._events.append({
            "event_type": event_type,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
