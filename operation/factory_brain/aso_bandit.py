"""
E15.1.2 — ASO Bandit
=====================

Deterministic explore-then-commit bandit over store-listing variants
(title / icon / screenshot_set), mirroring the Creative Evolution idea:

    variant A live -> observe CVR -> variant B live -> observe CVR
    -> winner -> PublishingMemory ("what works")

State is a JSONL trial log (append-only). CVR observations are fed in
by the operator (or later by store-console exports) — never fetched
from a real API here.

Decision rule (explore-then-commit, no randomness):
    - every variant needs >= min_impressions before judging
    - once all variants qualify, the highest CVR wins
    - winner is recorded to PublishingMemory as kind="aso_variant"
      so SpecGenerator / AsoGenerator can bias future output.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from operation.publishing_factory.memory import (
    PublishingMemory, PublishingMemoryEntry,
)

from .models import AsoVariant

DEFAULT_PATH = "data/aso_trials.jsonl"

_MIN_IMPRESSIONS = 500       # per-variant evidence floor
_MIN_EDGE = 0.01             # winner must beat runner-up by >= 1pt CVR


class AsoBandit:
    """Explore-then-commit bandit with JSONL persistence."""

    def __init__(self, path: str = DEFAULT_PATH,
                 memory: PublishingMemory = None,
                 min_impressions: int = _MIN_IMPRESSIONS):
        self.path = path
        self.memory = memory or PublishingMemory()
        self.min_impressions = min_impressions

    # ------------------------------------------------------------------ #
    # persistence
    # ------------------------------------------------------------------ #
    def _append(self, row: dict) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)),
                    exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _rows(self) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        out: List[dict] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    # ------------------------------------------------------------------ #
    # trial lifecycle
    # ------------------------------------------------------------------ #
    def register(self, variant: AsoVariant) -> None:
        """Add a variant to the trial (idempotent by variant_id)."""
        if self._find(variant.game_id, variant.kind, variant.variant_id):
            return
        self._append({"event": "register", **variant.to_dict()})

    def observe(self, game_id: str, kind: str, variant_id: str,
                impressions: int, installs: int) -> None:
        """Record an observation batch for a variant (additive)."""
        if impressions < 0 or installs < 0 or installs > impressions:
            raise ValueError("invalid observation: need "
                             "0 <= installs <= impressions")
        self._append({"event": "observe", "game_id": game_id,
                      "kind": kind, "variant_id": variant_id,
                      "impressions": impressions, "installs": installs})

    # ------------------------------------------------------------------ #
    # aggregation
    # ------------------------------------------------------------------ #
    def variants(self, game_id: str, kind: str) -> List[AsoVariant]:
        """Rebuild variant totals from the trial log."""
        agg: Dict[str, AsoVariant] = {}
        for r in self._rows():
            if r.get("game_id") != game_id or r.get("kind") != kind:
                continue
            vid = r["variant_id"]
            if r["event"] == "register" and vid not in agg:
                agg[vid] = AsoVariant(
                    variant_id=vid, game_id=game_id, kind=kind,
                    payload=r.get("payload", ""))
            elif r["event"] == "observe" and vid in agg:
                agg[vid].impressions += int(r.get("impressions", 0))
                agg[vid].installs += int(r.get("installs", 0))
        return sorted(agg.values(), key=lambda v: v.variant_id)

    def _find(self, game_id: str, kind: str,
              variant_id: str) -> Optional[AsoVariant]:
        for v in self.variants(game_id, kind):
            if v.variant_id == variant_id:
                return v
        return None

    # ------------------------------------------------------------------ #
    # decision
    # ------------------------------------------------------------------ #
    def pick_winner(self, game_id: str, kind: str,
                    genre: str = "") -> Optional[AsoVariant]:
        """Commit to a winner once evidence is sufficient, else None.

        On commit the winner is memorized to PublishingMemory so future
        generation is biased toward the winning pattern.
        """
        vs = self.variants(game_id, kind)
        if len(vs) < 2:
            return None                      # nothing to compare
        if any(v.impressions < self.min_impressions for v in vs):
            return None                      # still exploring
        ranked = sorted(vs, key=lambda v: (-v.cvr(), v.variant_id))
        top, second = ranked[0], ranked[1]
        if top.cvr() - second.cvr() < _MIN_EDGE:
            return None                      # too close to call
        self.memory.record(PublishingMemoryEntry(
            game_id=game_id, kind="aso_variant",
            key=f"{kind}:{top.payload}", outcome="good",
            value=top.cvr(),
            detail=(f"beat {second.payload} "
                    f"({top.cvr():.4f} vs {second.cvr():.4f})"),
            genre=genre))
        return top

    def status(self, game_id: str, kind: str) -> dict:
        vs = self.variants(game_id, kind)
        return {
            "variants": [v.to_dict() for v in vs],
            "exploring": any(v.impressions < self.min_impressions
                             for v in vs) or len(vs) < 2,
        }


__all__ = ["AsoBandit", "DEFAULT_PATH"]
