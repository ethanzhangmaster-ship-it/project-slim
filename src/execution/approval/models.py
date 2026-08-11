"""P2.3.1 Approval Request Model + P2.3.7 Authorization Token.

ApprovalRequest: the auditable record of "who asked to do what, and what happened".
ExecutionAuthorization: the token a provider MUST hold to execute in PRODUCTION.

Discipline:
- Pure dataclasses + constants. No I/O here.
- All timestamps are ISO-8601 UTC strings.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_EXPIRED = "EXPIRED"
STATUS_CANCELLED = "CANCELLED"

VALID_STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_EXPIRED,
    STATUS_CANCELLED,
)

# Terminal statuses: once reached, the request can no longer transition.
TERMINAL_STATUSES = (STATUS_REJECTED, STATUS_EXPIRED, STATUS_CANCELLED)

# Risk categories derived from numeric risk_level.
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def risk_category(risk_level: float) -> str:
    """Map numeric risk (0..1) to a category string."""
    try:
        value = float(risk_level)
    except (TypeError, ValueError):
        return RISK_HIGH
    if value < 0.3:
        return RISK_LOW
    if value < 0.6:
        return RISK_MEDIUM
    return RISK_HIGH


def impact_float(value: Any) -> float:
    """Best-effort conversion of expected_impact to float (default 0.0)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_str(value: Any) -> str:
    """Normalize str-Enum members to their value (py3.11 str() pitfall)."""
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------------------
# ApprovalRequest
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    """A single approval request tied to one ExecutionRequest."""

    execution_request_id: str
    intent_id: str
    action: str
    domain: str
    target: str
    risk_level: str = RISK_MEDIUM
    expected_impact: float = 0.0
    confidence: float = 0.0
    requested_by: str = "system"
    status: str = STATUS_PENDING
    approval_id: str = ""
    created_at: str = ""
    resolved_at: Optional[str] = None
    resolved_by: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.approval_id:
            self.approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid approval status: {self.status}")

    # -- state helpers -----------------------------------------------------

    @property
    def is_pending(self) -> bool:
        return self.status == STATUS_PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == STATUS_APPROVED

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "execution_request_id": self.execution_request_id,
            "intent_id": self.intent_id,
            "action": _as_str(self.action),
            "domain": _as_str(self.domain),
            "target": self.target,
            "risk_level": self.risk_level,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "requested_by": self.requested_by,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        return cls(
            execution_request_id=str(data.get("execution_request_id", "")),
            intent_id=str(data.get("intent_id", "")),
            action=str(data.get("action", "")),
            domain=str(data.get("domain", "")),
            target=str(data.get("target", "")),
            risk_level=str(data.get("risk_level", RISK_MEDIUM)),
            expected_impact=impact_float(data.get("expected_impact", 0.0)),
            confidence=impact_float(data.get("confidence", 0.0)),
            requested_by=str(data.get("requested_by", "system")),
            status=str(data.get("status", STATUS_PENDING)),
            approval_id=str(data.get("approval_id", "")),
            created_at=str(data.get("created_at", "")),
            resolved_at=data.get("resolved_at"),
            resolved_by=str(data.get("resolved_by", "")),
            reason=str(data.get("reason", "")),
        )


# ---------------------------------------------------------------------------
# ExecutionAuthorization (P2.3.7)
# ---------------------------------------------------------------------------

DEFAULT_AUTHORIZATION_TTL_HOURS = 24


@dataclass
class ExecutionAuthorization:
    """Token proving that a specific action was approved by a human/policy.

    A provider (via the router's AuthorizationGate) MUST verify:
    - allowed_action matches the action being executed (Rule 2)
    - expires_at has not passed (Rule 3)
    - the approval_id has not been consumed already (Rule 4)
    """

    approval_id: str
    approved_by: str
    allowed_action: str
    approved_at: str = ""
    expires_at: str = ""

    def __post_init__(self) -> None:
        if not self.approved_at:
            self.approved_at = _now_iso()
        if not self.expires_at:
            base = datetime.strptime(self.approved_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            self.expires_at = (
                base + timedelta(hours=DEFAULT_AUTHORIZATION_TTL_HOURS)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

    def is_expired(self, now: Optional[str] = None) -> bool:
        current = now or _now_iso()
        return current >= self.expires_at

    def allows(self, action: str) -> bool:
        return bool(action) and action == self.allowed_action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "allowed_action": _as_str(self.allowed_action),
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionAuthorization":
        return cls(
            approval_id=str(data.get("approval_id", "")),
            approved_by=str(data.get("approved_by", "")),
            allowed_action=str(data.get("allowed_action", "")),
            approved_at=str(data.get("approved_at", "")),
            expires_at=str(data.get("expires_at", "")),
        )
