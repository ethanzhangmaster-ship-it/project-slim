"""
E16.1 — Growth Action Sink (E13.3 Growth Decision Executor seam)

Implementations of the ``GrowthActionSink`` protocol. The Revenue Intelligence
Agent only *recommends* actions; the actual execution decision lives in the
E13.3 Growth Decision Executor. These sinks are the hand-off point:

* ``JsonlGrowthActionSink`` — durable append-only outbox (default, auditable)
* ``InMemoryGrowthActionSink`` — for tests / dry runs
* ``NullGrowthActionSink`` — explicitly do nothing (auto_execute=False default)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import GrowthAction


class JsonlGrowthActionSink:
    """Append-only JSONL outbox of recommended GrowthActions."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def submit(self, action: GrowthAction) -> bool:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(action.to_dict(), ensure_ascii=False) + "\n")
        return True

    def all(self) -> List[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out


class InMemoryGrowthActionSink:
    """Collects submitted actions in a list (for tests / dry runs)."""

    def __init__(self) -> None:
        self.submitted: List[GrowthAction] = []

    def submit(self, action: GrowthAction) -> bool:
        self.submitted.append(action)
        return True


class NullGrowthActionSink:
    """Accepts and discards actions (auto_execute=False default)."""

    def submit(self, action: GrowthAction) -> bool:
        return True


__all__ = [
    "JsonlGrowthActionSink",
    "InMemoryGrowthActionSink",
    "NullGrowthActionSink",
]
