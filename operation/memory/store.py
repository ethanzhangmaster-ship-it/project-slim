"""
E15.2.1 — Operation Memory Store

JSONL-backed persistent store for OperationRecords.
Supports append, query by game_id/operation/context, and summary aggregation.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .models import OperationRecord


class OperationMemoryStore:
    """Append-only JSONL store keyed by game_id."""

    def __init__(self, base_dir: str = "data/memory"):
        self._base_dir = os.path.abspath(base_dir)
        os.makedirs(self._base_dir, exist_ok=True)

    def _path(self, game_id: str) -> str:
        return os.path.join(self._base_dir, f"{game_id}.jsonl")

    def append(self, record: OperationRecord) -> None:
        """Append a record to the game's memory file."""
        with open(self._path(record.game_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def load(self, game_id: str) -> List[OperationRecord]:
        """Load all records for a game."""
        p = self._path(game_id)
        if not os.path.exists(p):
            return []
        records = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(OperationRecord.from_dict(json.loads(line)))
        return records

    def query(
        self,
        game_id: Optional[str] = None,
        operation: Optional[str] = None,
        provider: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[OperationRecord]:
        """Filtered query across games."""
        results: List[OperationRecord] = []
        if game_id:
            records = self.load(game_id)
        else:
            records = []
            for fn in sorted(os.listdir(self._base_dir)):
                if fn.endswith(".jsonl"):
                    records.extend(self.load(fn.replace(".jsonl", "")))

        for r in records:
            if operation and r.operation != operation:
                continue
            if provider and r.provider != provider:
                continue
            if r.confidence < min_confidence:
                continue
            results.append(r)

        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def find_similar(
        self, game_id: str, operation: str, context: Dict[str, Any], limit: int = 10
    ) -> List[OperationRecord]:
        """Find past operations with matching context keys."""
        records = self.load(game_id)
        results = []
        for r in records:
            if r.operation != operation:
                continue
            # Match on any shared context key
            shared = set(context.keys()) & set(r.context.keys())
            if not shared:
                continue
            match = all(context[k] == r.context[k] for k in shared)
            if match:
                results.append(r)
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def summary(self, game_id: str) -> Dict[str, Any]:
        """Aggregated summary of a game's operation memory."""
        records = self.load(game_id)
        if not records:
            return {"game_id": game_id, "total_operations": 0}

        ops = [r.operation for r in records]
        op_counts: Dict[str, int] = {}
        for o in ops:
            op_counts[o] = op_counts.get(o, 0) + 1

        success_rate = sum(1 for r in records if r.result_success) / len(records)
        avg_confidence = sum(r.confidence for r in records) / len(records)

        # Find top-performing operations by revenue impact
        profitable = [r for r in records if r.revenue_impact is not None and r.revenue_impact > 0]
        profitable.sort(key=lambda r: r.revenue_impact or 0, reverse=True)

        # Find most common failure operations
        failures = [r for r in records if not r.result_success]

        return {
            "game_id": game_id,
            "total_operations": len(records),
            "success_rate": round(success_rate, 3),
            "avg_confidence": round(avg_confidence, 3),
            "operation_counts": dict(sorted(op_counts.items(), key=lambda x: -x[1])),
            "top_profitable": [
                {"operation": r.operation, "impact_pct": r.revenue_impact, "confidence": r.confidence}
                for r in profitable[:5]
            ],
            "failure_count": len(failures),
            "recent_errors": [r.error for r in failures[-5:] if r.error],
        }
