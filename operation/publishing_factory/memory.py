"""
E15.1.1 — Publishing Memory
============================

JSONL-backed learning store. Records what WORKED in publishing so the
factory can bias future generation (mirrors the OptimizationMemory in
the Revenue OS — "what is effective").

Entries capture:
  - screenshot style -> store_cvr observed
  - keyword set -> impressions / installs observed
  - rejection reason -> fix that resolved it

Deterministic recall/summarize over the JSONL file.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PublishingMemoryEntry:
    game_id: str
    kind: str                 # "screenshot_style" | "keyword_set" | "reject_fix"
    key: str                  # e.g. genre+style, or rejection code
    outcome: str              # "good" | "bad" | "resolved"
    value: float = 0.0        # numeric signal (cvr / lift / 1.0)
    detail: str = ""
    genre: str = ""

    def to_dict(self) -> dict:
        return {"game_id": self.game_id, "kind": self.kind, "key": self.key,
                "outcome": self.outcome, "value": self.value,
                "detail": self.detail, "genre": self.genre}

    @classmethod
    def from_dict(cls, d: dict) -> "PublishingMemoryEntry":
        return cls(game_id=d.get("game_id", ""), kind=d.get("kind", ""),
                   key=d.get("key", ""), outcome=d.get("outcome", ""),
                   value=d.get("value", 0.0), detail=d.get("detail", ""),
                   genre=d.get("genre", ""))


class PublishingMemory:
    """Append-only JSONL memory of publishing effectiveness."""

    def __init__(self, path: str = "data/publishing_memory.jsonl"):
        self.path = path

    def record(self, entry: PublishingMemoryEntry) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def all(self) -> List[PublishingMemoryEntry]:
        out: List[PublishingMemoryEntry] = []
        if not os.path.exists(self.path):
            return out
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(PublishingMemoryEntry.from_dict(json.loads(line)))
        return out

    def recall(self, kind: str = None, genre: str = None,
               outcome: str = None) -> List[PublishingMemoryEntry]:
        return [e for e in self.all()
                if (kind is None or e.kind == kind)
                and (genre is None or e.genre == genre)
                and (outcome is None or e.outcome == outcome)]

    def best_style(self, genre: str) -> Optional[str]:
        """Return the screenshot-style key with the highest avg cvr."""
        entries = self.recall(kind="screenshot_style", genre=genre, outcome="good")
        if not entries:
            return None
        by_key: Dict[str, List[float]] = {}
        for e in entries:
            by_key.setdefault(e.key, []).append(e.value)
        best, best_avg = None, -1.0
        for k, vals in by_key.items():
            avg = sum(vals) / len(vals)
            if avg > best_avg:
                best, best_avg = k, avg
        return best

    def summarize(self, genre: str = None) -> dict:
        entries = self.recall(genre=genre)
        kinds: Dict[str, int] = {}
        for e in entries:
            kinds[e.kind] = kinds.get(e.kind, 0) + 1
        return {"total": len(entries), "by_kind": kinds,
                "best_style": self.best_style(genre) if genre else None}


__all__ = ["PublishingMemory", "PublishingMemoryEntry"]
