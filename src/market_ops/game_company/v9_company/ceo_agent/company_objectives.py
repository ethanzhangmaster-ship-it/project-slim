from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class ObjectiveCategory(Enum):
    REVENUE = "revenue"
    USER = "user"
    PRODUCT = "product"
    MARKET = "market"
    TEAM = "team"


@dataclass
class KeyResult:
    kr_id: str
    description: str
    target_value: float = 0.0
    current_value: float = 0.0
    unit: str = ""
    deadline: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kr_id": self.kr_id,
            "description": self.description,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "unit": self.unit,
            "deadline": self.deadline,
        }


@dataclass
class ObjectiveStatus:
    objective_id: str
    status: str = "active"
    progress_pct: float = 0.0
    blocked: bool = False
    blockers: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "blocked": self.blocked,
            "blockers": self.blockers,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Objective:
    objective_id: str
    title: str
    category: ObjectiveCategory
    description: str = ""
    priority: str = "medium"
    key_results: List[KeyResult] = field(default_factory=list)
    status: ObjectiveStatus = field(default_factory=lambda: ObjectiveStatus(objective_id=""))
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.status.objective_id:
            self.status.objective_id = self.objective_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "title": self.title,
            "category": self.category.value,
            "description": self.description,
            "priority": self.priority,
            "key_results": [kr.to_dict() for kr in self.key_results],
            "status": self.status.to_dict(),
            "created_at": self.created_at.isoformat(),
        }


class CompanyObjectives:
    def __init__(self):
        self._objectives: Dict[str, Objective] = {}

    def set_objective(self, objective: Objective) -> None:
        self._objectives[objective.objective_id] = objective

    def get_objectives(self) -> List[Objective]:
        return list(self._objectives.values())

    def get_active_objectives(self) -> List[Objective]:
        return [
            obj for obj in self._objectives.values()
            if obj.status.status in ("active", "in_progress")
        ]

    def complete_objective(self, objective_id: str) -> bool:
        obj = self._objectives.get(objective_id)
        if not obj:
            return False
        obj.status.status = "completed"
        obj.status.progress_pct = 1.0
        obj.status.last_updated = datetime.now()
        return True

    def track_progress(self, objective_id: str) -> Optional[ObjectiveStatus]:
        obj = self._objectives.get(objective_id)
        if not obj:
            return None

        total_krs = len(obj.key_results)
        if total_krs > 0:
            avg_progress = sum(
                min(kr.current_value / max(kr.target_value, 1e-6), 1.0)
                for kr in obj.key_results
            ) / total_krs
            obj.status.progress_pct = round(avg_progress, 4)

        obj.status.last_updated = datetime.now()
        return obj.status

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._objectives)
        active = sum(1 for o in self._objectives.values() if o.status.status == "active")
        completed = sum(1 for o in self._objectives.values() if o.status.status == "completed")
        blocked = sum(1 for o in self._objectives.values() if o.status.blocked)
        return {
            "total_objectives": total,
            "active": active,
            "completed": completed,
            "blocked": blocked,
            "completion_rate": completed / total if total else 0.0,
        }
