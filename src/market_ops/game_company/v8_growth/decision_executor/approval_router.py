from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class ApprovalLevel(Enum):
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"


@dataclass
class ApprovalRequest:
    request_id: str
    action_id: str
    action_type: str
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    impact: float = 0.0
    risk: str = "medium"
    level: ApprovalLevel = ApprovalLevel.MEDIUM
    status: ApprovalStatus = ApprovalStatus.PENDING
    requester: str = "system"
    approver: str = ""
    reason: str = ""
    submitted_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
            "impact": self.impact,
            "risk": self.risk,
            "level": self.level.value,
            "status": self.status.value,
            "requester": self.requester,
            "approver": self.approver,
            "reason": self.reason,
            "submitted_at": self.submitted_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class ApprovalRule:
    rule_id: str
    action_types: List[str] = field(default_factory=list)
    impact_threshold: float = 0.0
    risk_levels: List[str] = field(default_factory=list)
    approval_level: ApprovalLevel = ApprovalLevel.MEDIUM
    auto_approve: bool = False
    timeout_minutes: int = 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "action_types": self.action_types,
            "impact_threshold": self.impact_threshold,
            "risk_levels": self.risk_levels,
            "approval_level": self.approval_level.value,
            "auto_approve": self.auto_approve,
            "timeout_minutes": self.timeout_minutes,
        }


class ApprovalRouter:
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._rules: Dict[str, ApprovalRule] = {}
        self._approval_history: List[ApprovalRequest] = []
        self._default_rules = self._init_default_rules()

    def _init_default_rules(self) -> Dict[str, ApprovalRule]:
        return {
            "auto_rule": ApprovalRule(
                rule_id="auto_rule",
                action_types=["optimize", "test"],
                impact_threshold=0.1,
                risk_levels=["low"],
                approval_level=ApprovalLevel.AUTO,
                auto_approve=True,
            ),
            "standard_rule": ApprovalRule(
                rule_id="standard_rule",
                action_types=["scale_up", "scale_down", "update"],
                impact_threshold=0.3,
                risk_levels=["low", "medium"],
                approval_level=ApprovalLevel.MEDIUM,
            ),
            "critical_rule": ApprovalRule(
                rule_id="critical_rule",
                action_types=["deploy", "pause"],
                impact_threshold=1.0,
                risk_levels=["high", "critical"],
                approval_level=ApprovalLevel.HIGH,
            ),
        }

    def route_action(
        self,
        action_id: str,
        action_type: str,
        target: str,
        impact: float,
        risk: str,
        parameters: Dict[str, Any] = None
    ) -> ApprovalRequest:
        request_id = f"appr_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        level = self._determine_level(action_type, impact, risk)
        auto_approve = self._check_auto_approve(action_type, impact, risk)

        request = ApprovalRequest(
            request_id=request_id,
            action_id=action_id,
            action_type=action_type,
            target=target,
            parameters=parameters or {},
            impact=impact,
            risk=risk,
            level=level,
        )

        if auto_approve:
            request.status = ApprovalStatus.APPROVED
            request.reviewed_at = datetime.now()
            request.approver = "auto"

        self._requests[request_id] = request
        return request

    def _determine_level(self, action_type: str, impact: float, risk: str) -> ApprovalLevel:
        if impact < 0.1 and risk == "low":
            return ApprovalLevel.AUTO
        elif impact < 0.3 and risk in ["low", "medium"]:
            return ApprovalLevel.LOW
        elif impact < 0.5 or risk == "medium":
            return ApprovalLevel.MEDIUM
        elif impact < 0.8 or risk == "high":
            return ApprovalLevel.HIGH
        return ApprovalLevel.CRITICAL

    def _check_auto_approve(self, action_type: str, impact: float, risk: str) -> bool:
        for rule in self._default_rules.values():
            if (action_type in rule.action_types and
                impact <= rule.impact_threshold and
                risk in rule.risk_levels and
                rule.auto_approve):
                return True
        return False

    def approve(self, request_id: str, approver: str, reason: str = "") -> Optional[ApprovalRequest]:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return None
        request.status = ApprovalStatus.APPROVED
        request.approver = approver
        request.reason = reason
        request.reviewed_at = datetime.now()
        self._approval_history.append(request)
        return request

    def reject(self, request_id: str, approver: str, reason: str) -> Optional[ApprovalRequest]:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return None
        request.status = ApprovalStatus.REJECTED
        request.approver = approver
        request.reason = reason
        request.reviewed_at = datetime.now()
        self._approval_history.append(request)
        return request

    def escalate(self, request_id: str, reason: str) -> Optional[ApprovalRequest]:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalStatus.PENDING:
            return None
        request.status = ApprovalStatus.ESCALATED
        request.reason = reason
        request.level = ApprovalLevel.CRITICAL
        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def get_pending_requests(self, level: ApprovalLevel = None) -> List[ApprovalRequest]:
        requests = [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]
        if level:
            requests = [r for r in requests if r.level == level]
        return requests

    def get_all_requests(self) -> List[ApprovalRequest]:
        return list(self._requests.values())

    def get_approval_history(self) -> List[ApprovalRequest]:
        return list(self._approval_history)

    def add_rule(self, rule: ApprovalRule):
        self._rules[rule.rule_id] = rule

    def get_rules(self) -> List[ApprovalRule]:
        return list(self._default_rules.values()) + list(self._rules.values())

    def get_stats(self) -> Dict[str, Any]:
        requests = list(self._requests.values())
        return {
            "total_requests": len(requests),
            "requests_by_status": {
                status.value: sum(1 for r in requests if r.status == status)
                for status in ApprovalStatus
            },
            "requests_by_level": {
                level.value: sum(1 for r in requests if r.level == level)
                for level in ApprovalLevel
            },
            "total_rules": len(self.get_rules()),
            "history_count": len(self._approval_history),
        }