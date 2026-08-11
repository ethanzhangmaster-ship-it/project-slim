"""E15.2 Decision 数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlayAction(Enum):
    INCREASE_ROLLOUT = "increase_rollout"
    HOLD_ROLLOUT = "hold_rollout"
    HALT_RELEASE = "halt_release"
    REQUEST_REVIEW = "request_review"
    PROMOTE_TESTER = "promote_tester"
    UPDATE_LISTING = "update_listing"


@dataclass
class PlayDecision:
    package_name: str
    action: PlayAction
    confidence: float  # 0.0-1.0
    reason: str
    rule_name: str = ""
    created_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "action": self.action.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "rule_name": self.rule_name,
            "created_at": self.created_at.isoformat(),
        }
