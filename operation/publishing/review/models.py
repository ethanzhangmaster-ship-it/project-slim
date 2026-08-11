"""
E15.1.6 — Review Intelligence models
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ReviewRejectEvent:
    store: str                                   # "google_play" | "app_store"
    game_id: str
    rejection_code: str                          # e.g. "Guideline 4.3", "Policy:Privacy"
    reason: str = ""
    affected_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "store": self.store, "game_id": self.game_id,
            "rejection_code": self.rejection_code, "reason": self.reason,
            "affected_fields": self.affected_fields,
        }


@dataclass
class ReviewFixPlan:
    issue: str
    cause: str
    fix_actions: List[str] = field(default_factory=list)
    priority: str = "medium"                     # high | medium | low

    def to_dict(self) -> dict:
        return {
            "issue": self.issue, "cause": self.cause,
            "fix_actions": self.fix_actions, "priority": self.priority,
        }


__all__ = ["ReviewRejectEvent", "ReviewFixPlan"]
