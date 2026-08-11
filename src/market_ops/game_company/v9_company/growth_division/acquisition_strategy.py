from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ChannelMix:
    channel: str
    budget_pct: float
    target_cpi: float
    target_installs: int
    actual_cpi: float = 0.0
    actual_installs: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "budget_pct": self.budget_pct,
            "target_cpi": self.target_cpi,
            "target_installs": self.target_installs,
            "actual_cpi": self.actual_cpi,
            "actual_installs": self.actual_installs,
        }


@dataclass
class CohortAnalysis:
    cohort_date: datetime
    channel: str
    installs: int
    d1_retention: float
    d7_retention: float
    d30_retention: float
    d7_revenue: float
    d30_revenue: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_date": self.cohort_date.isoformat(),
            "channel": self.channel,
            "installs": self.installs,
            "d1_retention": self.d1_retention,
            "d7_retention": self.d7_retention,
            "d30_retention": self.d30_retention,
            "d7_revenue": self.d7_revenue,
            "d30_revenue": self.d30_revenue,
        }


@dataclass
class LTVPrediction:
    channel: str
    predicted_d30_ltv: float
    predicted_d90_ltv: float
    predicted_d365_ltv: float
    confidence_interval: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "predicted_d30_ltv": self.predicted_d30_ltv,
            "predicted_d90_ltv": self.predicted_d90_ltv,
            "predicted_d365_ltv": self.predicted_d365_ltv,
            "confidence_interval": self.confidence_interval,
        }


class AcquisitionStrategy:
    def __init__(self):
        self._channel_mix: Dict[str, ChannelMix] = {}
        self._cohorts: List[CohortAnalysis] = []

    def optimize_acquisition(self) -> List[ChannelMix]:
        optimized = [
            ChannelMix("meta_ads", 40.0, 3.50, 20000, 3.80, 18500),
            ChannelMix("google_ads", 25.0, 4.00, 12000, 3.90, 12500),
            ChannelMix("tiktok_ads", 20.0, 2.80, 15000, 2.60, 17200),
            ChannelMix("apple_search_ads", 10.0, 5.00, 4000, 4.80, 4200),
            ChannelMix("unity_ads", 5.0, 2.00, 8000, 2.10, 7500),
        ]
        for c in optimized:
            self._channel_mix[c.channel] = c
        return optimized

    def get_channel_mix(self) -> List[ChannelMix]:
        return list(self._channel_mix.values()) or self.optimize_acquisition()

    def adjust_channel_budget(self, channel: str, amount: float) -> ChannelMix:
        if channel in self._channel_mix:
            self._channel_mix[channel].budget_pct += amount
            return self._channel_mix[channel]
        new_mix = ChannelMix(channel, amount, 3.00, 5000)
        self._channel_mix[channel] = new_mix
        return new_mix

    def get_cohort_analysis(self) -> List[CohortAnalysis]:
        now = datetime.now()
        return [
            CohortAnalysis(now, "meta_ads", 5000, 0.45, 0.20, 0.08, 0.80, 2.50),
            CohortAnalysis(now, "google_ads", 4000, 0.42, 0.18, 0.07, 0.75, 2.30),
            CohortAnalysis(now, "tiktok_ads", 6000, 0.38, 0.15, 0.05, 0.60, 1.80),
        ]

    def predict_ltv(self) -> List[LTVPrediction]:
        return [
            LTVPrediction("meta_ads", 2.80, 4.50, 8.20, 0.12),
            LTVPrediction("google_ads", 2.60, 4.20, 7.80, 0.14),
            LTVPrediction("tiktok_ads", 2.10, 3.50, 6.50, 0.18),
            LTVPrediction("apple_search_ads", 3.50, 5.80, 10.50, 0.15),
            LTVPrediction("unity_ads", 1.80, 3.00, 5.50, 0.20),
        ]

    def get_stats(self) -> Dict[str, Any]:
        mix = self.get_channel_mix()
        cohorts = self.get_cohort_analysis()
        total_installs = sum(c.actual_installs for c in mix)
        return {
            "active_channels": len(mix),
            "total_installs_achieved": total_installs,
            "blended_actual_cpi": round(sum(c.actual_cpi * c.actual_installs for c in mix) / total_installs, 2) if total_installs else 0,
            "cohorts_analyzed": len(cohorts),
        }