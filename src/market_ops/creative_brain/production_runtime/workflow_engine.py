"""V4.4 Workflow Engine — DAG-based workflow execution.

Auto-calculates execution order from dependencies.
Supports: parallel execution within levels, retry, rollback, checkpointing.

Example:
  Facebook → Knowledge → Reasoning → Validation → Policy
  A → B, A → C, B → D, C → D
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .schemas import (RuntimeTask, RuntimeReport, TaskStatus, TaskPriority,
                       WorkflowNode, WorkflowDAG, WorkerType, OnErrorPolicy)
from .dependency_graph import DependencyGraph
from .task_queue import TaskQueue
from .retry_manager import RetryManager
from .rollback_manager import RollbackManager
from .checkpoint_manager import CheckpointManager
from .logger import Logger


class WorkflowEngine:
    """DAG-based workflow execution engine."""

    def __init__(self, task_queue: TaskQueue | None = None,
                 retry_manager: RetryManager | None = None,
                 rollback_manager: RollbackManager | None = None,
                 checkpoint_manager: CheckpointManager | None = None,
                 logger: Logger | None = None) -> None:
        self._task_queue = task_queue or TaskQueue()
        self._retry_manager = retry_manager or RetryManager()
        self._rollback_manager = rollback_manager or RollbackManager()
        self._checkpoint_manager = checkpoint_manager or CheckpointManager()
        self._logger = logger or Logger("workflow")
        self._registered_workflows: dict[str, WorkflowDAG] = {}
        self._execution_history: list[dict[str, Any]] = []
        self._task_executors: dict[str, Callable] = {}  # task_type → executor_fn

    def register_workflow(self, workflow: WorkflowDAG) -> None:
        """Register a workflow definition."""
        self._registered_workflows[workflow.workflow_id] = workflow

    def register_executor(self, task_type: str,
                          executor: Callable[[RuntimeTask], tuple[bool, Any]]) -> None:
        """Register a task type executor function.

        Args:
            task_type: Task type string (e.g., 'facebook_sync', 'reasoning').
            executor: Callable(task) → (success, result).
        """
        self._task_executors[task_type] = executor

    def build_dag(self, workflow_id: str) -> DependencyGraph:
        """Build a dependency graph from a registered workflow."""
        workflow = self._registered_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        graph = DependencyGraph()
        for node in workflow.nodes:
            graph.add_node(node.task_name, node.dependencies)
        return graph

    def execute(self, workflow_id: str,
                state: dict[str, Any] | None = None) -> RuntimeReport:
        """Execute a workflow from start to finish.

        Args:
            workflow_id: Registered workflow ID.
            state: Optional initial state for rollback.

        Returns:
            RuntimeReport with execution results.
        """
        workflow = self._registered_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")

        self._logger.info(f"Starting workflow: {workflow.name}", workflow_id=workflow_id)

        # Take snapshot for rollback
        if state is not None:
            self._rollback_manager.snapshot(workflow_id, state)

        report = RuntimeReport(
            workflow_id=workflow_id,
            started_at=time.time(),
            total_tasks=len(workflow.nodes),
        )

        try:
            # Build DAG and get execution levels
            graph = self.build_dag(workflow_id)
            if graph.has_cycle():
                raise ValueError("Workflow has circular dependencies")

            levels = graph.get_execution_levels()

            # Create tasks from workflow nodes
            tasks = self._create_tasks(workflow)

            # Enqueue all tasks
            self._task_queue.enqueue_batch(tasks)

            # Execute level by level
            for level_idx, level in enumerate(levels):
                self._logger.info(f"Executing level {level_idx}: {level}")
                self._execute_level(level, tasks, report)

                # Save checkpoint after each level
                self._save_checkpoint(workflow_id, report)

            report.completed_at = time.time()
            self._logger.info(
                f"Workflow complete: {report.completed}/{report.total_tasks} tasks",
                workflow_id=workflow_id,
            )

        except Exception as e:
            self._logger.error(f"Workflow failed: {e}", workflow_id=workflow_id)
            report.errors.append(str(e))

            # Rollback on failure
            if state is not None:
                restored = self._rollback_manager.rollback(workflow_id)
                if restored:
                    self._logger.info("Rollback successful", workflow_id=workflow_id)

        finally:
            report.completed_at = time.time()

        self._execution_history.append(report.to_dict())
        return report

    def _create_tasks(self, workflow: WorkflowDAG) -> list[RuntimeTask]:
        """Create RuntimeTask objects from WorkflowDAG nodes."""
        tasks = []
        for node in workflow.nodes:
            task = RuntimeTask(
                task_id=f"{workflow.workflow_id}_{node.task_name}",
                name=node.task_name,
                task_type=node.task_type,
                priority=node.priority,
                worker_type=node.worker_type,
                dependencies=[
                    f"{workflow.workflow_id}_{dep}" for dep in node.dependencies
                ],
                timeout=node.timeout,
                max_retries=node.max_retries,
                created_at=time.time(),
                metadata={"on_error": node.on_error.value},
            )
            tasks.append(task)
        return tasks

    def _execute_level(self, level: list[str],
                       tasks: list[RuntimeTask],
                       report: RuntimeReport) -> None:
        """Execute all tasks in a level (could be parallel in production).

        Supports OnErrorPolicy:
          - FAIL_WORKFLOW: stop entire DAG on failure
          - SKIP_CONTINUE: skip failed task, continue DAG
          - RETRY_THEN_SKIP: retry first, then skip if still fails
          - RETRY_THEN_FAIL: retry first, then fail DAG if still fails
        """
        task_map = {t.name: t for t in tasks}

        for task_name in level:
            task = task_map.get(task_name)
            if task is None:
                continue

            on_error_str = task.metadata.get("on_error", "fail_workflow")
            on_error = OnErrorPolicy(on_error_str)

            success = self._execute_task(task, report)

            if not success:
                if on_error == OnErrorPolicy.SKIP_CONTINUE:
                    task.status = TaskStatus.SKIPPED
                    report.skipped += 1
                    self._task_queue.complete(task.task_id, None)
                    self._logger.warning(
                        f"Task skipped (on_error=skip_continue): {task.name}",
                        task_id=task.task_id,
                    )
                elif on_error == OnErrorPolicy.RETRY_THEN_SKIP:
                    # Retry once more
                    retry_success, _ = self._retry_manager.retry_with_backoff(
                        task, self._task_executors.get(task.task_type, lambda t: (False, ""))
                    )
                    if retry_success:
                        task.status = TaskStatus.COMPLETED
                        report.completed += 1
                    else:
                        task.status = TaskStatus.SKIPPED
                        report.skipped += 1
                        self._task_queue.complete(task.task_id, None)
                        self._logger.warning(
                            f"Task skipped after retry: {task.name}",
                            task_id=task.task_id,
                        )
                elif on_error == OnErrorPolicy.RETRY_THEN_FAIL:
                    retry_success, _ = self._retry_manager.retry_with_backoff(
                        task, self._task_executors.get(task.task_type, lambda t: (False, ""))
                    )
                    if retry_success:
                        task.status = TaskStatus.COMPLETED
                        report.completed += 1
                    else:
                        raise RuntimeError(
                            f"Task failed after retry: {task.name} - {task.error}"
                        )
                else:  # FAIL_WORKFLOW (default)
                    raise RuntimeError(
                        f"Task failed (on_error=fail_workflow): {task.name} - {task.error}"
                    )

    def _execute_task(self, task: RuntimeTask,
                      report: RuntimeReport) -> bool:
        """Execute a single task with retry support.

        Returns:
            True if task completed successfully, False if failed.
        """
        executor = self._task_executors.get(task.task_type)
        if executor is None:
            self._logger.warning(f"No executor for task type: {task.task_type}",
                                 task_id=task.task_id)
            task.status = TaskStatus.SKIPPED
            report.skipped += 1
            return False

        self._logger.set_task_context(task.task_id)
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        success, result = self._retry_manager.retry_with_backoff(task, executor)

        task.completed_at = time.time()
        report.retries += task.retry_count

        if success:
            task.status = TaskStatus.COMPLETED
            task.result = result
            report.completed += 1
            self._task_queue.complete(task.task_id, result)
            self._logger.info(f"Task completed: {task.name}", task_id=task.task_id)
        else:
            task.status = TaskStatus.FAILED
            task.error = str(result) if result else "Unknown error"
            report.failed += 1
            report.errors.append(f"{task.name}: {task.error}")
            self._task_queue.fail(task.task_id, task.error)
            self._logger.error(f"Task failed: {task.name} - {task.error}",
                               task_id=task.task_id)

        self._logger.clear_task_context()
        return success

    def _save_checkpoint(self, workflow_id: str, report: RuntimeReport) -> None:
        """Save execution checkpoint."""
        self._checkpoint_manager.save(
            workflow_id=workflow_id,
            tasks=[],
            task_states={
                "completed": report.completed,
                "failed": report.failed,
                "skipped": report.skipped,
            },
        )

    def execute_task_type(self, task_type: str, task_name: str = "",
                          priority: TaskPriority = TaskPriority.NORMAL,
                          worker_type: WorkerType = WorkerType.CPU,
                          dependencies: list[str] | None = None,
                          metadata: dict[str, Any] | None = None) -> RuntimeReport:
        """Execute a single task type directly.

        Useful for ad-hoc task execution outside of workflows.
        """
        task = RuntimeTask(
            task_id=f"adhoc_{task_type}_{int(time.time())}",
            name=task_name or task_type,
            task_type=task_type,
            priority=priority,
            worker_type=worker_type,
            dependencies=dependencies or [],
            created_at=time.time(),
            metadata=metadata or {},
        )

        report = RuntimeReport(
            workflow_id=f"adhoc_{task_type}",
            started_at=time.time(),
            total_tasks=1,
        )

        self._execute_task(task, report)
        report.completed_at = time.time()
        return report

    def get_execution_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent execution history."""
        return self._execution_history[-limit:]

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get current status of a workflow."""
        workflow = self._registered_workflows.get(workflow_id)
        if not workflow:
            return {"error": "Workflow not found"}

        try:
            graph = self.build_dag(workflow_id)
            levels = graph.get_execution_levels()
        except ValueError:
            levels = []

        return {
            "workflow_id": workflow_id,
            "name": workflow.name,
            "nodes": len(workflow.nodes),
            "levels": len(levels),
            "execution_order": [n for level in levels for n in level],
        }

    def list_workflows(self) -> list[dict[str, Any]]:
        """List all registered workflows."""
        return [
            {"id": wf.workflow_id, "name": wf.name, "nodes": len(wf.nodes)}
            for wf in self._registered_workflows.values()
        ]