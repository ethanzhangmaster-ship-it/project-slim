"""Task Dependency"""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class TaskNode:
    task_id: str = ""
    task_type: str = ""
    status: str = "pending"
    depends_on: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5

    def is_ready(self, completed_tasks: List[str]) -> bool:
        return all(dep in completed_tasks for dep in self.depends_on)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "depends_on": self.depends_on,
            "outputs": self.outputs,
            "priority": self.priority,
        }
