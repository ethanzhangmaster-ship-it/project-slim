"""
E13.3.1 — Module 2: Metric Store
=================================

Holds the computed MonetizationFacts. In-memory, with optional JSON-file
persistence. No database.

Facts are keyed by (game, date, country, platform, segment_type,
ad_format, network, traffic_source, user_cohort) so re-running `update()`
on a growing stream merges / replaces rather than duplicating.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from monetization.facts import MonetizationFact


def _fact_key(f: MonetizationFact) -> tuple:
    return (
        f.game, f.date, f.country, f.platform, f.segment_type,
        f.ad_format or "", f.network or "",
        getattr(f, "traffic_source", None) or "unknown",
        getattr(f, "user_cohort", None) or "unknown",
    )


class MetricStore:
    def __init__(self):
        self._facts: Dict[tuple, MonetizationFact] = {}

    # -- write ----------------------------------------------------------- #
    def put(self, facts: List[MonetizationFact]) -> int:
        n = 0
        for f in facts:
            self._facts[_fact_key(f)] = f
            n += 1
        return n

    def merge(self, other: "MetricStore") -> int:
        return self.put(list(other._facts.values()))

    # -- read ------------------------------------------------------------ #
    def all(self) -> List[MonetizationFact]:
        return list(self._facts.values())

    def by_segment_type(self, segment_type: str) -> List[MonetizationFact]:
        return [f for f in self._facts.values() if f.segment_type == segment_type]

    def size(self) -> int:
        return len(self._facts)

    # -- persistence ----------------------------------------------------- #
    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump([f.to_dict() for f in self._facts.values()], f, indent=2)

    def load(self, path: str | Path) -> int:
        p = Path(path)
        if not p.exists():
            return 0
        data = json.loads(p.read_text(encoding="utf-8"))
        facts = [MonetizationFact(**_normalize(d)) for d in data]
        return self.put(facts)

    def clear(self) -> None:
        self._facts.clear()


def _normalize(d: dict) -> dict:
    """MonetizationFact(**dict) needs only constructor fields; drop extras."""
    return {
        "game": d.get("game", ""),
        "date": d.get("date", ""),
        "country": d.get("country", "unknown"),
        "platform": d.get("platform", "unknown"),
        "segment_type": d.get("segment_type", "ad"),
        "ad_format": d.get("ad_format"),
        "network": d.get("network"),
        "metric": d.get("metric", {}),
    }
