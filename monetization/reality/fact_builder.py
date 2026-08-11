"""
E13.3.1 — Module 4: Fact Builder
=================================

Turns a RichAggregatedData (from SegmentEngine) into standard
MonetizationFacts. Emits two grain levels:

  * Daily Fact  — rolled up to (date, country, platform, ad_format, network);
                  traffic_source / user_cohort = "unknown". This is the
                  schema-stable grain the E13.2.8 Opportunity Detector eats.
  * Segment Fact — kept at the fine (traffic_source, user_cohort) grain.
                  Future auto-optimization slices on these.

Reuses E13.2.8 metric math (compute_ad_metrics / compute_user_metrics /
compute_retention / compute_d0_ltv). No new metric definitions here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from analytics.aggregation.event_aggregator import AdSegment, DailyUser
from monetization.facts import MonetizationFact
from monetization.metrics import (
    add_days,
    compute_ad_metrics,
    compute_d0_ltv,
    compute_retention,
    compute_user_metrics,
)
from monetization.reality.segment_engine import RichAggregatedData


# --------------------------------------------------------------------------- #
# Roll-ups (rich -> base grain)
# --------------------------------------------------------------------------- #
def _rollup_ad_segments(rich) -> List[AdSegment]:
    base: Dict[tuple, AdSegment] = {}
    for s in rich.ad_segments:
        k = (s.date, s.game, s.country, s.platform, s.ad_format, s.network)
        b = base.get(k)
        if b is None:
            b = AdSegment(*k)
            base[k] = b
        b.requests += s.requests
        b.impressions += s.impressions
        b.completions += s.completions
        b.revenue += s.revenue
        b.revenue_impressions += s.revenue_impressions
    return list(base.values())


def _rollup_daily_users(rich) -> List[DailyUser]:
    base: Dict[tuple, DailyUser] = {}
    for du in rich.daily_users:
        k = (du.date, du.game, du.country, du.platform)
        b = base.get(k)
        if b is None:
            b = DailyUser(*k)
            base[k] = b
        b.installs += du.installs
        b.dau += du.dau
        b.ad_revenue += du.ad_revenue
        b.iap_revenue += du.iap_revenue
    return list(base.values())


def _impression_map(segments: List[AdSegment]) -> Dict[tuple, int]:
    m: Dict[tuple, int] = defaultdict(int)
    for s in segments:
        m[(s.date, s.country, s.platform)] += s.impressions
    return dict(m)


def _ctx(rich) -> Tuple[str, str]:
    """Best-effort (game, platform) for single-game demo streams."""
    for du in rich.daily_users:
        return (du.game, du.platform)
    return ("unknown", "unknown")


def _d1_ret(rich, date: str, country: str):
    """Per-date D1 retention estimate (mirrors E13.2.8): users installed on
    date-1 in `country` and active on `date`."""
    prev = add_days(date, -1)
    num = den = 0
    for uid, ic in rich.cohorts.items():
        if ic[1] != country or ic[0] != prev:
            continue
        den += 1
        if date in (rich.user_active.get(uid) or set()):
            num += 1
    return round(num / den, 4) if den else None


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def build_daily_facts(rich: RichAggregatedData) -> List[MonetizationFact]:
    """Base-grain facts (traffic_source / user_cohort = 'unknown')."""
    facts: List[MonetizationFact] = []
    game, platform = _ctx(rich)

    base_ads = _rollup_ad_segments(rich)
    for seg in base_ads:
        facts.append(MonetizationFact(
            game=seg.game, date=seg.date, country=seg.country,
            platform=seg.platform, segment_type="ad",
            ad_format=seg.ad_format, network=seg.network,
            metric=compute_ad_metrics(seg),
        ))

    impr = _impression_map(base_ads)
    base_users = _rollup_daily_users(rich)
    for du in base_users:
        apd = None
        total = impr.get((du.date, du.country, du.platform))
        if total and du.dau:
            apd = total / du.dau
        m = compute_user_metrics(du, ads_per_dau=apd)
        d1 = _d1_ret(rich, du.date, du.country)
        if d1 is not None:
            m["d1_retention_est"] = d1
        facts.append(MonetizationFact(
            game=du.game, date=du.date, country=du.country,
            platform=du.platform, segment_type="user", metric=m,
        ))

    # retention (base grain)
    cohorts_base = {uid: (ic[0], ic[1]) for uid, ic in rich.cohorts.items()}
    groups = sorted({(du.game, du.country, du.platform) for du in base_users})

    def _gk_base(uid, ic):
        for g in groups:
            if ic[1] == g[1]:
                return g
        return None

    ret = compute_retention(cohorts_base, rich.user_active, _gk_base, days=(1, 7, 30))
    d0 = compute_d0_ltv(base_users, groups)
    for g in groups:
        rec = dict(ret.get(g, {}))
        rec["d0_ltv"] = d0.get(g, 0.0)
        latest = max((du.date for du in base_users
                      if (du.game, du.country, du.platform) == g), default="")
        facts.append(MonetizationFact(
            game=g[0], date=latest, country=g[1], platform=g[2],
            segment_type="retention", metric=rec,
        ))
    return facts


def build_segment_facts(rich: RichAggregatedData) -> List[MonetizationFact]:
    """Fine-grain facts sliced by traffic_source + user_cohort."""
    facts: List[MonetizationFact] = []
    game, platform = _ctx(rich)

    # ad segments (keep ts / cohort)
    for s in rich.ad_segments:
        facts.append(MonetizationFact(
            game=s.game, date=s.date, country=s.country, platform=s.platform,
            segment_type="ad", ad_format=s.ad_format, network=s.network,
            traffic_source=s.traffic_source, user_cohort=s.user_cohort,
            metric=compute_ad_metrics(s),
        ))

    # user segments (keep ts / cohort)
    impr = _impression_map(_rollup_ad_segments(rich))
    for du in rich.daily_users:
        apd = None
        total = impr.get((du.date, du.country, du.platform))
        if total and du.dau:
            apd = total / du.dau
        m = compute_user_metrics(du, ads_per_dau=apd)
        d1 = _d1_ret(rich, du.date, du.country)
        if d1 is not None:
            m["d1_retention_est"] = d1
        facts.append(MonetizationFact(
            game=du.game, date=du.date, country=du.country, platform=du.platform,
            segment_type="user", traffic_source=du.traffic_source,
            user_cohort=du.user_cohort, metric=m,
        ))

    # retention per (game, country, platform, ts, cohort)
    # compute_retention expects a 2-tuple (install_date, country); the
    # group_key re-fetches the full 4-tuple from rich.cohorts by uid.
    cohorts_seg = {uid: (ic[0], ic[1]) for uid, ic in rich.cohorts.items()}

    def _gk_seg(uid, ic):
        full = rich.cohorts[uid]
        return (game, full[1], platform, full[2], full[3])

    groups_seg = sorted({(game, ic[1], platform, ic[2], ic[3])
                         for ic in rich.cohorts.values()})
    ret = compute_retention(cohorts_seg, rich.user_active, _gk_seg, days=(1, 7, 30))
    d0 = compute_d0_ltv(rich.daily_users, groups_seg)
    for g in groups_seg:
        rec = dict(ret.get(g, {}))
        rec["d0_ltv"] = d0.get(g, 0.0)
        latest = max((du.date for du in rich.daily_users
                      if (du.game, du.country, du.platform,
                          du.traffic_source, du.user_cohort) == g), default="")
        facts.append(MonetizationFact(
            game=g[0], date=latest, country=g[1], platform=g[2],
            segment_type="retention", traffic_source=g[3], user_cohort=g[4],
            metric=rec,
        ))
    return facts


def build_reality_facts(rich: RichAggregatedData):
    """Return (daily_facts, segment_facts)."""
    return build_daily_facts(rich), build_segment_facts(rich)
