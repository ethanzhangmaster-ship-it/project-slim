"""
E14.7.1 — Reality Normalizer

Takes raw data from Adjust / Meta / MAX readers and normalizes into one
RealitySnapshot. This is the canonical view that E12 Intelligence and
E13 Monetization Agent consume — they never see the raw source format.

Design: pure-data transformation. No API calls, no I/O beyond reading the
reader output. Each reader's data is normalised into a segment keyed by
(country, platform, ad_format) so the Opportunity Detector can map signals
directly to E13 segments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from monetization.reality.production.adjust_reader import (
    AdjustCohort, AdjustDailySnapshot, AdjustReader,
)
from monetization.reality.production.max_reader import MaxReader, MaxTrend
from monetization.reality.production.meta_reader import MetaCreative, MetaReader


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RealitySegment:
    """One (country, platform, maybe format) slice of reality."""
    country: str
    platform: str
    ad_format: str = ""

    # ---- acquisition ----
    installs: int = 0
    sessions: int = 0
    dau: int = 0
    spend: float = 0.0

    # ---- monetization ----
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    arpdau: float = 0.0
    ecpm: float = 0.0
    fill_rate: float = 0.0

    # ---- retention ----
    d1: float = 0.0
    d7: float = 0.0
    d30: float = 0.0
    payer_conversion: float = 0.0

    # ---- trends (relative, 0..1) ----
    ecpm_trend: float = 0.0
    installs_trend: float = 0.0
    revenue_trend: float = 0.0

    # ---- risk flags ----
    ecpm_declined: bool = False
    payer_low: bool = False
    installs_declining: bool = False

    def to_dict(self) -> dict:
        return {
            "country": self.country, "platform": self.platform,
            "ad_format": self.ad_format,
            "installs": self.installs, "sessions": self.sessions,
            "dau": self.dau, "spend": self.spend,
            "iap_revenue": self.iap_revenue, "ad_revenue": self.ad_revenue,
            "arpdau": round(self.arpdau, 4), "ecpm": round(self.ecpm, 2),
            "fill_rate": round(self.fill_rate, 4),
            "d1": round(self.d1, 4), "d7": round(self.d7, 4),
            "d30": round(self.d30, 4),
            "payer_conversion": round(self.payer_conversion, 4),
            "ecpm_trend": round(self.ecpm_trend, 4),
            "installs_trend": round(self.installs_trend, 4),
            "revenue_trend": round(self.revenue_trend, 4),
            "ecpm_declined": self.ecpm_declined,
            "payer_low": self.payer_low,
            "installs_declining": self.installs_declining,
        }


@dataclass
class RealitySnapshot:
    """Canonical view for E12/E13 — ONE snapshot per game per day."""
    game_id: str
    generated_at: str = field(default_factory=_now)
    segments: List[RealitySegment] = field(default_factory=list)
    creatives: List[MetaCreative] = field(default_factory=list)
    max_trends: List[MaxTrend] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "generated_at": self.generated_at,
            "segments": [s.to_dict() for s in self.segments],
            "creatives": [c.to_dict() for c in self.creatives],
            "max_trends": [t.to_dict() for t in self.max_trends],
            "metadata": self.metadata,
        }


class RealityNormalizer:
    """Normalizes raw reader data into a RealitySnapshot."""

    def __init__(self, adjust: AdjustReader, meta: MetaReader,
                 max_reader: MaxReader, game_profile: dict):
        self.adjust = adjust
        self.meta = meta
        self.max = max_reader
        self.profile = game_profile
        self.baselines = game_profile.get("baselines", {})

    # ------------------------------------------------------------------ #
    def build(self, game_id: str) -> RealitySnapshot:
        segments = self._build_segments()
        creatives = self.meta.creatives()
        max_trends = self.max.trends()
        return RealitySnapshot(
            game_id=game_id,
            segments=segments,
            creatives=creatives,
            max_trends=max_trends,
            metadata={
                "platforms": self.profile.get("platforms", []),
                "monetization": self.profile.get("monetization", []),
                "mode": self.profile.get("mode", "shadow"),
            },
        )

    def _build_segments(self) -> List[RealitySegment]:
        """Merge Adjust + MAX data into per-(platform, country) segments."""
        segs: dict = {}
        # seed from Adjust daily snapshots (latest per platform)
        for platform in self.profile.get("platforms", []):
            snap = self.adjust.latest_snapshot(platform)
            coh = self._cohort_for(platform)
            if snap is None:
                continue
            seg = RealitySegment(
                country="US", platform=platform, ad_format="reward",
                installs=snap.installs, sessions=snap.sessions,
                dau=snap.dau, iap_revenue=snap.iap_revenue,
                ad_revenue=snap.ad_revenue, arpdau=snap.arpdau,
                d1=coh.d1 if coh else 0.0,
                d7=coh.d7 if coh else 0.0,
                d30=coh.d30 if coh else 0.0,
                payer_conversion=coh.payer_d7 if coh else 0.0,
            )
            segs[f"{platform}_US"] = seg

        # overlay MAX eCPM + trends
        for t in self.max.trends():
            key = "ios_US" if t.country == "US" else t.country
            seg = segs.get(key)
            if seg is None:
                seg = RealitySegment(country=t.country, platform="ios",
                                     ad_format=t.format)
                segs[key] = seg
            seg.ecpm_trend = t.ecpm_7d_pct
            seg.revenue_trend = t.revenue_7d_pct
            seg.ecpm_declined = t.ecpm_7d_pct < -0.10
            snap = self.max.latest_for_unit(t.country, t.format)
            if snap:
                seg.ecpm = snap.ecpm
                seg.fill_rate = snap.fill_rate

        # overlay Adjust install trends
        for at in self.adjust.trends():
            key = f"{at.platform}_US"
            seg = segs.get(key)
            if seg:
                seg.installs_trend = at.installs_7d_pct
                seg.installs_declining = at.installs_7d_pct < -0.10
                seg.payer_conversion = at.payer_conversion

        # flag payer below baseline
        for seg in segs.values():
            bl = self.baselines.get("payer_conversion", {}).get(seg.platform, 0.03)
            if seg.payer_conversion > 0 and seg.payer_conversion < bl * 0.65:
                seg.payer_low = True

        return sorted(segs.values(), key=lambda s: (s.platform, s.country))

    def _cohort_for(self, platform: str) -> Optional[AdjustCohort]:
        for c in self.adjust.cohorts():
            if c.platform == platform:
                return c
        return None


__all__ = ["RealityNormalizer", "RealitySnapshot", "RealitySegment"]
