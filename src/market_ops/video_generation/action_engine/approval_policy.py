from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime


class ApprovalLevel(Enum):
    AUTO = 0
    AUTO_WITH_LOG = 1
    REQUIRES_APPROVAL = 2


@dataclass
class ApprovalRequest:
    action_id: str
    action_type: str
    decision_id: str
    details: Dict[str, Any] = field(default_factory=dict)
    level: ApprovalLevel = ApprovalLevel.AUTO
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ApprovalResponse:
    request_id: str
    approved: bool
    level: ApprovalLevel
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class ApprovalPolicy:
    def __init__(self):
        self.policies = {
            "pause": ApprovalLevel.AUTO,
            "kill": ApprovalLevel.AUTO,
            "resume": ApprovalLevel.AUTO,
            "scale_up": ApprovalLevel.AUTO_WITH_LOG,
            "scale_down": ApprovalLevel.AUTO_WITH_LOG,
            "update_budget": ApprovalLevel.AUTO_WITH_LOG,
            "adjust_bid": ApprovalLevel.AUTO_WITH_LOG,
            "create_campaign": ApprovalLevel.REQUIRES_APPROVAL,
            "upload_creative": ApprovalLevel.AUTO,
        }

    def evaluate(self, action_type: str, details: Dict[str, Any]) -> ApprovalRequest:
        base_level = self.policies.get(action_type, ApprovalLevel.REQUIRES_APPROVAL)
        
        if action_type in ["scale_up", "update_budget"]:
            old_budget = details.get("old_budget", 0)
            new_budget = details.get("new_budget", 0)
            if old_budget > 0:
                change_percent = (new_budget - old_budget) / old_budget
                if change_percent > 2.0:
                    base_level = ApprovalLevel.REQUIRES_APPROVAL
        
        return ApprovalRequest(
            action_id=f"action_{hash(action_type + str(details)) % 10000:04d}",
            action_type=action_type,
            decision_id=details.get("decision_id", ""),
            details=details,
            level=base_level,
        )

    def approve(self, request: ApprovalRequest, auto_approve: bool = True) -> ApprovalResponse:
        if request.level == ApprovalLevel.AUTO:
            return ApprovalResponse(
                request_id=request.action_id,
                approved=True,
                level=request.level,
                reason="Auto-approved: Level 0 action",
            )
        
        if request.level == ApprovalLevel.AUTO_WITH_LOG:
            return ApprovalResponse(
                request_id=request.action_id,
                approved=True,
                level=request.level,
                reason="Auto-approved with log: Level 1 action",
            )
        
        if auto_approve:
            return ApprovalResponse(
                request_id=request.action_id,
                approved=True,
                level=request.level,
                reason="Manually approved: Level 2 action (auto-approve mode)",
            )
        
        return ApprovalResponse(
            request_id=request.action_id,
            approved=False,
            level=request.level,
            reason="Requires human approval: Level 2 action",
        )

    def get_level_description(self, level: ApprovalLevel) -> str:
        descriptions = {
            ApprovalLevel.AUTO: "Level 0: Auto-execute (e.g., pause failing ads)",
            ApprovalLevel.AUTO_WITH_LOG: "Level 1: Auto-execute + log (e.g., budget increase 20%)",
            ApprovalLevel.REQUIRES_APPROVAL: "Level 2: Requires confirmation (e.g., budget increase 200%)",
        }
        return descriptions.get(level, "Unknown level")

    def evaluate_demo(self) -> ApprovalRequest:
        return self.evaluate("scale_up", {"old_budget": 500, "new_budget": 700, "decision_id": "d1"})

    def approve_demo(self) -> ApprovalResponse:
        request = self.evaluate_demo()
        return self.approve(request, auto_approve=True)
