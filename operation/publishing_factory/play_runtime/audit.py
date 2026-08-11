"""E13.5 — Play Runtime audit log.

Every routed operation (regardless of stage) is appended to a JSONL file
so the morning briefing and the operator can replay exactly what the
system proposed / simulated / executed against the real console.

Lean rule: append-only JSONL, no database. One line per event.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from operation.publishing_factory.play_runtime.models import PlayResult

# Default location: <launchforge>/data/play_runtime/audit.jsonl
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "play_runtime"


def audit_path() -> Path:
    """Return the audit file path (env-overridable for tests)."""
    import os
    env = os.environ.get("LAUNCHFORGE_PLAY_AUDIT")
    if env:
        return Path(env)
    return _DEFAULT_DIR / "audit.jsonl"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append(result: PlayResult) -> None:
    """Persist one operation result as a JSONL line."""
    path = audit_path()
    _ensure_parent(path)
    line = json.dumps(result.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def recent(limit: int = 50, since_iso: Optional[str] = None) -> List[Dict]:
    """Return the most recent ``limit`` audit records (newest last)."""
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
            if since_iso and rec.get("at", "") < since_iso:
                continue
            out.append(rec)
    return out[-limit:]


def last_24h() -> List[Dict]:
    """Audit records from the last 24 hours."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return recent(limit=10_000, since_iso=cutoff)


__all__ = ["audit_path", "append", "recent", "last_24h"]
