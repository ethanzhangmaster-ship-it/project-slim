from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class GrowthChannel(Enum):
    PAID = "paid"
    ORGANIC = "organic"
    VIRAL = "viral"
    REFERRAL = "referral"
    ASO = "aso"


@dataclass
class GrowthPerformance:
    channel: GrowthChannel
    installs: int
    spend: float
    cpi: float
    roas_d7: float
    date: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel.value,
            "installs": self.installs,
            "spend": self.spend,
            "cpi": self.cpi,
            "roas_d7": self.roas_d7,
            "date": self.date.isoformat(),
        }


@dataclass
class ChannelHealth:
    channel: GrowthChannel
    health_score: float
    trend: str
    budget_utilization: float
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel.value,
            "health_score": self.health_score,
            "trend": self.trend,
            "budget_utilization": self.budget_utilization,
            "issues": self.issues,
        }


@dataclass
class GrowthTarget:
    target_id: str
    metric: str
    target_value: float
    deadline: datetime
    current_value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "metric": self.metric,
            "target_value": self.target_value,
            "deadline": self.deadline.isoformat(),
            "current_value": self.current_value,
        }


class GrowthDirector:
    def __init__(self):
        self._performance: Dict[str, List[GrowthPerformance]] = {}
        self._targets: Dict[str, GrowthTarget] = {}

    def review_growth_performance(self) -> List[GrowthPerformance]:
        return [
            GrowthPerformance(GrowthChannel.PAID, 45000, 180000.0, 4.0, 1.25),
            GrowthPerformance(GrowthChannel.ORGANIC, 32000, 0.0, 0.0, 2.50),
            GrowthPerformance(GrowthChannel.VIRAL, 12000, 5000.0, 0.42, 3.00),
            GrowthPerformance(GrowthChannel.REFERRAL, 8000, 2000.0, 0.25, 1.80),
            GrowthPerformance(GrowthChannel.ASO, 15000, 3000.0, 0.20, 2.00),
        ]

    def get_channel_health(self) -> List[ChannelHealth]:
        return [
            ChannelHealth(GrowthChannel.PAID, 82.0, "stable", 0.88, ["cpi_rising"]),
            ChannelHealth(GrowthChannel.ORGANIC, 91.0, "up", 0.45, []),
            ChannelHealth(GrowthChannel.VIRAL, 74.0, "down", 0.62, ["share_rate_decline"]),
            ChannelHealth(GrowthChannel.REFERRAL, 68.0, "stable", 0.55, ["low_invite_conversion"]),
            ChannelHealth(GrowthChannel.ASO, 85.0, "up", 0.70, []),
        ]

    def allocate_growth_budget(self) -> Dict[str, Any]:
        return {
            "total_budget": 250000.0,
            "allocations": {
                GrowthChannel.PAID.value: 150000.0,
                GrowthChannel.ORGANIC.value: 20000.0,
                GrowthChannel.VIRAL.value: 15000.0,
                GrowthChannel.REFERRAL.value: 10000.0,
                GrowthChannel.ASO.value: 25000.0,
            },
            "reserve": 30000.0,
            "period": "monthly",
        }

    def get_growth_strategy(self) -> Dict[str, Any]:
        return {
            "primary_channel": GrowthChannel.PAID.value,
            "secondary_channel": GrowthChannel.ASO.value,
            "focus": "scale_profitable_cohorts",
            "experiment_budget_pct": 15.0,
            "target_cpi": 3.50,
            "target_roas_d7": 1.30,
        }

    def set_growth_targets(self, targets: List[GrowthTarget]) -> List[GrowthTarget]:
        for t in targets:
            self._targets[t.target_id] = t
        return targets

    def get_stats(self) -> Dict[str, Any]:
        perf = self.review_growth_performance()
        total_installs = sum(p.installs for p in perf)
        total_spend = sum(p.spend for p in perf)
        return {
            "total_installs": total_installs,
            "total_spend": round(total_spend, 2),
            "blended_cpi": round(total_spend / total_installs, 2) if total_installs else 0,
            "active_targets": len(self._targets),
        }