"""
E13.3.1 — Module 3: Segment Engine
====================================

Aggregates the raw event stream across the *full* dimension set that future
auto-optimization needs:

    game · country · platform · ad_format · network
    + traffic_source · user_cohort        (new vs E13.2.8)

It reuses the E13.2.8 pure metric functions (compute_ad_metrics /
compute_user_metrics / compute_retention) — it does NOT re-implement metric
math. It only adds the two finer grouping dimensions on top of the existing
aggregation.

Output: a RichAggregatedData container consumed by the FactBuilder.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from analytics.aggregation.event_aggregator import AdSegment, DailyUser, parse_date


# --------------------------------------------------------------------------- #
# Dimension-rich containers (extend E13.2.8 base segments with 2 new dims)
# --------------------------------------------------------------------------- #
@dataclass
class RichAdSegment(AdSegment):
    traffic_source: str = "unknown"
    user_cohort: str = "unknown"


@dataclass
class RichDailyUser(DailyUser):
    traffic_source: str = "unknown"
    user_cohort: str = "unknown"


@dataclass
class RichAggregatedData:
    ad_segments: List[RichAdSegment] = field(default_factory=list)
    daily_users: List[RichDailyUser] = field(default_factory=list)
    # user_id -> (install_date, country, traffic_source, user_cohort)
    cohorts: Dict[str, Tuple[str, str, str, str]] = field(default_factory=dict)
    # user_id -> set of active dates
    user_active: Dict[str, Set[str]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def _ad_dims(e: dict) -> Tuple[str, str, str, str, str, str, str, str]:
    return (
        parse_date(e.get("timestamp_ms")),
        e.get("game") or "unknown",
        e.get("country") or "unknown",
        e.get("platform") or "unknown",
        e.get("ad_format") or "unknown",
        e.get("network") or "unknown",
        e.get("traffic_source") or "unknown",
        e.get("user_cohort") or "unknown",
    )


def segment_aggregate(events: List[dict]) -> RichAggregatedData:
    ad_map: Dict[tuple, RichAdSegment] = {}
    daily_dau: Dict[tuple, Set[str]] = defaultdict(set)
    daily_installs: Dict[tuple, Set[str]] = defaultdict(set)
    daily_ad_rev: Dict[tuple, List[float]] = defaultdict(lambda: [0.0, 0.0])
    cohorts: Dict[str, Tuple[str, str, str, str]] = {}
    user_active: Dict[str, Set[str]] = defaultdict(set)

    for e in events:
        ev = e.get("event")
        if ev is None:
            continue
        uid = e.get("user_id")
        d = parse_date(e.get("timestamp_ms"))

        if ev == "install":
            if uid:
                ts_src = e.get("traffic_source") or "unknown"
                coh = e.get("user_cohort") or "unknown"
                cohorts[uid] = (d, e.get("country") or "unknown", ts_src, coh)
                daily_installs[(d, e.get("game"), e.get("country") or "unknown",
                                e.get("platform"), ts_src, coh)].add(uid)
        elif ev == "session_start":
            if uid:
                user_active[uid].add(d)
                daily_dau[(d, e.get("game"), e.get("country") or "unknown",
                           e.get("platform"),
                           e.get("traffic_source") or "unknown",
                           e.get("user_cohort") or "unknown")].add(uid)
        elif ev in ("ad_request", "ad_show", "ad_complete", "ad_revenue"):
            key = _ad_dims(e)
            seg = ad_map.get(key)
            if seg is None:
                seg = RichAdSegment(*key[:6], traffic_source=key[6], user_cohort=key[7])
                ad_map[key] = seg
            if ev == "ad_request":
                seg.requests += 1
            elif ev == "ad_show":
                seg.impressions += 1
            elif ev == "ad_complete":
                if e.get("completed"):
                    seg.completions += 1
            elif ev == "ad_revenue":
                seg.revenue += float(e.get("revenue") or 0.0)
                seg.revenue_impressions += 1
                drev = daily_ad_rev[(key[0], key[1], key[2], key[3], key[6], key[7])]
                drev[0] += float(e.get("revenue") or 0.0)
        elif ev == "purchase":
            drev = daily_ad_rev[(d, e.get("game"), e.get("country") or "unknown",
                                 e.get("platform"),
                                 e.get("traffic_source") or "unknown",
                                 e.get("user_cohort") or "unknown")]
            drev[1] += float(e.get("price") or 0.0)

    ad_segments = list(ad_map.values())
    daily_users: List[RichDailyUser] = []
    for (date, game, country, platform, ts_src, coh), dau_set in daily_dau.items():
        ad, iap = daily_ad_rev.get((date, game, country, platform, ts_src, coh), [0.0, 0.0])
        inst = daily_installs.get((date, game, country, platform, ts_src, coh), set())
        daily_users.append(RichDailyUser(
            date=date, game=game, country=country, platform=platform,
            installs=len(inst), dau=len(dau_set),
            ad_revenue=round(ad, 4), iap_revenue=round(iap, 4),
            traffic_source=ts_src, user_cohort=coh,
        ))

    return RichAggregatedData(
        ad_segments=ad_segments,
        daily_users=daily_users,
        cohorts=cohorts,
        user_active=dict(user_active),
    )
