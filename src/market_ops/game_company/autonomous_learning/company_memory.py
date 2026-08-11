from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class MemoryEntry:
    entry_id: str
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = None
    importance: float = 0.0


class CompanyMemory:
    def __init__(self):
        self.memories: Dict[str, MemoryEntry] = {}
        self.strategies: Dict[str, Dict[str, Any]] = {}
        self.failed_projects: List[Dict[str, Any]] = []
        self.success_patterns: List[Dict[str, Any]] = []

    def store(self, entry_type: str, data: Dict[str, Any], importance: float = 0.5) -> MemoryEntry:
        entry = MemoryEntry(
            entry_id=f"mem_{hash(str(data)) % 10000:04d}",
            type=entry_type,
            data=data,
            timestamp=datetime.now(),
            importance=importance,
        )

        self.memories[entry.entry_id] = entry
        
        if entry_type == "strategy":
            self.strategies[data.get("strategy_id", entry.entry_id)] = data
        elif entry_type == "failure":
            self.failed_projects.append(data)
        elif entry_type == "success":
            self.success_patterns.append(data)

        return entry

    def retrieve(self, entry_type: str = None) -> List[MemoryEntry]:
        if entry_type:
            return [m for m in self.memories.values() if m.type == entry_type]
        return list(self.memories.values())

    def get_success_patterns(self) -> List[Dict[str, Any]]:
        return self.success_patterns

    def get_failed_patterns(self) -> List[Dict[str, Any]]:
        return self.failed_projects

    def get_best_strategies(self, limit: int = 5) -> List[Dict[str, Any]]:
        sorted_strategies = sorted(
            self.strategies.values(),
            key=lambda x: x.get("success_rate", 0),
            reverse=True
        )
        return sorted_strategies[:limit]

    def store_demo(self) -> MemoryEntry:
        data = {
            "project_id": "proj_002",
            "name": "Cozy Witch Garden",
            "genre": "Merge",
            "success_rate": 0.85,
            "key_factors": ["merge mechanics", "decoration", "female audience"],
        }
        return self.store("success", data, importance=0.9)
