"""
E15.2.5 — Report-row aggregation shared by all intelligence analyzers.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from operation.optimizer.intel_models import SegmentStat, fnum


def aggregate(rows: List[dict], key_col: str) -> Dict[str, SegmentStat]:
    """Aggregate raw MAX report rows by one column (network/application/country/ad_format)."""
    acc: Dict[str, SegmentStat] = {}
    day_sets: Dict[str, set] = defaultdict(set)
    for r in rows:
        k = str(r.get(key_col) or "?")
        s = acc.get(k)
        if s is None:
            s = acc[k] = SegmentStat(key=k)
        s.revenue += fnum(r.get("estimated_revenue"))
        s.impressions += int(fnum(r.get("impressions")))
        s.attempts += int(fnum(r.get("attempts")))
        s.responses += int(fnum(r.get("responses")))
        day_sets[k].add(r.get("day"))
    for k, s in acc.items():
        s.days = len(day_sets[k])
    return acc


def totals(stats: Dict[str, SegmentStat]) -> SegmentStat:
    t = SegmentStat(key="TOTAL")
    for s in stats.values():
        t.revenue += s.revenue
        t.impressions += s.impressions
        t.attempts += s.attempts
        t.responses += s.responses
        t.days = max(t.days, s.days)
    return t
