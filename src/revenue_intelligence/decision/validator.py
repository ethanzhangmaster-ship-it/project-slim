"""
E16.1.1 — Decision Validator (the Confidence Gate enforcer)

Consumes a ``GrowthAction`` plus its simulation and historical experience stats,
produces a ``GrowthDecision`` (score + route), and *enforces* the route:

    AUTO          -> submit to the Growth Action Sink (E13.3 Executor seam)
    HUMAN_QUEUE   -> enqueue into the human Approval Queue (JSONL)
    RECORD_ONLY   -> audit only, nothing executed or queued

Every decision is written to a JSONL audit trail for full traceability. The
human queue supports ``approve`` / ``reject`` which, on approval, submit the
action to the sink -- closing the human-in-the-loop branch.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..experience import JsonlRevenueExperienceStore
from ..models import GrowthAction, GrowthActionSink
from .policy import ApprovalRoute, DecisionPolicy, GrowthDecisionScore


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GrowthDecision:
    """The gated outcome of one action."""
    action: GrowthAction
    score: GrowthDecisionScore
    approval: ApprovalRoute
    executed: bool = False
    queued: bool = False
    simulation: Optional[Dict[str, Any]] = None
    audit_id: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "score": self.score.to_dict(),
            "approval": self.approval.value,
            "executed": self.executed,
            "queued": self.queued,
            "simulation": self.simulation,
            "audit_id": self.audit_id,
            "note": self.note,
        }


class JsonlApprovalQueue:
    """Human-in-the-loop approval outbox for mid-confidence decisions."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def enqueue(self, decision: GrowthDecision) -> None:
        entry = decision.to_dict()
        entry["status"] = "pending"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def pending(self) -> List[Dict[str, Any]]:
        return [e for e in self._all() if e.get("status") == "pending"]

    def get(self, audit_id: str) -> Optional[Dict[str, Any]]:
        for e in self._all():
            if e.get("audit_id") == audit_id:
                return e
        return None

    def has_resolution(self, audit_id: str) -> bool:
        return any(
            e.get("kind") == "resolution" and e.get("audit_id") == audit_id
            for e in self._all()
        )

    def resolve(
        self, audit_id: str, status: str, *, executed: bool = False
    ) -> None:
        rec = {
            "audit_id": audit_id,
            "status": status,
            "executed": executed,
            "kind": "resolution",
            "resolved_at": _now().isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class DecisionValidator:
    """Enforces the three-tier confidence gate and routes each action."""

    def __init__(
        self,
        policy: Optional[DecisionPolicy] = None,
        action_sink: Optional[GrowthActionSink] = None,
        approval_queue: Optional[JsonlApprovalQueue] = None,
        experience_store: Optional[JsonlRevenueExperienceStore] = None,
        audit_path: Optional[str] = None,
    ):
        self.policy = policy or DecisionPolicy()
        self.action_sink = action_sink
        self.approval_queue = approval_queue
        self.experience_store = experience_store
        self.audit_path = Path(audit_path) if audit_path else None
        if self.audit_path:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.audit_path.exists():
                self.audit_path.write_text("", encoding="utf-8")

    # ------------------------------------------------------------------ #
    def validate(
        self,
        action: GrowthAction,
        simulation: Optional[Any] = None,
        experience_stats: Optional[Dict[str, Any]] = None,
    ) -> GrowthDecision:
        exp_stats = experience_stats or {}
        sample_size = int(exp_stats.get("n", 0))
        success_rate = float(exp_stats.get("success_rate", 0.0))
        score = self.policy.score(
            action, sample_size=sample_size, success_rate=success_rate
        )
        decision = GrowthDecision(
            action=action,
            score=score,
            approval=score.approval,
            simulation=simulation.to_dict() if simulation is not None else None,
            audit_id=self._audit_id(),
            note=score.reason,
        )
        self._route(decision)
        self._audit(decision, "validate")
        return decision

    # ------------------------------------------------------------------ #
    def _route(self, decision: GrowthDecision) -> None:
        if decision.approval == ApprovalRoute.AUTO:
            if self.action_sink is not None:
                decision.executed = bool(self.action_sink.submit(decision.action))
        elif decision.approval == ApprovalRoute.HUMAN_QUEUE:
            decision.queued = True
            if self.approval_queue is not None:
                self.approval_queue.enqueue(decision)
        else:  # RECORD_ONLY
            # audited only; nothing executed or queued
            decision.queued = False
            decision.executed = False

    # ------------------------------------------------------------------ #
    def approve(self, audit_id: str) -> bool:
        if self.approval_queue is None:
            return False
        entry = self.approval_queue.get(audit_id)
        if entry is None or entry.get("status") != "pending":
            return False
        if self.approval_queue.has_resolution(audit_id):
            return False
        executed = False
        if self.action_sink is not None:
            action = GrowthAction.from_dict(entry["action"])
            executed = bool(self.action_sink.submit(action))
        self.approval_queue.resolve(audit_id, "approved", executed=executed)
        self._audit_resolved(audit_id, "approved", executed)
        return True

    def reject(self, audit_id: str) -> bool:
        if self.approval_queue is None:
            return False
        entry = self.approval_queue.get(audit_id)
        if entry is None or entry.get("status") != "pending":
            return False
        if self.approval_queue.has_resolution(audit_id):
            return False
        self.approval_queue.resolve(audit_id, "rejected", executed=False)
        self._audit_resolved(audit_id, "rejected", False)
        return True

    # ------------------------------------------------------------------ #
    @staticmethod
    def _audit_id() -> str:
        return f"dec_{uuid.uuid4().hex[:12]}"

    def _audit(self, decision: GrowthDecision, event: str) -> None:
        if not self.audit_path:
            return
        rec = {
            "event": event,
            "audit_id": decision.audit_id,
            "action": getattr(
                decision.action.action, "value", decision.action.action
            ),
            "game_id": decision.action.game_id,
            "approval": decision.approval.value,
            "executed": decision.executed,
            "queued": decision.queued,
            "ts": _now().isoformat(),
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _audit_resolved(self, audit_id: str, status: str, executed: bool) -> None:
        if not self.audit_path:
            return
        rec = {
            "event": "resolve",
            "audit_id": audit_id,
            "status": status,
            "executed": executed,
            "ts": _now().isoformat(),
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


__all__ = [
    "GrowthDecision",
    "JsonlApprovalQueue",
    "DecisionValidator",
]
