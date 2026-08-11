from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum
from .task_graph import TaskGraph, TaskNode, TaskStatus, TaskResult
from .dependency_manager import DependencyManager
from .retry_engine import RetryEngine, RetryPolicy


class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Workflow:
    workflow_id: str
    name: str
    task_graph: TaskGraph
    status: WorkflowStatus = WorkflowStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_progress(self) -> Dict[str, Any]:
        return self.task_graph.get_progress()


class WorkflowRunner:
    def __init__(self, max_concurrent_tasks: int = 5):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.dependency_manager = DependencyManager()
        self.retry_engine = RetryEngine()
        self.task_handlers: Dict[str, Callable] = {}
        self.workflows: Dict[str, Workflow] = {}
        self.active_workflows: List[str] = []

    def register_handler(self, task_type: str, handler: Callable):
        self.task_handlers[task_type] = handler

    def register_handlers(self, handlers: Dict[str, Callable]):
        self.task_handlers.update(handlers)

    def create_workflow(
        self,
        name: str,
        tasks: List[TaskNode] = None,
        context: Dict[str, Any] = None,
    ) -> Workflow:
        workflow_id = f"wf_{hash(name + str(datetime.now())) % 100000:05d}"
        task_graph = TaskGraph(workflow_name=name)

        if tasks:
            for task in tasks:
                task_graph.add_task(task)

        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            task_graph=task_graph,
            context=context or {},
        )

        self.workflows[workflow_id] = workflow
        return workflow

    def start_workflow(self, workflow_id: str) -> Workflow:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()
        self.active_workflows.append(workflow_id)

        return workflow

    def execute_step(self, workflow_id: str) -> Dict[str, Any]:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {"error": "workflow_not_found"}

        if workflow.status != WorkflowStatus.RUNNING:
            return {"status": workflow.status.value}

        task_graph = workflow.task_graph
        running_tasks = task_graph.get_running_tasks()

        if len(running_tasks) >= self.max_concurrent_tasks:
            return {
                "status": "running",
                "running_tasks": len(running_tasks),
                "max_concurrent": self.max_concurrent_tasks,
            }

        ready_tasks = task_graph.get_ready_tasks()
        available_slots = self.max_concurrent_tasks - len(running_tasks)
        tasks_to_run = ready_tasks[:available_slots]

        executed = []
        for task in tasks_to_run:
            result = self._execute_task(task, workflow)
            executed.append(result)

        if task_graph.is_complete():
            workflow.completed_at = datetime.now()
            if task_graph.is_success():
                workflow.status = WorkflowStatus.COMPLETED
            else:
                workflow.status = WorkflowStatus.FAILED
            if workflow_id in self.active_workflows:
                self.active_workflows.remove(workflow_id)

        return {
            "status": workflow.status.value,
            "tasks_executed": len(executed),
            "executed_tasks": executed,
            "progress": workflow.get_progress(),
        }

    def _execute_task(self, task: TaskNode, workflow: Workflow) -> TaskResult:
        task.status = TaskStatus.RUNNING
        start_time = datetime.now()

        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.RUNNING,
            started_at=start_time,
        )

        try:
            handler = self.task_handlers.get(task.task_type)
            if handler:
                output = handler(task, workflow.context)
                result.output = output if isinstance(output, dict) else {"result": output}
                result.status = TaskStatus.COMPLETED
            else:
                result.output = task.metadata
                result.status = TaskStatus.COMPLETED

            task.status = TaskStatus.COMPLETED

        except Exception as e:
            error_msg = str(e)
            result.error = error_msg
            result.status = TaskStatus.FAILED
            task.status = TaskStatus.FAILED

            retry_record = self.retry_engine.schedule_retry(
                task_id=task.task_id,
                task_type=task.task_type,
                error=error_msg,
                attempt=result.attempt,
            )

            if retry_record:
                task.status = TaskStatus.PENDING
                result.status = TaskStatus.PENDING

        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - start_time).total_seconds()
        task.result = result

        return result

    def run_until_complete(self, workflow_id: str) -> Workflow:
        workflow = self.start_workflow(workflow_id)

        while workflow.status == WorkflowStatus.RUNNING:
            self.execute_step(workflow_id)
            due_retries = self.retry_engine.get_due_retries()
            for retry in due_retries:
                task = workflow.task_graph.get_task(retry.task_id)
                if task:
                    task.status = TaskStatus.PENDING

        return workflow

    def pause_workflow(self, workflow_id: str) -> bool:
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.PAUSED
            return True
        return False

    def resume_workflow(self, workflow_id: str) -> bool:
        workflow = self.workflows.get(workflow_id)
        if workflow and workflow.status == WorkflowStatus.PAUSED:
            workflow.status = WorkflowStatus.RUNNING
            return True
        return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        workflow = self.workflows.get(workflow_id)
        if workflow:
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = datetime.now()
            if workflow_id in self.active_workflows:
                self.active_workflows.remove(workflow_id)
            return True
        return False

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self.workflows.get(workflow_id)

    def get_active_workflows(self) -> List[Workflow]:
        return [self.workflows[wid] for wid in self.active_workflows if wid in self.workflows]

    def get_workflow_stats(self) -> Dict[str, Any]:
        total = len(self.workflows)
        completed = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.COMPLETED)
        failed = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.FAILED)
        running = len(self.active_workflows)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "paused": sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.PAUSED),
            "success_rate": round(completed / (completed + failed) * 100, 1) if (completed + failed) > 0 else 0,
        }
