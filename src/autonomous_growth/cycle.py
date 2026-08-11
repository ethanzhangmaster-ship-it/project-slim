"""P4.2 resumable Autonomous Growth Cycle."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class CycleStage(str, Enum):
    OBSERVE = "observe"
    UNDERSTAND = "understand"
    REMEMBER = "remember"
    DECIDE = "decide"
    SIMULATE = "simulate"
    APPROVE = "approve"
    EXECUTE = "execute"
    MEASURE = "measure"
    LEARN = "learn"
    IMPROVE = "improve"
    COMPLETE = "complete"


ORDER = list(CycleStage)


@dataclass
class CycleState:
    cycle_id: str
    business_date: str
    stage: CycleStage = CycleStage.OBSERVE
    completed_stages: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    blocked_reason: str = ""
    failed_stage: str = ""
    revision: int = 0

    def to_dict(self):
        return {"cycle_id": self.cycle_id, "business_date": self.business_date,
                "stage": self.stage.value, "completed_stages": list(self.completed_stages),
                "artifacts": dict(self.artifacts), "blocked_reason": self.blocked_reason,
                "failed_stage": self.failed_stage, "revision": self.revision}

    @classmethod
    def from_dict(cls, data):
        return cls(str(data["cycle_id"]), str(data["business_date"]),
                   CycleStage(data.get("stage", "observe")),
                   list(data.get("completed_stages") or []),
                   dict(data.get("artifacts") or {}), str(data.get("blocked_reason", "")),
                   str(data.get("failed_stage", "")), int(data.get("revision", 0)))


class CycleStore:
    """Append-only state journal; latest revision wins on recovery."""
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, state: CycleState) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(state.to_dict(), ensure_ascii=False) + "\n")

    def load(self, cycle_id: str) -> Optional[CycleState]:
        if not self.path.exists(): return None
        latest = None
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    data = json.loads(line)
                    if data.get("cycle_id") == cycle_id:
                        candidate = CycleState.from_dict(data)
                        if latest is None or candidate.revision >= latest.revision:
                            latest = candidate
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return latest


class AutonomousCycle:
    def __init__(self, store: CycleStore, handlers: Dict[str, Callable[..., Any]],
                 production: bool = False):
        self.store, self.handlers, self.production = store, dict(handlers), production

    def run(self, cycle_id: str, business_date: str, *, approval_present: bool = False) -> CycleState:
        state = self.store.load(cycle_id) or CycleState(cycle_id, business_date)
        while state.stage != CycleStage.COMPLETE:
            stage = state.stage
            if stage == CycleStage.APPROVE and self.production and not approval_present:
                state.blocked_reason = "production approval missing"
                self._save(state)
                return state
            handler = self.handlers.get(stage.value)
            if handler is None:
                state.blocked_reason = f"handler missing: {stage.value}"
                self._save(state)
                return state
            try:
                result = handler(state=state, artifacts=dict(state.artifacts))
                state.artifacts[stage.value] = result
                if stage.value not in state.completed_stages:
                    state.completed_stages.append(stage.value)
                state.blocked_reason = ""
                state.failed_stage = ""
                state.stage = ORDER[ORDER.index(stage) + 1]
                self._save(state)
            except Exception as exc:
                state.failed_stage = stage.value
                state.blocked_reason = f"{type(exc).__name__}"
                self._save(state)
                return state
        return state

    def _save(self, state):
        state.revision += 1
        self.store.save(state)


__all__ = ["CycleStage", "CycleState", "CycleStore", "AutonomousCycle", "ORDER"]
