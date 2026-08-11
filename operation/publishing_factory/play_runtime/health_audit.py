"""E13.5 — Health Agent audit log.

Every Vitals evaluation (regardless of gate stage) is appended to a JSONL
file so the morning briefing and the operator can see the latest health
board for every tracked package without re-calling the Reporting API.

Lean rule: append-only JSONL, no database. One line per evaluation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


# Default location: <launchforge>/data/play_runtime/health.jsonl
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "play_runtime"


def audit_path() -> Path:
    """Return the health audit file path (env-overridable for tests)."""
    env = os.environ.get("LAUNCHFORGE_PLAY_HEALTH")
    if env:
        return Path(env)
    return _DEFAULT_DIR / "health.jsonl"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append(report) -> None:
    """Persist one health evaluation as a JSONL line.

    ``report`` is duck-typed: anything exposing ``to_dict()`` (e.g. a
    :class:`HealthReport`) works. Avoids a circular import with
    ``health_agent`` (which imports this module).
    """
    path = audit_path()
    _ensure_parent(path)
    line = json.dumps(report.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def recent(limit: int = 200, since_iso: Optional[str] = None) -> List[Dict]:
    """Return the most recent ``limit`` health records (newest last)."""
    path = audit_path()
    if not path.exists():
        return []
    out: List[Dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if since_iso and rec.get("read_at", "") < since_iso:
                continue
            out.append(rec)
    return out[-limit:]


def last_24h() -> List[Dict]:
    """Health records from the last 24 hours."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return recent(limit=10_000, since_iso=cutoff)


def latest_board() -> Dict[str, Dict]:
    """Return the most recent evaluation per package (keyed by package)."""
    board: Dict[str, Dict] = {}
    for rec in recent(limit=10_000):
        board[rec.get("package_name")] = rec
    return board


__all__ = ["audit_path", "append", "recent", "last_24h", "latest_board"]
