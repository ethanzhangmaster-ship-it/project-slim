"""E13.5 — Review Agent audit log.

Every review evaluation (classification + recommended reply, and any posted
reply) is appended to a JSONL file so the morning briefing and the operator
can see the latest review-intelligence board per package without re-calling
the Reviews API. The ``seen_ids`` / ``replied_ids`` helpers power the
idempotency guard so the agent never double-replies a review.

Lean rule: append-only JSONL, no database. One line per evaluated review.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


# Default location: <launchforge>/data/play_runtime/reviews.jsonl
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "play_runtime"


def audit_path() -> Path:
    """Return the review audit file path (env-overridable for tests)."""
    env = os.environ.get("LAUNCHFORGE_PLAY_REVIEWS")
    if env:
        return Path(env)
    return _DEFAULT_DIR / "reviews.jsonl"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append(report) -> None:
    """Persist one review evaluation as a JSONL line.

    ``report`` is duck-typed: anything exposing ``to_dict()`` (e.g. a
    :class:`ReviewReport`) works. Avoids a circular import with
    ``review_agent`` (which imports this module).
    """
    path = audit_path()
    _ensure_parent(path)
    line = json.dumps(report.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _all() -> List[Dict]:
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
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return out


def seen_ids() -> set:
    """All review_ids ever evaluated (idempotency guard)."""
    return {r.get("review_id") for r in _all() if r.get("review_id")}


def replied_ids() -> set:
    """Review_ids we have already posted a reply to."""
    return {r.get("review_id") for r in _all()
            if r.get("review_id") and r.get("replied")}


def recent(limit: int = 200, since_iso: Optional[str] = None) -> List[Dict]:
    """Return the most recent ``limit`` review records (newest last)."""
    out = _all()
    if since_iso:
        out = [r for r in out if r.get("evaluated_at", "") >= since_iso]
    return out[-limit:]


def last_24h() -> List[Dict]:
    """Review records from the last 24 hours."""
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    return recent(limit=10_000, since_iso=cutoff)


def summary_by_package() -> Dict[str, Dict[str, int]]:
    """Aggregate category / reply counts per package.

    Returns ``{pkg: {"total", "crash", "bug", "complaint", "question",
    "praise", "ignore", "needs_reply", "replied"}}``.
    """
    board: Dict[str, Dict[str, int]] = {}
    for r in _all():
        pkg = r.get("package_name", "?")
        agg = board.setdefault(pkg, {
            "total": 0, "crash": 0, "bug": 0, "complaint": 0,
            "question": 0, "praise": 0, "ignore": 0,
            "needs_reply": 0, "replied": 0,
        })
        agg["total"] += 1
        cat = r.get("category", "ignore")
        if cat in agg:
            agg[cat] += 1
        if r.get("needs_reply"):
            agg["needs_reply"] += 1
        if r.get("replied"):
            agg["replied"] += 1
    return board


__all__ = ["audit_path", "append", "seen_ids", "replied_ids",
           "recent", "last_24h", "summary_by_package"]
