"""
E14.2 — Module 3: Structured Runtime Event Log
===============================================

NOT a free-form log file. Every runtime event is one structured JSON record
with a fixed schema:

    {
      "event":   "strategy_executed",   # enum-ish string
      "game":    "word_quest",
      "level":   "info",                 # info | warning | critical
      "timestamp": "2026-07-23T10:00:00+00:00",
      "meta":    { ... arbitrary structured context ... }
    }

These records are line-delimited JSON (JSONL) so they can be tailed into
Grafana / Datadog / CloudWatch later without re-parsing free text.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


# Canonical runtime event names
EVENT_CYCLE_START = "cycle_start"
EVENT_CYCLE_DONE = "cycle_done"
EVENT_STRATEGY_EXECUTED = "strategy_executed"
EVENT_STRATEGY_EXPERIMENTED = "strategy_experimented"
EVENT_STRATEGY_BLOCKED = "strategy_blocked"
EVENT_CHECKPOINT_SAVED = "checkpoint_saved"
EVENT_CHECKPOINT_RESTORED = "checkpoint_restored"
EVENT_AGENT_CRASH = "agent_crash"
EVENT_AGENT_RESTART = "agent_restart"
EVENT_AGENT_DEGRADED = "agent_degraded"
EVENT_EXECUTION_DISABLED = "execution_disabled"
EVENT_HEALTH_STALL = "health_stall"
EVENT_HEALTH_FAILURE_RATE = "health_failure_rate"
EVENT_STORE_CORRUPTED = "store_corrupted"
EVENT_STORE_RESTORED = "store_restored"


@dataclass
class RuntimeEvent:
    event: str
    game: str = ""
    level: str = "info"                # info | warning | critical
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class EventLogger:
    """Append-only, structured JSONL event sink (plus in-memory ring)."""

    def __init__(self, path: Optional[str] = None, ring_size: int = 2000):
        self.path = Path(path) if path else None
        self._ring: List[RuntimeEvent] = []
        self._ring_size = ring_size

    # ------------------------------------------------------------------ #
    def log(self, event: str, game: str = "", level: str = "info",
            **meta) -> RuntimeEvent:
        ev = RuntimeEvent(event=event, game=game, level=level, meta=meta)
        self._ring.append(ev)
        if len(self._ring) > self._ring_size:
            self._ring = self._ring[-self._ring_size:]
        if self.path is not None:
            self._append_file(ev)
        return ev

    def _append_file(self, ev: RuntimeEvent) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            pass  # logging must never crash the runtime

    # ------------------------------------------------------------------ #
    def recent(self, n: int = 50, game: str = "") -> List[RuntimeEvent]:
        evs = [e for e in self._ring if (not game or e.game == game)]
        return evs[-n:]

    def count(self) -> int:
        return len(self._ring)

    def to_dicts(self) -> List[dict]:
        return [e.to_dict() for e in self._ring]

    def flush(self) -> None:
        # ring is already durable per-event when a path is set; nothing buffered.
        pass


__all__ = [
    "RuntimeEvent", "EventLogger",
    "EVENT_CYCLE_START", "EVENT_CYCLE_DONE", "EVENT_STRATEGY_EXECUTED",
    "EVENT_STRATEGY_EXPERIMENTED", "EVENT_STRATEGY_BLOCKED",
    "EVENT_CHECKPOINT_SAVED", "EVENT_CHECKPOINT_RESTORED", "EVENT_AGENT_CRASH",
    "EVENT_AGENT_RESTART", "EVENT_AGENT_DEGRADED", "EVENT_EXECUTION_DISABLED",
    "EVENT_HEALTH_STALL", "EVENT_HEALTH_FAILURE_RATE", "EVENT_STORE_CORRUPTED",
    "EVENT_STORE_RESTORED",
]
