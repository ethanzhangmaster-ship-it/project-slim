"""Generation Task Model"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import json

from .generation_state import GenerationStatus, can_transition


@dataclass
class GenerationTask:
    task_id: str = ""
    blueprint_id: str = ""
    scene_id: str = ""
    platform: str = ""
    status: GenerationStatus = GenerationStatus.CREATED
    priority: int = 5
    progress: float = 0.0
    cost: float = 0.0
    prompt: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.task_id:
            self.task_id = self._generate_task_id()
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def _generate_task_id(self) -> str:
        if self.blueprint_id and self.scene_id and self.platform:
            return f"{self.blueprint_id}_{self.scene_id}_{self.platform}"
        return f"task_{uuid.uuid4().hex[:12]}"

    def can_transition_to(self, target: GenerationStatus) -> bool:
        return can_transition(self.status, target)

    def transition_to(self, target: GenerationStatus) -> bool:
        if not self.can_transition_to(target):
            return False
        self.status = target
        if target == GenerationStatus.SUBMITTED and not self.started_at:
            self.started_at = datetime.now().isoformat()
        if target in {GenerationStatus.COMPLETED, GenerationStatus.FAILED}:
            self.completed_at = datetime.now().isoformat()
            if self.started_at:
                start = datetime.fromisoformat(self.started_at)
                end = datetime.fromisoformat(self.completed_at)
                self.duration = (end - start).total_seconds()
        return True

    def is_terminal(self) -> bool:
        from .generation_state import TERMINAL_STATUSES
        return self.status in TERMINAL_STATUSES

    def is_active(self) -> bool:
        from .generation_state import ACTIVE_STATUSES
        return self.status in ACTIVE_STATUSES

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, GenerationStatus) else self.status
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationTask":
        status = data.get("status", "created")
        if isinstance(status, str):
            status = GenerationStatus(status)
        return cls(
            task_id=data.get("task_id", ""),
            blueprint_id=data.get("blueprint_id", ""),
            scene_id=data.get("scene_id", ""),
            platform=data.get("platform", ""),
            status=status,
            priority=data.get("priority", 5),
            progress=data.get("progress", 0.0),
            cost=data.get("cost", 0.0),
            prompt=data.get("prompt", {}),
            result=data.get("result", {}),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            duration=data.get("duration", 0.0),
            metadata=data.get("metadata", {}),
        )
