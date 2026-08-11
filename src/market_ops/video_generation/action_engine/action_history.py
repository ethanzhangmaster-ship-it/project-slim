from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class ActionRecord:
    action_id: str
    action_type: str
    decision_id: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    approval_level: str = ""
    executed_at: datetime = field(default_factory=datetime.now)
    rollback_id: str = ""


class ActionHistory:
    def __init__(self):
        self.records: Dict[str, ActionRecord] = {}
        self.index: Dict[str, List[str]] = {
            "action_type": {},
            "status": {},
            "decision_id": {},
        }

    def add(self, action: ActionRecord) -> None:
        self.records[action.action_id] = action
        
        for key in ["action_type", "status", "decision_id"]:
            value = getattr(action, key)
            if value not in self.index[key]:
                self.index[key][value] = []
            self.index[key][value].append(action.action_id)

    def get(self, action_id: str) -> Optional[ActionRecord]:
        return self.records.get(action_id)

    def filter_by_type(self, action_type: str) -> List[ActionRecord]:
        ids = self.index["action_type"].get(action_type, [])
        return [self.records[id] for id in ids]

    def filter_by_status(self, status: str) -> List[ActionRecord]:
        ids = self.index["status"].get(status, [])
        return [self.records[id] for id in ids]

    def get_by_decision(self, decision_id: str) -> List[ActionRecord]:
        ids = self.index["decision_id"].get(decision_id, [])
        return [self.records[id] for id in ids]

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.records)
        success = len(self.filter_by_status("success"))
        failed = len(self.filter_by_status("failed"))
        
        type_counts = {}
        for action_type, ids in self.index["action_type"].items():
            type_counts[action_type] = len(ids)
        
        return {
            "total_actions": total,
            "success_count": success,
            "failed_count": failed,
            "success_rate": success / total if total > 0 else 0,
            "actions_by_type": type_counts,
        }

    def add_demo(self) -> ActionRecord:
        record = ActionRecord(
            action_id="action_0001",
            action_type="scale_up",
            decision_id="d1",
            status="success",
            details={"old_budget": 500, "new_budget": 700},
            approval_level="AUTO_WITH_LOG",
        )
        self.add(record)
        return record
