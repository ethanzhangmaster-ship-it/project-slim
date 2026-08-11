"""Execution Context"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from .generation_task import GenerationTask


@dataclass
class ExecutionContext:
    """任务执行上下文"""
    task: GenerationTask
    settings: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def log(self, level: str, message: str, details: Dict[str, Any] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
        }
        if details:
            entry["details"] = details
        self.logs.append(entry)

    def complete(self, success: bool, result: Dict[str, Any] = None):
        self.finished_at = datetime.now().isoformat()
        status = "completed" if success else "failed"
        self.log("info", f"Task {status}")
        if result:
            self.task.result = result
