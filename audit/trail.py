"""
EP0.7 — Audit Trail: immutably record every agent decision and execution.

Critical for production AI systems: explain WHY every action was taken.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
from pathlib import Path


class ApprovalType(str, Enum):
    AUTO = "auto"
    HUMAN_CONFIRM = "human_confirm"
    HUMAN_DECIDE = "human_decide"


@dataclass
class DecisionRecord:
    agent: str
    action: str
    game_id: str
    reason: str
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision_id: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id or "",
            "agent": self.agent,
            "action": self.action,
            "game_id": self.game_id,
            "reason": self.reason,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "inputs": self.inputs,
        }


@dataclass
class ExecutionRecord:
    decision_id: str
    agent: str
    action: str
    success: bool
    duration_ms: float
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "agent": self.agent,
            "action": self.action,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ApprovalRecord:
    decision_id: str
    approver: str
    approved: bool
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "approver": self.approver,
            "approved": self.approved,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class AuditTrail:
    """Immutable audit log for all agent decisions.

    Usage::

        trail = AuditTrail(audit_dir="data/audit")
        trail.record_decision(DecisionRecord(agent="aso", action="update_screenshot", ...))
        trail.record_execution(ExecutionRecord(...))
        trail.record_approval(ApprovalRecord(...))

    All records are append-only JSONL files.
    """

    def __init__(self, audit_dir: str = "data/audit"):
        self.dir = Path(audit_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._decisions_file = self.dir / "decisions.jsonl"
        self._executions_file = self.dir / "executions.jsonl"
        self._approvals_file = self.dir / "approvals.jsonl"

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record_decision(self, record: DecisionRecord) -> None:
        self._append(self._decisions_file, record.to_dict())

    def record_execution(self, record: ExecutionRecord) -> None:
        self._append(self._executions_file, record.to_dict())

    def record_approval(self, record: ApprovalRecord) -> None:
        self._append(self._approvals_file, record.to_dict())

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def recent_decisions(self, limit: int = 50) -> List[Dict]:
        return self._tail(self._decisions_file, limit)

    def recent_executions(self, limit: int = 50) -> List[Dict]:
        return self._tail(self._executions_file, limit)

    def query_decisions(
        self, agent: Optional[str] = None, game_id: Optional[str] = None
    ) -> List[Dict]:
        results = []
        for record in self._read_all(self._decisions_file):
            if agent and record.get("agent") != agent:
                continue
            if game_id and record.get("game_id") != game_id:
                continue
            results.append(record)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append(self, path: Path, data: Dict) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, default=str, ensure_ascii=False) + "\n")

    def _tail(self, path: Path, limit: int) -> List[Dict]:
        results = []
        if not path.exists():
            return results
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        for line in lines[-limit:]:
            try:
                results.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
        return results

    def _read_all(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        results = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return results
