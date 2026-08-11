"""
E13.2.8 — Module 1: Event Aggregator
=====================================

Turns raw GameFactoryEvents (E13.2.7 contract) into daily aggregated counts
that the Metrics Engine can turn into business facts.

Design notes
------------
* Ad events are keyed by (date, game, country, platform, ad_format, network).
  The real SDK knows country + network at init time (from MAX impression data
  / GameFactoryConfig), so production events carry them on every ad event.
  Synthetic data in `intelligence/synthetic_events.py` does the same.
* Impressions are counted from `ad_show`; revenue + paid impressions from
  `ad_revenue`. Requests from `ad_request`; reward completions from
  `ad_complete` where `completed == true`.
* DAU is distinct users with a `session_start` on that (date, country,
  platform). Installs feed the retention cohort.
* No backend, no I/O side effects. Pure aggregation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple


# --------------------------------------------------------------------------- #
# Aggregated data containers
# --------------------------------------------------------------------------- #
@dataclass
class AdSegment:
    date: str
    game: str
    country: str
    platform: str
    ad_format: str
    network: str
    requests: int = 0
    impressions: int = 0
    completions: int = 0
    revenue: float = 0.0
    revenue_impressions: int = 0  # count of paid impressions (ad_revenue events)


@dataclass
class DailyUser:
    date: str
    game: str
    country: str
    platform: str
    installs: int = 0
    dau: int = 0
    ad_revenue: float = 0.0
    iap_revenue: float = 0.0


@dataclass
class AggregatedData:
    ad_segments: List[AdSegment] = field(default_factory=list)
    daily_users: List[DailyUser] = field(default_factory=list)
    # user_id -> (install_date, country)
    cohorts: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # user_id -> set of active dates (from session_start)
    user_active: Dict[str, Set[str]] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse_date(ts_ms: Optional[int]) -> str:
    """Convert a millisecond epoch timestamp to a UTC date string 'YYYY-MM-DD'."""
    if ts_ms is None:
        return "unknown"
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def _ad_key(e: dict) -> Tuple[str, str, str, str, str, str]:
    return (
        parse_date(e.get("timestamp_ms")),
        e.get("game") or "unknown",
        e.get("country") or "unknown",
        e.get("platform") or "unknown",
        e.get("ad_format") or "unknown",
        e.get("network") or "unknown",
    )


# --------------------------------------------------------------------------- #
# Core aggregation
# --------------------------------------------------------------------------- #
def aggregate(events: List[dict]) -> AggregatedData:
    ad_map: Dict[tuple, AdSegment] = {}
    daily_dau: Dict[tuple, Set[str]] = defaultdict(set)
    daily_installs: Dict[tuple, Set[str]] = defaultdict(set)
    daily_ad_rev: Dict[tuple, List[float]] = defaultdict(lambda: [0.0, 0.0])  # [ad, iap]
    cohorts: Dict[str, Tuple[str, str]] = {}
    user_active: Dict[str, Set[str]] = defaultdict(set)

    for e in events:
        ev = e.get("event")
        if ev is None:
            continue
        uid = e.get("user_id")
        if ev == "install":
            if uid:
                cohorts[uid] = (parse_date(e.get("timestamp_ms")), e.get("country") or "unknown")
                daily_installs[(parse_date(e.get("timestamp_ms")),
                                e.get("game"), e.get("country") or "unknown",
                                e.get("platform"))].add(uid)
        elif ev == "session_start":
            if uid:
                d = parse_date(e.get("timestamp_ms"))
                user_active[uid].add(d)
                daily_dau[(d, e.get("game"), e.get("country") or "unknown",
                           e.get("platform"))].add(uid)
        elif ev in ("ad_request", "ad_show", "ad_complete", "ad_revenue"):
            key = _ad_key(e)
            seg = ad_map.get(key)
            if seg is None:
                seg = AdSegment(*key)
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
                drev = daily_ad_rev[(key[0], key[1], key[2], key[3])]
                drev[0] += float(e.get("revenue") or 0.0)
        elif ev == "purchase":
            drev = daily_ad_rev[(parse_date(e.get("timestamp_ms")), e.get("game"),
                                 e.get("country") or "unknown", e.get("platform"))]
            drev[1] += float(e.get("price") or 0.0)

    ad_segments = list(ad_map.values())
    daily_users: List[DailyUser] = []
    for (date, game, country, platform), dau_set in daily_dau.items():
        ad, iap = daily_ad_rev.get((date, game, country, platform), [0.0, 0.0])
        inst = daily_installs.get((date, game, country, platform), set())
        daily_users.append(DailyUser(
            date=date, game=game, country=country, platform=platform,
            installs=len(inst), dau=len(dau_set),
            ad_revenue=round(ad, 4), iap_revenue=round(iap, 4),
        ))

    return AggregatedData(
        ad_segments=ad_segments,
        daily_users=daily_users,
        cohorts=cohorts,
        user_active=dict(user_active),
    )


# --------------------------------------------------------------------------- #
# Impression map helper (used by the Facts builder to attach ads_per_dau)
# --------------------------------------------------------------------------- #
def impression_map(agg: AggregatedData) -> Dict[tuple, int]:
    """(date, country, platform) -> total impressions across formats/networks."""
    m: Dict[tuple, int] = defaultdict(int)
    for seg in agg.ad_segments:
        m[(seg.date, seg.country, seg.platform)] += seg.impressions
    return dict(m)
