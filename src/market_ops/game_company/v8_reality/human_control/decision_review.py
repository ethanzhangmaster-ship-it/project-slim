from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class DecisionStatus(Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class DecisionRecord:
    decision_id: str
    submitter: str
    decision_type: str
    content: Dict[str, Any] = field(default_factory=dict)
    status: DecisionStatus = DecisionStatus.PENDING
    submitted_at: datetime = field(default_factory=datetime.now)
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    approval_comments: Optional[str] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "submitter": self.submitter,
            "decision_type": self.decision_type,
            "content": self.content,
            "status": self.status.value,
            "submitted_at": self.submitted_at.isoformat(),
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "approval_comments": self.approval_comments,
            "rejection_reason": self.rejection_reason,
        }


class DecisionReview:
    def __init__(self):
        self._decisions: Dict[str, DecisionRecord] = {}
        self._pending_decisions: List[str] = []

    def submit_decision(self, decision: DecisionRecord) -> DecisionRecord:
        self._decisions[decision.decision_id] = decision
        if decision.status == DecisionStatus.PENDING:
            self._pending_decisions.append(decision.decision_id)
        return decision

    def review_decision(self, decision_id: str) -> bool:
        if decision_id not in self._decisions:
            return False
        decision = self._decisions[decision_id]
        if decision.status != DecisionStatus.PENDING:
            return False
        decision.status = DecisionStatus.UNDER_REVIEW
        decision.reviewer = "reviewer_admin"
        decision.reviewed_at = datetime.now()
        return True

    def approve_decision(self, decision_id: str, comments: str = "") -> bool:
        if decision_id not in self._decisions:
            return False
        decision = self._decisions[decision_id]
        if decision.status not in [DecisionStatus.PENDING, DecisionStatus.UNDER_REVIEW]:
            return False
        decision.status = DecisionStatus.APPROVED
        decision.approval_comments = comments
        if not decision.reviewer:
            decision.reviewer = "reviewer_admin"
        if not decision.reviewed_at:
            decision.reviewed_at = datetime.now()
        if decision_id in self._pending_decisions:
            self._pending_decisions.remove(decision_id)
        return True

    def reject_decision(self, decision_id: str, reason: str = "") -> bool:
        if decision_id not in self._decisions:
            return False
        decision = self._decisions[decision_id]
        if decision.status not in [DecisionStatus.PENDING, DecisionStatus.UNDER_REVIEW]:
            return False
        decision.status = DecisionStatus.REJECTED
        decision.rejection_reason = reason
        if not decision.reviewer:
            decision.reviewer = "reviewer_admin"
        if not decision.reviewed_at:
            decision.reviewed_at = datetime.now()
        if decision_id in self._pending_decisions:
            self._pending_decisions.remove(decision_id)
        return True

    def get_pending_decisions(self) -> List[DecisionRecord]:
        return [self._decisions[did] for did in self._pending_decisions]

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        return self._decisions.get(decision_id)

    def get_all_decisions(self) -> List[DecisionRecord]:
        return sorted(
            self._decisions.values(),
            key=lambda d: d.submitted_at,
            reverse=True
        )

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._decisions)
        pending = len(self._pending_decisions)
        under_review = sum(1 for d in self._decisions.values() if d.status == DecisionStatus.UNDER_REVIEW)
        approved = sum(1 for d in self._decisions.values() if d.status == DecisionStatus.APPROVED)
        rejected = sum(1 for d in self._decisions.values() if d.status == DecisionStatus.REJECTED)
        return {
            "total_decisions": total,
            "pending_decisions": pending,
            "under_review_decisions": under_review,
            "approved_decisions": approved,
            "rejected_decisions": rejected,
            "approval_rate": approved / (approved + rejected) if (approved + rejected) > 0 else 0,
        }