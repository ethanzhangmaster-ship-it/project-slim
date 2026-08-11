"""E15.2.7 §10 — Player-level learning memory. JSONL, append-only."""
from __future__ import annotations
import json, os
from typing import Any, Dict, Optional
from datetime import date as _date

from operation.player_monetization.models import PlayerLearningRecord

DEFAULT_PATH = os.path.join("outputs", "player_monetization",
                            "player_learning.jsonl")


class PlayerLearningMemory:
    def __init__(self, path: str = DEFAULT_PATH) -> None:
        self.path = path

    def record(self, rec: PlayerLearningRecord) -> Dict[str, Any]:
        row = rec.to_dict()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def query(self, segment: Optional[str] = None,
              action: Optional[str] = None) -> Dict[str, Any]:
        rows = self._load()
        hits = [r for r in rows
                if (not segment or r.get("segment") == segment)
                and (not action or r.get("action") == action)]
        positive = [r for r in hits if r.get("decision") == "positive"]
        return {"precedents": len(hits),
                "positive_rate": round(len(positive)/len(hits), 2) if hits else 0.0,
                "rows": hits}

    def _load(self):
        if not os.path.exists(self.path): return []
        rows = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try: rows.append(json.loads(line.strip()))
                except: continue
        return rows
