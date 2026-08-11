"""
E13.2.8 — Module 5: Opportunity Detector  (the Agent's precursor)
===============================================================

Reads MonetizationFacts and surfaces *what is wrong / worth acting on*.
It is detection-only — it never mutates config, never calls an API.

Detects (against the trailing window, by default latest vs previous day):
  * ecpm_drop          — eCPM fell >= 20% (high if >= 30%)
  * revenue_drop       — ad revenue fell >= 20%
  * fill_drop          — fill rate fell >= 15%
  * ad_frequency_issue — ads_per_dau rose >= 30% while D1 retention fell >= 8%
                         (early half vs late half of the window)

Output: a list of Opportunity dicts (JSON-serialisable).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class Opportunity:
    id: str
    type: str
    severity: str
    segment: dict
    metric: str
    detail: dict
    recommendation: str
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


# Thresholds (tunable)
ECPM_DROP = 0.20
ECPM_DROP_HIGH = 0.30
REVENUE_DROP = 0.20
FILL_DROP = 0.15
FREQ_RISE = 1.30       # ads_per_dau late/early
RET_DROP = 0.92        # d1_retention_est late/early (<= this)


def _seg_key(f) -> tuple:
    return (f.country, f.platform, f.ad_format or "", f.network or "")


def detect_opportunities(facts: List, window: Optional[int] = None) -> List[Opportunity]:
    opps: List[Opportunity] = []

    # ---- ad-segment time series -----------------------------------------
    series: Dict[tuple, List] = defaultdict(list)
    for f in facts:
        if f.segment_type == "ad":
            series[_seg_key(f)].append(f)
    for key, flist in series.items():
        flist.sort(key=lambda x: x.date)
        if window:
            flist = flist[-window:]
        if len(flist) < 2:
            continue
        latest, prev = flist[-1], flist[-2]
        m_l, m_p = latest.metric, prev.metric
        seg = {
            "country": key[0], "platform": key[1],
            "ad_format": key[2], "network": key[3],
        }

        # eCPM drop
        if m_p.get("ecpm", 0) > 0:
            drop = (m_p["ecpm"] - m_l.get("ecpm", 0)) / m_p["ecpm"]
            if drop >= ECPM_DROP:
                opps.append(Opportunity(
                    id=str(uuid.uuid4())[:8],
                    type="ecpm_drop",
                    severity="high" if drop >= ECPM_DROP_HIGH else "medium",
                    segment=seg, metric="ecpm",
                    detail={"prev_ecpm": m_p["ecpm"], "cur_ecpm": m_l.get("ecpm", 0),
                            "drop_pct": round(drop * 100, 1)},
                    recommendation="Review waterfall priority and bidding for this segment; "
                                   "check if a top network lost fill or a bid floor moved.",
                ))

        # revenue drop
        if m_p.get("revenue", 0) > 0:
            rdrop = (m_p["revenue"] - m_l.get("revenue", 0)) / m_p["revenue"]
            if rdrop >= REVENUE_DROP:
                opps.append(Opportunity(
                    id=str(uuid.uuid4())[:8],
                    type="revenue_drop",
                    severity="high" if rdrop >= ECPM_DROP_HIGH else "medium",
                    segment=seg, metric="revenue",
                    detail={"prev_revenue": m_p["revenue"], "cur_revenue": m_l.get("revenue", 0),
                            "drop_pct": round(rdrop * 100, 1)},
                    recommendation="Investigate impression loss vs revenue loss; "
                                   "correlate with fill_rate and eCPM drops.",
                ))

        # fill drop
        if m_p.get("fill_rate", 0) > 0:
            fdrop = (m_p["fill_rate"] - m_l.get("fill_rate", 0)) / m_p["fill_rate"]
            if fdrop >= FILL_DROP:
                opps.append(Opportunity(
                    id=str(uuid.uuid4())[:8],
                    type="fill_drop",
                    severity="medium",
                    segment=seg, metric="fill_rate",
                    detail={"prev_fill": m_p["fill_rate"], "cur_fill": m_l.get("fill_rate", 0),
                            "drop_pct": round(fdrop * 100, 1)},
                    recommendation="Check mediation: a network may be timing out or a "
                                   "bid floor is too high; consider enabling backup networks.",
                ))

    # ---- ad frequency vs retention (user-segment series) ----------------
    _detect_frequency_issue(facts, opps)
    return opps


def _detect_frequency_issue(facts: List, opps: List[Opportunity]) -> None:
    user_series: Dict[tuple, List] = defaultdict(list)
    for f in facts:
        if f.segment_type == "user" and "ads_per_dau" in f.metric:
            user_series[(f.country, f.platform)].append(f)
    for key, flist in user_series.items():
        flist.sort(key=lambda x: x.date)
        n = len(flist)
        if n < 4:
            continue
        half = n // 2
        early, late = flist[:half], flist[half:]
        early_apd = [x.metric["ads_per_dau"] for x in early if x.metric.get("ads_per_dau")]
        late_apd = [x.metric["ads_per_dau"] for x in late if x.metric.get("ads_per_dau")]
        early_ret = [x.metric["d1_retention_est"] for x in early if x.metric.get("d1_retention_est") is not None]
        late_ret = [x.metric["d1_retention_est"] for x in late if x.metric.get("d1_retention_est") is not None]
        if not (early_apd and late_apd and early_ret and late_ret):
            continue
        apd_ratio = (sum(late_apd) / len(late_apd)) / (sum(early_apd) / len(early_apd))
        ret_ratio = (sum(late_ret) / len(late_ret)) / (sum(early_ret) / len(early_ret))
        if apd_ratio >= FREQ_RISE and ret_ratio <= RET_DROP:
            opps.append(Opportunity(
                id=str(uuid.uuid4())[:8],
                type="ad_frequency_issue",
                severity="high" if ret_ratio <= 0.85 else "medium",
                segment={"country": key[0], "platform": key[1]},
                metric="ads_per_dau_vs_d1_retention",
                detail={
                    "ads_per_dau_ratio": round(apd_ratio, 3),
                    "d1_retention_ratio": round(ret_ratio, 3),
                    "interpretation": "Ad load increased while D1 retention dropped.",
                },
                recommendation="Reduce ad frequency (e.g. raise remote_config "
                               "ads.reward_frequency interval) and re-measure retention.",
            ))
