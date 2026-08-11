"""
E13.2.8 — Module 4 (builder): Monetization Fact assembly
========================================================

Combines the Event Aggregator output + Metrics Engine into
`MonetizationFact` records — the canonical "Reality Facts" the future
E13.3 Agent consumes. Each fact is a flat, schema-validatable dict.

Three fact kinds:
  * ad   — one per (date, country, platform, ad_format, network) segment
  * user — one per (date, country, platform) with ARPDAU / ads_per_dau
  * retention — one per (game, country, platform) with D1/D7/D30 + D0 LTV
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from analytics.aggregation.event_aggregator import (
    AggregatedData,
    impression_map,
)
from monetization.metrics import (
    add_days,
    compute_ad_metrics,
    compute_d0_ltv,
    compute_retention,
    compute_user_metrics,
)


def _d1_retention_est(agg: AggregatedData, date: str, country: str) -> Optional[float]:
    """Per-date D1 retention estimate: users installed on date-1 and active on date."""
    prev = add_days(date, -1)
    num = den = 0
    for uid, (idate, c) in agg.cohorts.items():
        if c != country or idate != prev:
            continue
        den += 1
        if date in (agg.user_active.get(uid) or set()):
            num += 1
    return round(num / den, 4) if den else None


@dataclass
class MonetizationFact:
    game: str
    date: str
    country: str
    platform: str
    segment_type: str  # "ad" | "user" | "retention"
    ad_format: Optional[str] = None
    network: Optional[str] = None
    traffic_source: Optional[str] = "unknown"  # E13.3.1: UA channel
    user_cohort: Optional[str] = "unknown"     # E13.3.1: user segment
    metric: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "game": self.game,
            "date": self.date,
            "country": self.country,
            "platform": self.platform,
            "segment_type": self.segment_type,
            "ad_format": self.ad_format,
            "network": self.network,
            "traffic_source": self.traffic_source,
            "user_cohort": self.user_cohort,
            "metric": self.metric,
        }


def build_monetization_facts(agg: AggregatedData) -> List[MonetizationFact]:
    facts: List[MonetizationFact] = []

    # --- ad facts ---------------------------------------------------------
    for seg in agg.ad_segments:
        facts.append(MonetizationFact(
            game=seg.game, date=seg.date, country=seg.country,
            platform=seg.platform, segment_type="ad",
            ad_format=seg.ad_format, network=seg.network,
            metric=compute_ad_metrics(seg),
        ))

    # --- user facts (with ads_per_dau + per-date D1 retention estimate) --
    impr = impression_map(agg)
    for du in agg.daily_users:
        apd = None
        total_impr = impr.get((du.date, du.country, du.platform))
        if total_impr and du.dau:
            apd = total_impr / du.dau
        m = compute_user_metrics(du, ads_per_dau=apd)
        d1 = _d1_retention_est(agg, du.date, du.country)
        if d1 is not None:
            m["d1_retention_est"] = d1
        facts.append(MonetizationFact(
            game=du.game, date=du.date, country=du.country,
            platform=du.platform, segment_type="user",
            metric=m,
        ))

    # --- retention + D0 LTV facts ----------------------------------------
    groups = set()
    for du in agg.daily_users:
        groups.add((du.game, du.country, du.platform))
    groups = sorted(groups)

    def _gk(uid, ic):
        game = None
        # find the group this user's country/platform belongs to
        idate, country = ic
        for (g_game, g_country, g_platform) in groups:
            if country == g_country:
                return (g_game, g_country, g_platform)
        return None

    retention = compute_retention(agg.cohorts, agg.user_active, _gk, days=(1, 7, 30))
    d0 = compute_d0_ltv(agg.daily_users, groups)

    for g in groups:
        rec = dict(retention.get(g, {}))
        rec["d0_ltv"] = d0.get(g, 0.0)
        # date is the latest daily_users date for this group (snapshot)
        latest = max((du.date for du in agg.daily_users
                      if (du.game, du.country, du.platform) == g), default="")
        facts.append(MonetizationFact(
            game=g[0], date=latest, country=g[1], platform=g[2],
            segment_type="retention", metric=rec,
        ))

    return facts
