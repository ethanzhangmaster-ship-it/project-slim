"""P3.6.4 GovernanceStore — writer-lineage adapter."""
from __future__ import annotations

from typing import Any, Dict, Iterable


class GovernanceStore:
    def __init__(self, recorder: Any = None) -> None:
        self.recorder = recorder

    @property
    def real_api_called(self) -> bool:
        return False

    def save(self, record: Any) -> Dict[str, int]:
        if self.recorder is None:
            return {"nodes_added": 0, "edges_added": 0}
        try:
            return self.recorder.govern_record(record)
        except Exception:
            return {"nodes_added": 0, "edges_added": 0}

    def save_all(self, records: Iterable[Any]) -> Dict[str, int]:
        total = {"nodes_added": 0, "edges_added": 0}
        for record in records or []:
            counts = self.save(record)
            total["nodes_added"] += int(counts.get("nodes_added", 0))
            total["edges_added"] += int(counts.get("edges_added", 0))
        return total


__all__ = ["GovernanceStore"]
