"""
E16.1.1 — Revenue Experience Memory

Lets the agent answer the closed-loop question: *"did this decision make money
before?"*

A ``RevenueExperience`` records the *outcome* of a (real or simulated) decision:
which game, which action, why, the before/after revenue state (focused on ROAS),
and a computed ``reward`` + ``success`` flag. ``JsonlRevenueExperienceStore``
persists these durably and answers aggregate queries (``success_rate``,
``avg_reward``) that feed back into the Decision Policy's risk grade -- turning
the agent from a recommender into a learner.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import RevenueAction, RevenueSnapshot


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RevenuePoint:
    """A minimal before/after revenue snapshot focused on the money levers."""
    roas: float = 0.0
    revenue_total: float = 0.0
    spend: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "roas": round(self.roas, 4),
            "revenue_total": round(self.revenue_total, 4),
            "spend": round(self.spend, 4),
        }

    @classmethod
    def from_snapshot(cls, s: RevenueSnapshot) -> "RevenuePoint":
        spend = s.spend or 0.0
        rev = s.revenue_total or 0.0
        roas = s.roas if s.roas else (rev / spend if spend > 0 else 0.0)
        return cls(roas=roas, revenue_total=rev, spend=spend)


@dataclass
class RevenueExperience:
    """One recorded outcome of a decision (the "Result" in the loop)."""
    game_id: str
    action: Any  # str-Enum member (RevenueAction / EconomyAction / ...) or str
    reason: str
    before: RevenuePoint
    after: RevenuePoint
    reward: float = 0.0
    success: bool = False
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "action": getattr(self.action, "value", self.action),
            "reason": self.reason,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "reward": round(self.reward, 4),
            "success": self.success,
            "created_at": self.created_at.isoformat(),
        }


def compute_reward(exp: RevenueExperience) -> "tuple[float, bool]":
    """Reward = ROAS improvement (primary), revenue lift (fallback).

    Returns ``(reward, success)`` where ``reward`` is a relative delta and
    ``success`` is ``reward > 0``.
    """
    b, a = exp.before, exp.after
    if b.roas > 0 and a.roas > 0:
        reward = (a.roas - b.roas) / b.roas
    elif b.roas == 0 and a.roas > 0:
        reward = 1.0  # went from no return to a positive return
    elif b.revenue_total > 0:
        reward = (a.revenue_total - b.revenue_total) / b.revenue_total
    elif a.revenue_total > 0:
        reward = 1.0
    else:
        reward = 0.0
    return reward, reward > 0.0


class JsonlRevenueExperienceStore:
    """Append-only JSONL store of decision outcomes (Revenue Memory)."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def add(self, exp: RevenueExperience) -> None:
        reward, success = compute_reward(exp)
        exp.reward = reward
        exp.success = success
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def for_game_action(
        self, game_id: str, action: Union[RevenueAction, str, Any]
    ) -> List[Dict[str, Any]]:
        action_value = getattr(action, "value", action)
        return [
            e
            for e in self.all()
            if e.get("game_id") == game_id and e.get("action") == action_value
        ]

    def stats(
        self, game_id: str, action: Union[RevenueAction, str, Any]
    ) -> Dict[str, Any]:
        rows = self.for_game_action(game_id, action)
        n = len(rows)
        if n == 0:
            return {"n": 0, "success_rate": 0.0, "avg_reward": 0.0}
        successes = sum(1 for r in rows if r.get("success"))
        avg_reward = sum(float(r.get("reward", 0.0)) for r in rows) / n
        return {
            "n": n,
            "success_rate": round(successes / n, 4),
            "avg_reward": round(avg_reward, 4),
        }


__all__ = [
    "RevenuePoint",
    "RevenueExperience",
    "compute_reward",
    "JsonlRevenueExperienceStore",
]
