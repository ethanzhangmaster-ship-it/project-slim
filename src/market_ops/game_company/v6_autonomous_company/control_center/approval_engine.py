from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class ApprovalLevel(Enum):
    LEVEL_0_AUTO = "level_0_auto"
    LEVEL_1_NOTIFY = "level_1_notify"
    LEVEL_2_APPROVAL = "level_2_approval"
    LEVEL_3_BLOCKED = "level_3_blocked"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    ESCALATED = "escalated"


@dataclass
class ApprovalRequest:
    request_id: str
    action: str
    description: str
    level: ApprovalLevel
    requested_by: str = "system"
    parameters: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: str = ""


class ApprovalEngine:
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._rules: Dict[str, ApprovalLevel] = {
            "budget_increase_small": ApprovalLevel.LEVEL_0_AUTO,
            "budget_increase_medium": ApprovalLevel.LEVEL_1_NOTIFY,
            "budget_increase_large": ApprovalLevel.LEVEL_2_APPROVAL,
            "campaign_create": ApprovalLevel.LEVEL_1_NOTIFY,
            "campaign_pause": ApprovalLevel.LEVEL_0_AUTO,
            "creative_generation": ApprovalLevel.LEVEL_0_AUTO,
            "game_launch": ApprovalLevel.LEVEL_2_APPROVAL,
            "game_kill": ApprovalLevel.LEVEL_2_APPROVAL,
            "strategy_change": ApprovalLevel.LEVEL_2_APPROVAL,
            "spend_over_10k": ApprovalLevel.LEVEL_2_APPROVAL,
            "spend_over_100k": ApprovalLevel.LEVEL_3_BLOCKED,
        }

    def _determine_level(self, action: str, parameters: Dict[str, Any]) -> ApprovalLevel:
        if action == "budget_increase":
            amount = parameters.get("amount", 0)
            if amount > 100000:
                return ApprovalLevel.LEVEL_3_BLOCKED
            elif amount > 10000:
                return ApprovalLevel.LEVEL_2_APPROVAL
            elif amount > 1000:
                return ApprovalLevel.LEVEL_1_NOTIFY
            else:
                return ApprovalLevel.LEVEL_0_AUTO

        return self._rules.get(action, ApprovalLevel.LEVEL_1_NOTIFY)

    def _calculate_risk(self, action: str, parameters: Dict[str, Any]) -> float:
        risk = 0.3

        if "budget" in action.lower() or "spend" in action.lower():
            amount = parameters.get("amount", 0)
            if amount > 100000:
                risk += 0.5
            elif amount > 10000:
                risk += 0.3
            elif amount > 1000:
                risk += 0.15

        if "launch" in action.lower() or "game" in action.lower():
            risk += 0.2

        if "kill" in action.lower() or "pause" in action.lower():
            risk += 0.1

        return min(risk, 1.0)

    def request_approval(
        self,
        action: str,
        description: str,
        parameters: Dict[str, Any] = None,
        requested_by: str = "system",
    ) -> ApprovalRequest:
        parameters = parameters or {}
        level = self._determine_level(action, parameters)
        risk_score = self._calculate_risk(action, parameters)

        request_id = f"appr_{hash(action + str(datetime.now())) % 100000:05d}"

        request = ApprovalRequest(
            request_id=request_id,
            action=action,
            description=description,
            level=level,
            requested_by=requested_by,
            parameters=parameters,
            risk_score=round(risk_score, 2),
        )

        if level == ApprovalLevel.LEVEL_0_AUTO:
            request.status = ApprovalStatus.AUTO_APPROVED
            request.resolved_at = datetime.now()
            request.resolved_by = "auto"

        self._requests[request_id] = request
        return request

    def approve(self, request_id: str, approver: str = "human", notes: str = "") -> bool:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return False

        request.status = ApprovalStatus.APPROVED
        request.resolved_at = datetime.now()
        request.resolved_by = approver
        request.resolution_notes = notes
        return True

    def reject(self, request_id: str, rejecter: str = "human", reason: str = "") -> bool:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return False

        request.status = ApprovalStatus.REJECTED
        request.resolved_at = datetime.now()
        request.resolved_by = rejecter
        request.resolution_notes = reason
        return True

    def can_execute(self, request_id: str) -> bool:
        request = self._requests.get(request_id)
        if not request:
            return False
        return request.status in (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED)

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def get_pending_requests(self, level: ApprovalLevel = None) -> List[ApprovalRequest]:
        pending = [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]
        if level:
            pending = [r for r in pending if r.level == level]
        return sorted(pending, key=lambda r: r.created_at, reverse=True)

    def get_requests_by_status(self, status: ApprovalStatus) -> List[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == status]

    def add_rule(self, action: str, level: ApprovalLevel):
        self._rules[action] = level

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._requests)
        pending = len(self.get_pending_requests())
        approved = len(self.get_requests_by_status(ApprovalStatus.APPROVED))
        auto_approved = len(self.get_requests_by_status(ApprovalStatus.AUTO_APPROVED))
        rejected = len(self.get_requests_by_status(ApprovalStatus.REJECTED))
        return {
            "total_requests": total,
            "pending": pending,
            "approved": approved,
            "auto_approved": auto_approved,
            "rejected": rejected,
            "auto_approval_rate": round((auto_approved + approved) / total * 100, 1) if total > 0 else 0,
        }
