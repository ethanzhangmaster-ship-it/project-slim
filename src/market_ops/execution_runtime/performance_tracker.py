"""E10.1 Performance Tracker — Mock performance metrics collection.

Generates PerformanceSnapshot from ExecutionResult.
Phase 4: purely simulated data, no real platform API calls.
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import (
    ExecutionResult,
    PerformanceSnapshot,
    ExecutionStatus,
    ActionType,
)


class PerformanceTracker:
    """Simulates performance metric collection post-execution.

    Maps execution outcomes to business metrics (impressions,
    clicks, spend, ROAS, etc.) using deterministic mock data
    based on action type.

    Usage:
        tracker = PerformanceTracker()
        snapshot = tracker.snapshot(result)
    """

    def snapshot(self, result: ExecutionResult) -> PerformanceSnapshot:
        """Generate a PerformanceSnapshot from an ExecutionResult.

        Args:
            result: The execution result to derive metrics from.

        Returns:
            PerformanceSnapshot with simulated business metrics.
        """
        if result.status == ExecutionStatus.FAILED.value:
            return self._failed_snapshot(result)

        # Derive action_type from result metrics if available
        action_type = result.metrics.get("action_type", ActionType.WATCH.value)

        if action_type == ActionType.SCALE.value:
            return self._scale_snapshot(result)
        if action_type == ActionType.KILL.value:
            return self._kill_snapshot(result)
        if action_type == ActionType.RETEST.value:
            return self._retest_snapshot(result)

        return self._watch_snapshot(result)

    def _scale_snapshot(self, result: ExecutionResult) -> PerformanceSnapshot:
        """Simulate metrics for a SCALE action."""
        budget_after = result.actual_change.get("after", 100.0)
        multiplier = budget_after / max(1.0, result.actual_change.get("before", 100.0))

        impressions = int(10000 * multiplier)
        clicks = int(impressions * 0.05)
        conversions = int(clicks * 0.10)
        spend = budget_after
        revenue = spend * 1.6

        return PerformanceSnapshot(
            task_id=result.task_id,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            spend=spend,
            revenue=revenue,
            roas=1.6,
            ctr=0.05,
            cvr=0.10,
            status="active",
        )

    def _kill_snapshot(self, result: ExecutionResult) -> PerformanceSnapshot:
        """Simulate metrics for a KILL action."""
        return PerformanceSnapshot(
            task_id=result.task_id,
            impressions=0,
            clicks=0,
            conversions=0,
            spend=0.0,
            revenue=0.0,
            roas=0.0,
            ctr=0.0,
            cvr=0.0,
            status="stopped",
        )

    def _watch_snapshot(self, result: ExecutionResult) -> PerformanceSnapshot:
        """Simulate metrics for a WATCH action."""
        return PerformanceSnapshot(
            task_id=result.task_id,
            impressions=5000,
            clicks=250,
            conversions=20,
            spend=50.0,
            revenue=80.0,
            roas=1.6,
            ctr=0.05,
            cvr=0.08,
            status="monitoring",
        )

    def _retest_snapshot(self, result: ExecutionResult) -> PerformanceSnapshot:
        """Simulate metrics for a RETEST action."""
        return PerformanceSnapshot(
            task_id=result.task_id,
            impressions=3000,
            clicks=120,
            conversions=10,
            spend=30.0,
            revenue=42.0,
            roas=1.4,
            ctr=0.04,
            cvr=0.083,
            status="testing",
        )

    def _failed_snapshot(self, result: ExecutionResult) -> PerformanceSnapshot:
        """Simulate metrics for a FAILED execution."""
        return PerformanceSnapshot(
            task_id=result.task_id,
            impressions=0,
            clicks=0,
            conversions=0,
            spend=0.0,
            revenue=0.0,
            roas=0.0,
            ctr=0.0,
            cvr=0.0,
            status="failed",
        )
