from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    request_id: str
    requester: str
    request_type: str
    level: ApprovalLevel = ApprovalLevel.MEDIUM
    status: ApprovalStatus = ApprovalStatus.PENDING
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requester": self.requester,
            "request_type": self.request_type,
            "level": self.level.value,
            "status": self.status.value,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
        }


class ApprovalCenter:
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        self._pending_requests: List[str] = []

    def request_approval(self, request: ApprovalRequest) -> ApprovalRequest:
        self._requests[request.request_id] = request
        if request.status == ApprovalStatus.PENDING:
            self._pending_requests.append(request.request_id)
        return request

    def approve_request(self, request_id: str) -> bool:
        if request_id not in self._requests:
            return False
        request = self._requests[request_id]
        if request.status != ApprovalStatus.PENDING:
            return False
        request.status = ApprovalStatus.APPROVED
        request.approved_by = "system_admin"
        request.approved_at = datetime.now()
        if request_id in self._pending_requests:
            self._pending_requests.remove(request_id)
        return True

    def reject_request(self, request_id: str, reason: str = "") -> bool:
        if request_id not in self._requests:
            return False
        request = self._requests[request_id]
        if request.status != ApprovalStatus.PENDING:
            return False
        request.status = ApprovalStatus.REJECTED
        request.approved_by = "system_admin"
        request.approved_at = datetime.now()
        request.rejection_reason = reason
        if request_id in self._pending_requests:
            self._pending_requests.remove(request_id)
        return True

    def get_pending_requests(self) -> List[ApprovalRequest]:
        return [self._requests[rid] for rid in self._pending_requests]

    def get_request_history(self) -> List[ApprovalRequest]:
        return sorted(
            self._requests.values(),
            key=lambda r: r.created_at,
            reverse=True
        )

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._requests)
        pending = len(self._pending_requests)
        approved = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for r in self._requests.values() if r.status == ApprovalStatus.REJECTED)
        return {
            "total_requests": total,
            "pending_requests": pending,
            "approved_requests": approved,
            "rejected_requests": rejected,
            "approval_rate": approved / (approved + rejected) if (approved + rejected) > 0 else 0,
        }