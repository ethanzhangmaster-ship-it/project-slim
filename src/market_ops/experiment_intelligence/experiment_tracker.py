"""E9.9 Module 5: Experiment Tracker.

Manages experiment lifecycle with state machine:
  CREATED → RUNNING → PAUSED → RUNNING (resume)
                   → WINNER / FAILED / COMPLETED
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_ops.experiment_intelligence.schemas import (
    ExperimentPlan, ExperimentStatus, PerformanceSnapshot,
)


class ExperimentTracker:
    """Tracks experiment lifecycle and performance.

    Usage:
        tracker = ExperimentTracker()
        for plan in plans:
            tracker.start(plan)
        ...
        tracker.complete(plan, result)
    """

    def __init__(self) -> None:
        self._experiments: dict[str, ExperimentPlan] = {}
        self._history: dict[str, list[PerformanceSnapshot]] = {}
        self._status_log: dict[str, list[tuple[str, str]]] = {}  # exp_id → [(status, timestamp)]

    # ── State Transitions ──────────────────────────────────

    def start(self, plan: ExperimentPlan) -> ExperimentPlan:
        """Start an experiment (CREATED → RUNNING)."""
        if plan.experiment_id not in self._experiments:
            self._experiments[plan.experiment_id] = plan
            self._history[plan.experiment_id] = []
            self._status_log[plan.experiment_id] = []

        plan.status = ExperimentStatus.RUNNING.value
        self._log_status(plan.experiment_id, ExperimentStatus.RUNNING.value)
        return plan

    def pause(self, experiment_id: str) -> ExperimentPlan | None:
        """Pause an experiment (RUNNING → PAUSED)."""
        plan = self._experiments.get(experiment_id)
        if plan and plan.status == ExperimentStatus.RUNNING.value:
            plan.status = ExperimentStatus.PAUSED.value
            self._log_status(experiment_id, ExperimentStatus.PAUSED.value)
        return plan

    def resume(self, experiment_id: str) -> ExperimentPlan | None:
        """Resume a paused experiment (PAUSED → RUNNING)."""
        plan = self._experiments.get(experiment_id)
        if plan and plan.status == ExperimentStatus.PAUSED.value:
            plan.status = ExperimentStatus.RUNNING.value
            self._log_status(experiment_id, ExperimentStatus.RUNNING.value)
        return plan

    def mark_winner(self, experiment_id: str) -> ExperimentPlan | None:
        """Mark experiment as winner (RUNNING → WINNER)."""
        plan = self._experiments.get(experiment_id)
        if plan:
            plan.status = ExperimentStatus.WINNER.value
            self._log_status(experiment_id, ExperimentStatus.WINNER.value)
        return plan

    def mark_failed(self, experiment_id: str) -> ExperimentPlan | None:
        """Mark experiment as failed (RUNNING → FAILED)."""
        plan = self._experiments.get(experiment_id)
        if plan:
            plan.status = ExperimentStatus.FAILED.value
            self._log_status(experiment_id, ExperimentStatus.FAILED.value)
        return plan

    def complete(self, experiment_id: str) -> ExperimentPlan | None:
        """Mark experiment as completed (RUNNING → COMPLETED)."""
        plan = self._experiments.get(experiment_id)
        if plan:
            plan.status = ExperimentStatus.COMPLETED.value
            self._log_status(experiment_id, ExperimentStatus.COMPLETED.value)
        return plan

    # ── Performance Recording ──────────────────────────────

    def record_performance(
        self, experiment_id: str, snapshot: PerformanceSnapshot
    ) -> None:
        """Record a performance snapshot for an experiment."""
        if experiment_id not in self._history:
            self._history[experiment_id] = []
        self._history[experiment_id].append(snapshot)

    def get_performance_history(
        self, experiment_id: str
    ) -> list[PerformanceSnapshot]:
        """Get all performance snapshots for an experiment."""
        return self._history.get(experiment_id, [])

    def get_latest_performance(
        self, experiment_id: str
    ) -> PerformanceSnapshot | None:
        """Get the most recent performance snapshot."""
        history = self._history.get(experiment_id, [])
        return history[-1] if history else None

    # ── Queries ────────────────────────────────────────────

    def get_status(self, experiment_id: str) -> str:
        """Get current status of an experiment."""
        plan = self._experiments.get(experiment_id)
        return plan.status if plan else "UNKNOWN"

    def get_plan(self, experiment_id: str) -> ExperimentPlan | None:
        """Get experiment plan by ID."""
        return self._experiments.get(experiment_id)

    def get_active(self) -> list[ExperimentPlan]:
        """Get all currently active (RUNNING) experiments."""
        return [
            p for p in self._experiments.values()
            if p.status == ExperimentStatus.RUNNING.value
        ]

    def get_all(self) -> list[ExperimentPlan]:
        """Get all tracked experiments."""
        return list(self._experiments.values())

    # ── Internal ───────────────────────────────────────────

    def _log_status(self, experiment_id: str, status: str) -> None:
        """Log a status change."""
        if experiment_id not in self._status_log:
            self._status_log[experiment_id] = []
        self._status_log[experiment_id].append(
            (status, datetime.now(timezone.utc).isoformat())
        )

    # ── Summary ────────────────────────────────────────────

    def get_tracking_summary(self) -> dict[str, Any]:
        """Get summary of all tracked experiments."""
        status_counts: dict[str, int] = {}
        for plan in self._experiments.values():
            status_counts[plan.status] = status_counts.get(plan.status, 0) + 1

        return {
            "total_experiments": len(self._experiments),
            "by_status": status_counts,
            "active": len(self.get_active()),
            "total_snapshots": sum(len(h) for h in self._history.values()),
        }