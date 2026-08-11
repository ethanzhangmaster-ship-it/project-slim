from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class ActionType(Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    PAUSE = "pause"
    RESUME = "resume"
    OPTIMIZE = "optimize"
    TEST = "test"
    DEPLOY = "deploy"
    UPDATE = "update"


class ActionStatus(Enum):
    PENDING = "pending"
    PLANNED = "planned"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Action:
    action_id: str
    action_type: ActionType
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    status: ActionStatus = ActionStatus.PENDING
    expected_impact: float = 0.0
    confidence: float = 0.0
    risk_level: str = "medium"
    source: str = ""
    reason: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "target": self.target,
            "parameters": self.parameters,
            "priority": self.priority,
            "status": self.status.value,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "source": self.source,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


@dataclass
class ActionPlan:
    plan_id: str
    name: str
    description: str = ""
    actions: List[Action] = field(default_factory=list)
    total_expected_impact: float = 0.0
    status: str = "draft"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "actions": [a.to_dict() for a in self.actions],
            "total_expected_impact": self.total_expected_impact,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class ActionPlanner:
    def __init__(self):
        self._actions: Dict[str, Action] = {}
        self._plans: Dict[str, ActionPlan] = []
        self._action_history: List[Action] = []

    def create_action(
        self,
        action_type: ActionType,
        target: str,
        parameters: Dict[str, Any] = None,
        expected_impact: float = 0.0,
        confidence: float = 0.8,
        priority: int = 5,
        source: str = "system",
        reason: str = ""
    ) -> Action:
        action_id = f"action_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"
        action = Action(
            action_id=action_id,
            action_type=action_type,
            target=target,
            parameters=parameters or {},
            expected_impact=expected_impact,
            confidence=confidence,
            priority=priority,
            source=source,
            reason=reason,
        )
        self._actions[action_id] = action
        return action

    def create_plan(self, name: str, actions: List[Action], description: str = "") -> ActionPlan:
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        total_impact = sum(a.expected_impact for a in actions)
        plan = ActionPlan(
            plan_id=plan_id,
            name=name,
            description=description,
            actions=actions,
            total_expected_impact=total_impact,
        )
        self._plans.append(plan)
        return plan

    def prioritize_actions(self, actions: List[Action] = None) -> List[Action]:
        action_list = actions or list(self._actions.values())
        return sorted(action_list, key=lambda a: (a.priority, -a.expected_impact))

    def get_action(self, action_id: str) -> Optional[Action]:
        return self._actions.get(action_id)

    def get_actions_by_status(self, status: ActionStatus) -> List[Action]:
        return [a for a in self._actions.values() if a.status == status]

    def get_actions_by_type(self, action_type: ActionType) -> List[Action]:
        return [a for a in self._actions.values() if a.action_type == action_type]

    def get_all_actions(self) -> List[Action]:
        return list(self._actions.values())

    def get_plans(self) -> List[ActionPlan]:
        return list(self._plans)

    def get_action_history(self) -> List[Action]:
        return list(self._action_history)

    def get_stats(self) -> Dict[str, Any]:
        actions = list(self._actions.values())
        return {
            "total_actions": len(actions),
            "actions_by_status": {
                status.value: sum(1 for a in actions if a.status == status)
                for status in ActionStatus
            },
            "actions_by_type": {
                type.value: sum(1 for a in actions if a.action_type == type)
                for type in ActionType
            },
            "total_plans": len(self._plans),
            "history_count": len(self._action_history),
        }