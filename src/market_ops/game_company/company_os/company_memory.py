from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CompanyRecord:
    record_id: str
    type: str
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5


class CompanyMemory:
    def __init__(self):
        self.records: Dict[str, CompanyRecord] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.memories: Dict[str, CompanyRecord] = {}

    def store(self, entry_type: str, data: Dict[str, Any], importance: float = 0.5) -> CompanyRecord:
        record_id = f"record_{hash(str(data)) % 10000:04d}"
        
        record = CompanyRecord(
            record_id=record_id,
            type=entry_type,
            content=data,
            importance=importance,
        )
        
        self.records[record_id] = record
        
        if entry_type not in self.category_index:
            self.category_index[entry_type] = []
        self.category_index[entry_type].append(record_id)
        
        return record

    def record(self, record_type: str, content: Dict[str, Any]) -> CompanyRecord:
        return self.store(record_type, content)

    def retrieve(self, record_type: str = None) -> List[CompanyRecord]:
        if record_type:
            ids = self.category_index.get(record_type, [])
            return [self.records[id] for id in ids[-50:]]
        return list(self.records.values())[-100:]

    def get_key_insights(self) -> Dict[str, Any]:
        insights = {"successful_projects": [], "failed_projects": [], "market_patterns": []}
        
        for record in self.records.values():
            if record.type == "project_result":
                if record.content.get("success"):
                    insights["successful_projects"].append(record.content)
                else:
                    insights["failed_projects"].append(record.content)
            elif record.type == "market_analysis":
                insights["market_patterns"].append(record.content)
        
        return insights

    def record_demo(self) -> CompanyRecord:
        return self.record(
            record_type="project_result",
            content={
                "project": "Merge Cozy",
                "launch_date": "2026-07-01",
                "revenue": 500000,
                "target": 400000,
                "success": True,
                "lessons": ["Merge + Decoration genre works", "US Female audience responsive"],
            },
        )
