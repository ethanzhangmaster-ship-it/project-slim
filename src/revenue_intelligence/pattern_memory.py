"""
E16.1 — Pattern Memory (E13.4 Growth Memory seam)

A JSONL-backed implementation of the ``PatternMemory`` protocol. Historical
cases are stored as ``PatternMatch`` records and retrieved by similarity to a
live signal. This is the local, testable stand-in for the full E13.4 Growth
Memory; ``adapters.OperationRecordPatternMemory`` bridges the *real* operation
history in ``operation/memory``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import PatternMatch, resolve_action


class JsonlPatternMemory:
    """Append-only JSONL store of historical revenue patterns."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    # ------------------------------------------------------------------ #
    def add(self, pattern: PatternMatch, game_id: str = "") -> None:
        """Persist a pattern (optionally bound to a game)."""
        entry = pattern.to_dict()
        entry["game_id"] = game_id
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def all(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    # ------------------------------------------------------------------ #
    def search_similar(
        self, game_id: str, signal: Dict[str, Any], limit: int = 3
    ) -> List[PatternMatch]:
        entries = self.all()
        # scope to the game when we have game-specific cases
        if game_id:
            scoped = [e for e in entries if e.get("game_id") == game_id]
            if scoped:
                entries = scoped
        ranked = sorted(
            entries, key=lambda e: self._score(e, signal), reverse=True
        )
        return [self._from_entry(e) for e in ranked[:limit]]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _score(entry: Dict[str, Any], signal: Dict[str, Any]) -> float:
        """Base score = stored confidence, boosted by signal overlap."""
        score = float(entry.get("confidence", 0.0))
        sig_keys = set(signal.keys())
        ent_keys = set(entry.keys())
        overlap = len(sig_keys & ent_keys - {"confidence", "game_id"})
        return score + 0.05 * overlap

    @staticmethod
    def _from_entry(entry: Dict[str, Any]) -> PatternMatch:
        rec = entry.get("recommended_action")
        return PatternMatch(
            pattern_id=entry.get("pattern_id", ""),
            description=entry.get("description", ""),
            confidence=float(entry.get("confidence", 0.0)),
            similar_case=entry.get("similar_case", ""),
            recommended_action=resolve_action(rec) if rec else None,
            recommended_strategy=entry.get("recommended_strategy", ""),
            source=entry.get("source", "growth_memory"),
        )


__all__ = ["JsonlPatternMemory"]
