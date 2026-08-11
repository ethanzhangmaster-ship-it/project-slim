"""V4.4 Runtime API — unified interface for runtime operations.

Provides: Run, Pause, Resume, Cancel, Status.
Single entry point for all runtime control operations.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import (RuntimeReport, RuntimeTask, TaskStatus, TaskPriority,
                       WorkflowDAG, WorkflowNode, WorkerType, Alert, AlertLevel)
from .workflow_engine import WorkflowEngine
from .scheduler import Scheduler
from .task_queue import TaskQueue
from .resource_manager import ResourceManager
from .health_monitor import HealthMonitor
from .metrics_collector import MetricsCollector
from .alert_manager import AlertManager
from .config_manager import ConfigManager
from .logger import Logger


class RuntimeAPI:
    """Unified Runtime API — the single entry point for all runtime control."""

    def __init__(self, config: ConfigManager | None = None,
                 logger: Logger | None = None) -> None:
        self.config = config or ConfigManager().load_defaults()
        self.logger = logger or Logger("runtime_api")

        # Core subsystems
        self.task_queue = TaskQueue()
        self.resource_manager = ResourceManager(
            cpu_limit=self.config.get("resources.cpu_limit", 0.9),
            gpu_limit=self.config.get("resources.gpu_limit", 0.95),
            memory_limit=self.config.get("resources.memory_limit", 0.85),
            disk_limit=self.config.get("resources.disk_limit", 0.90),
        )
        self.health_monitor = HealthMonitor(
            check_interval=self.config.get("health.check_interval", 30.0),
            timeout=self.config.get("health.timeout", 5.0),
            max_consecutive_failures=self.config.get("health.max_consecutive_failures", 3),
        )
        self.metrics = MetricsCollector()
        self.alerts = AlertManager(
            enabled=self.config.get("alert.enabled", True),
        )
        self.scheduler = Scheduler(
            timezone=self.config.get("scheduler.timezone", "Asia/Shanghai"),
        )
        self.workflow_engine = WorkflowEngine(
            task_queue=self.task_queue,
            logger=self.logger,
        )

        # Runtime state
        self._running = False
        self._paused_workflows: set[str] = set()
        self._execution_history: list[dict[str, Any]] = []

    # ── Lifecycle ──────────────────────────────────────────

    def start(self) -> None:
        """Start the runtime."""
        self._running = True
        self.logger.info("Runtime started")
        self.alerts.info("runtime", "Runtime started")

    def stop(self) -> None:
        """Stop the runtime gracefully."""
        self._running = False
        self.logger.info("Runtime stopped")
        self.alerts.info("runtime", "Runtime stopped")

    def is_running(self) -> bool:
        """Check if runtime is running."""
        return self._running

    # ── Workflow Control ───────────────────────────────────

    def run_workflow(self, workflow_id: str,
                     state: dict[str, Any] | None = None) -> RuntimeReport:
        """Run a registered workflow.

        Args:
            workflow_id: Workflow ID to execute.
            state: Optional initial state for rollback.

        Returns:
            RuntimeReport with execution results.
        """
        self.logger.info(f"Running workflow: {workflow_id}")
        report = self.workflow_engine.execute(workflow_id, state)

        self._execution_history.append({
            "action": "run_workflow",
            "workflow_id": workflow_id,
            "completed": report.completed,
            "failed": report.failed,
            "timestamp": time.time(),
        })

        return report

    def run_daily_workflow(self) -> RuntimeReport:
        """Run the standard daily workflow.

        Daily Runtime:
          Facebook Sync → Knowledge Update → Retriever Refresh
          → Validation → Lifecycle → Policy → Creative Generation
          → Upload → Learning
        """
        daily_workflow = WorkflowDAG(
            workflow_id="daily_runtime",
            name="Daily Runtime",
            nodes=[
                WorkflowNode(task_name="facebook_sync", task_type="facebook_sync",
                             dependencies=[], worker_type=WorkerType.IO),
                WorkflowNode(task_name="knowledge_update", task_type="knowledge_update",
                             dependencies=["facebook_sync"], worker_type=WorkerType.CPU),
                WorkflowNode(task_name="retriever_refresh", task_type="retriever_refresh",
                             dependencies=["knowledge_update"], worker_type=WorkerType.GPU),
                WorkflowNode(task_name="validation", task_type="validation",
                             dependencies=["knowledge_update"], worker_type=WorkerType.CPU),
                WorkflowNode(task_name="lifecycle", task_type="lifecycle",
                             dependencies=["validation"], worker_type=WorkerType.CPU),
                WorkflowNode(task_name="policy", task_type="policy",
                             dependencies=["lifecycle"], worker_type=WorkerType.CPU),
                WorkflowNode(task_name="creative_generation", task_type="creative_generation",
                             dependencies=["policy"], worker_type=WorkerType.GPU),
                WorkflowNode(task_name="upload", task_type="upload",
                             dependencies=["creative_generation"], worker_type=WorkerType.IO),
                WorkflowNode(task_name="learning", task_type="learning",
                             dependencies=["upload"], worker_type=WorkerType.CPU),
            ],
        )

        self.workflow_engine.register_workflow(daily_workflow)
        return self.run_workflow("daily_runtime")

    def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow."""
        self._paused_workflows.add(workflow_id)
        self.logger.info(f"Workflow paused: {workflow_id}")
        return True

    def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow."""
        self._paused_workflows.discard(workflow_id)
        self.logger.info(f"Workflow resumed: {workflow_id}")
        return True

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow."""
        self._paused_workflows.discard(workflow_id)
        self.logger.info(f"Workflow cancelled: {workflow_id}")
        self._execution_history.append({
            "action": "cancel_workflow",
            "workflow_id": workflow_id,
            "timestamp": time.time(),
        })
        return True

    # ── Status ─────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive runtime status."""
        return {
            "runtime": {
                "running": self._running,
                "paused_workflows": list(self._paused_workflows),
            },
            "tasks": self.task_queue.get_status_counts(),
            "queue": {
                "length": self.task_queue.get_queue_length(),
                "pending": self.task_queue.get_pending_count(),
            },
            "resources": self.resource_manager.get_usage_summary(),
            "health": self.health_monitor.get_summary(),
            "metrics": self.metrics.get_summary(),
            "alerts": self.alerts.get_summary(),
            "scheduler": self.scheduler.get_summary(),
        }

    def get_health(self) -> dict[str, Any]:
        """Get health status of all services."""
        self.health_monitor.check_all()
        return self.health_monitor.get_summary()

    def get_metrics(self) -> dict[str, Any]:
        """Get current runtime metrics."""
        return self.metrics.get_summary()

    def get_alerts(self, active_only: bool = True) -> list[dict[str, Any]]:
        """Get alerts."""
        if active_only:
            return [a.to_dict() for a in self.alerts.get_active_alerts()]
        return [
            {"id": a.alert_id, "level": a.level.value, "service": a.service,
             "message": a.message, "acknowledged": a.acknowledged,
             "resolved": a.resolved}
            for a in self.alerts._alerts
        ]

    # ── Task Management ────────────────────────────────────

    def submit_task(self, name: str, task_type: str,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    worker_type: WorkerType = WorkerType.CPU,
                    dependencies: list[str] | None = None,
                    metadata: dict[str, Any] | None = None) -> str:
        """Submit a single task for execution.

        Returns:
            task_id
        """
        task = RuntimeTask(
            task_id=f"task_{task_type}_{int(time.time())}",
            name=name,
            task_type=task_type,
            priority=priority,
            worker_type=worker_type,
            dependencies=dependencies or [],
            created_at=time.time(),
            metadata=metadata or {},
        )
        self.task_queue.enqueue(task)
        self.logger.info(f"Task submitted: {name}", task_id=task.task_id)
        return task.task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get task status by ID."""
        task = self.task_queue.peek(task_id)
        if task:
            return task.to_dict()
        return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        task = self.task_queue.peek(task_id)
        if task:
            self.task_queue.cancel(task_id)
            return True
        return False

    # ── Scheduling ─────────────────────────────────────────

    def add_schedule(self, job_id: str, cron_expr: str,
                     workflow_id: str) -> None:
        """Schedule a workflow to run on a cron expression.

        Args:
            job_id: Unique job identifier.
            cron_expr: 5-field cron expression.
            workflow_id: Workflow to execute.
        """
        def _run():
            self.run_workflow(workflow_id)

        self.scheduler.add_cron(
            job_id=job_id,
            cron_expr=cron_expr,
            fn=_run,
            description=f"Schedule {workflow_id}",
        )

    # ── History ────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent execution history."""
        return self._execution_history[-limit:]

    def get_report(self) -> dict[str, Any]:
        """Get comprehensive runtime report."""
        return {
            "status": self.get_status(),
            "workflows": self.workflow_engine.list_workflows(),
            "schedules": self.scheduler.get_all_jobs(),
            "history": self.get_history(),
            "log_counts": self.logger.get_counts(),
        }