"""E13.5 — Listing Experiment audit (JSONL, append-only).

The Experiment Agent appends one record per experiment event (proposed /
created / running / ended / winner-recommended). The morning briefing reads
this file to render the ASO section — zero network, zero writes at read time.

Duck-typing: ``append`` calls ``record.to_dict()`` so the audit module never
imports the agent (avoids a circular import with ``connector``/``models``).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


def _audit_path() -> str:
    # explicit override (used by tests for isolation)
    override = os.environ.get("LAUNCHFORGE_PLAY_EXPERIMENTS")
    if override:
        return override
    root = os.environ.get("LAUNCHFORGE_ROOT")
    if root:
        base = root
    else:
        # play_runtime/ -> operation/ -> launchforge/
        here = os.path.dirname(os.path.abspath(__file__))
        base = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(base, "data", "play_runtime", "experiments.jsonl")


def append(record: Any) -> None:
    """Persist one experiment record. ``record`` must expose ``.to_dict()``."""
    path = _audit_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(record.to_dict(), ensure_ascii=False, default=str)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_all() -> List[Dict[str, Any]]:
    path = _audit_path()
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def active_experiments() -> List[Dict[str, Any]]:
    """Experiments whose latest recorded state is still running."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in read_all():
        eid = r.get("experiment_id") or r.get("name")
        if eid is None:
            continue
        # keep the most recent record for each experiment
        prev = by_id.get(eid)
        if prev is None or r.get("recorded_at", "") >= prev.get("recorded_at", ""):
            by_id[eid] = r
    return [r for r in by_id.values()
            if r.get("status") in ("proposed", "running", "created")]


def summary_by_package() -> Dict[str, Dict[str, int]]:
    """Aggregate event counts per package for the morning digest."""
    agg: Dict[str, Dict[str, int]] = {}
    for r in read_all():
        pkg = r.get("package_name") or "(unknown)"
        bucket = agg.setdefault(pkg, {
            "proposed": 0, "created": 0, "running": 0,
            "ended": 0, "winner": 0})
        st = r.get("status")
        if st in bucket:
            bucket[st] += 1
        # a winner *recommendation* also counts toward the winner column
        if r.get("recommendation") == "promote_variant":
            bucket["winner"] += 1
    return agg


__all__ = ["append", "read_all", "active_experiments", "summary_by_package"]
