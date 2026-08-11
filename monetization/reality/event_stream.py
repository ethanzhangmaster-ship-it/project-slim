"""
E13.3.1 — Module 1: Event Stream Consumer
===========================================

A lightweight, append-only consumer for the GameFactory event stream.

Design
------
* Ingest events one-at-a-time or in batches.
* Optionally persists every event to a JSONL file (append mode) so a process
  crash / restart can `replay()` the stream — this is what makes the layer
  "continuous" rather than a one-shot batch job.
* No external dependencies, no database.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional


# Minimal envelope every GameFactory event is expected to carry.
_REQUIRED_FIELDS = ("event", "game", "platform", "timestamp_ms")


def _is_valid_envelope(event: dict) -> bool:
    return isinstance(event, dict) and all(k in event for k in _REQUIRED_FIELDS)


class GameEventStream:
    def __init__(self, persist_path: Optional[str | Path] = None):
        self._events: List[dict] = []
        self._persist_path: Optional[Path] = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self.replay(self._persist_path)

    # -- ingestion ------------------------------------------------------- #
    def ingest(self, event: dict) -> bool:
        if not _is_valid_envelope(event):
            return False
        self._events.append(event)
        if self._persist_path:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True

    def ingest_batch(self, events: Iterable[dict]) -> int:
        n = 0
        for e in events:
            if self.ingest(e):
                n += 1
        return n

    # -- access ---------------------------------------------------------- #
    def events(self) -> List[dict]:
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()

    # -- persistence ----------------------------------------------------- #
    def replay(self, path: str | Path) -> int:
        """Load a JSONL event log into the in-memory buffer (idempotent-ish:
        appends whatever is in the file). Returns #events loaded."""
        p = Path(path)
        if not p.exists():
            return 0
        n = 0
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _is_valid_envelope(ev):
                    self._events.append(ev)
                    n += 1
        return n

    def flush_log(self, path: str | Path) -> None:
        """Write the entire buffer to a fresh JSONL file (overwrites)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for e in self._events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
