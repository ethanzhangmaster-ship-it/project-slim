"""
E13.4.1 — Module 2: Decision Store
===================================

The persistent memory of the autonomous monetization loop. Pure-Python, no DB:
a JSONL file (append-only rows) backs an in-memory index for fast querying.

Design notes:
  * File store => survives process restarts, human-inspectable, trivially
    portable. No sqlite / no server (Lean architecture per E13.4.1 scope).
  * Each `DecisionRecord.to_dict()` is one JSON line.
  * Queries return lightweight filters over the loaded list; for very large
    corpora (100k+ rows) this can be upgraded to an indexed store without
    changing the public API.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from monetization.learning.models import DecisionRecord


class DecisionStore:
    """Append-only JSONL store + in-memory query index for DecisionRecords."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else None
        self._records: List[DecisionRecord] = []
        self._by_id: Dict[str, DecisionRecord] = {}
        if self.path and self.path.exists():
            self.load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def load(self) -> int:
        """Reload all rows from the backing JSONL file. Returns count.

        The in-memory index is reset first, so a reload of a corrupted or
        externally-changed file replaces (never merges with) stale state.
        """
        if not self.path or not self.path.exists():
            self._records = []
            self._by_id = {}
            return 0
        self._records = []
        self._by_id = {}
        n = 0
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = DecisionRecord.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
                self._records.append(rec)
                self._by_id[rec.decision_id] = rec
                n += 1
        return n

    def save(self) -> None:
        """Flush all records to the JSONL file (overwrite, sorted by created_at)."""
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self._records, key=lambda r: r.created_at)
        with self.path.open("w", encoding="utf-8") as fh:
            for rec in ordered:
                fh.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def append(self, record: DecisionRecord) -> None:
        """Add (or replace-by-id) a decision record and persist.

        A *new* id is appended as one JSON line (O(1) — the backing file is a
        JSONL log, so high-frequency writes stay cheap). A *duplicate* id
        (re-closing a loop with its actual outcome) is rare and triggers a full
        ordered rewrite via ``save()``.
        """
        if record.decision_id in self._by_id:
            # update in place (e.g. loop closed with actual outcome)
            idx = self._records.index(self._by_id[record.decision_id])
            self._records[idx] = record
            self._by_id[record.decision_id] = record
            self.save()
        else:
            self._records.append(record)
            self._by_id[record.decision_id] = record
            self._append_line(record)

    def _append_line(self, record: DecisionRecord) -> None:
        """Append a single JSON line to the backing file (O(1) write)."""
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def update(self, record: DecisionRecord) -> None:
        """Same as append (idempotent by decision_id)."""
        self.append(record)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get(self, decision_id: str) -> Optional[DecisionRecord]:
        return self._by_id.get(decision_id)

    def all(self) -> List[DecisionRecord]:
        return list(self._records)

    def count(self) -> int:
        return len(self._records)

    def by_strategy(self, strategy_type: str) -> List[DecisionRecord]:
        return [r for r in self._records if r.strategy_type == strategy_type]

    def by_opportunity_type(self, opportunity_type: str) -> List[DecisionRecord]:
        return [r for r in self._records if r.opportunity_type == opportunity_type]

    def by_segment(self, segment: dict) -> List[DecisionRecord]:
        """Records whose segment is a superset-match of the given keys."""
        out = []
        for r in self._records:
            ok = all(r.segment.get(k) == v for k, v in segment.items())
            if ok:
                out.append(r)
        return out

    def executed(self) -> List[DecisionRecord]:
        """Only records that were actually executed (mock or real)."""
        return [r for r in self._records if r.execution_status == "executed"]

    def closed(self) -> List[DecisionRecord]:
        """Only records whose loop is closed (actual outcome recorded)."""
        return [r for r in self._records if r.closed_loop and r.actual is not None]

    def to_dicts(self) -> List[dict]:
        return [r.to_dict() for r in self._records]
