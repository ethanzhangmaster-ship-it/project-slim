from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class RunnerStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PRIORITIZED = "prioritized"


@dataclass
class ExperimentTask:
    task_id: str
    experiment_id: str
    experiment_type: str
    priority: int = 5
    status: str = "pending"
    progress: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "experiment_id": self.experiment_id,
            "experiment_type": self.experiment_type,
            "priority": self.priority,
            "status": self.status,
            "progress": self.progress,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RunnerConfig:
    execution_mode: ExecutionMode = ExecutionMode.PARALLEL
    max_concurrent: int = 5
    auto_start: bool = True
    retry_on_failure: bool = True
    max_retries: int = 3
    timeout_minutes: int = 60
    notification_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_mode": self.execution_mode.value,
            "max_concurrent": self.max_concurrent,
            "auto_start": self.auto_start,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
            "timeout_minutes": self.timeout_minutes,
            "notification_enabled": self.notification_enabled,
        }


@dataclass
class RunnerMetrics:
    total_experiments: int = 0
    successful_experiments: int = 0
    failed_experiments: int = 0
    average_duration_minutes: float = 0.0
    success_rate: float = 0.0
    current_load: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_experiments": self.total_experiments,
            "successful_experiments": self.successful_experiments,
            "failed_experiments": self.failed_experiments,
            "average_duration_minutes": self.average_duration_minutes,
            "success_rate": self.success_rate,
            "current_load": self.current_load,
        }


@dataclass
class ExecutionResult:
    result_id: str
    task_id: str
    experiment_id: str
    status: str = "completed"
    output: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "task_id": self.task_id,
            "experiment_id": self.experiment_id,
            "status": self.status,
            "output": self.output,
            "metrics": self.metrics,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat(),
        }


class ExperimentRunner:
    def __init__(self):
        self._tasks: Dict[str, ExperimentTask] = {}
        self._results: Dict[str, ExecutionResult] = []
        self._config: RunnerConfig = RunnerConfig()
        self._status: RunnerStatus = RunnerStatus.IDLE
        self._metrics: RunnerMetrics = RunnerMetrics()
        self._queue: List[str] = []
        self._running: List[str] = []

    def submit_experiment(
        self,
        experiment_id: str,
        experiment_type: str,
        priority: int = 5
    ) -> ExperimentTask:
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        task = ExperimentTask(
            task_id=task_id,
            experiment_id=experiment_id,
            experiment_type=experiment_type,
            priority=priority,
        )
        self._tasks[task_id] = task
        self._queue.append(task_id)
        self._update_metrics()

        if self._config.auto_start:
            self._try_start_next()
        return task

    def start_runner(self) -> bool:
        if self._status == RunnerStatus.RUNNING:
            return False
        self._status = RunnerStatus.RUNNING
        self._try_start_next()
        return True

    def pause_runner(self) -> bool:
        if self._status != RunnerStatus.RUNNING:
            return False
        self._status = RunnerStatus.PAUSED
        return True

    def stop_runner(self) -> bool:
        self._status = RunnerStatus.IDLE
        self._running.clear()
        return True

    def _try_start_next(self):
        if self._status != RunnerStatus.RUNNING:
            return

        if len(self._running) >= self._config.max_concurrent:
            return

        while self._queue and len(self._running) < self._config.max_concurrent:
            task_id = self._queue.pop(0)
            task = self._tasks.get(task_id)
            if task:
                self._execute_task(task)

    def _execute_task(self, task: ExperimentTask):
        task.status = "running"
        task.start_time = datetime.now()
        self._running.append(task.task_id)

        try:
            duration = random.uniform(10, 300)
            task.progress = 100.0
            task.status = "completed"
            task.end_time = datetime.now()

            result = ExecutionResult(
                result_id=f"result_{task.task_id}",
                task_id=task.task_id,
                experiment_id=task.experiment_id,
                status="completed",
                output={"message": "Experiment completed successfully"},
                metrics={"performance": random.uniform(0.8, 1.2)},
                duration_seconds=duration,
            )
            self._results.append(result)
            self._metrics.successful_experiments += 1

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self._metrics.failed_experiments += 1

        finally:
            if task.task_id in self._running:
                self._running.remove(task.task_id)
            self._metrics.total_experiments += 1
            self._update_metrics()
            self._try_start_next()

    def cancel_task(self, task_id: str) -> Optional[ExperimentTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None

        if task_id in self._queue:
            self._queue.remove(task_id)
        if task_id in self._running:
            self._running.remove(task_id)

        task.status = "cancelled"
        task.end_time = datetime.now()
        return task

    def get_task(self, task_id: str) -> Optional[ExperimentTask]:
        return self._tasks.get(task_id)

    def get_tasks_by_status(self, status: str) -> List[ExperimentTask]:
        return [t for t in self._tasks.values() if t.status == status]

    def get_all_tasks(self) -> List[ExperimentTask]:
        return list(self._tasks.values())

    def get_results(self, experiment_id: str = None) -> List[ExecutionResult]:
        if experiment_id:
            return [r for r in self._results if r.experiment_id == experiment_id]
        return list(self._results)

    def set_config(self, config: RunnerConfig):
        self._config = config

    def get_config(self) -> RunnerConfig:
        return self._config

    def get_status(self) -> RunnerStatus:
        return self._status

    def _update_metrics(self):
        total = self._metrics.total_experiments
        if total > 0:
            self._metrics.success_rate = self._metrics.successful_experiments / total
        self._metrics.current_load = len(self._running) / self._config.max_concurrent if self._config.max_concurrent > 0 else 0

    def get_metrics(self) -> RunnerMetrics:
        return self._metrics

    def get_stats(self) -> Dict[str, Any]:
        return {
            "status": self._status.value,
            "config": self._config.to_dict(),
            "metrics": self._metrics.to_dict(),
            "queue_size": len(self._queue),
            "running_count": len(self._running),
            "total_tasks": len(self._tasks),
            "total_results": len(self._results),
        }