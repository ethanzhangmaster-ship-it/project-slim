from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class PriorityLevel(Enum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"


@dataclass
class PriorityItem:
    item_id: str
    title: str
    level: PriorityLevel
    category: str = ""
    impact_score: float = 0.0
    urgency_score: float = 0.0
    effort_score: float = 0.0
    blocked_by: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "level": self.level.value,
            "category": self.category,
            "impact_score": self.impact_score,
            "urgency_score": self.urgency_score,
            "effort_score": self.effort_score,
            "blocked_by": self.blocked_by,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PriorityMatrix:
    matrix_id: str
    items: List[PriorityItem] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matrix_id": self.matrix_id,
            "items": [i.to_dict() for i in self.items],
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class PriorityWeight:
    category: str
    impact_weight: float = 0.4
    urgency_weight: float = 0.4
    effort_weight: float = 0.2
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "impact_weight": self.impact_weight,
            "urgency_weight": self.urgency_weight,
            "effort_weight": self.effort_weight,
            "updated_at": self.updated_at.isoformat(),
        }


class PriorityEngine:
    def __init__(self):
        self._items: Dict[str, PriorityItem] = {}
        self._weights: Dict[str, PriorityWeight] = {}
        self._matrix_history: List[PriorityMatrix] = []

    def calculate_priorities(self, issues: List[Dict[str, Any]]) -> List[PriorityItem]:
        items = []
        for issue in issues:
            item_id = issue.get("id", f"item_{datetime.now().strftime('%Y%m%d%H%M%S')}")
            impact = issue.get("impact", 0.5)
            urgency = issue.get("urgency", 0.5)
            effort = issue.get("effort", 0.5)
            score = impact * 0.4 + urgency * 0.4 - effort * 0.2

            level = (
                PriorityLevel.P0 if score >= 0.7
                else PriorityLevel.P1 if score >= 0.5
                else PriorityLevel.P2 if score >= 0.3
                else PriorityLevel.P3 if score >= 0.1
                else PriorityLevel.P4
            )

            item = PriorityItem(
                item_id=item_id,
                title=issue.get("title", "Untitled"),
                level=level,
                category=issue.get("category", "general"),
                impact_score=impact,
                urgency_score=urgency,
                effort_score=effort,
                blocked_by=issue.get("blocked_by", []),
            )
            items.append(item)
            self._items[item.item_id] = item

        matrix = PriorityMatrix(
            matrix_id=f"matrix_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            items=items,
        )
        self._matrix_history.append(matrix)
        return sorted(items, key=lambda i: (
            [PriorityLevel.P0, PriorityLevel.P1, PriorityLevel.P2, PriorityLevel.P3, PriorityLevel.P4].index(i.level),
            -(i.impact_score + i.urgency_score),
        ))

    def get_priority_matrix(self) -> Optional[PriorityMatrix]:
        return self._matrix_history[-1] if self._matrix_history else None

    def update_priority_weight(self, category: str, weight: Dict[str, float]) -> PriorityWeight:
        pw = PriorityWeight(
            category=category,
            impact_weight=weight.get("impact", 0.4),
            urgency_weight=weight.get("urgency", 0.4),
            effort_weight=weight.get("effort", 0.2),
        )
        self._weights[category] = pw
        return pw

    def get_top_priorities(self, n: int = 5) -> List[PriorityItem]:
        active = [item for item in self._items.values() if item.level in (PriorityLevel.P0, PriorityLevel.P1)]
        return sorted(
            active,
            key=lambda i: i.impact_score + i.urgency_score,
            reverse=True,
        )[:n]

    def resolve_conflicts(self) -> List[Dict[str, Any]]:
        conflicts = []
        for item in self._items.values():
            if item.blocked_by:
                conflicts.append({
                    "item_id": item.item_id,
                    "blocked_by": item.blocked_by,
                    "resolution": "Escalate to executive review",
                })
        return conflicts

    def get_stats(self) -> Dict[str, Any]:
        counts = {level.value: 0 for level in PriorityLevel}
        for item in self._items.values():
            counts[item.level.value] += 1
        return {
            "total_items": len(self._items),
            "items_by_level": counts,
            "total_matrices": len(self._matrix_history),
            "weight_categories": len(self._weights),
        }
