"""
E13.2.8 — Module 2: Monetization Metrics Engine
================================================

Pure functions turning aggregated counts into business metrics.

Ad metrics
----------
* eCPM            = revenue / paid_impressions * 1000
* Fill Rate       = impressions / requests
* Show Rate       = impressions / requests   (rendered / requested)
* Reward Completion = completions / impressions

User-value metrics
------------------
* ARPDAU          = (ad_revenue + iap_revenue) / DAU
* Ad ARPDAU       = ad_revenue / DAU

Retention / LTV (Module 3 support)
----------------------------------
* D1 / D7 / D30 retention from install cohorts
* D0 LTV = day-0 revenue per install (averaged across install cohorts)

No backend. No I/O side effects.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from analytics.aggregation.event_aggregator import AdSegment, DailyUser


# --------------------------------------------------------------------------- #
# Ad metrics
# --------------------------------------------------------------------------- #
def compute_ad_metrics(seg: AdSegment) -> dict:
    paid = seg.revenue_impressions or seg.impressions or 0
    ecpm = (seg.revenue / paid * 1000.0) if paid else 0.0
    denom = seg.requests if seg.requests else 0
    fill = (seg.impressions / denom) if denom else 0.0
    show = (seg.impressions / denom) if denom else 0.0
    reward = (seg.completions / seg.impressions) if seg.impressions else 0.0
    return {
        "impressions": seg.impressions,
        "requests": seg.requests,
        "completions": seg.completions,
        "revenue": round(seg.revenue, 4),
        "ecpm": round(ecpm, 3),
        "fill_rate": round(fill, 4),
        "show_rate": round(show, 4),
        "reward_completion": round(reward, 4),
    }


# --------------------------------------------------------------------------- #
# User-value metrics
# --------------------------------------------------------------------------- #
def compute_user_metrics(du: DailyUser, ads_per_dau: Optional[float] = None) -> dict:
    dau = du.dau if du.dau else 1
    total = du.ad_revenue + du.iap_revenue
    m = {
        "dau": du.dau,
        "ad_revenue": round(du.ad_revenue, 4),
        "iap_revenue": round(du.iap_revenue, 4),
        "arpdau": round(total / dau, 4),
        "ad_arpdau": round(du.ad_revenue / dau, 4),
    }
    if ads_per_dau is not None:
        m["ads_per_dau"] = round(ads_per_dau, 4)
    return m


# --------------------------------------------------------------------------- #
# Retention / LTV
# --------------------------------------------------------------------------- #
def add_days(date_str: str, days: int) -> str:
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=days)).strftime("%Y-%m-%d")


def compute_retention(
    cohorts: Dict[str, Tuple[str, str]],
    user_active: Dict[str, Set[str]],
    group_key,
    days: Tuple[int, ...] = (1, 7, 30),
) -> dict:
    """
    Retention for one (game, platform, country) group.

    cohorts:     user_id -> (install_date, country)
    user_active: user_id -> set(active dates)
    group_key:   callable(user_id, (install_date, country)) -> group tuple or None
                 (return None to skip the user)
    """
    by_install: Dict[tuple, List[str]] = defaultdict(list)
    for uid, (idate, country) in cohorts.items():
        g = group_key(uid, (idate, country))
        if g is None:
            continue
        by_install[g].append(uid)

    out: Dict[tuple, dict] = {}
    for g, uids in by_install.items():
        rec = {}
        den = len(uids)
        for d in days:
            num = 0
            for uid in uids:
                idate = cohorts[uid][0]
                tgt = add_days(idate, d)
                if tgt in (user_active.get(uid) or set()):
                    num += 1
            rec[f"d{d}_retention"] = round(num / den, 4) if den else 0.0
        out[g] = rec
    return out


def compute_d0_ltv(
    daily_users: List[DailyUser],
    groups: List[tuple],
) -> Dict[tuple, float]:
    """
    D0 LTV = total revenue on a user's install day / installs on that day.
    Averaged across the install days present in `daily_users` for each group.
    """
    # (date, game, country, platform) -> (revenue, installs)
    by_day: Dict[tuple, List[float]] = defaultdict(lambda: [0.0, 0])
    for du in daily_users:
        key = (du.date, du.game, du.country, du.platform)
        by_day[key][0] += du.ad_revenue + du.iap_revenue
        by_day[key][1] += du.installs

    out: Dict[tuple, float] = {}
    for g in groups:
        vals = []
        for (date, game, country, platform), (rev, inst) in by_day.items():
            if (game, country, platform) == g and inst > 0:
                vals.append(rev / inst)
        out[g] = round(sum(vals) / len(vals), 4) if vals else 0.0
    return out
