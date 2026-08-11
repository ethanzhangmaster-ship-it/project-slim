from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class RollbackRecord:
    action_id: str
    rollback_id: str
    action_type: str
    rollback_action: str
    original_state: Dict[str, Any] = field(default_factory=dict)
    new_state: Dict[str, Any] = field(default_factory=dict)
    executed: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class RollbackManager:
    def __init__(self):
        self.records: Dict[str, RollbackRecord] = {}
        self.rollback_map = {
            "scale_up": "scale_down",
            "scale_down": "scale_up",
            "pause": "resume",
            "resume": "pause",
            "kill": "create_campaign",
            "create_campaign": "kill",
            "update_budget": "update_budget",
            "adjust_bid": "adjust_bid",
        }

    def record(self, action_id: str, action_type: str, original_state: Dict[str, Any], new_state: Dict[str, Any]) -> RollbackRecord:
        rollback_action = self.rollback_map.get(action_type, action_type)
        
        record = RollbackRecord(
            action_id=action_id,
            rollback_id=f"rollback_{hash(action_id) % 10000:04d}",
            action_type=action_type,
            rollback_action=rollback_action,
            original_state=original_state,
            new_state=new_state,
        )
        
        self.records[action_id] = record
        return record

    def rollback(self, action_id: str) -> RollbackRecord:
        if action_id not in self.records:
            raise ValueError(f"No rollback record found for action: {action_id}")
        
        record = self.records[action_id]
        
        if record.action_type == "update_budget":
            record.original_state, record.new_state = record.new_state, record.original_state
        elif record.action_type == "adjust_bid":
            record.original_state, record.new_state = record.new_state, record.original_state
        
        record.executed = True
        return record

    def get_record(self, action_id: str) -> Optional[RollbackRecord]:
        return self.records.get(action_id)

    def rollback_demo(self) -> RollbackRecord:
        self.record(
            action_id="action_0001",
            action_type="update_budget",
            original_state={"budget": 500},
            new_state={"budget": 1000},
        )
        return self.rollback("action_0001")
