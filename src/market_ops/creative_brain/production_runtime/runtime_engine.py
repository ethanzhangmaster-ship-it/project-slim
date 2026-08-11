"""V4.4 Runtime Engine — unified production runtime orchestrator.

The central entry point that ties together all runtime subsystems (26 modules):
  Scheduler → Workflow Engine → Task Queue → Worker Pool
  → Resource Manager → Cache Manager → Retry/Rollback/Checkpoint
  → State Manager → Event Bus → Lock Manager → Rate Limiter
  → Health Monitor → Metrics → Alerts
  → Artifact Manager → Secret Manager

Daily Runtime:
  Facebook Sync → Knowledge Update → Retriever Refresh
  → Validation → Lifecycle → Policy → Creative Generation
  → Upload → Learning
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .config_manager import ConfigManager
from .logger import Logger
from .scheduler import Scheduler
from .task_queue import TaskQueue
from .worker_pool import WorkerPool
from .cache_manager import CacheManager
from .resource_manager import ResourceManager
from .dependency_graph import DependencyGraph
from .retry_manager import RetryManager
from .rollback_manager import RollbackManager
from .checkpoint_manager import CheckpointManager
from .state_manager import StateManager
from .event_bus import EventBus
from .lock_manager import LockManager
from .rate_limiter import RateLimiter
from .health_monitor import HealthMonitor
from .metrics_collector import MetricsCollector
from .alert_manager import AlertManager
from .service_registry import ServiceRegistry
from .plugin_manager import PluginManager
from .artifact_manager import ArtifactManager
from .secret_manager import SecretManager
from .workflow_engine import WorkflowEngine
from .runtime_api import RuntimeAPI
from .schemas import (RuntimeReport, RuntimeTask, TaskStatus, TaskPriority,
                       WorkflowDAG, WorkflowNode, WorkerType)


class RuntimeEngine:
    """Unified Production Runtime Engine — the 24/7 execution layer.

    This is NOT an AI enhancement layer. It makes the entire Creative Brain
    run as a stable production system.
    """

    def __init__(self, config: ConfigManager | None = None) -> None:
        # Configuration
        self.config = config or ConfigManager().load_defaults()

        # Logging
        self.logger = Logger("runtime_engine")

        # Core subsystems
        self.scheduler = Scheduler(
            timezone=self.config.get("scheduler.timezone", "Asia/Shanghai"),
        )
        self.task_queue = TaskQueue()
        self.worker_pool = WorkerPool(
            cpu_workers=self.config.get("worker_pool.cpu_workers", 4),
            gpu_workers=self.config.get("worker_pool.gpu_workers", 2),
            io_workers=self.config.get("worker_pool.io_workers", 8),
        )
        self.cache = CacheManager(
            enabled=self.config.get("cache.enabled", True),
            ttl=self.config.get("cache.ttl", 3600),
            max_size=self.config.get("cache.max_size", 10000),
        )
        self.resource_manager = ResourceManager(
            cpu_limit=self.config.get("resources.cpu_limit", 0.9),
            gpu_limit=self.config.get("resources.gpu_limit", 0.95),
            memory_limit=self.config.get("resources.memory_limit", 0.85),
            disk_limit=self.config.get("resources.disk_limit", 0.90),
        )
        self.retry_manager = RetryManager(
            max_retries=self.config.get("retry.max_retries", 3),
            base_delay=self.config.get("retry.base_delay", 1.0),
            max_delay=self.config.get("retry.max_delay", 60.0),
            backoff_multiplier=self.config.get("retry.backoff_multiplier", 2.0),
        )
        self.rollback_manager = RollbackManager()
        self.checkpoint_manager = CheckpointManager(
            enabled=self.config.get("checkpoint.enabled", True),
            max_checkpoints=self.config.get("checkpoint.max_checkpoints", 10),
        )

        # State & Events
        self.state_manager = StateManager()
        self.event_bus = EventBus()

        # Coordination
        self.lock_manager = LockManager()
        self.rate_limiter = RateLimiter()

        # Monitoring
        self.health_monitor = HealthMonitor(
            check_interval=self.config.get("health.check_interval", 30.0),
            timeout=self.config.get("health.timeout", 5.0),
            max_consecutive_failures=self.config.get("health.max_consecutive_failures", 3),
        )
        self.metrics = MetricsCollector()
        self.alerts = AlertManager(
            enabled=self.config.get("alert.enabled", True),
        )

        # Service management
        self.service_registry = ServiceRegistry()
        self.plugin_manager = PluginManager()

        # AI Asset Management
        self.artifact_manager = ArtifactManager()
        self.secret_manager = SecretManager()

        # Workflow
        self.workflow_engine = WorkflowEngine(
            task_queue=self.task_queue,
            retry_manager=self.retry_manager,
            rollback_manager=self.rollback_manager,
            checkpoint_manager=self.checkpoint_manager,
            logger=self.logger,
        )

        # Runtime API (unified entry point)
        self.api = RuntimeAPI(config=self.config, logger=self.logger)
        # Replace api's subsystems with our instances
        self.api.task_queue = self.task_queue
        self.api.resource_manager = self.resource_manager
        self.api.health_monitor = self.health_monitor
        self.api.metrics = self.metrics
        self.api.alerts = self.alerts
        self.api.scheduler = self.scheduler
        self.api.workflow_engine = self.workflow_engine

        # State
        self._running = False
        self._started_at: float = 0.0
        self._execution_count: int = 0

    # ── Lifecycle ──────────────────────────────────────────

    def start(self) -> None:
        """Start the production runtime engine."""
        self._running = True
        self._started_at = time.time()
        self.logger.info("Production Runtime Engine started")
        self.alerts.info("runtime", "Runtime Engine started")

    def stop(self) -> None:
        """Stop the production runtime engine gracefully."""
        self._running = False
        self.logger.info("Production Runtime Engine stopped",
                         uptime_sec=round(time.time() - self._started_at, 1))
        self.alerts.info("runtime", "Runtime Engine stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Daily Runtime ──────────────────────────────────────

    def run_daily(self) -> RuntimeReport:
        """Execute the standard daily production runtime.

        This is the main entry point for daily automated execution.
        """
        self.logger.info("Starting Daily Runtime")
        self._execution_count += 1

        # Register the daily workflow
        daily = WorkflowDAG(
            workflow_id="daily_runtime",
            name="Daily Production Runtime",
            nodes=[
                WorkflowNode(task_name="facebook_sync", task_type="facebook_sync",
                             dependencies=[], worker_type=WorkerType.IO,
                             priority=TaskPriority.CRITICAL),
                WorkflowNode(task_name="knowledge_update", task_type="knowledge_update",
                             dependencies=["facebook_sync"], worker_type=WorkerType.CPU,
                             priority=TaskPriority.HIGH),
                WorkflowNode(task_name="retriever_refresh", task_type="retriever_refresh",
                             dependencies=["knowledge_update"], worker_type=WorkerType.GPU,
                             priority=TaskPriority.HIGH),
                WorkflowNode(task_name="validation", task_type="validation",
                             dependencies=["knowledge_update"], worker_type=WorkerType.CPU,
                             priority=TaskPriority.HIGH),
                WorkflowNode(task_name="lifecycle", task_type="lifecycle",
                             dependencies=["validation"], worker_type=WorkerType.CPU,
                             priority=TaskPriority.NORMAL),
                WorkflowNode(task_name="policy", task_type="policy",
                             dependencies=["lifecycle"], worker_type=WorkerType.CPU,
                             priority=TaskPriority.NORMAL),
                WorkflowNode(task_name="creative_generation", task_type="creative_generation",
                             dependencies=["policy"], worker_type=WorkerType.GPU,
                             priority=TaskPriority.NORMAL),
                WorkflowNode(task_name="upload", task_type="upload",
                             dependencies=["creative_generation"], worker_type=WorkerType.IO,
                             priority=TaskPriority.NORMAL),
                WorkflowNode(task_name="learning", task_type="learning",
                             dependencies=["upload"], worker_type=WorkerType.CPU,
                             priority=TaskPriority.LOW),
            ],
        )
        self.workflow_engine.register_workflow(daily)

        # Take state snapshot before execution
        state = {"resources": self.resource_manager.get_usage_summary()}
        self.rollback_manager.snapshot("daily_runtime", state)

        # Execute
        report = self.workflow_engine.execute("daily_runtime", state)

        # Collect metrics
        self.metrics.collect(
            queue_length=self.task_queue.get_queue_length(),
        )

        self.logger.info(
            f"Daily Runtime complete: {report.completed}/{report.total_tasks} tasks",
            failed=report.failed,
            retries=report.retries,
        )

        return report

    # ── Scheduling ─────────────────────────────────────────

    def setup_daily_schedule(self) -> None:
        """Configure the standard daily schedule.

        06:00 Facebook Sync
        08:00 Knowledge Update
        09:00 Validation + Lifecycle
        10:00 Policy
        11:00 Creative Generation
        12:00 Upload
        """
        self.scheduler.add_cron(
            "facebook_sync", "0 6 * * *",
            lambda: self._run_single_task("facebook_sync", "facebook_sync"),
            "Facebook data sync",
        )
        self.scheduler.add_cron(
            "knowledge_update", "0 8 * * *",
            lambda: self._run_single_task("knowledge_update", "knowledge_update"),
            "Knowledge graph update",
        )
        self.scheduler.add_cron(
            "validation", "0 9 * * *",
            lambda: self._run_single_task("validation", "validation"),
            "Creative validation",
        )
        self.scheduler.add_cron(
            "lifecycle", "0 9 * * *",
            lambda: self._run_single_task("lifecycle", "lifecycle"),
            "Knowledge lifecycle",
        )
        self.scheduler.add_cron(
            "policy", "0 10 * * *",
            lambda: self._run_single_task("policy", "policy"),
            "Decision policy",
        )
        self.scheduler.add_cron(
            "creative_generation", "0 11 * * *",
            lambda: self._run_single_task("creative_generation", "creative_generation"),
            "Creative generation",
        )
        self.scheduler.add_cron(
            "upload", "0 12 * * *",
            lambda: self._run_single_task("upload", "upload"),
            "Upload to Facebook",
        )

    def _run_single_task(self, task_type: str, task_name: str) -> None:
        """Run a single task type through the workflow engine."""
        self.workflow_engine.execute_task_type(
            task_type=task_type,
            task_name=task_name,
        )

    # ── Registration ───────────────────────────────────────

    def register_executor(self, task_type: str,
                          executor: Callable[[RuntimeTask], tuple[bool, Any]]) -> None:
        """Register a task executor function.

        Args:
            task_type: Task type string.
            executor: Callable(task) → (success, result).
        """
        self.workflow_engine.register_executor(task_type, executor)

    def register_service(self, name: str, service_type: str,
                         instance: Any = None,
                         health_check: Callable[[], bool] | None = None,
                         tags: list[str] | None = None) -> None:
        """Register a service in the service registry."""
        self.service_registry.register(
            name=name,
            service_type=service_type,
            instance=instance,
            health_check=health_check,
            tags=tags,
        )

    def register_health_check(self, service_name: str,
                              check_fn: Callable[[], bool]) -> None:
        """Register a health check for a service."""
        self.health_monitor.register_service(service_name, check_fn)

    def register_plugin(self, name: str, plugin_class: type | Callable,
                        version: str = "0.0.0",
                        dependencies: list[str] | None = None,
                        config: dict[str, Any] | None = None) -> None:
        """Register a plugin."""
        self.plugin_manager.register(
            name=name,
            plugin_class=plugin_class,
            version=version,
            dependencies=dependencies,
            config=config,
        )

    # ── Monitoring ─────────────────────────────────────────

    def check_health(self) -> dict[str, Any]:
        """Run health checks on all services."""
        self.health_monitor.check_all()
        return self.health_monitor.get_summary()

    def collect_metrics(self) -> dict[str, Any]:
        """Collect current metrics."""
        return self.metrics.collect(
            queue_length=self.task_queue.get_queue_length(),
        ).to_dict()

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive runtime status."""
        return {
            "engine": {
                "running": self._running,
                "uptime_sec": round(time.time() - self._started_at, 1) if self._started_at else 0,
                "execution_count": self._execution_count,
            },
            "scheduler": self.scheduler.get_summary(),
            "tasks": self.task_queue.get_status_counts(),
            "workers": self.worker_pool.get_status(),
            "resources": self.resource_manager.get_usage_summary(),
            "health": self.health_monitor.get_summary(),
            "metrics": self.metrics.get_summary(),
            "alerts": self.alerts.get_summary(),
            "cache": self.cache.get_stats(),
            "services": self.service_registry.get_counts_by_type(),
            "plugins": len(self.plugin_manager.list_plugins()),
            "state": self.state_manager.get_summary(),
            "event_bus": self.event_bus.get_stats(),
            "locks": self.lock_manager.get_summary(),
            "rate_limiter": self.rate_limiter.get_summary(),
            "artifacts": self.artifact_manager.get_stats(),
            "secrets": self.secret_manager.get_stats(),
        }

    def get_report(self) -> dict[str, Any]:
        """Get comprehensive runtime report."""
        return {
            "status": self.get_status(),
            "workflows": self.workflow_engine.list_workflows(),
            "schedules": self.scheduler.get_all_jobs(),
            "execution_history": self.workflow_engine.get_execution_history(),
            "alerts": self.alerts.get_summary(),
            "log_counts": self.logger.get_counts(),
            "artifacts": self.artifact_manager.get_stats(),
            "secrets": self.secret_manager.get_stats(),
        }