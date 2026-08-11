"""Task Graph - DAG 任务依赖图"""
from typing import Dict, List, Any, Optional
from collections import deque

from .dependency import TaskNode


class TaskGraph:
    """任务依赖图 - 管理任务间的依赖关系"""

    def __init__(self):
        self._nodes: Dict[str, TaskNode] = {}
        self._completed: List[str] = []

    def add_node(self, node: TaskNode):
        self._nodes[node.task_id] = node

    def get_node(self, task_id: str) -> Optional[TaskNode]:
        return self._nodes.get(task_id)

    def remove_node(self, task_id: str):
        if task_id in self._nodes:
            del self._nodes[task_id]

    def mark_completed(self, task_id: str):
        if task_id not in self._completed:
            self._completed.append(task_id)
        if task_id in self._nodes:
            self._nodes[task_id].status = "completed"

    def get_ready_tasks(self) -> List[TaskNode]:
        ready = []
        for node in self._nodes.values():
            if node.status == "pending" and node.is_ready(self._completed):
                ready.append(node)
        return sorted(ready, key=lambda n: n.priority, reverse=True)

    def has_cycles(self) -> bool:
        visited = set()
        rec_stack = set()

        def dfs(node_id: str) -> bool:
            if node_id not in visited:
                visited.add(node_id)
                rec_stack.add(node_id)
                node = self._nodes.get(node_id)
                if node:
                    for dep in node.depends_on:
                        if dep not in visited and dfs(dep):
                            return True
                        elif dep in rec_stack:
                            return True
            if node_id in rec_stack:
                rec_stack.remove(node_id)
            return False

        for node_id in self._nodes:
            if dfs(node_id):
                return True
        return False

    def topological_sort(self) -> List[str]:
        in_degree = {task_id: len(node.depends_on) for task_id, node in self._nodes.items()}
        queue = deque([task_id for task_id, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            task_id = queue.popleft()
            result.append(task_id)

            for node in self._nodes.values():
                if task_id in node.depends_on:
                    in_degree[node.task_id] -= 1
                    if in_degree[node.task_id] == 0:
                        queue.append(node.task_id)

        if len(result) != len(self._nodes):
            raise ValueError("Graph contains cycles")
        return result

    def get_children(self, task_id: str) -> List[str]:
        children = []
        for node_id, node in self._nodes.items():
            if task_id in node.depends_on:
                children.append(node_id)
        return children

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._nodes)
        completed = len(self._completed)
        pending = sum(1 for n in self._nodes.values() if n.status == "pending")
        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "pending_tasks": pending,
            "progress": round(completed / total * 100, 1) if total > 0 else 0,
        }

    @classmethod
    def from_blueprint(cls, blueprint_id: str, scenes: List[Dict[str, Any]]) -> "TaskGraph":
        graph = cls()

        for scene in scenes:
            scene_id = scene.get("scene_id", "")

            graph.add_node(TaskNode(
                task_id=f"{blueprint_id}_{scene_id}_image",
                task_type="image",
                priority=10,
                payload={"scene": scene, "type": "image"},
            ))

            graph.add_node(TaskNode(
                task_id=f"{blueprint_id}_{scene_id}_video",
                task_type="video",
                depends_on=[f"{blueprint_id}_{scene_id}_image"],
                priority=9,
                payload={"scene": scene, "type": "video"},
            ))

            graph.add_node(TaskNode(
                task_id=f"{blueprint_id}_{scene_id}_subtitle",
                task_type="subtitle",
                depends_on=[f"{blueprint_id}_{scene_id}_video"],
                priority=7,
                payload={"scene": scene, "type": "subtitle"},
            ))

            graph.add_node(TaskNode(
                task_id=f"{blueprint_id}_{scene_id}_thumbnail",
                task_type="thumbnail",
                depends_on=[f"{blueprint_id}_{scene_id}_video"],
                priority=6,
                payload={"scene": scene, "type": "thumbnail"},
            ))

            graph.add_node(TaskNode(
                task_id=f"{blueprint_id}_{scene_id}_qa",
                task_type="qa",
                depends_on=[f"{blueprint_id}_{scene_id}_video"],
                priority=8,
                payload={"scene": scene, "type": "qa"},
            ))

        return graph
