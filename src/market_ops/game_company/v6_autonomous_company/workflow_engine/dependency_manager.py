from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from .task_graph import TaskGraph, TaskNode, TaskStatus


@dataclass
class DependencyCheckResult:
    task_id: str
    is_ready: bool
    missing_dependencies: List[str] = field(default_factory=list)
    completed_dependencies: List[str] = field(default_factory=list)
    failed_dependencies: List[str] = field(default_factory=list)


class DependencyManager:
    def __init__(self):
        self.dependency_cache: Dict[str, DependencyCheckResult] = {}

    def check_dependencies(self, task_id: str, task_graph: TaskGraph) -> DependencyCheckResult:
        task = task_graph.get_task(task_id)
        if not task:
            return DependencyCheckResult(
                task_id=task_id,
                is_ready=False,
                missing_dependencies=["task_not_found"],
            )

        if task.status in (TaskStatus.COMPLETED, TaskStatus.RUNNING, TaskStatus.FAILED):
            return DependencyCheckResult(
                task_id=task_id,
                is_ready=False,
                completed_dependencies=[d for d in task.dependencies],
            )

        missing = []
        completed = []
        failed = []

        for dep_id in task.dependencies:
            dep_task = task_graph.get_task(dep_id)
            if not dep_task:
                missing.append(dep_id)
            elif dep_task.status == TaskStatus.COMPLETED:
                completed.append(dep_id)
            elif dep_task.status == TaskStatus.FAILED:
                failed.append(dep_id)
            else:
                missing.append(dep_id)

        is_ready = len(missing) == 0 and len(failed) == 0

        result = DependencyCheckResult(
            task_id=task_id,
            is_ready=is_ready,
            missing_dependencies=missing,
            completed_dependencies=completed,
            failed_dependencies=failed,
        )

        self.dependency_cache[task_id] = result
        return result

    def get_dependents(self, task_id: str, task_graph: TaskGraph) -> List[str]:
        dependents = []
        for task in task_graph.get_all_tasks():
            if task_id in task.dependencies:
                dependents.append(task.task_id)
        return dependents

    def get_dependency_chain(self, task_id: str, task_graph: TaskGraph) -> List[str]:
        chain = []
        visited = set()
        stack = [task_id]

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            task = task_graph.get_task(current)
            if task:
                chain.append(current)
                for dep in task.dependencies:
                    stack.append(dep)

        return chain

    def detect_cycles(self, task_graph: TaskGraph) -> List[List[str]]:
        cycles = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(task_id: str):
            visited.add(task_id)
            rec_stack.add(task_id)
            path.append(task_id)

            task = task_graph.get_task(task_id)
            if task:
                for dep_id in task.dependencies:
                    if dep_id not in visited:
                        dfs(dep_id)
                    elif dep_id in rec_stack:
                        cycle_start = path.index(dep_id)
                        cycles.append(path[cycle_start:] + [dep_id])

            path.pop()
            rec_stack.remove(task_id)

        for task_id in task_graph.tasks:
            if task_id not in visited:
                dfs(task_id)

        return cycles

    def get_critical_path(self, task_graph: TaskGraph) -> List[str]:
        memo: Dict[str, List[str]] = {}

        def longest_path(task_id: str) -> List[str]:
            if task_id in memo:
                return memo[task_id]

            task = task_graph.get_task(task_id)
            if not task or not task.dependencies:
                memo[task_id] = [task_id]
                return [task_id]

            longest = []
            for dep_id in task.dependencies:
                dep_path = longest_path(dep_id)
                if len(dep_path) > len(longest):
                    longest = dep_path

            result = longest + [task_id]
            memo[task_id] = result
            return result

        end_tasks = [
            t.task_id for t in task_graph.get_all_tasks()
            if not self.get_dependents(t.task_id, task_graph)
        ]

        if not end_tasks:
            return []

        critical = max(
            (longest_path(t) for t in end_tasks),
            key=len,
            default=[],
        )

        return critical

    def batch_check(self, task_ids: List[str], task_graph: TaskGraph) -> Dict[str, DependencyCheckResult]:
        results = {}
        for task_id in task_ids:
            results[task_id] = self.check_dependencies(task_id, task_graph)
        return results

    def invalidate_cache(self, task_id: str = None):
        if task_id:
            if task_id in self.dependency_cache:
                del self.dependency_cache[task_id]
        else:
            self.dependency_cache.clear()
