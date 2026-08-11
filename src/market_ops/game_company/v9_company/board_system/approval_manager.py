from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional, Dict
import uuid


class ApprovalLevel(Enum):
    AUTO = "auto"
    MANAGER = "manager"
    DIRECTOR = "director"
    C_LEVEL = "c_level"
    BOARD = "board"


@dataclass
class ApprovalCriteria:
    criteria_id: str
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    required_level: ApprovalLevel = ApprovalLevel.MANAGER
    departments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "criteria_id": self.criteria_id,
            "min_amount": self.min_amount,
            "max_amount": self.max_amount,
            "required_level": self.required_level.value,
            "departments": self.departments,
        }


@dataclass
class ApprovalRequest:
    request_id: str
    requester: str
    title: str
    description: str
    amount: Optional[float] = None
    level: ApprovalLevel = ApprovalLevel.MANAGER
    status: str = "pending"
    submitted_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "requester": self.requester,
            "title": self.title,
            "description": self.description,
            "amount": self.amount,
            "level": self.level.value,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat(),
        }


@dataclass
class ApprovalRecord:
    record_id: str
    request_id: str
    approver: str
    action: str
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "request_id": self.request_id,
            "approver": self.approver,
            "action": self.action,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }


class ApprovalManager:
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._records: Dict[str, ApprovalRecord] = {}

    def submit_request(self, request: ApprovalRequest) -> ApprovalRequest:
        self._requests[request.request_id] = request
        return request

    def approve_request(self, request_id: str, approver: str = "System") -> Optional[ApprovalRequest]:
        req = self._requests.get(request_id)
        if req is None:
            return None
        req.status = "approved"
        record = ApprovalRecord(
            record_id=str(uuid.uuid4()),
            request_id=request_id,
            approver=approver,
            action="approved",
        )
        self._records[record.record_id] = record
        return req

    def reject_request(self, request_id: str, reason: str, approver: str = "System") -> Optional[ApprovalRequest]:
        req = self._requests.get(request_id)
        if req is None:
            return None
        req.status = "rejected"
        record = ApprovalRecord(
            record_id=str(uuid.uuid4()),
            request_id=request_id,
            approver=approver,
            action="rejected",
            reason=reason,
        )
        self._records[record.record_id] = record
        return req

    def get_pending_approvals(self) -> List[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "pending"]

    def get_approval_history(self) -> List[ApprovalRecord]:
        return list(self._records.values())

    def get_stats(self) -> Dict:
        total = len(self._requests)
        pending = sum(1 for r in self._requests.values() if r.status == "pending")
        approved = sum(1 for r in self._requests.values() if r.status == "approved")
        rejected = sum(1 for r in self._requests.values() if r.status == "rejected")
        return {
            "total_requests": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(approved / total, 2) if total else 0.0,
        }
